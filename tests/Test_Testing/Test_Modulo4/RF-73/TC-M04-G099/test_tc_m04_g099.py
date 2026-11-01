# | Fecha      | Nombre                   | Que se hizo                                                                 |
# |------------|--------------------------|-----------------------------------------------------------------------------|
# | 2026-10-25 | HulkyZeus                | TC-M04-056: test negativo honesto inicial (pre-fix)                         |
# | 2026-10-30 | Juan Sebastian Gutierrez | RF-73 TC-M04-G099 (TC-M04-305): D1-D3 Casos A/B/C con contrato tipado y Op3+ |
# | 2026-11-01 | Juan Sebastian Gutierrez | RF-73 TC-M04-G099: Fase 1c ORM explicito D0-D4                             |
"""
TC-M04-G099 — Consistencia temporal y corrección automática de timestamp (RF-73 v2.0 Flujo E7).
Subcaso: TC-M04-305.

Verifica el contrato del fix PR #785 (commit b440932a):
  - Caso A: timestamp futuro (> 60s respecto al reloj del servidor) se reemplaza por
    la hora del servidor y emite evento secundario TIMESTAMP_CORREGIDO con severidad WARNING
    y motivo="FUTURO".
  - Caso B: timestamp desordenado (anterior al último evento registrado con el mismo
    correlacion_id) se reemplaza por la hora del servidor y emite TIMESTAMP_CORREGIDO
    con severidad WARNING y motivo="DESORDENADO".
  - Caso C: sin timestamp_evento el comportamiento no cambia (persiste con hora del
    servidor sin emitir evento secundario).

Reglas de calidad:
  - L17: CERO consultas SQL crudas bajo RLS. Verificación mediante consulta ORM explícita sobre EventoAuditoriaM04Model.
  - L18: Asserts estrictos y honestos sobre el contrato tipado ResultadoRegistroAuditoriaM04 y payload.
  - DEF-04: Prueba de repositorio puro con db_session transaccional (SAVEPOINT + rollback).
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.prediction.infrastructure.models.evento_auditoria_m04_model import (
    EventoAuditoriaM04Model,
)
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)


def _payload_version_registrada() -> dict:
    """Retorna payload válido para VERSION_REGISTRADA conforme a _PAYLOAD_REQUERIDO."""
    return {
        "tipo_modelo": "MODELO_RIESGO_CONTAGIO",
        "id_version": 1,
    }


def test_tc_m04_305a_timestamp_futuro(db_session):
    """TC-M04-305a (Caso A): timestamp futuro (> 60s) se corrige a hora servidor y emite TIMESTAMP_CORREGIDO (WARNING, motivo=FUTURO)."""
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)
    ahora = datetime.now(timezone.utc)
    futuro = ahora + timedelta(hours=1)
    correlacion = uuid.uuid4()
    ref_id = str(uuid.uuid4())

    res = repo.registrar(
        tipo_evento="VERSION_REGISTRADA",
        tipo_actor="SISTEMA",
        id_sistema="PYTEST_G099",
        id_referencia=ref_id,
        payload_evento=_payload_version_registrada(),
        severidad_evento="INFO",
        timestamp_evento=futuro,
        correlacion_id=correlacion,
        origen_dato="BACKEND",
    )
    db_session.flush()

    # Contrato tipado reforzado
    assert res.aceptado is True, "El evento con timestamp futuro debió ser aceptado tras corrección"
    assert res.codigo is None, f"Un evento aceptado no debe tener codigo de error, obtenido: {res.codigo}"
    assert isinstance(res.id_evento, uuid.UUID), "id_evento debe ser un UUID válido"

    # Verificar TIMESTAMP_CORREGIDO mediante consulta ORM explícita
    corr = (
        db_session.query(EventoAuditoriaM04Model)
        .filter_by(tipo_evento="TIMESTAMP_CORREGIDO", correlacion_id=correlacion)
        .first()
    )
    assert corr is not None, (
        f"El evento TIMESTAMP_CORREGIDO no se persistió para correlacion_id={correlacion}"
    )
    assert corr.severidad_evento == "WARNING", f"Severidad esperada 'WARNING', obtenida {corr.severidad_evento}"
    assert corr.payload_evento.get("motivo") == "FUTURO", (
        f"Motivo esperado 'FUTURO', obtenido {corr.payload_evento.get('motivo')}"
    )
    assert corr.payload_evento.get("tipo_evento_corregido") == "VERSION_REGISTRADA"
    assert corr.payload_evento.get("id_evento_corregido") == str(res.id_evento)
    assert corr.payload_evento.get("timestamp_original") == futuro.isoformat()
    assert "timestamp_original" in corr.payload_evento, "El payload debe incluir timestamp_original"
    assert "timestamp_corregido" in corr.payload_evento, "El payload debe incluir timestamp_corregido"
    assert corr.correlacion_id == correlacion
    assert corr.id_referencia == str(res.id_evento)

    # Verificar que el evento original se persistió con hora del servidor (no la fecha futura del caller)
    orig = (
        db_session.query(EventoAuditoriaM04Model)
        .filter_by(id_evento=res.id_evento)
        .first()
    )
    assert orig is not None, "No se encontró el evento original en la sesión"
    orig_fecha = orig.fecha_evento.replace(tzinfo=timezone.utc) if orig.fecha_evento.tzinfo is None else orig.fecha_evento
    assert abs((orig_fecha - ahora).total_seconds()) < 10, (
        f"El evento original debió persistirse con hora del servidor ({ahora}), pero tiene {orig.fecha_evento}"
    )


def test_tc_m04_305b_timestamp_desordenado(db_session):
    """TC-M04-305b (Caso B): timestamp anterior al último del mismo correlacion_id se corrige y emite TIMESTAMP_CORREGIDO (DESORDENADO)."""
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)
    ahora = datetime.now(timezone.utc)
    correlacion = uuid.uuid4()

    # Evento 1 con T0 (orden cronológico inicial)
    res1 = repo.registrar(
        tipo_evento="VERSION_REGISTRADA",
        tipo_actor="SISTEMA",
        id_sistema="PYTEST_G099",
        id_referencia=str(uuid.uuid4()),
        payload_evento=_payload_version_registrada(),
        severidad_evento="INFO",
        timestamp_evento=ahora,
        correlacion_id=correlacion,
        origen_dato="BACKEND",
    )
    db_session.flush()
    assert res1.aceptado is True
    assert isinstance(res1.id_evento, uuid.UUID)

    # Evento 2 con T0 - 10 min (mismo correlacion_id, cronológicamente desordenado)
    t2 = ahora - timedelta(minutes=10)
    res = repo.registrar(
        tipo_evento="VERSION_REGISTRADA",
        tipo_actor="SISTEMA",
        id_sistema="PYTEST_G099",
        id_referencia=str(uuid.uuid4()),
        payload_evento=_payload_version_registrada(),
        severidad_evento="INFO",
        timestamp_evento=t2,
        correlacion_id=correlacion,
        origen_dato="BACKEND",
    )
    db_session.flush()
    assert res.aceptado is True
    assert res.codigo is None, f"Un evento aceptado no debe tener codigo de error, obtenido: {res.codigo}"
    assert isinstance(res.id_evento, uuid.UUID)

    # Verificar TIMESTAMP_CORREGIDO por desorden mediante consulta ORM explícita
    corr = (
        db_session.query(EventoAuditoriaM04Model)
        .filter_by(tipo_evento="TIMESTAMP_CORREGIDO", correlacion_id=correlacion)
        .first()
    )
    assert corr is not None, (
        f"Se esperaba exactamente 1 evento TIMESTAMP_CORREGIDO por desorden para la correlación {correlacion}"
    )
    assert corr.severidad_evento == "WARNING", f"Severidad esperada 'WARNING', obtenida {corr.severidad_evento}"
    assert corr.payload_evento.get("motivo") == "DESORDENADO", (
        f"Motivo esperado 'DESORDENADO', obtenido {corr.payload_evento.get('motivo')}"
    )
    assert corr.payload_evento.get("tipo_evento_corregido") == "VERSION_REGISTRADA"
    assert corr.payload_evento.get("id_evento_corregido") == str(res.id_evento)
    assert corr.payload_evento.get("timestamp_original") == t2.isoformat()
    assert "timestamp_original" in corr.payload_evento
    assert "timestamp_corregido" in corr.payload_evento
    assert corr.correlacion_id == correlacion
    assert corr.id_referencia == str(res.id_evento)


def test_tc_m04_305c_sin_timestamp_evento(db_session):
    """TC-M04-305c (Caso C): sin timestamp_evento el comportamiento no cambia (hora servidor, sin TIMESTAMP_CORREGIDO)."""
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)
    correlacion = uuid.uuid4()
    ahora = datetime.now(timezone.utc)

    res = repo.registrar(
        tipo_evento="VERSION_REGISTRADA",
        tipo_actor="SISTEMA",
        id_sistema="PYTEST_G099",
        id_referencia=str(uuid.uuid4()),
        payload_evento=_payload_version_registrada(),
        severidad_evento="INFO",
        correlacion_id=correlacion,
        origen_dato="BACKEND",
    )
    db_session.flush()

    assert res.aceptado is True
    assert res.codigo is None, f"Un evento aceptado no debe tener codigo de error, obtenido: {res.codigo}"
    assert isinstance(res.id_evento, uuid.UUID)

    # Sin timestamp_evento NO debe emitirse TIMESTAMP_CORREGIDO
    corregidos = (
        db_session.query(EventoAuditoriaM04Model)
        .filter_by(tipo_evento="TIMESTAMP_CORREGIDO", correlacion_id=correlacion)
        .all()
    )
    assert len(corregidos) == 0, (
        f"Sin timestamp_evento NO debe emitirse TIMESTAMP_CORREGIDO. Encontrados: {len(corregidos)}"
    )

    # Verificar persistencia con hora del servidor
    orig = (
        db_session.query(EventoAuditoriaM04Model)
        .filter_by(id_evento=res.id_evento)
        .first()
    )
    assert orig is not None
    orig_fecha = orig.fecha_evento.replace(tzinfo=timezone.utc) if orig.fecha_evento.tzinfo is None else orig.fecha_evento
    assert abs((orig_fecha - ahora).total_seconds()) < 10, (
        f"El evento original debió persistirse con hora del servidor ({ahora}), pero tiene {orig.fecha_evento}"
    )
