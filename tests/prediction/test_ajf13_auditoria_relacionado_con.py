# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-13 RF-73: filtro por entidad_referencia y nombre legible de la referencia |
"""AJF-13: "ID de referencia" libre mezclaba el lote 2, la versión 2 y la patología 2.

El filtro "Relacionado con" manda ``entidad_referencia`` junto con el id, y cada
evento trae ``nombre_referencia`` (código del animal, nombre de la versión). Sin DB:
repositorio y sesión falsos.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.prediction.domain.entities.evento_auditoria_m04 import EventoAuditoriaM04


def _evento(entidad: str, id_ref: str) -> EventoAuditoriaM04:
    return EventoAuditoriaM04(
        id_evento=uuid.uuid4(), tipo_evento="VERSION_ACTIVADA", modulo="M04",
        fecha_evento=datetime(2026, 11, 2, tzinfo=timezone.utc), tipo_actor="USUARIO",
        correlacion_id=uuid.uuid4(), payload_evento={}, es_payload_truncado=False,
        severidad_evento="INFO", origen_registro="DIRECTO", id_usuario=None, id_sistema=None,
        id_referencia=id_ref, entidad_referencia=entidad, resultado_operacion=None, codigo_error=None,
        descripcion_error=None, origen_dato=None, version_modelo=None, latencia_ms=None, hash_evento=None,
    )


class _Repo:
    def __init__(self):
        self.filtros = None

    def consultar(self, **kw):
        self.filtros = kw
        return [_evento("version_modelo", "2"), _evento("lote", "2")], 2


class _Resultado:
    def __init__(self, filas):
        self._filas = filas

    def all(self):
        return self._filas


class _Db:
    """Responde a las lecturas de nombre: usuarios (ninguno), versiones y activos."""

    def execute(self, sql, params=None):
        texto = str(sql)
        if "versiones_modelos" in texto:
            return _Resultado([("2", "porcinos v3")])
        if "activos_biologicos" in texto:
            return _Resultado([("2", "BOV-003")])
        return _Resultado([])


@pytest.fixture
def cliente(monkeypatch):
    from src.prediction.infrastructure.routers import auditoria_m04_router as router_mod
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    repo = _Repo()
    monkeypatch.setattr(router_mod, "SqlAlchemyEventoAuditoriaM04Repository", lambda db: repo)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router_mod.router)
    app.dependency_overrides[get_db] = lambda: _Db()
    for ruta in router_mod.router.routes:
        for dependencia in ruta.dependencies:
            app.dependency_overrides[dependencia.dependency] = lambda: None
    return TestClient(app), repo


def test_listar_pasa_entidad_referencia_al_repositorio(cliente):
    client, repo = cliente
    r = client.get("/prediccion/auditoria", params={"entidad_referencia": "activo_biologico", "id_referencia": "2"})
    assert r.status_code == 200
    assert repo.filtros["entidad_referencia"] == "activo_biologico"
    assert repo.filtros["id_referencia"] == "2"


def test_cada_evento_trae_el_nombre_de_su_referencia(cliente):
    client, _ = cliente
    items = client.get("/prediccion/auditoria").json()["items"]
    assert [i["nombre_referencia"] for i in items] == ["porcinos v3", "BOV-003"]


def test_entidad_de_id_uuid_no_es_filtrable(cliente):
    client, _ = cliente
    r = client.get("/prediccion/auditoria", params={"entidad_referencia": "resultado_inferencia"})
    assert r.status_code == 422


def test_animal_o_lote_filtra_por_las_dos_etiquetas():
    from sqlalchemy.dialects import postgresql

    from src.prediction.infrastructure.repositories import evento_auditoria_m04_repository as mod

    capturado = {}

    class _Sesion:
        def execute(self, q):
            capturado.setdefault("q", q)

            class _R:
                def scalar_one(self): return 0
                def scalars(self): return self
                def all(self): return []
            return _R()

    mod.SqlAlchemyEventoAuditoriaM04Repository(_Sesion()).consultar(entidad_referencia="activo_biologico")
    sql = str(capturado["q"].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "'activo_biologico'" in sql and "'lote'" in sql
