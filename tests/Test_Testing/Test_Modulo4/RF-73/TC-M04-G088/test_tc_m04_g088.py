"""
TC-M04-G088 — Límites de tamaño del payload (truncamiento 64 KB, no rechazo).
Subcasos: TC-M04-270 (65536 exacto), TC-M04-271 (65537), TC-M04-272 (204800).

Diseño (RF-73 v2.0 / Fix PR #785 / commit b440932a):
- TC-M04-270 (021): 65536 bytes exactos no trunca, severidad INFO, payload_truncado ausente.
- TC-M04-271 (022): 65537 bytes trunca a 64 KB, severidad WARNING, payload_truncado=True,
  campos_omitidos presente y no vacío, preservando tipo_modelo e id_version.
- TC-M04-272 (023): 204800 bytes trunca a 64 KB, igual que 022.
- Verificación ORM explícita sobre EventoAuditoriaM04Model (D1) y contrato tipado
  ResultadoRegistroAuditoriaM04 con aceptado=True (D2).
"""
import json
import uuid

from src.prediction.domain.services.validacion_auditoria_m04 import (
    ResultadoRegistroAuditoriaM04,
)
from src.prediction.infrastructure.models.evento_auditoria_m04_model import (
    EventoAuditoriaM04Model,
)
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


def _as_dict(payload_persistido) -> dict:
    if isinstance(payload_persistido, str):
        return json.loads(payload_persistido)
    return payload_persistido


def test_tc_m04_270_payload_64kb_exacto(db_session):
    """TC-M04-270 — 65536 bytes exactos: NO debe truncarse."""
    payload = _make_payload_exact(65536)
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)
    id_ref = str(uuid.uuid4())

    res = repo.registrar(
        tipo_evento="VERSION_REGISTRADA",
        tipo_actor="SISTEMA",
        id_sistema="PYTEST_G088",
        id_referencia=id_ref,
        payload_evento=payload,
        severidad_evento="INFO",
    )

    assert isinstance(res, ResultadoRegistroAuditoriaM04), "debe retornar ResultadoRegistroAuditoriaM04"
    assert res.aceptado is True, (
        f"Payload de 65536 B (exacto) debe aceptarse sin truncar, "
        f"obtenido: aceptado={res.aceptado}, codigo={res.codigo}"
    )
    assert res.codigo is None, (
        f"Un evento aceptado no debe tener codigo de error, obtenido: {res.codigo}"
    )
    assert isinstance(res.id_evento, uuid.UUID), (
        f"id_evento debe ser UUID, obtenido: {type(res.id_evento)}"
    )

    evento = (
        db_session.query(EventoAuditoriaM04Model)
        .filter_by(id_evento=res.id_evento)
        .first()
    )
    assert evento is not None, "no se encontró el evento persistido"
    assert evento.es_payload_truncado is False, (
        f"Payload de 65536 B no debe truncarse (es exactamente el límite), "
        f"es_payload_truncado={evento.es_payload_truncado}"
    )
    assert evento.severidad_evento == "INFO", (
        f"Severidad esperada INFO para payload no truncado, "
        f"obtenida: {evento.severidad_evento}"
    )

    d = _as_dict(evento.payload_evento)
    assert "payload_truncado" not in d or not d.get("payload_truncado"), (
        "Payload no truncado NO debe incluir payload_truncado=True"
    )
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

    res = repo.registrar(
        tipo_evento="VERSION_REGISTRADA",
        tipo_actor="SISTEMA",
        id_sistema="PYTEST_G088",
        id_referencia=id_ref,
        payload_evento=payload,
        severidad_evento="WARNING",
    )

    assert isinstance(res, ResultadoRegistroAuditoriaM04), "debe retornar ResultadoRegistroAuditoriaM04"
    assert res.aceptado is True, (
        f"El evento aceptado debe tener aceptado=True, obtenido: {res.aceptado}, "
        f"codigo={res.codigo}"
    )
    assert res.codigo is None, (
        f"Un evento aceptado no debe tener codigo de error, obtenido: {res.codigo}"
    )
    assert isinstance(res.id_evento, uuid.UUID), (
        f"id_evento debe ser UUID, obtenido: {type(res.id_evento)}"
    )

    evento = (
        db_session.query(EventoAuditoriaM04Model)
        .filter_by(id_evento=res.id_evento)
        .first()
    )
    assert evento is not None, (
        f"El evento truncado no se persistió para id_evento={res.id_evento}"
    )
    assert evento.es_payload_truncado is True, (
        f"El payload > 64KB debe marcarse como truncado, "
        f"es_payload_truncado={evento.es_payload_truncado}"
    )
    assert evento.severidad_evento == "WARNING", (
        f"Severidad esperada WARNING para payload truncado, "
        f"obtenida: {evento.severidad_evento}"
    )

    d = _as_dict(evento.payload_evento)
    assert d.get("payload_truncado") is True, (
        f"El payload persistido debe incluir payload_truncado=True, "
        f"obtenido: {d.get('payload_truncado')}"
    )

    # Verificar preservación de claves mínimas (core del fix #785)
    campos_omitidos = d.get("campos_omitidos", [])
    assert campos_omitidos, (
        "campos_omitidos debe estar presente y no vacío al truncar"
    )
    assert "tipo_modelo" not in campos_omitidos, (
        "El fix #785 debe preservar tipo_modelo fuera de campos_omitidos"
    )
    assert "id_version" not in campos_omitidos, (
        "El fix #785 debe preservar id_version fuera de campos_omitidos"
    )
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

    res = repo.registrar(
        tipo_evento="VERSION_REGISTRADA",
        tipo_actor="SISTEMA",
        id_sistema="PYTEST_G088",
        id_referencia=id_ref,
        payload_evento=payload,
        severidad_evento="WARNING",
    )

    assert isinstance(res, ResultadoRegistroAuditoriaM04), "debe retornar ResultadoRegistroAuditoriaM04"
    assert res.aceptado is True, (
        f"El evento aceptado debe tener aceptado=True, obtenido: {res.aceptado}, "
        f"codigo={res.codigo}"
    )
    assert res.codigo is None, (
        f"Un evento aceptado no debe tener codigo de error, obtenido: {res.codigo}"
    )
    assert isinstance(res.id_evento, uuid.UUID), (
        f"id_evento debe ser UUID, obtenido: {type(res.id_evento)}"
    )

    evento = (
        db_session.query(EventoAuditoriaM04Model)
        .filter_by(id_evento=res.id_evento)
        .first()
    )
    assert evento is not None, (
        f"El evento truncado no se persistió para id_evento={res.id_evento}"
    )
    assert evento.es_payload_truncado is True, (
        f"El payload > 64KB debe marcarse como truncado, "
        f"es_payload_truncado={evento.es_payload_truncado}"
    )
    assert evento.severidad_evento == "WARNING", (
        f"Severidad esperada WARNING para payload truncado, "
        f"obtenida: {evento.severidad_evento}"
    )

    d = _as_dict(evento.payload_evento)
    assert d.get("payload_truncado") is True, (
        f"El payload persistido debe incluir payload_truncado=True, "
        f"obtenido: {d.get('payload_truncado')}"
    )

    # Verificar preservación de claves mínimas (core del fix #785)
    campos_omitidos = d.get("campos_omitidos", [])
    assert campos_omitidos, (
        "campos_omitidos debe estar presente y no vacío al truncar"
    )
    assert "tipo_modelo" not in campos_omitidos, (
        "El fix #785 debe preservar tipo_modelo fuera de campos_omitidos"
    )
    assert "id_version" not in campos_omitidos, (
        "El fix #785 debe preservar id_version fuera de campos_omitidos"
    )
    assert "tipo_modelo" in d, (
        "GAP A7 (INC-M04-159-G088): campo 'tipo_modelo' ausente en payload "
        f"truncado. Keys persistidas: {list(d.keys())}."
    )
    assert "id_version" in d, (
        "GAP A7 (INC-M04-159-G088): campo 'id_version' ausente en payload "
        f"truncado. Keys persistidas: {list(d.keys())}."
    )
