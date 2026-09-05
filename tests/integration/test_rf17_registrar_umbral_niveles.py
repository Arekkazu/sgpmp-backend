"""RF-17 (#144) — registrar un umbral ambiental con sus 3 niveles de alerta.

Causa raíz: el modo `insertmanyvalues` de SQLAlchemy 2.0 agrupa las 3
inserciones de `NivelAlertaAmbientalModel` (normal/precaucion/critico, siempre
obligatorias juntas) en una sola sentencia, casteando cada parámetro a
`::VARCHAR` explícito. La columna `nivel` es un ENUM nativo de Postgres
(`modulo9.enum_nivel_alerta`), así que Postgres rechaza el cast con
`DatatypeMismatch` -> 500. Con un solo nivel no se activa el modo batch, por
eso pasó desapercibido: en la práctica, **todo** umbral con niveles fallaba.
"""
from __future__ import annotations

import random
import string
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"


def _sufijo(largo: int = 6) -> str:
    return "".join(random.choices(string.ascii_uppercase, k=largo))


@pytest.fixture
def especie_activa(db_session: Session) -> int:
    existe = db_session.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'modulo9'")
    ).first()
    if existe is None:
        pytest.skip("La base de pruebas no tiene el schema modulo9.")
    fila = db_session.execute(
        text("SELECT id_especie FROM modulo9.especies WHERE es_activo ORDER BY id_especie LIMIT 1")
    ).first()
    if fila is None:
        pytest.skip("Se requiere al menos una especie activa en modulo9.especies.")
    return fila[0]


@pytest.fixture
def variable_ambiental_activa(db_session: Session) -> int:
    return db_session.execute(
        text(
            """
            INSERT INTO modulo9.variables_ambientales
                (nombre, unidad, valor_fisico_min, valor_fisico_max, es_activo)
            VALUES (:nombre, '°C', 0, 45, TRUE)
            RETURNING id_variable_ambiental
            """
        ),
        {"nombre": f"Temperatura RF17 {_sufijo()}"},
    ).scalar_one()


@pytest.fixture
def config_client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    from src.configuration.infrastructure.routers.umbral_router import router as umbral_router
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(umbral_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, client=("sgpmp-integration-tests", 50000), raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def test_registrar_umbral_con_3_niveles_ya_no_da_500(
    config_client, especie_activa: int, variable_ambiental_activa: int, crear_usuario_db, crear_auth_headers
) -> None:
    admin = crear_usuario_db(id_rol=1, estado=2)
    headers = crear_auth_headers(admin)

    resp = config_client.post(
        "/configuracion/umbrales",
        json={
            "id_especie": especie_activa,
            "id_variable_ambiental": variable_ambiental_activa,
            "valor_min": "15.0",
            "valor_max": "30.0",
            "niveles": [
                {"nivel": "normal", "limite_inferior": "15.0", "limite_superior": "25.0"},
                {"nivel": "precaucion", "limite_inferior": "25.0", "limite_superior": "28.0"},
                {"nivel": "critico", "limite_inferior": "28.0", "limite_superior": "30.0"},
            ],
        },
        headers=headers,
    )

    assert resp.status_code == 201, resp.text
    assert len(resp.json()["niveles"]) == 3
