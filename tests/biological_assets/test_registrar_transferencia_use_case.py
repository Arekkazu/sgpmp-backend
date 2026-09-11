"""RF-48: la fecha futura se rechaza como regla funcional con HTTP 422."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.biological_assets.application.use_cases.gestion.registrar_transferencia_use_case import (
    RegistrarTransferenciaUseCase,
)
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
        raise AssertionError(f'La fecha futura no debe invocar {nombre}.')


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=35, id_token=1, id_rol=2, id_estado_cuenta=2)


def _dto(fecha_transferencia: date) -> RegistrarTransferenciaDTO:
    return RegistrarTransferenciaDTO(
        infraestructura_origen_id=48,
        infraestructura_destino_id=51,
        fecha_transferencia=fecha_transferencia,
        motivo_transferencia='Validación TC-M02-140',
    )


def test_fecha_futura_es_regla_funcional_y_no_inicia_persistencia() -> None:
    colaborador = ColaboradorNoInvocado()
    caso_uso = RegistrarTransferenciaUseCase(
        db=colaborador,
        activo_repo=colaborador,
        transferencia_repo=colaborador,
        infra_port=colaborador,
        bitacora_repo=colaborador,
    )

    with pytest.raises(BusinessRuleError) as capturada:
        caso_uso.execute(292, _dto(date.today() + timedelta(days=5)), _usuario())

    error = capturada.value
    assert error.status_code == 422
    assert error.code == 'FECHA_TRANSFERENCIA_FUTURA'
    assert error.field == 'fecha_transferencia'
    assert error.message == 'La fecha de transferencia no puede ser posterior a la fecha actual.'


@pytest.fixture
def cliente_transferencia(monkeypatch: pytest.MonkeyPatch):
    colaborador = ColaboradorNoInvocado()
    monkeypatch.setattr(router_module, 'SqlAlchemyActivoBiologicoRepository', lambda _db: colaborador)
    monkeypatch.setattr(router_module, 'SqlAlchemyTransferenciaRepository', lambda _db: colaborador)
    monkeypatch.setattr(router_module, 'InfraestructuraM09Adapter', lambda _db: colaborador)
    monkeypatch.setattr(router_module, 'SqlAlchemyBitacoraAuditoriaRepository', lambda _db: colaborador)

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router_module.router)
    app.dependency_overrides[get_db] = lambda: colaborador
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
        activo_repo=ColaboradorNoInvocado(),
        transferencia_repo=TransferenciaRepo(),
        infra_port=ColaboradorNoInvocado(),
    )

    with pytest.raises(ConflictError) as capturada:
        caso_uso.execute(292, _dto(date.today()), _usuario())

    assert capturada.value.code == 'TRANSFERENCIA_CONCURRENTE'
