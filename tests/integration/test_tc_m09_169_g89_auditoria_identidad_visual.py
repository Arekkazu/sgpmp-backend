"""TC-M09-169-G89 (#307): PATCH de identidad visual consultable por API.

La finca, su dueño y la identidad visual de partida son fixtures propias de la
prueba (no datos de la base compartida): igual que en
``test_inc_m09_g82_acceso_finca_integration.py``, la prueba nunca debe asumir
que un registro transaccional preexiste en el ambiente. La transacción
exterior de ``db_session`` revierte tanto la finca como el cambio visual y su
auditoría al finalizar.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"


def _nombre_finca() -> str:
    # modulo9.trg_fn_finca_nombre_unique solo admite letras, espacios y
    # caracteres del español: sin dígitos ni símbolos (mismo criterio que
    # test_inc_m09_g82_acceso_finca_integration.py).
    traduccion = str.maketrans("0123456789abcdef", "abcdefghijklmnop")
    return "Finca Integracion RF Veintiseis " + uuid.uuid4().hex[:12].translate(traduccion)


def _crear_finca(db_session: Session, id_usuario: int) -> int:
    ubicacion = json.dumps(
        {
            "departamento": "Huila",
            "municipio": "Neiva",
            "vereda": "Centro",
            "latitud": "2.93",
            "longitud": "-75.28",
        }
    )
    id_finca = db_session.execute(
        text(
            """
            INSERT INTO modulo9.fincas (
                nombre, ubicacion, tamano_h, fecha_actualizacion,
                fecha_creacion, es_activo, id_usuario
            ) VALUES (
                :nombre, CAST(:ubicacion AS jsonb), 10.00, now(), now(), true, :id_usuario
            )
            RETURNING id_finca
            """
        ),
        {
            "nombre": _nombre_finca(),
            "ubicacion": ubicacion,
            "id_usuario": id_usuario,
        },
    ).scalar_one()
    db_session.flush()
    return id_finca


@pytest.fixture
def identidad_visual_existente(db_session: Session, crear_usuario_db) -> dict:
    dueno = crear_usuario_db(id_rol=1, estado=2)
    id_finca = _crear_finca(db_session, dueno["id_usuario"])

    fila = db_session.execute(
        text(
            """
            INSERT INTO modulo9.identidad_visuales (
                id_finca, id_usuario, primary_color, secondary_color,
                org_display_name, version, fecha_creacion
            ) VALUES (
                :id_finca, :id_usuario, '#3A7BD5', '#1F2933',
                'Integracion RF26 base', 1, now()
            )
            RETURNING id_finca, primary_color, secondary_color, org_display_name, version
            """
        ),
        {"id_finca": id_finca, "id_usuario": dueno["id_usuario"]},
    ).mappings().one()
    db_session.flush()
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
