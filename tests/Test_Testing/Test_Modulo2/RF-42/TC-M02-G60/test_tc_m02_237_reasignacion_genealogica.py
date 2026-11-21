"""
TC-M02-G60 (parte Pytest) - Rechazo de reasignacion de madre/padre a una
cria ya existente (TC-M02-237).

RF relacionado: RF-42, CU08 Gestionar eventos reproductivos
Categoria: Pruebas de validacion

Criterio de aceptacion (segun la ficha, sub-caso 2):
    "Cada cria debe tener exactamente 1 madre y 1 padre (N:1); no se
    permite sobreescritura genealogica." Precondicion: "Cria con relacion
    genealogica (madre y/o padre) ya registrada previamente." Paso:
    "Intentar registrar/asociar una segunda madre o un segundo padre a
    una cria que ya tiene relacion genealogica registrada." Resultado
    esperado: "El sistema rechaza la operacion, preservando la relacion
    genealogica original de la cria (1 madre y 1 padre maximo)."

CORRECCION 2026-09-09 (revisado con el usuario): la version anterior de
este test asumia que "registrar una segunda inseminacion con un padre
distinto sobre la MISMA hembra" era equivalente al escenario de la ficha
("reasignar madre/padre a una CRIA ya existente"), y lo dejaba en rojo
como si fuera un bug. Tras revision, esa premisa es incorrecta:

1. **No existe ninguna entidad "cria" individual en el modelo de datos**
   (ya documentado en TC-M02-G58/TC-M02-229): `numero_crias` es un
   entero agregado en un unico evento (`eventos_reproductivos`), sin
   registros por-cria. El escenario LITERAL de la ficha -- reasignar el
   padre/madre de una cria especifica que ya tiene su propia relacion
   genealogica registrada -- no tiene forma de materializarse contra el
   sistema real: no hay ninguna entidad "cria" a la que apuntar.

2. La aproximacion mas cercana disponible -- una HEMBRA (el activo
   tratado, no una cria) que ya tiene una inseminacion previa recibe un
   SEGUNDO evento de inseminacion con un padre DISTINTO -- no es
   "sobreescritura genealogica de una cria". Es un nuevo ciclo
   reproductivo independiente sobre la misma hembra. La regla N:1 de la
   ficha aplica a la genealogia de la CRIA resultante de un evento (su
   registro de nacimiento tiene 1 madre y 1 padre), no al historial
   reproductivo de la hembra a lo largo de su vida. Una hembra puede
   (y biologicamente debe poder) tener multiples ciclos reproductivos
   con machos distintos en distintas fechas -- es exactamente la funcion
   que RF-42 debe cumplir, no una violacion de ninguna regla.

Por lo tanto: que el sistema ACEPTE una segunda inseminacion con un padre
distinto es el comportamiento CORRECTO, no un bug. Este test se corrige
para afirmar ese comportamiento (aceptacion) en vez de rechazo -- pasa en
verde.

**Conclusion final para TC-M02-237: NO APLICA / no es un hallazgo
reportable.** El escenario literal de la ficha no es materializable
contra el sistema real por el gap de diseno ya documentado en
TC-M02-G58 (ausencia de entidad "cria"), y la aproximacion mas cercana
observable demuestra comportamiento correcto del sistema, no un defecto.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_237_reasignacion_genealogica.py -v \
        --html=Resultados/reporte-TC-M02-237.html --self-contained-html
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.biological_assets.application.use_cases.gestion.registrar_evento_reproductivo_use_case import (
    RegistrarEventoReproductivoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    EventoActivo,
    EventoReproductivo,
)
from src.biological_assets.infrastructure.dto.registrar_evento_reproductivo_dto import (
    RegistrarEventoReproductivoDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual

ID_MADRE = 500
ID_PADRE_ORIGINAL = 501
ID_PADRE_NUEVO = 502


def _activo(id_activo_biologico: int) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=10,
        tipo='INDIVIDUAL',
        origen_financiero='compra',
        id_infraestructura=3,
        id_estado=1,
        id_usuario=1,
        id_activo_biologico=id_activo_biologico,
        fecha_creacion=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class TestTCM02237ReasignacionGenealogica:

    def test_no_existe_entidad_cria_por_lo_que_el_escenario_de_la_ficha_no_es_materializable(self):
        """
        Documenta por que TC-M02-237 no puede probarse literalmente: el
        modelo de datos no tiene ninguna entidad "cria" individual con
        su propia relacion genealogica -- ver EventoReproductivo, que
        solo expone `numero_crias` (int agregado), sin lista de crias.
        """
        campos = set(EventoReproductivo.__dataclass_fields__.keys())

        assert 'numero_cria' in campos or 'numero_crias' in campos
        assert 'crias' not in campos and 'lista_crias' not in campos, (
            'Si existiera una coleccion de crias individuales aqui, el '
            'escenario de TC-M02-237 (reasignar madre/padre a UNA cria '
            'ya existente) si seria materializable. No existe -- '
            'confirma el gap de diseno ya documentado en TC-M02-G58.'
        )

    def test_una_segunda_inseminacion_con_padre_distinto_es_un_nuevo_ciclo_valido_no_una_reasignacion(self):
        """
        RF-42: una hembra que ya tiene una inseminacion previa registrada
        puede recibir un SEGUNDO evento de inseminacion con un padre
        distinto -- esto es un nuevo ciclo reproductivo independiente,
        no una sobreescritura de la genealogia de ninguna cria. El
        sistema lo acepta correctamente.
        """
        madre = _activo(ID_MADRE)
        padre_original = _activo(ID_PADRE_ORIGINAL)
        padre_nuevo = _activo(ID_PADRE_NUEVO)

        def _obtener_por_id(id_activo):
            if id_activo == ID_MADRE:
                return madre
            if id_activo == ID_PADRE_ORIGINAL:
                return padre_original
            if id_activo == ID_PADRE_NUEVO:
                return padre_nuevo
            return None

        activo_repo = MagicMock()
        activo_repo.obtener_por_id.side_effect = _obtener_por_id

        evento_repo = MagicMock()
        evento_repo.obtener_ultima_fecha.return_value = None
        # La madre YA tiene una inseminacion previa registrada con
        # padre_original -- precondicion de la ficha ("relacion
        # genealogica ya registrada previamente"), reinterpretada a
        # nivel de evento/hembra en vez de cria (ver docstring del
        # modulo).
        evento_repo.tiene_servicio_o_inseminacion_previa.return_value = True
        evento_guardado = EventoActivo(
            id_activo_biologico=ID_MADRE,
            fecha=datetime(2026, 9, 9, tzinfo=timezone.utc),
            id_usuario=1,
            id_eventos=701,
            reproductivo=EventoReproductivo(
                categoria='inseminacion', resultado='exitoso', id_padre=ID_PADRE_NUEVO,
            ),
        )
        evento_repo.guardar.return_value = evento_guardado

        db = MagicMock()
        use_case = RegistrarEventoReproductivoUseCase(
            db=db, activo_repo=activo_repo, evento_repo=evento_repo, bitacora_repo=MagicMock(),
        )
        usuario_actual = UsuarioActual(id_usuario=1, id_token=1, id_rol=2, id_estado_cuenta=2)
        dto_segundo_ciclo = RegistrarEventoReproductivoDTO(
            categoria='inseminacion', resultado='exitoso', id_padre=ID_PADRE_NUEVO,
        )

        resultado = use_case.execute(ID_MADRE, dto_segundo_ciclo, usuario_actual)

        assert resultado is evento_guardado, (
            'Un segundo evento de inseminacion con un padre distinto sobre '
            'la misma hembra debe aceptarse -- es un nuevo ciclo '
            'reproductivo valido, no una violacion de la regla N:1 de '
            'genealogia (esa regla aplica a la cria resultante de un '
            'evento, no al historial reproductivo de la hembra).'
        )
        assert resultado.reproductivo.id_padre == ID_PADRE_NUEVO
