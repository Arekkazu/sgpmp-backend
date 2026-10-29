"""RF-16 — una etapa desactivada se puede reactivar y vuelve a ser editable.

Antes quedaba bloqueada: editarla respondía 422 ETAPA_INACTIVA ("Reactívela
primero") y no existía forma de reactivarla; su nombre seguía ocupado.
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


@pytest.fixture
def una_especie(db_session: Session) -> int:
    fila = db_session.execute(
        text("SELECT id_especie FROM modulo9.especies WHERE es_activo ORDER BY id_especie LIMIT 1")
    ).first()
    if fila is None:
        pytest.skip("Se requiere al menos 1 especie activa en modulo9.especies.")
    return fila[0]


@pytest.fixture
def client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    from src.configuration.infrastructure.routers.ciclo_router import router
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, client=("sgpmp-integration-tests", 50000), raise_server_exceptions=False) as c:
        yield c


def test_reactivar_etapa_inactiva_la_deja_editable(
    client, una_especie, crear_usuario_db, crear_auth_headers,
) -> None:
    headers = crear_auth_headers(crear_usuario_db(id_rol=1, estado=2))
    nombre = "Etapa IT " + "".join(random.choices(string.ascii_letters, k=10))
    creada = client.post(
        "/configuracion/ciclos",
        json={"id_especie": una_especie, "nombre": nombre, "duracion_dias": 10},
        headers=headers,
    )
    assert creada.status_code == 201, creada.text
    id_ciclo = creada.json()["id_ciclo_biologico"]
    assert client.patch(f"/configuracion/ciclos/{id_ciclo}/desactivar", headers=headers).status_code == 200

    r = client.patch(f"/configuracion/ciclos/{id_ciclo}/reactivar", headers=headers)

    assert r.status_code == 200, r.text
    assert r.json()["es_activo"] is True
    editada = client.patch(
        f"/configuracion/ciclos/{id_ciclo}",
        json={"nombre": nombre, "duracion_dias": 12, "fecha_actualizacion": r.json()["fecha_actualizacion"]},
        headers=headers,
    )
    assert editada.status_code == 200, editada.text
    otra = client.patch(f"/configuracion/ciclos/{id_ciclo}/reactivar", headers=headers)
    assert otra.status_code == 422
    assert otra.json()["error_code"] == "ETAPA_YA_ACTIVA"


def test_editar_etapa_nunca_editada_con_fecha_null(
    client, una_especie, crear_usuario_db, crear_auth_headers,
) -> None:
    # Contrato del que depende el frontend: una etapa nunca editada tiene
    # fecha_actualizacion null y se edita enviando null, sin 412.
    headers = crear_auth_headers(crear_usuario_db(id_rol=1, estado=2))
    nombre = "Etapa IT " + "".join(random.choices(string.ascii_letters, k=10))
    creada = client.post(
        "/configuracion/ciclos",
        json={"id_especie": una_especie, "nombre": nombre, "duracion_dias": 10},
        headers=headers,
    ).json()
    assert creada["fecha_actualizacion"] is None

    r = client.patch(
        f"/configuracion/ciclos/{creada['id_ciclo_biologico']}",
        json={"nombre": nombre, "duracion_dias": 11, "fecha_actualizacion": None},
        headers=headers,
    )

    assert r.status_code == 200, r.text
