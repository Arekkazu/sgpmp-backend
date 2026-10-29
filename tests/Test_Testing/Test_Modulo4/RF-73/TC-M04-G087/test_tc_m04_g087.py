r"""
TC-M04-G087 — Rechazo por catálogo inválido y exclusividad de fuente.
Subcasos: TC-M04-016 (tipo no catalogado), TC-M04-017 (SISTEMA sin
id_sistema), TC-M04-018 (USUARIO con id_sistema no nulo).

Diseño (D/P):
- Subcaso 1 usa EVENTO_INVENTADO. Backend esperado: rechazo con
  AUDITORIA_EVENTO_INVALIDO (RF-73 Fase 2.1).
- Subcasos 2 y 3 usan VERSION_REGISTRADA con payload válido. Aísla la
  exclusividad como causa de rechazo (RF-73 Fase 2.2 / CA-13).
- Se espera rechazo limpio con AUDITORIA_EVENTO_INVALIDO, no
  InfrastructureError del constraint BD (P2B).

Nota: los 3 subcasos fallarán hoy contra el backend TEST por
INC-M04-152-G086. Es el resultado esperado (RECHAZADO honesto).
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


def _payload_version_registrada() -> dict:
    """Payload válido de VERSION_REGISTRADA según _PAYLOAD_REQUERIDO."""
    return {
        "tipo_modelo": "MODELO_ESPECIES_MEDIANAS",
        "id_version": str(uuid.uuid4()),
    }



def test_tc_m04_016_tipo_evento_fuera_catalogo(db_session):
    """TC-M04-016 — EVENTO_INVENTADO debe rechazarse y generar AUDITORIA_EVENTO_INVALIDO."""
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)
    n_antes_audinv = _count(db_session, "AUDITORIA_EVENTO_INVALIDO")

    res = repo.registrar(
        tipo_evento="EVENTO_INVENTADO",
        tipo_actor="SISTEMA",
        id_sistema="PYTEST_G087",
        id_referencia=str(uuid.uuid4()),
        payload_evento={},
        severidad_evento="ERROR",
    )
    db_session.flush()

    n_despues_audinv = _count(db_session, "AUDITORIA_EVENTO_INVALIDO")

    assert res.aceptado is False, "RF-73 E1: tipo no catalogado debe ser rechazado"
    assert "tipo_evento" in res.campos_invalidos, "RF-73 E1: campos_invalidos debe reportar tipo_evento"
    assert n_despues_audinv == n_antes_audinv + 1, (
        "RF-73 E1: tipo fuera de catálogo debe generar AUDITORIA_EVENTO_INVALIDO. "
        f"Se crearon {n_despues_audinv - n_antes_audinv} fila(s)."
    )


def test_tc_m04_017_sistema_sin_id_sistema(db_session):
    """TC-M04-017 — tipo_actor=SISTEMA con id_sistema=null debe rechazarse."""
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)
    n_antes_ver = _count(db_session, "VERSION_REGISTRADA")
    n_antes_audinv = _count(db_session, "AUDITORIA_EVENTO_INVALIDO")

    res = repo.registrar(
        tipo_evento="VERSION_REGISTRADA",
        tipo_actor="SISTEMA",
        id_sistema=None,       # FALTA para SISTEMA
        id_usuario=None,
        id_referencia=str(uuid.uuid4()),
        payload_evento=_payload_version_registrada(),
        severidad_evento="ERROR",
    )
    db_session.flush()

    n_despues_ver = _count(db_session, "VERSION_REGISTRADA")
    n_despues_audinv = _count(db_session, "AUDITORIA_EVENTO_INVALIDO")

    assert res.aceptado is False, "RF-73 Fase 2.2 / CA-13: SISTEMA requiere id_sistema"
    assert n_despues_ver == n_antes_ver, (
        "RF-73 CA-13: SISTEMA sin id_sistema no debe persistirse. "
        f"Se persistieron {n_despues_ver - n_antes_ver} fila(s)."
    )
    assert n_despues_audinv == n_antes_audinv + 1, (
        "RF-73 E1: exclusividad violada debe generar "
        f"AUDITORIA_EVENTO_INVALIDO. Se crearon "
        f"{n_despues_audinv - n_antes_audinv} fila(s)."
    )


def test_tc_m04_018_usuario_con_id_sistema(db_session):
    """TC-M04-018 — tipo_actor=USUARIO con id_sistema no nulo debe rechazarse."""
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)
    n_antes_ver = _count(db_session, "VERSION_REGISTRADA")
    n_antes_audinv = _count(db_session, "AUDITORIA_EVENTO_INVALIDO")

    res = repo.registrar(
        tipo_evento="VERSION_REGISTRADA",
        tipo_actor="USUARIO",
        id_usuario=5,
        id_sistema="motor_inferencia",  # NO debe estar para USUARIO
        id_referencia=str(uuid.uuid4()),
        payload_evento=_payload_version_registrada(),
        severidad_evento="ERROR",
    )
    db_session.flush()

    n_despues_ver = _count(db_session, "VERSION_REGISTRADA")
    n_despues_audinv = _count(db_session, "AUDITORIA_EVENTO_INVALIDO")

    assert res.aceptado is False, "RF-73 Fase 2.2 / CA-13: USUARIO no puede tener id_sistema"
    assert n_despues_ver == n_antes_ver, (
        "RF-73 CA-13: USUARIO con id_sistema no nulo no debe persistirse. "
        f"Se persistieron {n_despues_ver - n_antes_ver} fila(s)."
    )
    assert n_despues_audinv == n_antes_audinv + 1, (
        "RF-73 E1: exclusividad violada debe generar "
        f"AUDITORIA_EVENTO_INVALIDO. Se crearon "
        f"{n_despues_audinv - n_antes_audinv} fila(s)."
    )
