"""TC-M09-G79 / TC-M09-150 — atomicidad de la calibracion ante fallo de persistencia.

Escenario de RF-24 (flujo alterno «Fallo en el registro de auditoria»):

    calibracion valida -> flush dentro de la transaccion -> falla la auditoria
    -> rollback -> HTTP 500 -> ningun ajuste aplicado -> ningun dato parcial

Se ejecuta el codigo REAL de `RegistrarCalibracionUseCase`. Solo se inyecta el
fallo en la persistencia de auditoria; el commit, el rollback, el manejo de la
excepcion y la respuesta los produce el producto, no la prueba.

Tipo de evidencia: **integracion transaccional controlada** con dobles de
repositorio que comparten una unica sesion transaccional emulada (staged /
committed), siguiendo el patron ya establecido en este proyecto por
`tests/configuration/test_rf32_snapshot_rollback_atomicidad.py`. **No** es una
prueba E2E contra el backend desplegado: TEST solo se consulta por GET para
tomar datos reales y para demostrar que G79 no escribio nada en el.

No se modifica `src/`, ni infraestructura, ni el esquema, ni PostgreSQL.
"""
from __future__ import annotations

import copy
import os
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

# `src.shared.database` exige DATABASE_URL al importarse. El engine de SQLAlchemy
# es perezoso: no abre ninguna conexion al crearse, y este harness nunca usa
# SessionLocal ni engine (la sesion la sustituye DbFake). Se fija aqui, en el
# archivo QA, una URL que no apunta a ninguna base real: no se toca `src/`, ni el
# entorno desplegado, ni ninguna configuracion funcional.
os.environ.setdefault('DATABASE_URL', 'postgresql+psycopg2://harness:harness@127.0.0.1:1/g79_harness_sin_conexion')

from src.configuration.application.use_cases.sensores.registrar_calibracion_use_case import (  # noqa: E402
    RegistrarCalibracionUseCase,
)
from src.configuration.domain.entities.calibracion import Calibracion  # noqa: E402
from src.configuration.domain.repositories.auditoria_calibracion_repository import (  # noqa: E402
    AuditoriaCalibracionRepository,
)
from src.configuration.domain.repositories.calibracion_repository import CalibracionRepository  # noqa: E402
from src.configuration.infrastructure.dto.registrar_calibracion_dto import RegistrarCalibracionDTO  # noqa: E402
from src.shared.errors import InfrastructureError  # noqa: E402

import helpers_g79 as h  # noqa: E402

ID_USUARIO_QA = 4  # Ingeniero de campo; el harness no falsea identidad arbitraria.


# --------------------------------------------------------------------------- #
# Sesion transaccional compartida (patron establecido en el proyecto)
# --------------------------------------------------------------------------- #
class TransactionalStore:
    """Emula la atomicidad de una unica sesion compartida por los repositorios.

    `staged` son las escrituras provisionales (equivalente a flush) y `committed`
    el estado confirmado. Solo `commit()` promueve staged; `rollback()` lo descarta.
    """

    def __init__(self, estado_inicial: dict) -> None:
        self.committed = copy.deepcopy(estado_inicial)
        self.staged = copy.deepcopy(estado_inicial)

    def commit(self) -> None:
        self.committed = copy.deepcopy(self.staged)

    def rollback(self) -> None:
        self.staged = copy.deepcopy(self.committed)


class DbFake:
    """Sustituye a la Session de SQLAlchemy y contabiliza commits y rollbacks."""

    def __init__(self, store: TransactionalStore) -> None:
        self.store = store
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1
        self.store.commit()

    def rollback(self) -> None:
        self.rollbacks += 1
        self.store.rollback()


class CalibracionRepoFake(CalibracionRepository):
    """Escribe en `staged`, como hace el repositorio real con add()+flush()."""

    def __init__(self, store: TransactionalStore) -> None:
        self.store = store
        self.guardados = 0

    def guardar(self, calibracion: Calibracion) -> Calibracion:
        self.guardados += 1
        nuevo_id = max([c['id_calibracion'] for c in self.store.staged['calibraciones']], default=0) + 1
        calibracion.id_calibracion = nuevo_id
        self.store.staged['calibraciones'].append({
            'id_calibracion': nuevo_id,
            'id_dispositivo_iot': calibracion.id_dispositivo_iot,
            'id_sensor': calibracion.id_sensor,
            'valor_referencia': str(calibracion.valor_referencia),
            'ganancia': str(calibracion.ganancia),
            'offset': str(calibracion.offset),
            'fecha_calibracion': calibracion.fecha_calibracion.isoformat(),
            'id_usuario': calibracion.id_usuario,
            'observaciones': calibracion.observaciones,
        })
        return calibracion

    def listar_por_sensor(self, id_sensor: int) -> list[Calibracion]:
        return []


class AuditoriaRepoFake(AuditoriaCalibracionRepository):
    """Punto de fault injection: puede fallar como fallaria la BD real."""

    def __init__(self, store: TransactionalStore, *, fallar: bool) -> None:
        self.store = store
        self.fallar = fallar
        self.llamadas = 0
        self.staged_al_fallar: list | None = None

    def registrar(self, *, id_calibracion, id_usuario, tipo_operacion, valores_nuevos,
                  valores_anteriores=None) -> None:
        self.llamadas += 1
        # Evidencia del §63: cuando se intenta auditar, la calibracion ya esta
        # escrita de forma provisional dentro de la transaccion.
        self.staged_al_fallar = copy.deepcopy(self.store.staged['calibraciones'])
        if self.fallar:
            raise OperationalError('INSERT INTO modulo9.auditoria_calibraciones ...', {},
                                   Exception('fault injection QA TC-M09-150: fallo de persistencia de auditoria'))
        self.store.staged['auditoria'].append({
            'id_calibracion': id_calibracion, 'id_usuario': id_usuario,
            'tipo_operacion': tipo_operacion, 'valores_nuevos': valores_nuevos,
        })


def _repos_de_lectura(plan):
    """Dobles de solo lectura con los datos REALES descubiertos en TEST."""
    dispositivo = SimpleNamespace(id_dispositivo_iot=plan['dispositivo']['id'], es_activo=True)
    sensor = SimpleNamespace(id_sensores=plan['sensor']['id'], id_dispositivo_iot=plan['dispositivo']['id'],
                             categoria=plan['sensor']['categoria'], es_activo=True)
    asociacion = SimpleNamespace(id_infraestructura=plan['area']['id_infraestructura'])
    rango = SimpleNamespace(categoria=plan['sensor']['categoria'],
                            valor_min=Decimal(plan['rangoTecnico']['min']),
                            valor_max=Decimal(plan['rangoTecnico']['max']))
    # `verificar` es la logica real de dominio: se usa la entidad, no una copia.
    from src.configuration.domain.entities.rango_calibracion import RangoCalibracion
    rango_real = RangoCalibracion(categoria=rango.categoria, valor_min=rango.valor_min, valor_max=rango.valor_max)
    return (
        SimpleNamespace(obtener_por_id=lambda _id: sensor),
        SimpleNamespace(obtener_por_id=lambda _id: dispositivo),
        SimpleNamespace(obtener_asociacion_activa=lambda _id: asociacion),
        SimpleNamespace(obtener_por_categoria=lambda _cat: rango_real),
    )


def _estado_inicial(plan) -> dict:
    """BEFORE del harness: refleja el historial real del sensor en TEST."""
    return {
        'calibraciones': [
            {'id_calibracion': c['id_calibracion'], 'id_sensor': plan['sensor']['id'],
             'valor_referencia': c['valor_referencia'], 'fecha_calibracion': c['fecha_calibracion'],
             'id_usuario': c['id_usuario'], 'historico': True}
            for c in plan['historialTest']['items']
        ],
        'auditoria': [],
    }


def _ejecutar(plan, *, fallar: bool):
    store = TransactionalStore(_estado_inicial(plan))
    db = DbFake(store)
    sensor_repo, dispositivo_repo, sensor_area_repo, rango_repo = _repos_de_lectura(plan)
    calibracion_repo = CalibracionRepoFake(store)
    auditoria_repo = AuditoriaRepoFake(store, fallar=fallar)
    caso_de_uso = RegistrarCalibracionUseCase(
        db=db, sensor_repo=sensor_repo, dispositivo_repo=dispositivo_repo,
        sensor_area_repo=sensor_area_repo, calibracion_repo=calibracion_repo,
        rango_repo=rango_repo, auditoria_repo=auditoria_repo,
    )
    dto = RegistrarCalibracionDTO(
        id_dispositivo_iot=plan['dispositivo']['id'],
        id_infraestructura=plan['area']['id_infraestructura'],
        valor_referencia=Decimal(plan['valor']),
        fecha_calibracion=datetime.now(timezone.utc),
        observaciones=f"QA TC-M09-150 G79 {h.RUN_ID}",
    )
    usuario = SimpleNamespace(id_usuario=ID_USUARIO_QA)
    error = None
    resultado = None
    try:
        resultado = caso_de_uso.execute(plan['sensor']['id'], dto, usuario)
    except Exception as exc:  # la reaccion la produce el producto, no la prueba
        error = exc
    return {'store': store, 'db': db, 'calibracion_repo': calibracion_repo,
            'auditoria_repo': auditoria_repo, 'error': error, 'resultado': resultado, 'dto': dto}


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope='module')
def token():
    return h.login()


@pytest.fixture(scope='module')
def plan(token):
    p = h.descubrir(token)
    h.guardar('TC-M09-150-descubrimiento.json', {'plan': p})
    return p


@pytest.fixture(scope='module')
def control(plan):
    """Ejecucion de control SIN fallo: demuestra que la calibracion era valida."""
    return _ejecutar(plan, fallar=False)


@pytest.fixture(scope='module')
def bajo_fallo(plan):
    """Ejecucion unica bajo fallo inyectado en la persistencia de auditoria."""
    return _ejecutar(plan, fallar=True)


# --------------------------------------------------------------------------- #
# TC-M09-150
# --------------------------------------------------------------------------- #
class TestTC150Precondiciones:

    def test_01_actor_autorizado_y_datos_reales(self, plan):
        assert 1 in plan['permisosRecurso12'], 'el actor debe poder crear calibraciones'
        assert plan['dispositivo']['es_activo'] is True
        assert plan['sensor']['es_activo'] is True
        assert plan['sensor']['id_dispositivo_iot'] == plan['dispositivo']['id']
        assert plan['area']['fecha_finalizacion'] is None, 'la asociacion de area debe estar vigente'

    def test_02_valor_dentro_del_rango_tecnico(self, plan):
        valor = Decimal(plan['valor'])
        assert Decimal(plan['rangoTecnico']['min']) <= valor <= Decimal(plan['rangoTecnico']['max'])
        assert 'rangos-calibracion' in plan['rangoTecnico']['fuente']

    def test_03_control_la_calibracion_es_valida_sin_el_fallo(self, control):
        """Sin fault injection la misma entrada se registra: la invalidez no viene del dato."""
        assert control['error'] is None, f"la calibracion de control fallo: {control['error']}"
        assert control['resultado'] is not None
        assert control['db'].commits == 1 and control['db'].rollbacks == 0
        assert len(control['store'].committed['auditoria']) == 1


class TestTC150FaultInjection:

    def test_04_el_fault_point_fue_alcanzado(self, bajo_fallo):
        assert bajo_fallo['auditoria_repo'].llamadas == 1, 'la auditoria debia intentarse exactamente una vez'
        assert bajo_fallo['error'] is not None, 'el fallo inyectado debia propagarse'

    def test_05_el_fallo_ocurrio_dentro_de_la_transaccion_tras_el_flush(self, bajo_fallo, plan):
        """§63: al fallar la auditoria la calibracion ya estaba escrita provisionalmente."""
        assert bajo_fallo['calibracion_repo'].guardados == 1
        staged = bajo_fallo['auditoria_repo'].staged_al_fallar
        assert staged is not None, 'no se capturo el estado provisional'
        nuevas = [c for c in staged if not c.get('historico')]
        assert len(nuevas) == 1, 'la calibracion debia estar en el area provisional al fallar la auditoria'
        assert nuevas[0]['valor_referencia'] == str(Decimal(plan['valor']))

    def test_06_el_producto_convierte_el_fallo_en_error_de_trazabilidad(self, bajo_fallo):
        error = bajo_fallo['error']
        assert isinstance(error, InfrastructureError), f'se esperaba InfrastructureError y llego {type(error).__name__}'
        assert error.code == 'AUDITORIA_CALIBRACION_FALLIDA'
        assert 'trazabilidad' in error.message.lower()
        assert 'no ha sido aplicado' in error.message.lower()

    def test_07_el_contrato_mapea_ese_error_a_http_500(self, bajo_fallo):
        assert bajo_fallo['error'].status_code == 500, 'RF-24 exige HTTP 500 para este flujo alterno'


class TestTC150Atomicidad:

    def test_08_no_hubo_commit_y_si_hubo_rollback(self, bajo_fallo):
        assert bajo_fallo['db'].commits == 0, 'no debe confirmarse nada tras el fallo'
        assert bajo_fallo['db'].rollbacks == 1, 'el producto debe ejecutar rollback exactamente una vez'

    def test_09_ninguna_calibracion_persistida(self, bajo_fallo, plan):
        confirmadas = bajo_fallo['store'].committed['calibraciones']
        nuevas = [c for c in confirmadas if not c.get('historico')]
        assert nuevas == [], f'quedo persistencia parcial de calibracion: {nuevas}'
        assert len(confirmadas) == plan['historialTest']['total']

    def test_10_ninguna_auditoria_huerfana(self, bajo_fallo):
        assert bajo_fallo['store'].committed['auditoria'] == [], 'no debe quedar auditoria del ajuste fallido'

    def test_11_estado_provisional_descartado(self, bajo_fallo):
        assert bajo_fallo['store'].staged == bajo_fallo['store'].committed, \
            'el area provisional debe quedar igual al estado confirmado tras el rollback'

    def test_12_historicos_previos_intactos(self, bajo_fallo, plan):
        confirmadas = {c['id_calibracion']: c for c in bajo_fallo['store'].committed['calibraciones']}
        for previo in plan['historialTest']['items']:
            actual = confirmadas.get(previo['id_calibracion'])
            assert actual is not None, f"la calibracion historica {previo['id_calibracion']} desaparecio"
            assert actual['valor_referencia'] == previo['valor_referencia'], 'valor historico alterado'
            assert actual['fecha_calibracion'] == previo['fecha_calibracion'], 'fecha historica alterada'


class TestTC150SinEfectosEnTest:

    def test_13_test_no_recibio_ninguna_escritura(self, token, plan, bajo_fallo):
        """G79 no escribe en TEST: el historial real debe seguir igual que al inicio."""
        despues = h.historial_test(token, plan['sensor']['id'])
        assert despues['total'] == plan['historialTest']['total']
        assert despues['ids'] == [c['id_calibracion'] for c in plan['historialTest']['items']]
        h.guardar('TC-M09-150-evidencia-' + os.environ.get('G79_INTENTO', 'intento1') + '.json', {
            'tipoDeEvidencia': 'integracion transaccional controlada (harness Pytest en proceso). '
                               'No es E2E contra el backend desplegado.',
            'actor': {'rol': 'Ingeniero de campo', 'id_usuario': ID_USUARIO_QA,
                      'permisosRecurso12': plan['permisosRecurso12']},
            'dispositivo': plan['dispositivo'], 'sensor': plan['sensor'], 'area': plan['area'],
            'rangoTecnico': plan['rangoTecnico'], 'valor': plan['valor'],
            'faultPoint': {'mecanismo': 'doble de AuditoriaCalibracionRepository que lanza la excepcion',
                           'puntoExacto': 'auditoria_repo.registrar(), despues del flush de la calibracion y antes del commit',
                           'excepcion': 'sqlalchemy.exc.OperationalError',
                           'modificoInfraestructura': False, 'modificoProducto': False,
                           'alcanzado': bajo_fallo['auditoria_repo'].llamadas == 1},
            'transaccion': {'commits': bajo_fallo['db'].commits, 'rollbacks': bajo_fallo['db'].rollbacks,
                            'calibracionesGuardadas': bajo_fallo['calibracion_repo'].guardados},
            'respuesta': {'excepcion': type(bajo_fallo['error']).__name__,
                          'codigo': getattr(bajo_fallo['error'], 'code', None),
                          'statusHttp': getattr(bajo_fallo['error'], 'status_code', None),
                          'mensaje': getattr(bajo_fallo['error'], 'message', None)},
            'before': {'calibracionesHarness': len(_estado_inicial(plan)['calibraciones']),
                       'auditoriaHarness': 0, 'historialTest': plan['historialTest']},
            'after': {'calibracionesHarness': len(bajo_fallo['store'].committed['calibraciones']),
                      'auditoriaHarness': len(bajo_fallo['store'].committed['auditoria']),
                      'historialTest': despues},
            'persistenciaParcial': {'calibracionSinAuditoria': False, 'auditoriaSinCalibracion': False,
                                    'registroHuerfano': False, 'historicoAlterado': False,
                                    'rollbackCompleto': True},
        })
