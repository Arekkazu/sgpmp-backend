"""RF-48: la fecha futura se rechaza como regla funcional con HTTP 422.

E-10 es la última validación del proceso (RF-48 paso 6f) — el control de
concurrencia (E-01) es "paso previo a cualquier otra validación" según el
propio RF, así que estos tests pasan primero por E-01..E-09 con fixtures
válidos (mismo patrón que test_registrar_transferencia_e08_finca.py) antes
de llegar a la fecha futura.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.biological_assets.application.use_cases.gestion.registrar_transferencia_use_case import (
    RegistrarTransferenciaUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, HistorialInfraestructura
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsulta
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.registrar_transferencia_dto import (
    RegistrarTransferenciaDTO,
)
from src.biological_assets.infrastructure.routers import activo_biologico_router as router_module
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import BusinessRuleError, ConflictError


class ColaboradorNoInvocado:
    def __getattr__(self, nombre: str):
        raise AssertionError(f'No debía invocarse {nombre} tras el rechazo.')


class DbFake:
    """`ejecutar_con_auditoria_de_rechazo` llama `db.rollback()` legítimamente
    para separar cualquier escritura pendiente del registro de auditoría del
    rechazo (ver docstring de `_auditoria_rechazos.py`) -- necesita un `db`
    real con no-ops, no un `ColaboradorNoInvocado` que explota con cualquier
    llamada.
    """

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


class ActivoRepoNoDebeConsultarse:
    """`execute()` toma una referencia a `obtener_por_id` (para el auditor de
    rechazos) incluso cuando `bitacora_repo` es `None` y esa referencia nunca
    llega a invocarse -- así que, a diferencia de `ColaboradorNoInvocado`, esta
    clase debe permitir el *acceso* al atributo sin lanzar; solo debe fallar si
    el método se llega a *invocar* de verdad.
    """

    def obtener_por_id(self, _id: int):
        raise AssertionError('No debía invocarse obtener_por_id tras el rechazo.')


class ActivoRepoFake:
    def __init__(self, activo, asociacion) -> None:
        self.activo = activo
        self.asociacion = asociacion

    def obtener_por_id(self, _id: int):
        return self.activo

    def obtener_asociacion_activa(self, _id: int):
        return self.asociacion


class TransferenciaRepoFake:
    def hay_transferencia_en_progreso(self, _id: int) -> bool:
        return False


class InfraPortFake:
    def __init__(self, infras: dict[int, InfraestructuraConsulta]) -> None:
        self.infras = infras

    def obtener_activa(self, id_infraestructura: int):
        return self.infras.get(id_infraestructura)

    def calcular_ocupacion(self, _id: int) -> int:
        return 0

    def es_tipo_compatible(self, tipo_infraestructura: str, id_especie: int) -> bool:
        return True


def _infra(id_infraestructura: int, id_finca: int) -> InfraestructuraConsulta:
    return InfraestructuraConsulta(
        id_infraestructura=id_infraestructura, nombre=f'Infra {id_infraestructura}',
        tipo='Corral', es_activo=True, id_finca=id_finca,
    )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=35, id_token=1, id_rol=2, id_estado_cuenta=2)


def _dto(fecha_transferencia: date) -> RegistrarTransferenciaDTO:
    return RegistrarTransferenciaDTO(
        infraestructura_origen_id=48,
        infraestructura_destino_id=51,
        fecha_transferencia=fecha_transferencia,
        motivo_transferencia='Validación TC-M02-140',
    )


def _caso_uso_hasta_e10() -> RegistrarTransferenciaUseCase:
    """Fixtures que pasan E-01..E-09 para que solo quede validar la fecha (E-10)."""
    activo = ActivoBiologico(
        id_especie=40, tipo='INDIVIDUAL', origen_financiero='PROPIO',
        id_infraestructura=48, id_estado=EstadoActivo.ACTIVO, id_usuario=35,
        id_activo_biologico=292, identificador='A-292',
    )
    asociacion = HistorialInfraestructura(
        id_historial=1, id_activo_biologico=292, id_infraestructura=48,
        nombre_infraestructura='Infra 48', tipo_infraestructura='Corral',
        fecha_inicio=None, fecha_fin=None,
    )
    return RegistrarTransferenciaUseCase(
        db=ColaboradorNoInvocado(),
        activo_repo=ActivoRepoFake(activo, asociacion),
        transferencia_repo=TransferenciaRepoFake(),
        infra_port=InfraPortFake({
            48: _infra(48, id_finca=10),
            51: _infra(51, id_finca=10),
        }),
    )


def test_fecha_futura_es_regla_funcional_y_no_inicia_persistencia() -> None:
    caso_uso = _caso_uso_hasta_e10()

    with pytest.raises(BusinessRuleError) as capturada:
        caso_uso.execute(292, _dto(date.today() + timedelta(days=5)), _usuario())

    error = capturada.value
    assert error.status_code == 422
    assert error.code == 'FECHA_TRANSFERENCIA_FUTURA'
    assert error.field == 'fecha_transferencia'
    assert error.message == 'La fecha de transferencia no puede ser posterior a la fecha actual.'


@pytest.fixture
def cliente_transferencia(monkeypatch: pytest.MonkeyPatch):
    activo = ActivoBiologico(
        id_especie=40, tipo='INDIVIDUAL', origen_financiero='PROPIO',
        id_infraestructura=48, id_estado=EstadoActivo.ACTIVO, id_usuario=35,
        id_activo_biologico=292, identificador='A-292',
    )
    asociacion = HistorialInfraestructura(
        id_historial=1, id_activo_biologico=292, id_infraestructura=48,
        nombre_infraestructura='Infra 48', tipo_infraestructura='Corral',
        fecha_inicio=None, fecha_fin=None,
    )
    activo_repo = ActivoRepoFake(activo, asociacion)
    transferencia_repo = TransferenciaRepoFake()
    infra_port = InfraPortFake({
        48: _infra(48, id_finca=10),
        51: _infra(51, id_finca=10),
    })
    monkeypatch.setattr(router_module, 'SqlAlchemyActivoBiologicoRepository', lambda _db: activo_repo)
    monkeypatch.setattr(router_module, 'SqlAlchemyTransferenciaRepository', lambda _db: transferencia_repo)
    monkeypatch.setattr(router_module, 'InfraestructuraM09Adapter', lambda _db: infra_port)
    monkeypatch.setattr(
        router_module, 'SqlAlchemyBitacoraAuditoriaRepository', lambda _db: ColaboradorNoInvocado()
    )

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router_module.router)
    app.dependency_overrides[get_db] = lambda: DbFake()
    app.dependency_overrides[get_current_user] = _usuario

    ruta = next(
        ruta
        for ruta in app.routes
        if ruta.path == '/activos-biologicos/{id_activo}/transferencias'
        and 'POST' in ruta.methods
    )
    for dependencia in ruta.dependant.dependencies:
        if dependencia.call not in {get_db, get_current_user}:
            app.dependency_overrides[dependencia.call] = lambda: None

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    app.dependency_overrides.clear()


def test_endpoint_fecha_futura_responde_422_con_campo_y_mensaje(
    cliente_transferencia: TestClient,
) -> None:
    respuesta = cliente_transferencia.post(
        '/activos-biologicos/292/transferencias',
        json={
            'infraestructura_origen_id': 48,
            'infraestructura_destino_id': 51,
            'fecha_transferencia': (date.today() + timedelta(days=5)).isoformat(),
            'motivo_transferencia': 'Validación TC-M02-140',
        },
    )

    assert respuesta.status_code == 422, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo['error_code'] == 'FECHA_TRANSFERENCIA_FUTURA'
    assert cuerpo['message'] == 'La fecha de transferencia no puede ser posterior a la fecha actual.'
    assert cuerpo['fields'] == [
        {
            'field': 'fecha_transferencia',
            'message': 'La fecha de transferencia no puede ser posterior a la fecha actual.',
        }
    ]


def test_fecha_actual_conserva_el_flujo_existente() -> None:
    class TransferenciaRepo:
        def hay_transferencia_en_progreso(self, id_activo: int) -> bool:
            assert id_activo == 292
            return True

    caso_uso = RegistrarTransferenciaUseCase(
        db=ColaboradorNoInvocado(),
        activo_repo=ActivoRepoNoDebeConsultarse(),
        transferencia_repo=TransferenciaRepo(),
        infra_port=ColaboradorNoInvocado(),
    )

    with pytest.raises(ConflictError) as capturada:
        caso_uso.execute(292, _dto(date.today()), _usuario())

    assert capturada.value.code == 'TRANSFERENCIA_CONCURRENTE'
