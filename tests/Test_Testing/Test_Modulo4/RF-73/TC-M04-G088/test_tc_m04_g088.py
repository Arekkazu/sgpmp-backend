"""
TC-M04-G088 — Límites de tamaño del payload (truncamiento 64 KB, no rechazo).
Subcasos: TC-M04-270 (65536 exacto), TC-M04-271 (65537), TC-M04-272 (204800).

Diseño (P1/P2/P3-A del QA Lead):
- P1: tipo_evento = VERSION_REGISTRADA (payload mínimos: tipo_modelo, id_version).
- P2: severidad_evento = ERROR en los 3 (passthrough en 270, override a WARNING en 271/272).
- P3-A: verificar 4 cosas en payload persistido: es_payload_truncado, severidad,
  JSON válido, y campos mínimos PRESENTES (Opción A estricta).

Nota: 271 y 272 FALLARÁN hoy contra el backend TEST porque _truncar_payload
usa un fallback que descarta los campos mínimos (gap A7, INC-M04-159-G088).
"""
import json
import uuid

from sqlalchemy import text

from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)


def _make_payload_exact(target_bytes: int) -> dict:
    """Payload cuyo json.dumps().encode() mida exactamente target_bytes."""
    payload = {
        "tipo_modelo": "MODELO_ESPECIES_MEDIANAS",
        "id_version": "00000000-0000-0000-0000-000000000000",
        "blob": "",
    }
    base_len = len(json.dumps(payload, default=str).encode())
    delta = target_bytes - base_len
    if delta < 0:
        raise ValueError(f"target_bytes={target_bytes} < base={base_len}")
    payload["blob"] = "x" * delta
    actual = len(json.dumps(payload, default=str).encode())
    if actual != target_bytes:
        raise RuntimeError(f"payload mide {actual} bytes, esperado {target_bytes}")
    return payload


def _count(db, tipo: str) -> int:
    return db.execute(
        text("SELECT COUNT(*) FROM modulo4.eventos_auditoria_m04 "
             "WHERE tipo_evento = :t"),
        {"t": tipo},
    ).scalar() or 0


def _get_persisted(db, id_ref: str):
    return db.execute(
        text("SELECT es_payload_truncado, severidad_evento, payload_evento "
             "FROM modulo4.eventos_auditoria_m04 "
             "WHERE id_referencia = :r AND tipo_evento = 'VERSION_REGISTRADA' "
             "ORDER BY fecha_evento DESC LIMIT 1"),
        {"r": id_ref},
    ).fetchone()


def _as_dict(payload_persistido) -> dict:
    if isinstance(payload_persistido, str):
        return json.loads(payload_persistido)
    return payload_persistido


def _registrar(repo, id_ref: str, payload: dict) -> None:
    try:
        repo.registrar(
            tipo_evento="VERSION_REGISTRADA",
            tipo_actor="SISTEMA",
            id_sistema="PYTEST_G088",
            id_referencia=id_ref,
            payload_evento=payload,
            severidad_evento="ERROR",
        )
    except Exception as e:
        raise AssertionError(
            f"registrar() lanzó excepción inesperada al persistir: "
            f"{type(e).__name__}: {e}"
        )


def test_tc_m04_270_payload_64kb_exacto(db_session):
    """TC-M04-270 — 65536 bytes exactos: NO debe truncarse."""
    payload = _make_payload_exact(65536)
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)
    id_ref = str(uuid.uuid4())
    n_antes = _count(db_session, "VERSION_REGISTRADA")
    _registrar(repo, id_ref, payload)
    db_session.flush()
    n_despues = _count(db_session, "VERSION_REGISTRADA")
    assert n_despues == n_antes + 1, (
        f"RF-73: evento debe persistirse (no rechazarse). "
        f"Filas nuevas: {n_despues - n_antes}."
    )
    row = _get_persisted(db_session, id_ref)
    assert row is not None, "no se encontró el evento persistido"
    es_truncado, sev, payload_persistido = row
    assert es_truncado is False, (
        f"RF-73: payload de 65536 bytes NO debe truncarse. "
        f"es_payload_truncado={es_truncado}."
    )
    assert sev == "ERROR", (
        f"RF-73: severidad debe passthrough como 'ERROR' cuando no trunca. "
        f"Obtenida: '{sev}'."
    )
    d = _as_dict(payload_persistido)
    assert "tipo_modelo" in d, (
        f"campo 'tipo_modelo' ausente en payload persistido. Keys: {list(d.keys())}"
    )
    assert "id_version" in d, (
        f"campo 'id_version' ausente en payload persistido. Keys: {list(d.keys())}"
    )


def test_tc_m04_271_payload_1_byte_sobre(db_session):
    """TC-M04-271 — 65537 bytes: DEBE truncarse y preservar campos mínimos."""
    payload = _make_payload_exact(65537)
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)
    id_ref = str(uuid.uuid4())
    n_antes = _count(db_session, "VERSION_REGISTRADA")
    _registrar(repo, id_ref, payload)
    db_session.flush()
    n_despues = _count(db_session, "VERSION_REGISTRADA")
    assert n_despues == n_antes + 1, (
        f"RF-73: evento debe persistirse (no rechazarse). "
        f"Filas nuevas: {n_despues - n_antes}."
    )
    row = _get_persisted(db_session, id_ref)
    assert row is not None, "no se encontró el evento persistido"
    es_truncado, sev, payload_persistido = row
    assert es_truncado is True, (
        f"RF-73: payload de 65537 bytes DEBE truncarse. "
        f"es_payload_truncado={es_truncado}."
    )
    assert sev == "WARNING", (
        f"RF-73 E1: severidad debe override a 'WARNING' al truncar. "
        f"Obtenida: '{sev}'."
    )
    d = _as_dict(payload_persistido)
    assert "tipo_modelo" in d, (
        "GAP A7 (INC-M04-159-G088): campo 'tipo_modelo' ausente en payload "
        f"truncado. Keys persistidas: {list(d.keys())}."
    )
    assert "id_version" in d, (
        "GAP A7 (INC-M04-159-G088): campo 'id_version' ausente en payload "
        f"truncado. Keys persistidas: {list(d.keys())}."
    )


def test_tc_m04_272_payload_mucho_sobre(db_session):
    """TC-M04-272 — 204800 bytes: DEBE truncarse y preservar campos mínimos."""
    payload = _make_payload_exact(204800)
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)
    id_ref = str(uuid.uuid4())
    n_antes = _count(db_session, "VERSION_REGISTRADA")
    _registrar(repo, id_ref, payload)
    db_session.flush()
    n_despues = _count(db_session, "VERSION_REGISTRADA")
    assert n_despues == n_antes + 1, (
        f"RF-73: evento debe persistirse (no rechazarse). "
        f"Filas nuevas: {n_despues - n_antes}."
    )
    row = _get_persisted(db_session, id_ref)
    assert row is not None, "no se encontró el evento persistido"
    es_truncado, sev, payload_persistido = row
    assert es_truncado is True, (
        f"RF-73: payload de 204800 bytes DEBE truncarse. "
        f"es_payload_truncado={es_truncado}."
    )
    assert sev == "WARNING", (
        f"RF-73 E1: severidad debe override a 'WARNING' al truncar. "
        f"Obtenida: '{sev}'."
    )
    d = _as_dict(payload_persistido)
    assert "tipo_modelo" in d, (
        "GAP A7 (INC-M04-159-G088): campo 'tipo_modelo' ausente en payload "
        f"truncado. Keys persistidas: {list(d.keys())}."
    )
    assert "id_version" in d, (
        "GAP A7 (INC-M04-159-G088): campo 'id_version' ausente en payload "
        f"truncado. Keys persistidas: {list(d.keys())}."
    )
