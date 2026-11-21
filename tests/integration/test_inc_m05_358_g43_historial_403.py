# | Fecha      | Nombre         | Que se hizo                                                          |
# |------------|----------------|----------------------------------------------------------------------|
# | 2026-11-12 | LuisfNarvaez01 | INC-M05-358-G43 RF-81: activo ajeno → 403 (E2), no 404, bajo RLS     |
"""INC-M05-358-G43 (#1086), TC-M05-G43 A02.

``GET /suministros/historial`` respondía 404 «El activo biológico N no existe» a un usuario
sin acceso a la finca del activo: la RLS de ``modulo2`` le oculta el activo y el caso de uso lo
tomaba como inexistente. RF-81 E2 pide 403 «No tiene permisos para consultar el historial del
activo N...». Los requests corren con el rol de la API (``sgpmp_app``), sujetos a RLS, como en
TEST; con el superusuario de pruebas el defecto no se ve."""
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.integration.test_m05_flujo_completo_integration import (  # noqa: F401 (fixtures)
    _catalogos, _consumo, _escenario, _id, admin, cliente,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def cliente_rls(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers
    from src.supplies.infrastructure.routers.historial_suministros_router import router as historial

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", "sgpmp-integration-tests-only")
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        db_session.info.clear()
        db_session.execute(text('SET LOCAL ROLE "sgpmp_app"'))
        try:
            yield db_session
        finally:
            db_session.execute(text("RESET ROLE"))

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(historial)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def activo_con_historial(cliente, db_session, admin):
    usuario, headers = admin
    esc = _escenario(db_session, usuario["id_usuario"])
    assert _consumo(cliente, headers, esc, "06:00").status_code == 201
    return esc


@pytest.fixture
def productor_de_otra_finca(db_session, crear_usuario_db, crear_auth_headers):
    productor = crear_usuario_db(id_rol=2, estado=2)
    otra = _escenario(db_session, productor["id_usuario"], con_fase=False)
    return productor, crear_auth_headers(productor), otra


def test_activo_de_otra_finca_responde_403_con_el_mensaje_de_e2(cliente_rls, activo_con_historial,
                                                               productor_de_otra_finca):
    _, headers, _ = productor_de_otra_finca
    id_activo = activo_con_historial["activo"]

    r = cliente_rls.get("/suministros/historial", headers=headers, params={"id_activo_biologico": id_activo})

    assert r.status_code == 403, r.text
    assert f"No tiene permisos para consultar el historial del activo {id_activo}" in r.json()["message"]
    assert "items" not in r.json() and "resumen" not in r.json()


def test_exportar_activo_de_otra_finca_tambien_responde_403(cliente_rls, activo_con_historial,
                                                            productor_de_otra_finca):
    _, headers, _ = productor_de_otra_finca
    r = cliente_rls.get("/suministros/historial/exportar", headers=headers, params={
        "id_activo_biologico": activo_con_historial["activo"], "formato_exportacion": "PDF"})
    assert r.status_code == 403, r.text


def test_activo_inexistente_sigue_respondiendo_404(cliente_rls, productor_de_otra_finca):
    _, headers, _ = productor_de_otra_finca
    r = cliente_rls.get("/suministros/historial", headers=headers, params={"id_activo_biologico": _id()})
    assert r.status_code == 404 and r.json()["error_code"] == "ACTIVO_NO_ENCONTRADO"


def test_activo_de_su_finca_responde_200(cliente_rls, productor_de_otra_finca):
    _, headers, propia = productor_de_otra_finca
    r = cliente_rls.get("/suministros/historial", headers=headers, params={"id_activo_biologico": propia["activo"]})
    assert r.status_code == 200, r.text
