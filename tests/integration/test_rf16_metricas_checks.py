"""RF-16 — Validación de métricas por endpoint (tipo_medicion + coherencia unidad↔tipo).

Guardado igual que `test_rf16_patologias_por_especie.py`: se salta si falta `modulo9`
o no hay especie activa. La coherencia pura se cubre en
`tests/configuration/test_rf16_metricas_coherencia.py`.
"""
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"


@pytest.fixture
def una_especie(db_session: Session) -> int:
    existe = db_session.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'modulo9'")
    ).first()
    if existe is None:
        pytest.skip("La base de pruebas no tiene el schema modulo9.")
    fila = db_session.execute(
        text("SELECT id_especie FROM modulo9.especies WHERE es_activo ORDER BY id_especie LIMIT 1")
    ).first()
    if fila is None:
        pytest.skip("Se requiere al menos 1 especie activa en modulo9.especies.")
    return fila[0]


@pytest.fixture
def config_client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    from src.configuration.infrastructure.routers.metrica_router import router as metrica_router
    from src.identity_access.infrastructure.routers.usuarios_routers import router as usuarios_router  # noqa: F401
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(metrica_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, client=("sgpmp-integration-tests", 50000), raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _headers_vet(crear_usuario_db, crear_auth_headers) -> dict:
    vet = crear_usuario_db(id_rol=3, estado=2)  # Veterinario: C sobre recurso 19
    return crear_auth_headers(vet)


def test_tipo_medicion_fuera_de_dominio_422(config_client, una_especie, crear_usuario_db, crear_auth_headers) -> None:
    h = _headers_vet(crear_usuario_db, crear_auth_headers)
    r = config_client.post(
        "/configuracion/metricas",
        json={"id_especie": una_especie, "nombre": "Metrica Rf Test", "unidad_medida": "kg", "tipo_medicion": "BASURA"},
        headers=h,
    )
    assert r.status_code == 422


def test_peso_con_unidad_volumen_incoherente_422(config_client, una_especie, crear_usuario_db, crear_auth_headers) -> None:
    h = _headers_vet(crear_usuario_db, crear_auth_headers)
    r = config_client.post(
        "/configuracion/metricas",
        json={"id_especie": una_especie, "nombre": "Peso Rf Test", "unidad_medida": "litros", "tipo_medicion": "PESO"},
        headers=h,
    )
    assert r.status_code == 422
    assert r.json()["error_code"] == "UNIDAD_MEDIDA_INCOHERENTE"


def test_volumen_litro_abreviado_ok_201(config_client, una_especie, crear_usuario_db, crear_auth_headers) -> None:
    # Regresión del fix: 'l' ahora es válido para VOLUMEN.
    h = _headers_vet(crear_usuario_db, crear_auth_headers)
    r = config_client.post(
        "/configuracion/metricas",
        json={"id_especie": una_especie, "nombre": "Volumen L Rf Test", "unidad_medida": "l", "tipo_medicion": "VOLUMEN"},
        headers=h,
    )
    assert r.status_code == 201, r.text
