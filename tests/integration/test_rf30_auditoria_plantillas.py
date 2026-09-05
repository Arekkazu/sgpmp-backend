"""RF-30 / INC-M09-03-G109 (#118) — endpoint para consultar la auditoría de
creación/versionado de plantillas de configuración (CU-07 Flujo D).

Guardado: se salta si la base de pruebas no tiene el schema `modulo9`.
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

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"  # igual que conftest

_SNAPSHOT_VALIDO = {
    "ciclos_biologicos": [
        {"nombre": "Engorde", "duracion_dias": 45, "descripcion": None},
    ],
}


def _sufijo_letras(largo: int = 6) -> str:
    return "".join(random.choices(string.ascii_uppercase, k=largo))


@pytest.fixture
def requiere_modulo9(db_session: Session) -> None:
    existe = db_session.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'modulo9'")
    ).first()
    if existe is None:
        pytest.skip("La base de pruebas no tiene el schema modulo9.")


@pytest.fixture
def especie_activa(db_session: Session, requiere_modulo9: None) -> int:
    fila = db_session.execute(
        text("SELECT id_especie FROM modulo9.especies WHERE es_activo ORDER BY id_especie LIMIT 1")
    ).first()
    if fila is None:
        pytest.skip("Se requiere al menos una especie activa en modulo9.especies.")
    return fila[0]


@pytest.fixture
def variable_ambiental_activa(db_session: Session, requiere_modulo9: None) -> dict:
    """Inserta una variable con rango físico [15.0, 30.0], propia de esta prueba."""
    id_variable = db_session.execute(
        text(
            """
            INSERT INTO modulo9.variables_ambientales
                (nombre, unidad, valor_fisico_min, valor_fisico_max, es_activo)
            VALUES (:nombre, '°C', 15.0, 30.0, TRUE)
            RETURNING id_variable_ambiental
            """
        ),
        {"nombre": f"Temperatura RF31 {_sufijo_letras()}"},
    ).scalar_one()
    db_session.flush()
    return {"id_variable_ambiental": id_variable, "min": 15.0, "max": 30.0}


@pytest.fixture
def config_client(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, requiere_modulo9: None
) -> Generator[TestClient, None, None]:
    from src.configuration.infrastructure.routers.plantilla_router import router as plantilla_router
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(plantilla_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, client=("sgpmp-integration-tests", 50000), raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def test_auditoria_lista_creacion_y_versionado(
    config_client, crear_usuario_db, crear_auth_headers, especie_activa: int
) -> None:
    """Antes del fix no existía este endpoint (404): crear y versionar una
    plantilla quedaban auditados en BD sin ninguna forma de consultarlos."""
    admin = crear_usuario_db(id_rol=1, estado=2)
    headers = crear_auth_headers(admin)
    nombre = f"Plantilla Auditoria {_sufijo_letras()}"

    creada = config_client.post(
        "/configuracion/plantillas",
        json={
            "template_name": nombre,
            "id_especie": especie_activa,
            "params_snapshot": _SNAPSHOT_VALIDO,
        },
        headers=headers,
    )
    assert creada.status_code == 201, creada.text
    id_plantilla = creada.json()["id_plantilla"]

    version = config_client.post(
        f"/configuracion/plantillas/{id_plantilla}/versiones",
        json={"params_snapshot": _SNAPSHOT_VALIDO},
        headers=headers,
    )
    assert version.status_code == 201, version.text
    id_plantilla_v2 = version.json()["id_plantilla"]

    auditoria = config_client.get("/configuracion/plantillas/auditoria", headers=headers)

    assert auditoria.status_code == 200, auditoria.text
    cuerpo = auditoria.json()
    ids_auditados = {item["id_plantilla"] for item in cuerpo["items"]}
    assert {id_plantilla, id_plantilla_v2} <= ids_auditados
    tipos = {item["tipo_operacion"] for item in cuerpo["items"] if item["id_plantilla"] in (id_plantilla, id_plantilla_v2)}
    assert tipos == {"CREATE"}


# ── RF-31 (#126) — rango físico de umbrales, contra BD real ──────────────────


def test_crear_plantilla_con_umbral_fuera_de_rango_fisico_responde_422(
    config_client, crear_usuario_db, crear_auth_headers, especie_activa: int, variable_ambiental_activa: dict
) -> None:
    admin = crear_usuario_db(id_rol=1, estado=2)
    headers = crear_auth_headers(admin)

    resp = config_client.post(
        "/configuracion/plantillas",
        json={
            "template_name": f"Plantilla Rango {_sufijo_letras()}",
            "id_especie": especie_activa,
            "params_snapshot": {
                "umbrales_ambientales": [{
                    "id_variable_ambiental": variable_ambiental_activa["id_variable_ambiental"],
                    "unidad_medida": "°C",
                    "valor_min": -999,
                    "valor_max": 999,
                }],
            },
        },
        headers=headers,
    )

    assert resp.status_code == 422, resp.text
    assert resp.json()["error_code"] == "RANGO_FISICO_INVALIDO"


def test_crear_plantilla_con_umbral_dentro_de_rango_fisico_permite_201(
    config_client, crear_usuario_db, crear_auth_headers, especie_activa: int, variable_ambiental_activa: dict
) -> None:
    admin = crear_usuario_db(id_rol=1, estado=2)
    headers = crear_auth_headers(admin)

    resp = config_client.post(
        "/configuracion/plantillas",
        json={
            "template_name": f"Plantilla Rango {_sufijo_letras()}",
            "id_especie": especie_activa,
            "params_snapshot": {
                "umbrales_ambientales": [{
                    "id_variable_ambiental": variable_ambiental_activa["id_variable_ambiental"],
                    "unidad_medida": "°C",
                    "valor_min": 18.0,
                    "valor_max": 25.0,
                }],
            },
        },
        headers=headers,
    )

    assert resp.status_code == 201, resp.text
