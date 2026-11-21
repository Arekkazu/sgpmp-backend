r"""
TC-M04-G087 — Rechazo por catálogo inválido y exclusividad de fuente.
Subcasos: TC-M04-016 (tipo no catalogado), TC-M04-017 (SISTEMA sin
id_sistema), TC-M04-018 (USUARIO con id_sistema no nulo).

Diseño y Verificación (RF-73 v2.0 / Fix #726):
- Subcaso 016: usa EVENTO_INVENTADO y payload completo. Valida rechazo con
  código AUDITORIA_EVENTO_INVALIDO y campos_invalidos con 'tipo_evento'.
- Subcaso 017: usa VERSION_REGISTRADA con tipo_actor=SISTEMA e id_sistema=None.
  Valida rechazo con campos_invalidos con 'actor' (RF-73 CA-13).
- Subcaso 018: usa VERSION_REGISTRADA con tipo_actor=USUARIO e id_sistema no nulo.
  Valida rechazo con campos_invalidos con 'actor' (RF-73 CA-13).
- Se verifica la no-persistencia del evento original en la sesión ORM (D1, Opción 3+)
  y la trazabilidad del evento AUDITORIA_EVENTO_INVALIDO emitido (D5).

Ejecutar con runner:
  pwsh tests\Test_Testing\Test_Modulo4\RF-73\TC-M04-G087\ejecutar_tc_m04_g087.ps1 -Suffix "_reintento1"
"""
import uuid
from src.prediction.infrastructure.models.evento_auditoria_m04_model import (
    EventoAuditoriaM04Model,
)
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)


def _payload_version_registrada() -> dict:
    """Payload válido de VERSION_REGISTRADA según _PAYLOAD_REQUERIDO."""
    return {
        "tipo_modelo": "MODELO_ESPECIES_MEDIANAS",
        "id_version": str(uuid.uuid4()),
    }


def test_tc_m04_016_tipo_evento_fuera_catalogo(db_session):
    """TC-M04-016 — EVENTO_INVENTADO debe rechazarse y generar AUDITORIA_EVENTO_INVALIDO."""
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)

    res = repo.registrar(
        tipo_evento="EVENTO_INVENTADO",
        tipo_actor="SISTEMA",
        id_sistema="PYTEST_G087",
        id_referencia=str(uuid.uuid4()),
        payload_evento=_payload_version_registrada(),
        severidad_evento="ERROR",
    )

    # D1 — Verificar que la sesión ORM no contiene el evento original
    candidatos = list(db_session.new) + list(db_session.dirty)
    eventos_originales = [
        obj for obj in candidatos
        if getattr(obj, "tipo_evento", None) == "EVENTO_INVENTADO"
    ]
    assert not eventos_originales, (
        f"RF-73 CA-15: el evento original NO debe estar en sesión: "
        f"{eventos_originales}"
    )

    # D2 — Contrato tipado
    assert res.aceptado is False, "RF-73 E1: tipo no catalogado debe ser rechazado"
    assert res.codigo == "AUDITORIA_EVENTO_INVALIDO"
    assert isinstance(res.id_evento, uuid.UUID)

    # D5 — Trazabilidad del incidente emitido
    eventos_inv = (
        db_session.query(EventoAuditoriaM04Model)
        .filter_by(id_evento=res.id_evento)
        .all()
    )
    assert len(eventos_inv) >= 1, (
        f"El evento AUDITORIA_EVENTO_INVALIDO no se persistió para id_evento={res.id_evento}"
    )
    assert eventos_inv[0].tipo_evento == "AUDITORIA_EVENTO_INVALIDO", (
        f"tipo_evento inesperado: {eventos_inv[0].tipo_evento}"
    )
    assert eventos_inv[0].severidad_evento == "ERROR", (
        f"severidad esperada ERROR, obtenida {eventos_inv[0].severidad_evento}"
    )
    assert eventos_inv[0].resultado_operacion == "FALLIDO", (
        f"resultado_operacion esperado FALLIDO, "
        f"obtenido {eventos_inv[0].resultado_operacion}"
    )
    assert eventos_inv[0].id_evento == res.id_evento, (
        "el id_evento del dataclass debe corresponder al del evento de incidencia emitido"
    )

    # D4 — Validación de campos_invalidos específicos
    assert "tipo_evento" in res.campos_invalidos, "RF-73 E1: campos_invalidos debe reportar tipo_evento"
    assert "payload_evento" not in res.campos_invalidos, (
        "016: el payload NO está vacío; 'payload_evento' no debe reportarse como faltante"
    )


def test_tc_m04_017_sistema_sin_id_sistema(db_session):
    """TC-M04-017 — tipo_actor=SISTEMA con id_sistema=null debe rechazarse."""
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)

    res = repo.registrar(
        tipo_evento="VERSION_REGISTRADA",
        tipo_actor="SISTEMA",
        id_sistema=None,       # FALTA para SISTEMA
        id_usuario=None,
        id_referencia=str(uuid.uuid4()),
        payload_evento=_payload_version_registrada(),
        severidad_evento="ERROR",
    )

    # D1 — Verificar que la sesión ORM no contiene el evento original
    candidatos = list(db_session.new) + list(db_session.dirty)
    eventos_originales = [
        obj for obj in candidatos
        if getattr(obj, "tipo_evento", None) == "VERSION_REGISTRADA"
    ]
    assert not eventos_originales, (
        f"RF-73 CA-13: el evento original NO debe estar en sesión: "
        f"{eventos_originales}"
    )

    # D2 — Contrato tipado
    assert res.aceptado is False, "RF-73 Fase 2.2 / CA-13: SISTEMA requiere id_sistema"
    assert res.codigo == "AUDITORIA_EVENTO_INVALIDO"
    assert isinstance(res.id_evento, uuid.UUID)

    # D5 — Trazabilidad del incidente emitido
    eventos_inv = (
        db_session.query(EventoAuditoriaM04Model)
        .filter_by(id_evento=res.id_evento)
        .all()
    )
    assert len(eventos_inv) >= 1, (
        f"El evento AUDITORIA_EVENTO_INVALIDO no se persistió para id_evento={res.id_evento}"
    )
    assert eventos_inv[0].tipo_evento == "AUDITORIA_EVENTO_INVALIDO", (
        f"tipo_evento inesperado: {eventos_inv[0].tipo_evento}"
    )
    assert eventos_inv[0].severidad_evento == "ERROR", (
        f"severidad esperada ERROR, obtenida {eventos_inv[0].severidad_evento}"
    )
    assert eventos_inv[0].resultado_operacion == "FALLIDO", (
        f"resultado_operacion esperado FALLIDO, "
        f"obtenido {eventos_inv[0].resultado_operacion}"
    )
    assert eventos_inv[0].id_evento == res.id_evento, (
        "el id_evento del dataclass debe corresponder al del evento de incidencia emitido"
    )

    # D3 — Validación de campos_invalidos específicos
    assert "actor" in res.campos_invalidos, (
        f"017: falta 'actor' en campos_invalidos: {res.campos_invalidos}"
    )


def test_tc_m04_018_usuario_con_id_sistema(db_session):
    """TC-M04-018 — tipo_actor=USUARIO con id_sistema no nulo debe rechazarse."""
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)

    res = repo.registrar(
        tipo_evento="VERSION_REGISTRADA",
        tipo_actor="USUARIO",
        id_usuario=5,
        id_sistema="motor_inferencia",  # NO debe estar para USUARIO
        id_referencia=str(uuid.uuid4()),
        payload_evento=_payload_version_registrada(),
        severidad_evento="ERROR",
    )

    # D1 — Verificar que la sesión ORM no contiene el evento original
    candidatos = list(db_session.new) + list(db_session.dirty)
    eventos_originales = [
        obj for obj in candidatos
        if getattr(obj, "tipo_evento", None) == "VERSION_REGISTRADA"
    ]
    assert not eventos_originales, (
        f"RF-73 CA-13: el evento original NO debe estar en sesión: "
        f"{eventos_originales}"
    )

    # D2 — Contrato tipado
    assert res.aceptado is False, "RF-73 Fase 2.2 / CA-13: USUARIO no puede tener id_sistema"
    assert res.codigo == "AUDITORIA_EVENTO_INVALIDO"
    assert isinstance(res.id_evento, uuid.UUID)

    # D5 — Trazabilidad del incidente emitido
    eventos_inv = (
        db_session.query(EventoAuditoriaM04Model)
        .filter_by(id_evento=res.id_evento)
        .all()
    )
    assert len(eventos_inv) >= 1, (
        f"El evento AUDITORIA_EVENTO_INVALIDO no se persistió para id_evento={res.id_evento}"
    )
    assert eventos_inv[0].tipo_evento == "AUDITORIA_EVENTO_INVALIDO", (
        f"tipo_evento inesperado: {eventos_inv[0].tipo_evento}"
    )
    assert eventos_inv[0].severidad_evento == "ERROR", (
        f"severidad esperada ERROR, obtenida {eventos_inv[0].severidad_evento}"
    )
    assert eventos_inv[0].resultado_operacion == "FALLIDO", (
        f"resultado_operacion esperado FALLIDO, "
        f"obtenido {eventos_inv[0].resultado_operacion}"
    )
    assert eventos_inv[0].id_evento == res.id_evento, (
        "el id_evento del dataclass debe corresponder al del evento de incidencia emitido"
    )

    # D3 — Validación de campos_invalidos específicos
    assert "actor" in res.campos_invalidos, (
        f"018: falta 'actor' en campos_invalidos: {res.campos_invalidos}"
    )
