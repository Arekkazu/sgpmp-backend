"""
TC-M02-G99 (RF-52, CU13) - Reintento 1 (2026-09-26) - RF-52 E1: el buffer de
auditoria recuperable llego con el merge de origin/test.

El archivo original (test_tc_m02_g99_bitacora_inmutabilidad_resiliencia.py) queda
intacto como evidencia historica. Sub-caso 168 (inmutabilidad por API/BD) NO
cambio -- no se repite aqui. Este reintento se enfoca solo en 169/170, cuyo
codigo subyacente SI cambio con el merge: `registrar_evento_bitacora()`
(src/biological_assets/application/use_cases/_registrar_evento_bitacora.py) ya
no hace `except Exception: pass` -- ahora implementa RF-52 E1 (buffer en disco +
recuperacion cronologica con un evento INDISPONIBILIDAD_AUDITORIA) y E3 (control
de carga). El archivo original documentaba en rojo la AUSENCIA de este mecanismo;
con el merge, ese mecanismo existe y este reintento lo verifica en verde.

RECTIFICACIONES sobre el original:

(TC-M02-169) El test original esperaba `len(repo.persistidos) == 3` (los 3
eventos generados, ni uno mas ni uno menos) y fallaba porque el codigo viejo
descartaba los 2 generados con el repositorio caido. Con el buffer nuevo, se
recuperan los 2 perdidos EN ORDEN CRONOLOGICO al restaurarse el repositorio,
pero ademas se genera un 4to evento (`INDISPONIBILIDAD_AUDITORIA`, RF52) que
documenta la caida -- el conteo correcto ya no es 3, es 4. Este reintento
corrige la aserción para reflejar el diseño real (no es un defecto que haya un
evento adicional: es la evidencia de recuperación exigida por la ficha).

HALLAZGO NUEVO (matiz, no perdida de datos): la recuperacion del backlog SI
preserva el orden cronologico DENTRO del backlog (los eventos atrapados durante
la caida salen en el mismo orden en que ocurrieron), pero el evento en vivo que
DISPARA la recuperacion (la escritura exitosa que encuentra el buffer) se
persiste ANTES de que se procese ese backlog -- ver el orden real
`_persistir(evento_nuevo)` seguido de `_recuperar_buffer(...)` en
`registrar_evento_bitacora()`. Cada evento conserva su propio `timestamp_evento`
real, asi que una consulta ordenada por ese campo (no por orden de
insercion/id_bitacora) siempre ve el orden correcto; solo el ORDEN DE INSERCION
en la tabla no es estrictamente cronologico frente a trafico concurrente nuevo.
No se reporta como bug (la ficha pide no perder ni desordenar lo atrapado por la
caida, que si se cumple) pero se documenta por si el equipo de desarrollo quiere
que la insercion tambien respete el orden global.

(TC-M02-170, test 2) El test original afirmaba `db.rollback.assert_not_called()`
-- ya no es cierto: `_persistir()` ahora llama `db.rollback()` cuando el intento
de ESCRITURA DE AUDITORIA falla (para no dejar esa sub-transaccion a medias),
antes de guardar el evento en el buffer. Se leyo el use case
(registrar_evento_crecimiento_use_case.py) para confirmar el ORDEN real:
`self.db.commit()` (los datos de negocio, el evento de crecimiento) ocurre
ANTES de `registrar_evento_bitacora(...)` -- el rollback posterior actua sobre
una transaccion ya cerrada por ese commit, no la deshace. Este reintento
reemplaza la aserción "rollback nunca se llama" por la aserción correcta: la
secuencia de llamadas al db es commit() y LUEGO rollback() (nunca al reves), lo
que confirma que el rollback es exclusivo del intento de auditoria y no revierte
la operacion de negocio ya confirmada.

(TC-M02-170, test 3 - latencia) SIN CAMBIOS: sigue en rojo, mismo hallazgo que
el original. El nuevo buffer solo actua ante una EXCEPCION del repositorio o
ante alta carga sostenida (tasa > umbral, RF-52 E3) -- una unica llamada lenta
sin excepcion sigue siendo sincrona dentro del request. No se repite aqui el
mismo test; ver el archivo original.

NOTA DE HERRAMIENTAS: correr esto en Windows requirio corregir el stub local de
`fcntl` (le faltaba `LOCK_NB`/`LOCK_SH`, usados por el nuevo candado
inter-proceso del buffer) -- ver `_win_fcntl_stub_borrar/fcntl.py`. Es una
correccion de la herramienta de esta sesion, no del backend.

Como correrlo (desde la raiz del repo):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m02_g99_bitacora_inmutabilidad_resiliencia_reintento1.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M02-G99_reintento1.html --self-contained-html
"""
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from src.biological_assets.application.use_cases import _registrar_evento_bitacora as buffer_mod
from src.biological_assets.application.use_cases.gestion.registrar_evento_crecimiento_use_case import (
    RegistrarEventoCrecimientoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, GestionFase
from src.biological_assets.infrastructure.dto.registrar_evento_crecimiento_dto import (
    RegistrarEventoCrecimientoDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual

ID_ACTIVO_CON_FASE = 374
USUARIO = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)


def _activo() -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=4, tipo='INDIVIDUAL', origen_financiero='compra', id_infraestructura=6, id_estado=1,
        id_usuario=1, id_activo_biologico=ID_ACTIVO_CON_FASE, fecha_inicio_ciclo=date(2026, 8, 1),
        fecha_creacion=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )


def _fase() -> GestionFase:
    return GestionFase(
        id_gestion_fases=1, id_activo_biologico=ID_ACTIVO_CON_FASE, id_ciclo_productiva=4,
        nombre_ciclo='Ciclo completo cachama 2025-A', nombre_fase_actual='Fase juvenil cachama', paso_actual=1,
        total_pasos=2, fecha_inicio=datetime(2026, 8, 1, tzinfo=timezone.utc), fecha_finalizacion=None,
        es_activa=True, id_usuario=1,
    )


def _crecimiento_use_case(bitacora_repo) -> tuple[RegistrarEventoCrecimientoUseCase, MagicMock]:
    activo_repo = MagicMock()
    activo_repo.obtener_por_id.return_value = _activo()
    activo_repo.obtener_fase_activa.return_value = _fase()
    evento_repo = MagicMock()
    evento_repo.obtener_ultima_fecha.return_value = None
    parametros = MagicMock()
    parametros.obtener_por_tipo_medicion.return_value = MagicMock(valor_min=None, valor_max=None)
    ciclo_port = MagicMock()
    ciclo_port.obtener_ciclo_con_fases.return_value = None
    db = MagicMock()
    uc = RegistrarEventoCrecimientoUseCase(
        db=db, activo_repo=activo_repo, evento_repo=evento_repo, infra_port=MagicMock(),
        parametros_port=parametros, ciclo_port=ciclo_port, bitacora_repo=bitacora_repo,
    )
    return uc, db


def _dto() -> RegistrarEventoCrecimientoDTO:
    return RegistrarEventoCrecimientoDTO(
        tipo_medicion='PESO', valor_medicion=Decimal('1.5'), unidad_medida='kg',
        fecha=datetime(2026, 9, 14, 10, tzinfo=timezone.utc),
    )


class _RepositorioDeAuditoriaIntermitente:
    """Repositorio falso: lanza mientras esta caido y guarda lo que recibe cuando esta disponible."""

    def __init__(self):
        self.caido = True
        self.persistidos = []

    def registrar(self, evento):
        if self.caido:
            raise ConnectionError('simulated: repositorio de auditoria no disponible')
        self.persistidos.append(evento)


class TestSubcaso169Reintento2BufferRecuperableRF52E1:

    def test_eventos_generados_con_el_repositorio_caido_se_recuperan_en_orden_mas_evento_de_indisponibilidad(self, tmp_path, monkeypatch):
        # Aisla el buffer en disco de esta corrida (RF-52 E1 usa un archivo compartido
        # en logs/, relativo al cwd -- no debe mezclarse con otras corridas ni con un
        # buffer real que pudiera existir del backend en ejecucion).
        monkeypatch.setattr(buffer_mod, '_DIR', tmp_path)

        repo = _RepositorioDeAuditoriaIntermitente()
        uc, _ = _crecimiento_use_case(repo)

        uc.execute(ID_ACTIVO_CON_FASE, _dto(), USUARIO)   # evento 1, repositorio caido -> va al buffer
        time.sleep(0.01)
        uc.execute(ID_ACTIVO_CON_FASE, _dto(), USUARIO)   # evento 2, repositorio caido -> va al buffer
        repo.caido = False                                  # el repositorio se restaura
        time.sleep(0.01)
        uc.execute(ID_ACTIVO_CON_FASE, _dto(), USUARIO)   # evento 3, repositorio disponible -> dispara la recuperacion

        assert len(repo.persistidos) == 4, (
            f'Se esperaban 4 registros en el repositorio real (2 recuperados del buffer + el evento 3 + el '
            f'INDISPONIBILIDAD_AUDITORIA de cierre), se obtuvieron {len(repo.persistidos)}. RF-52 E1 debe '
            'recuperar TODO lo pendiente en la primera escritura exitosa, sin perder ninguno.'
        )

        tipos = [e.tipo_evento for e in repo.persistidos]
        assert tipos.count('EVENTO_CRECIMIENTO_REGISTRADO') == 3, (
            'los 3 eventos de negocio (2 recuperados + 1 directo) deben llegar todos, sin perdida'
        )
        assert tipos.count('INDISPONIBILIDAD_AUDITORIA') == 1, (
            'RF-52 E1 exige un registro que documente el periodo de caida al recuperarse'
        )

        # HALLAZGO (matiz, no perdida de datos): el evento que DISPARA la recuperacion
        # (evento 3, directo) se persiste ANTES del backlog que libera -- ver linea
        # `if _persistir(...) and not en_alta_carga: _recuperar_buffer(...)` en
        # _registrar_evento_bitacora.py. Por eso el orden de INSERCION real observado
        # es [evento3, evento1, evento2, INDISPONIBILIDAD_AUDITORIA], no estrictamente
        # cronologico globalmente -- aunque cada evento SI conserva su propio
        # timestamp_evento real, asi que una consulta que ordene por ese campo (no por
        # orden de insercion/id_bitacora) veria el orden correcto. La ficha exige
        # "orden cronologico al recuperar" -- se interpreta y confirma sobre el
        # backlog recuperado ENTRE SI (los 2 que quedaron atrapados), que es lo que
        # esta en riesgo de desordenarse/perderse; no se exige la mismo relative al
        # trafico nuevo que llega mientras se recupera.
        eventos_crecimiento = [e for e in repo.persistidos if e.tipo_evento == 'EVENTO_CRECIMIENTO_REGISTRADO']
        marcas_ordenadas_por_recuperacion = sorted(e.timestamp_evento for e in eventos_crecimiento)
        assert marcas_ordenadas_por_recuperacion[0] < marcas_ordenadas_por_recuperacion[1] < marcas_ordenadas_por_recuperacion[2], (
            'los 3 eventos de negocio deben tener timestamps distintos y ordenables (sanity check de la fixture)'
        )
        # El backlog recuperado (evento1, evento2) SI debe salir en orden cronologico
        # entre si, sin importar donde caiga evento3 en la secuencia de insercion.
        indice_por_timestamp = {e.timestamp_evento: i for i, e in enumerate(repo.persistidos)}
        backlog_ordenado_por_fecha = sorted(
            [e for e in eventos_crecimiento if e.timestamp_evento != max(ev.timestamp_evento for ev in eventos_crecimiento)],
            key=lambda e: e.timestamp_evento,
        )
        posiciones_backlog = [indice_por_timestamp[e.timestamp_evento] for e in backlog_ordenado_por_fecha]
        assert posiciones_backlog == sorted(posiciones_backlog), (
            'el backlog recuperado (los eventos atrapados mientras el repositorio estaba caido) debe insertarse '
            'en el mismo orden cronologico en que ocurrieron, entre si'
        )

        evento_indisponibilidad = next(e for e in repo.persistidos if e.tipo_evento == 'INDISPONIBILIDAD_AUDITORIA')
        assert evento_indisponibilidad.rf_origen == 'RF52'
        assert evento_indisponibilidad.detalle_tecnico['eventos_recuperados'] == 2, (
            'debe reportar exactamente los 2 eventos que quedaron atrapados mientras el repositorio estaba caido'
        )


class TestSubcaso170Reintento2NoBloqueaYNoRevierteLoYaConfirmado:

    def test_la_operacion_de_negocio_se_confirma_antes_del_rollback_de_auditoria(self, tmp_path, monkeypatch):
        """RECTIFICACION: ya no se afirma 'rollback nunca se llama' (el buffer SI llama
        rollback para su propio intento fallido) sino lo que realmente importa para la
        ficha -- que el commit de los datos de negocio ya ocurrio ANTES de ese rollback,
        por lo que la operacion queda confirmada y el rollback no la afecta."""
        monkeypatch.setattr(buffer_mod, '_DIR', tmp_path)
        repo = _RepositorioDeAuditoriaIntermitente()   # caido todo el tiempo
        uc, db = _crecimiento_use_case(repo)

        evento, _fase_avanzada = uc.execute(ID_ACTIVO_CON_FASE, _dto(), USUARIO)

        assert evento is not None
        db.commit.assert_called_once()
        db.rollback.assert_called_once()  # el intento (fallido) de escribir la auditoria, no la operacion de negocio

        nombres_en_orden = [c[0] for c in db.method_calls if c[0] in ('commit', 'rollback')]
        assert nombres_en_orden == ['commit', 'rollback'], (
            f'se esperaba commit() de los datos de negocio ANTES del rollback() del intento de auditoria fallido; '
            f'orden observado: {nombres_en_orden}. Si el rollback ocurriera antes o en vez del commit, '
            'si arriesgaria la operacion de negocio.'
        )
