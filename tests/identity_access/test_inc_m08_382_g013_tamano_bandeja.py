# | Fecha      | Nombre       | Que se hizo                                                          |
# |------------|--------------|----------------------------------------------------------------------|
# | 2026-11-21 | destroyerban | INC-M08-382-G013 RF-105: la bandeja trae 50 por página sin tamano    |
"""INC-M08-382-G013 (#1198): ``GET /notificaciones`` sin ``tamano`` pagina de 50 en 50 (RF-105 reglas 7 y 10).

Por HTTP, sin BD: el router real con los manejadores de error globales y un repositorio falso que
registra cuántas filas se pidieron.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.routers import notificaciones_routers
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers


class RepoFake:
    def __init__(self, total: int) -> None:
        self.total = total
        self.pedidos: list[tuple[int, int]] = []

    def listar_internas(self, id_usuario, filtro, offset, limit):
        self.pedidos.append((offset, limit))
        return []

    def contar_internas(self, id_usuario, filtro):
        return self.total


@pytest.fixture
def repo(monkeypatch: pytest.MonkeyPatch) -> RepoFake:
    fake = RepoFake(total=463)
    monkeypatch.setattr(notificaciones_routers, "SqlAlchemyNotificacionRepository", lambda _db: fake)
    return fake


@pytest.fixture
def cliente(repo: RepoFake) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(notificaciones_routers.router)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=176, id_token=1, id_rol=2, id_estado_cuenta=2)
    return TestClient(app)


def test_sin_tamano_la_pagina_es_de_50(cliente: TestClient, repo: RepoFake):
    r = cliente.get("/notificaciones", params={"pagina": 1})
    assert r.status_code == 200
    assert r.json()["tamano"] == 50
    assert repo.pedidos == [(0, 50)]


def test_la_segunda_pagina_sin_tamano_empieza_en_50(cliente: TestClient, repo: RepoFake):
    assert cliente.get("/notificaciones", params={"pagina": 2}).status_code == 200
    assert repo.pedidos == [(50, 50)]


def test_un_tamano_menor_se_respeta(cliente: TestClient, repo: RepoFake):
    r = cliente.get("/notificaciones", params={"pagina": 1, "tamano": 10})
    assert r.json()["tamano"] == 10 and repo.pedidos == [(0, 10)]


@pytest.mark.parametrize("params", [{"pagina": 1, "tamano": 51}, {"pagina": 0}, {"pagina": 1, "tamano": 0}])
def test_fuera_de_rango_responde_400(cliente: TestClient, repo: RepoFake, params: dict):
    r = cliente.get("/notificaciones", params=params)
    assert r.status_code == 400
    assert r.json()["error_code"] == "VAL_ENTRADA"
    assert repo.pedidos == []
