"""TC-M09-G103 (#311) — el cambio de idioma personal se persistía correctamente

pero no quedaba ningún registro de auditoría consultable: GET /auditoria/
respondía 200 pero sin ningún evento asociado al cambio, y no existe (ni
debía crearse) un endpoint propio de auditoría para preferencias.
"""
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"


@pytest.fixture
def config_client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    from src.identity_access.infrastructure.routers.auditoria_routers import router as auditoria_router
    from src.configuration.infrastructure.routers.preferencia_idioma_router import router as idioma_router
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(idioma_router)
    app.include_router(auditoria_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, client=("sgpmp-integration-tests", 50000), raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def test_cambio_de_idioma_personal_queda_auditado_y_consultable(
    config_client, crear_usuario_db, crear_auth_headers
) -> None:
    admin = crear_usuario_db(id_rol=1, estado=2)
    headers = crear_auth_headers(admin)

    cambio = config_client.patch(
        "/configuracion/personalizacion/idioma",
        json={"locale_code": "en-US"},
        headers=headers,
    )
    assert cambio.status_code == 200, cambio.text
    assert cambio.json()["locale_code"] == "en-US"

    auditoria = config_client.get(
        "/auditoria/",
        params={"id_usuario": admin["id_usuario"], "tipo_evento": 27},
        headers=headers,
    )
    assert auditoria.status_code == 200, auditoria.text
    items = auditoria.json()["items"]
    assert len(items) == 1
    evento = items[0]
    assert evento["tipo_evento"] == 27
    assert evento["resultado"] == "exitoso"
    assert evento["detalle"]["locale_nuevo"] == "en-US"
