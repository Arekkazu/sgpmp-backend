"""RF-15 / INC-M09-02-G02 (#111) — POST /configuracion/especies con datos
válidos debe crear la especie (201), no fallar con 500.

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


def _sufijo_letras(largo: int = 6) -> str:
    """Sufijo aleatorio solo de letras: el nombre de especie no admite dígitos."""
    return "".join(random.choices(string.ascii_uppercase, k=largo))


@pytest.fixture
def requiere_modulo9(db_session: Session) -> None:
    existe = db_session.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'modulo9'")
    ).first()
    if existe is None:
        pytest.skip("La base de pruebas no tiene el schema modulo9.")


@pytest.fixture
def config_client(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, requiere_modulo9: None
) -> Generator[TestClient, None, None]:
    from src.configuration.infrastructure.routers.especie_router import router as especie_router
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(especie_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, client=("sgpmp-integration-tests", 50000), raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _headers_admin(crear_usuario_db, crear_auth_headers) -> dict:
    admin = crear_usuario_db(id_rol=1, estado=2)
    return crear_auth_headers(admin)


def test_registrar_especie_con_datos_validos_responde_201(
    config_client, crear_usuario_db, crear_auth_headers, db_session: Session
) -> None:
    """Antes del fix, el trigger huérfano `trg_especies_audit` (exige
    `app.usuario_id`, nunca provisto por la app) hacía fallar CUALQUIER
    INSERT sobre `modulo9.especies` con 500 ERROR_INTERNO."""
    headers = _headers_admin(crear_usuario_db, crear_auth_headers)
    nombre = f"Especie Prueba {_sufijo_letras()}"

    respuesta = config_client.post(
        "/configuracion/especies",
        json={"nombre": nombre, "descripcion": "Especie creada por prueba de regresión"},
        headers=headers,
    )

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["nombre"].upper() == nombre.upper()  # trigger de BD normaliza a Title Case
    assert cuerpo["es_activo"] is True

    auditoria = db_session.execute(
        text(
            "SELECT tipo_operacion FROM modulo9.auditorias_especies "
            "WHERE id_especie = :id ORDER BY id_auditoria_especie DESC LIMIT 1"
        ),
        {"id": cuerpo["id_especie"]},
    ).scalar_one()
    assert auditoria == "CREATE"


def test_editar_especie_activa_responde_200(
    config_client, crear_usuario_db, crear_auth_headers, db_session: Session
) -> None:
    """El trigger huérfano también rompía UPDATE (dispara en INSERT OR UPDATE),
    así que editar quedaba igual de roto aunque no estuviera reportado.

    `fecha_actualizacion` queda en NULL tras el registro (no se setea en el
    INSERT), y `EditarEspecieDTO.fecha_actualizacion` es un `datetime`
    obligatorio (no admite `null`) — un problema aparte del que trata este
    issue. Se fija el timestamp por SQL para poder ejercitar el UPDATE real
    sin toparse con ese bug distinto.
    """
    headers = _headers_admin(crear_usuario_db, crear_auth_headers)
    nombre = f"Especie Editable {_sufijo_letras()}"
    creada = config_client.post(
        "/configuracion/especies",
        json={"nombre": nombre, "descripcion": "Original"},
        headers=headers,
    )
    assert creada.status_code == 201, creada.text
    id_especie = creada.json()["id_especie"]

    fecha_actualizacion = db_session.execute(
        text(
            "UPDATE modulo9.especies SET fecha_actualizacion = now() "
            "WHERE id_especie = :id RETURNING fecha_actualizacion"
        ),
        {"id": id_especie},
    ).scalar_one()
    db_session.commit()

    editada = config_client.patch(
        f"/configuracion/especies/{id_especie}",
        json={
            "nombre": nombre,
            "descripcion": "Editada",
            "fecha_actualizacion": fecha_actualizacion.isoformat(),
        },
        headers=headers,
    )

    assert editada.status_code == 200, editada.text
    assert editada.json()["descripcion"] == "Editada"
