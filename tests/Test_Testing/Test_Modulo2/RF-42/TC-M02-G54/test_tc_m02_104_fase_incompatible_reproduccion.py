"""
TC-M02-G54 (parte Pytest) - Rechazar evento reproductivo por fase
productiva incompatible con reproduccion (TC-M02-104).

RF relacionado: RF-42, CU08 Gestionar eventos reproductivos
Categoria: Pruebas de validacion

Criterio de aceptacion (segun la ficha, sub-caso 2):
    "La fase productiva debe ser compatible con reproduccion (409 si
    no)." Precondicion: "Activo en fase 'Engorde/Finalizacion' no apta
    para reproduccion." Paso: "Intentar registrar un evento
    reproductivo." Resultado esperado: "HTTP 409 CONFLICT - 'La fase
    productiva del activo no permite registrar este tipo de evento'."

Por que Pytest y no Newman: no hay forma de llevar un activo a la fase
'Engorde/Finalizacion' via API -- TC-M02-G61 confirmo que POST
/activos-biologicos/{id}/fases (RF-37) responde 500 siempre, asi que
ningun activo puede tener NINGUNA fase asignada hoy en TEST, incompatible
o no.

Pero incluso si RF-37 funcionara, este test demuestra con dobles de
prueba que el resultado seria el mismo: `RegistrarEventoReproductivoUseCase`
(registrar_evento_reproductivo_use_case.py) NI SIQUIERA RECIBE un
`ciclo_port`/repositorio de fases en su constructor -- a diferencia de
`RegistrarEventoProductivoUseCase`, que si lo recibe y si valida E-02/E-04
(ver TC-M02-G61/G62). No existe ningun mecanismo, ni en Python ni en
trigger de BD, para que RF-42 rechace un evento reproductivo por la fase
del activo -- confirma y reafirma con un caso dedicado el hallazgo ya
documentado en TC-M02-G58 (la clase nunca llama
`activo_repo.obtener_fase_activa()`).

Se deja el test afirmando el comportamiento CORRECTO esperado por el RF
(rechazo 409 en fase incompatible) en vez de ajustarse al comportamiento
actual: un Pytest en rojo aqui es la evidencia documentada, mismo criterio
aplicado en TC-M02-G53/G55/G56/G58/G60.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_104_fase_incompatible_reproduccion.py -v \
        --html=Resultados/reporte-TC-M02-104.html --self-contained-html
"""
import inspect
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.biological_assets.application.use_cases.gestion.registrar_evento_reproductivo_use_case import (
    RegistrarEventoReproductivoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, EventoActivo, EventoReproductivo
from src.biological_assets.infrastructure.dto.registrar_evento_reproductivo_dto import (
    RegistrarEventoReproductivoDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual

ID_HEMBRA = 170
ID_PADRE = 171


def _activo(id_activo_biologico: int) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=10,
        tipo='INDIVIDUAL',
        origen_financiero='compra',
        id_infraestructura=3,
        id_estado=1,  # ACTIVO
        id_usuario=1,
        id_activo_biologico=id_activo_biologico,
        fecha_creacion=datetime(2026, 1, 15, tzinfo=timezone.utc),
    )


class TestTCM02104FaseIncompatibleConReproduccion:

    def test_use_case_no_tiene_forma_de_conocer_la_fase_del_activo(self):
        """
        Confirma estructuralmente que RegistrarEventoReproductivoUseCase
        no declara ningun parametro relacionado con fase/ciclo productivo
        en su constructor -- no puede consultar en que fase esta el
        activo aunque quisiera.
        """
        parametros = list(inspect.signature(RegistrarEventoReproductivoUseCase.__init__).parameters)
        relacionados_con_fase = [p for p in parametros if 'ciclo' in p.lower() or 'fase' in p.lower()]

        assert relacionados_con_fase == [], (
            'RF-42 exige que la fase productiva del activo sea compatible '
            'con reproduccion (rechazo 409 en fase Engorde/Finalizacion), '
            'pero RegistrarEventoReproductivoUseCase no recibe ningun '
            'ciclo_port/repositorio de fases -- no tiene forma de '
            'consultar la fase del activo. Parametros reales del '
            f'constructor: {parametros}.'
        )

    def test_registra_evento_reproductivo_sin_verificar_fase_del_activo(self):
        """
        RF-42: un evento reproductivo (servicio) sobre un activo cuya
        fase (simulada) seria 'Engorde/Finalizacion' -- no apta para
        reproduccion -- deberia rechazarse con 409. El use case lo
        acepta sin ninguna verificacion de fase.
        """
        hembra = _activo(ID_HEMBRA)
        padre = _activo(ID_PADRE)

        activo_repo = MagicMock()
        activo_repo.obtener_por_id.side_effect = lambda id_activo: (
            hembra if id_activo == ID_HEMBRA else padre if id_activo == ID_PADRE else None
        )
        # Nota: activo_repo no expone ningun metodo de fase que el use
        # case pueda llamar -- MagicMock() aceptaria cualquier llamada,
        # pero la asercion anterior ya confirmo que el constructor ni
        # siquiera recibe el puerto necesario para hacerla.

        evento_repo = MagicMock()
        evento_repo.obtener_ultima_fecha.return_value = None
        evento_repo.tiene_servicio_o_inseminacion_previa.return_value = False
        evento_repo.guardar.return_value = EventoActivo(
            id_activo_biologico=ID_HEMBRA,
            fecha=datetime(2026, 9, 9, tzinfo=timezone.utc),
            id_usuario=1,
            id_eventos=904,
            reproductivo=EventoReproductivo(categoria='servicio', resultado='exitoso', id_padre=ID_PADRE),
        )

        db = MagicMock()
        use_case = RegistrarEventoReproductivoUseCase(
            db=db, activo_repo=activo_repo, evento_repo=evento_repo, bitacora_repo=MagicMock(),
        )
        usuario_actual = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)
        dto = RegistrarEventoReproductivoDTO(categoria='servicio', resultado='exitoso', id_padre=ID_PADRE)

        excepcion_lanzada = None
        try:
            use_case.execute(ID_HEMBRA, dto, usuario_actual)
        except Exception as exc:
            excepcion_lanzada = exc

        assert excepcion_lanzada is not None, (
            'RF-42 exige que un evento reproductivo sobre un activo en '
            'fase incompatible con reproduccion (ej. Engorde/Finalizacion) '
            'sea rechazado con 409. El use case no lanzo ninguna '
            'excepcion -- de hecho, no tiene ningun mecanismo (ni Python '
            'ni trigger de BD) para verificar la fase del activo en '
            'absoluto antes de aceptar el evento.'
        )
