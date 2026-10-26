"""
TC-M04-G099 — Consistencia temporal y corrección automática de timestamp.
Subcaso: TC-M04-056 (desincronización futuro/desordenado).

Diseño: TEST NEGATIVO HONESTO para documentar BLOQUEADO_POR_DISENO.
Evidencia 3 bloqueos estructurales:
  B1: registrar() no acepta timestamp_evento como kwarg → TypeError
  B2: registrar() no acepta origen_dato como kwarg → TypeError
  B3: el backend no emite TIMESTAMP_CORREGIDO ni corrige fechas futuras

Veredicto esperado: BLOQUEADO_POR_DISENO (feature E7 no implementado).
Conforme RN-R05-EXT: no se adaptan asserts para que pase.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from src.prediction.infrastructure.repositories import evento_auditoria_m04_repository
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)


def _count(db, tipo_evento: str) -> int:
    return db.execute(
        text("SELECT COUNT(*) FROM modulo4.eventos_auditoria_m04 "
             "WHERE tipo_evento = :t"),
        {"t": tipo_evento},
    ).scalar() or 0


def test_tc_m04_056_bloqueo_timestamp(db_session):
    """TC-M04-056 — evidencia los 3 bloqueos estructurales de RF-73 E7."""
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)
    n_antes = _count(db_session, "TIMESTAMP_CORREGIDO")

    # B1: registrar() no acepta timestamp_evento
    with pytest.raises(TypeError):
        repo.registrar(
            tipo_evento="HISTORIAL_CONSULTADO",
            tipo_actor="SISTEMA",
            id_sistema="PYTEST_G099",
            payload_evento={"test": "b1"},
            timestamp_evento="2026-10-26T05:00:00Z",
        )

    # B2: registrar() no acepta origen_dato
    with pytest.raises(TypeError):
        repo.registrar(
            tipo_evento="HISTORIAL_CONSULTADO",
            tipo_actor="SISTEMA",
            id_sistema="PYTEST_G099",
            payload_evento={"test": "b2"},
            origen_dato="BACKEND",
        )

    # B3: el backend no corrige timestamps futuros ni emite TIMESTAMP_CORREGIDO
    futuro = datetime.now(timezone.utc) + timedelta(hours=1)

    original_datetime = evento_auditoria_m04_repository.datetime
    try:
        class _FakeDatetime:
            @classmethod
            def now(cls, tz=None):
                return futuro
            @classmethod
            def utcnow(cls):
                return futuro.replace(tzinfo=None)

        evento_auditoria_m04_repository.datetime = _FakeDatetime
        repo.registrar(
            tipo_evento="HISTORIAL_CONSULTADO",
            tipo_actor="SISTEMA",
            id_sistema="PYTEST_G099",
            payload_evento={"test": "b3"},
        )
        db_session.flush()
    finally:
        evento_auditoria_m04_repository.datetime = original_datetime

    n_despues = _count(db_session, "TIMESTAMP_CORREGIDO")

    assert n_despues > n_antes, (
        "RF-73 E7: el backend debería emitir TIMESTAMP_CORREGIDO al "
        "detectar un timestamp futuro o desordenado. No se emitió. "
        "Feature E7 no implementado — BLOQUEADO_POR_DISENO."
    )
