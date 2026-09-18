"""TC-M09-169-G89 (#307): PATCH de identidad visual consultable por API.

La transacción exterior de ``db_session`` revierte tanto el cambio visual como
su auditoría al finalizar la prueba.
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
def identidad_visual_existente(db_session: Session) -> dict:
    existe = db_session.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'modulo9'")
    ).first()
    if existe is None:
        pytest.skip("La base de pruebas no tiene el schema modulo9.")

    fila = db_session.execute(
        text(
            """
            SELECT id_finca, primary_color, secondary_color, org_display_name, version
              FROM modulo9.identidad_visuales
             WHERE primary_color IS NOT NULL
               AND secondary_color IS NOT NULL
               AND org_display_name IS NOT NULL
             ORDER BY id_identidad_visual
             LIMIT 1
            """
        )
    ).mappings().first()
    if fila is None:
        pytest.skip("Se requiere una identidad visual existente en la base de integración.")
    return dict(fila)


@pytest.fixture
def identidad_client(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    # Registra el modelo de la tabla referenciada para que el flush de SQLAlchemy
    # pueda resolver la FK de identidad_visuales -> fincas.
    from src.configuration.infrastructure.models.finca_model import FincaModel  # noqa: F401
    from src.configuration.infrastructure.routers.identidad_visual_router import (
        router as identidad_router,
    )
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(identidad_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(
        app,
        client=("sgpmp-integration-tests", 50000),
        raise_server_exceptions=False,
    ) as client:
        yield client
    app.dependency_overrides.clear()


def test_patch_aparece_en_auditoria_con_usuario_fecha_operacion_y_snapshots(
    identidad_client: TestClient,
    crear_usuario_db,
    crear_auth_headers,
    identidad_visual_existente: dict,
) -> None:
    admin = crear_usuario_db(id_rol=1, estado=2)
    headers = crear_auth_headers(admin)
    id_finca = identidad_visual_existente["id_finca"]

    anterior = identidad_client.get(
        f"/configuracion/identidad-visual/{id_finca}/auditoria",
        headers=headers,
    )
    assert anterior.status_code == 200, anterior.text

    actualizada = identidad_client.patch(
        f"/configuracion/identidad-visual/{id_finca}",
        headers=headers,
        data={
            "primary_color": identidad_visual_existente["primary_color"],
            "secondary_color": identidad_visual_existente["secondary_color"],
            "org_display_name": "Integracion RF26 G89",
            "version": identidad_visual_existente["version"],
        },
    )
    assert actualizada.status_code == 200, actualizada.text

    auditoria = identidad_client.get(
        f"/configuracion/identidad-visual/{id_finca}/auditoria",
        headers=headers,
    )
    assert auditoria.status_code == 200, auditoria.text
    cuerpo = auditoria.json()
    assert cuerpo["total"] == anterior.json()["total"] + 1

    ultimo = cuerpo["items"][0]
    assert ultimo["id_finca"] == id_finca
    assert ultimo["id_usuario"] == admin["id_usuario"]
    assert ultimo["usuario"]
    assert ultimo["fecha_creacion"]
    assert ultimo["tipo_operacion"] == "UPDATE"
    assert ultimo["valor_anterior"]["version"] == identidad_visual_existente["version"]
    assert ultimo["valor_nuevo"]["version"] == identidad_visual_existente["version"] + 1
    assert ultimo["valor_nuevo"]["org_display_name"] == "Integracion RF26 G89"
