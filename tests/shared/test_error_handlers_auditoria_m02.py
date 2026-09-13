"""INC-M02-43-G29 / RF-36: las operaciones de /activos-biologicos rechazadas
por validación de entrada (400 antes del use case) deben quedar registradas
en `modulo2.bitacora_auditoria_m02`, igual que las exitosas y las rechazadas
por reglas de negocio (que sí pasan por el use case).
"""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from src.shared.error_handlers import register_error_handlers


class _DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.closed = False

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class _BitacoraRepoFake:
    eventos: list[Any] = []

    def __init__(self, db) -> None:
        self.db = db

    def registrar(self, evento) -> None:
        _BitacoraRepoFake.eventos.append(evento)


class _Payload(BaseModel):
    raza: str


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    _BitacoraRepoFake.eventos = []

    import src.shared.database as database_module
    import src.shared.jwt as jwt_module
    import src.biological_assets.infrastructure.repositories.bitacora_auditoria_repository as bitacora_module

    monkeypatch.setattr(database_module, "SessionLocal", lambda: _DbFake())
    monkeypatch.setattr(jwt_module, "verify_token", lambda token: {"sub": "42"})
    monkeypatch.setattr(bitacora_module, "SqlAlchemyBitacoraAuditoriaRepository", _BitacoraRepoFake)

    app = FastAPI()
    register_error_handlers(app)

    @app.patch("/activos-biologicos/{id_activo}")
    def actualizar(id_activo: int, payload: _Payload):
        return {"ok": True}

    @app.post("/otro-modulo")
    def otro(payload: _Payload):
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


def test_400_en_activos_biologicos_registra_auditoria_fallida(client: TestClient) -> None:
    respuesta = client.patch(
        "/activos-biologicos/173",
        json={"biomasa_total": 999},
        headers={"Authorization": "Bearer token-valido"},
    )

    assert respuesta.status_code == 400
    assert len(_BitacoraRepoFake.eventos) == 1
    evento = _BitacoraRepoFake.eventos[0]
    assert evento.rf_origen == "RF36"
    assert evento.tipo_evento == "VALIDACION_RECHAZADA"
    assert evento.resultado == "FALLIDO"
    assert evento.id_activo_biologico == 173
    assert evento.id_usuario_responsable == 42


def test_400_sin_token_registra_auditoria_sin_usuario(client: TestClient) -> None:
    respuesta = client.patch("/activos-biologicos/173", json={"biomasa_total": 999})

    assert respuesta.status_code == 400
    assert len(_BitacoraRepoFake.eventos) == 1
    assert _BitacoraRepoFake.eventos[0].id_usuario_responsable is None


def test_400_fuera_de_activos_biologicos_no_toca_la_bitacora_m02(client: TestClient) -> None:
    respuesta = client.post("/otro-modulo", json={"raza": 123})

    assert respuesta.status_code == 400
    assert _BitacoraRepoFake.eventos == []
