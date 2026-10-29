r"""
TC-M04-G086 — Rechazo de eventos con estructura inválida (RF-73 v2.0)
Subcasos: TC-M04-264, TC-M04-268, TC-M04-269

Diseño fiel al caso (D1): se usa INFERENCIA_EJECUTADA, aunque el
diagnóstico del 2026-10-25 confirma que ese tipo_evento no tiene
esquema en _PAYLOAD_REQUERIDO en el backend. Esto hace que los 3
subcasos FALLEN honestamente (RECHAZADO).

Ejecutar SOLO con:
  .\.venv\Scripts\pytest.exe tests\Test_Testing\Test_Modulo4\RF-73\TC-M04-G086 -v
"""
import uuid
from sqlalchemy import text
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)


def _count(db, tipo_evento: str) -> int:
    return db.execute(
        text("SELECT COUNT(*) FROM modulo4.eventos_auditoria_m04 "
             "WHERE tipo_evento = :t"),
        {"t": tipo_evento},
    ).scalar() or 0


def test_tc_m04_264_payload_sin_campos_minimos(db_session):
    """TC-M04-264 — payload sin campos mínimos → rechazo esperado."""
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)

    n_antes = _count(db_session, "INFERENCIA_EJECUTADA")
    n_inv_antes = _count(db_session, "AUDITORIA_EVENTO_INVALIDO")

    repo.registrar(
        tipo_evento="INFERENCIA_EJECUTADA",
        tipo_actor="SISTEMA",
        id_sistema="PYTEST_G086",
        id_referencia=str(uuid.uuid4()),
        payload_evento={},
        resultado_operacion="FALLIDO",
        severidad_evento="ERROR",
    )
    db_session.flush()

    n_despues = _count(db_session, "INFERENCIA_EJECUTADA")
    n_inv_despues = _count(db_session, "AUDITORIA_EVENTO_INVALIDO")

    assert n_despues == n_antes, (
        f"RF-73 CA-15: evento INFERENCIA_EJECUTADA con payload sin "
        f"campos mínimos debe ser rechazado. Se persistieron "
        f"{n_despues - n_antes} fila(s) con tipo_evento="
        f"'INFERENCIA_EJECUTADA'."
    )
    assert n_inv_despues == n_inv_antes + 1, (
        f"RF-73 Flujo E1: debe crearse 1 fila AUDITORIA_EVENTO_INVALIDO. "
        f"Se crearon: {n_inv_despues - n_inv_antes}."
    )


def test_tc_m04_268_id_referencia_null(db_session):
    """TC-M04-268 — id_referencia=null → rechazo esperado (D3: FALLIDO)."""
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)

    n_antes = _count(db_session, "INFERENCIA_EJECUTADA")
    n_inv_antes = _count(db_session, "AUDITORIA_EVENTO_INVALIDO")

    repo.registrar(
        tipo_evento="INFERENCIA_EJECUTADA",
        tipo_actor="SISTEMA",
        id_sistema="PYTEST_G086",
        id_referencia=None,
        payload_evento={"activo_biologico_id": 999, "nivel_riesgo": 2},
        resultado_operacion="FALLIDO",
        severidad_evento="ERROR",
    )
    db_session.flush()

    n_despues = _count(db_session, "INFERENCIA_EJECUTADA")
    n_inv_despues = _count(db_session, "AUDITORIA_EVENTO_INVALIDO")

    assert n_despues == n_antes, (
        f"RF-73 Flujo E1: evento con id_referencia=NULL debe ser "
        f"rechazado. Se persistieron {n_despues - n_antes} fila(s)."
    )
    assert n_inv_despues == n_inv_antes + 1, (
        f"RF-73 Flujo E1: debe crearse 1 fila AUDITORIA_EVENTO_INVALIDO. "
        f"Se crearon: {n_inv_despues - n_inv_antes}."
    )


def test_tc_m04_269_payload_evento_vacio(db_session):
    """TC-M04-269 — payload_evento={} → rechazo esperado."""
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)

    n_antes = _count(db_session, "INFERENCIA_EJECUTADA")
    n_inv_antes = _count(db_session, "AUDITORIA_EVENTO_INVALIDO")

    repo.registrar(
        tipo_evento="INFERENCIA_EJECUTADA",
        tipo_actor="SISTEMA",
        id_sistema="PYTEST_G086",
        id_referencia=str(uuid.uuid4()),
        payload_evento={},
        resultado_operacion="FALLIDO",
        severidad_evento="ERROR",
    )
    db_session.flush()

    n_despues = _count(db_session, "INFERENCIA_EJECUTADA")
    n_inv_despues = _count(db_session, "AUDITORIA_EVENTO_INVALIDO")

    assert n_despues == n_antes, (
        f"RF-73 CA-15: payload_evento vacío debe ser rechazado. "
        f"Se persistieron {n_despues - n_antes} fila(s)."
    )
    assert n_inv_despues == n_inv_antes + 1, (
        f"RF-73 Flujo E1: debe crearse 1 fila AUDITORIA_EVENTO_INVALIDO. "
        f"Se crearon: {n_inv_despues - n_inv_antes}."
    )
