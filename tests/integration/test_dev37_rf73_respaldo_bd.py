# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | DEV-37 RF-73: sincronización del respaldo y lectura de la bitácora por el Veterinario |
"""DEV-37 contra PostgreSQL: el respaldo se sincroniza con su fecha original y origen
FALLBACK sin duplicarse, y el Veterinario lee la bitácora de M04 (DB-08)."""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


class _SinAviso:
    def __init__(self): self.avisos = []
    def avisar_fallback_activado(self, **kw): self.avisos.append(kw)


def test_respaldo_se_sincroniza_una_sola_vez_con_fecha_original(db_session, tmp_path):
    from src.prediction.application.use_cases.auditoria.sincronizar_fallback_auditoria_m04_use_case import (
        SincronizarFallbackAuditoriaM04UseCase,
    )
    from src.prediction.infrastructure.adapters.fallback_auditoria_m04_archivo import FallbackAuditoriaM04Archivo
    from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
        SqlAlchemyEventoAuditoriaM04Repository,
    )

    archivo = FallbackAuditoriaM04Archivo(tmp_path)
    id_evento, fecha = uuid.uuid4(), datetime(2026, 10, 20, 8, 30, tzinfo=timezone.utc)
    archivo.escribir(dict(
        id_evento=id_evento, fecha_evento=fecha, tipo_evento="HISTORIAL_CONSULTADO", tipo_actor="SISTEMA",
        id_sistema="DESARROLLO_M04", payload_evento={"prueba": "DEV-37"}, es_payload_truncado=False,
        severidad_evento="ERROR", correlacion_id=uuid.uuid4(), hash_evento="x" * 64,
    ))
    repo, aviso = SqlAlchemyEventoAuditoriaM04Repository(db_session, archivo), _SinAviso()
    caso = SincronizarFallbackAuditoriaM04UseCase(db=db_session, repo=repo, fallback=archivo, aviso=aviso)
    assert caso.execute().eventos == 1
    fila = db_session.execute(text(
        "SELECT origen_registro, fecha_evento FROM modulo4.eventos_auditoria_m04 WHERE id_evento = :id"
    ), {"id": id_evento}).one()
    assert fila.origen_registro == "FALLBACK" and fila.fecha_evento == fecha
    assert db_session.execute(text(
        "SELECT count(*) FROM modulo4.eventos_auditoria_m04 WHERE tipo_evento = 'AUDITORIA_FALLBACK_ACTIVADO' "
        "AND payload_evento->>'inicio_contingencia' = :inicio"
    ), {"inicio": fecha.isoformat()}).scalar_one() == 1
    assert aviso.avisos == [{"inicio_contingencia": fecha.isoformat(), "eventos": 1}]
    # El archivo quedó sincronizado; reinsertar el mismo id no duplica.
    assert archivo.pendientes() == []
    assert repo.registrar_desde_fallback({"id_evento": str(id_evento)}) is False


@pytest.fixture
def cliente(db_session, integration_app, monkeypatch):
    from src.prediction.infrastructure.routers.auditoria_m04_router import router
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", "sgpmp-integration-tests-only")
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_veterinario_lee_la_bitacora_y_el_productor_no(cliente, crear_usuario_db, crear_auth_headers):
    veterinario = crear_auth_headers(crear_usuario_db(id_rol=3, estado=2))
    productor = crear_auth_headers(crear_usuario_db(id_rol=2, estado=2))
    assert cliente.get("/prediccion/auditoria", headers=veterinario).status_code == 200
    assert cliente.get("/prediccion/auditoria", headers=productor).status_code == 403
