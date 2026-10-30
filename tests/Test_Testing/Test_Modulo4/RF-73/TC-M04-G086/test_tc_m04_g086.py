r"""
TC-M04-G086 — Rechazo de eventos con estructura inválida (RF-73 v2.0)
Subcasos: TC-M04-264, TC-M04-268, TC-M04-269

Verifica el rechazo pre-persistencia (#726, RFC-009, CA-13/CA-15) mediante
el contrato tipado ResultadoRegistroAuditoriaM04, validando códigos de
error, id_evento del incidente registrado, campos inválidos específicos con
asertos de exclusividad (D8), no-persistencia en sesión ORM (D4' Opción 3+)
y trazabilidad del evento AUDITORIA_EVENTO_INVALIDO emitido (D6').

Ejecutar SOLO con:
  .\.venv\Scripts\pytest.exe tests\Test_Testing\Test_Modulo4\RF-73\TC-M04-G086 -v
"""
import uuid
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)


def test_tc_m04_264_payload_sin_campos_minimos(db_session):
    """TC-M04-264 — payload sin campos mínimos → rechazo esperado."""
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)

    resultado = repo.registrar(
        tipo_evento="INFERENCIA_EJECUTADA",
        tipo_actor="SISTEMA",
        id_sistema="PYTEST_G086",
        id_referencia=str(uuid.uuid4()),
        payload_evento={
            "especie": "BOVINO",
            "tipo_modelo": "MODELO_ESPECIES_GRANDES",
            "version_modelo": "1.0.0",
        },
        resultado_operacion="FALLIDO",
        severidad_evento="ERROR",
    )

    # D4' — Verificar que la sesión ORM no contiene el evento original
    candidatos = (
        list(db_session.new)
        + list(db_session.dirty)
        + list(db_session.identity_map.values())
    )
    eventos_originales = [
        obj for obj in candidatos
        if getattr(obj, "tipo_evento", None) == "INFERENCIA_EJECUTADA"
    ]
    assert not eventos_originales, (
        f"RF-73 CA-15: el evento INFERENCIA_EJECUTADA NO debe estar "
        f"en la sesión tras rechazo. Encontrados: {eventos_originales}"
    )

    # D6' (1) — Contrato tipado reforzado
    assert resultado.aceptado is False, (
        "RF-73 CA-15: evento INFERENCIA_EJECUTADA con payload sin "
        "campos mínimos debe ser rechazado (aceptado=False)."
    )
    assert resultado.codigo == "AUDITORIA_EVENTO_INVALIDO", (
        f"RF-73 Flujo E1: código esperado 'AUDITORIA_EVENTO_INVALIDO', "
        f"obtenido: {resultado.codigo}."
    )
    assert isinstance(resultado.id_evento, uuid.UUID), (
        "id_evento del rechazo debe ser un UUID válido"
    )

    # D6' (2) — Verificar que el AUDITORIA_EVENTO_INVALIDO existe en sesión
    eventos_inv = [
        obj for obj in candidatos
        if getattr(obj, "tipo_evento", None) == "AUDITORIA_EVENTO_INVALIDO"
    ]
    assert len(eventos_inv) >= 1, (
        "RF-73 Flujo E1: debe emitirse al menos un AUDITORIA_EVENTO_INVALIDO"
    )
    ultimo_inv = eventos_inv[-1]
    assert ultimo_inv.severidad_evento == "ERROR", (
        f"severidad esperada ERROR, obtenida {ultimo_inv.severidad_evento}"
    )
    assert ultimo_inv.resultado_operacion == "FALLIDO", (
        f"resultado_operacion esperado FALLIDO, "
        f"obtenido {ultimo_inv.resultado_operacion}"
    )
    assert ultimo_inv.id_evento == resultado.id_evento, (
        "el id_evento del dataclass debe corresponder al del evento emitido"
    )

    # D8 — Campos inválidos específicos y exclusividad
    assert len(resultado.campos_invalidos) > 0, (
        "RF-73 CA-15: la tupla de campos_invalidos no debe estar vacía."
    )
    assert "payload_evento.activo_biologico_id" in resultado.campos_invalidos, (
        f"RF-73 CA-15: falta 'payload_evento.activo_biologico_id' en {resultado.campos_invalidos}."
    )
    assert "payload_evento.nivel_riesgo" in resultado.campos_invalidos, (
        f"RF-73 CA-15: falta 'payload_evento.nivel_riesgo' en {resultado.campos_invalidos}."
    )
    assert "payload_evento" not in resultado.campos_invalidos, (
        "payload NO está vacío, no debe reportarse 'payload_evento' como faltante"
    )


def test_tc_m04_268_id_referencia_null(db_session):
    """TC-M04-268 — id_referencia=null → rechazo esperado (D3: FALLIDO)."""
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)

    resultado = repo.registrar(
        tipo_evento="INFERENCIA_EJECUTADA",
        tipo_actor="SISTEMA",
        id_sistema="PYTEST_G086",
        id_referencia=None,
        payload_evento={
            "activo_biologico_id": 999,
            "especie": "BOVINO",
            "tipo_modelo": "MODELO_ESPECIES_GRANDES",
            "version_modelo": "1.0.0",
            "nivel_riesgo": 2,
            "probabilidad_riesgo_alto": 0.15,
            "enfermedad_estimada": "MASTITIS",
            "latencia_ms": 120,
            "contexto_incompleto": False,
        },
        resultado_operacion="FALLIDO",
        severidad_evento="ERROR",
    )

    # D4' — Verificar que la sesión ORM no contiene el evento original
    candidatos = (
        list(db_session.new)
        + list(db_session.dirty)
        + list(db_session.identity_map.values())
    )
    eventos_originales = [
        obj for obj in candidatos
        if getattr(obj, "tipo_evento", None) == "INFERENCIA_EJECUTADA"
    ]
    assert not eventos_originales, (
        f"RF-73 CA-15: el evento INFERENCIA_EJECUTADA NO debe estar "
        f"en la sesión tras rechazo. Encontrados: {eventos_originales}"
    )

    # D6' (1) — Contrato tipado reforzado
    assert resultado.aceptado is False, (
        "RF-73 Flujo E1: evento con id_referencia=NULL debe ser rechazado (aceptado=False)."
    )
    assert resultado.codigo == "AUDITORIA_EVENTO_INVALIDO", (
        f"RF-73 Flujo E1: código esperado 'AUDITORIA_EVENTO_INVALIDO', "
        f"obtenido: {resultado.codigo}."
    )
    assert isinstance(resultado.id_evento, uuid.UUID), (
        "id_evento del rechazo debe ser un UUID válido"
    )

    # D6' (2) — Verificar que el AUDITORIA_EVENTO_INVALIDO existe en sesión
    eventos_inv = [
        obj for obj in candidatos
        if getattr(obj, "tipo_evento", None) == "AUDITORIA_EVENTO_INVALIDO"
    ]
    assert len(eventos_inv) >= 1, (
        "RF-73 Flujo E1: debe emitirse al menos un AUDITORIA_EVENTO_INVALIDO"
    )
    ultimo_inv = eventos_inv[-1]
    assert ultimo_inv.severidad_evento == "ERROR", (
        f"severidad esperada ERROR, obtenida {ultimo_inv.severidad_evento}"
    )
    assert ultimo_inv.resultado_operacion == "FALLIDO", (
        f"resultado_operacion esperado FALLIDO, "
        f"obtenido {ultimo_inv.resultado_operacion}"
    )
    assert ultimo_inv.id_evento == resultado.id_evento, (
        "el id_evento del dataclass debe corresponder al del evento emitido"
    )

    # D8 — Campos inválidos específicos y exclusividad
    assert len(resultado.campos_invalidos) > 0, (
        "RF-73 Flujo E1: la tupla de campos_invalidos no debe estar vacía."
    )
    assert "id_referencia" in resultado.campos_invalidos, (
        f"RF-73 Flujo E1: falta 'id_referencia' en {resultado.campos_invalidos}."
    )
    assert "payload_evento.activo_biologico_id" not in resultado.campos_invalidos, (
        "el payload sí tiene los campos mínimos; solo falta id_referencia"
    )


def test_tc_m04_269_payload_evento_vacio(db_session):
    """TC-M04-269 — payload_evento={} → rechazo esperado."""
    repo = SqlAlchemyEventoAuditoriaM04Repository(db_session)

    resultado = repo.registrar(
        tipo_evento="INFERENCIA_EJECUTADA",
        tipo_actor="SISTEMA",
        id_sistema="PYTEST_G086",
        id_referencia=str(uuid.uuid4()),
        payload_evento={},
        resultado_operacion="FALLIDO",
        severidad_evento="ERROR",
    )

    # D4' — Verificar que la sesión ORM no contiene el evento original
    candidatos = (
        list(db_session.new)
        + list(db_session.dirty)
        + list(db_session.identity_map.values())
    )
    eventos_originales = [
        obj for obj in candidatos
        if getattr(obj, "tipo_evento", None) == "INFERENCIA_EJECUTADA"
    ]
    assert not eventos_originales, (
        f"RF-73 CA-15: el evento INFERENCIA_EJECUTADA NO debe estar "
        f"en la sesión tras rechazo. Encontrados: {eventos_originales}"
    )

    # D6' (1) — Contrato tipado reforzado
    assert resultado.aceptado is False, (
        "RF-73 CA-15: payload_evento vacío debe ser rechazado (aceptado=False)."
    )
    assert resultado.codigo == "AUDITORIA_EVENTO_INVALIDO", (
        f"RF-73 Flujo E1: código esperado 'AUDITORIA_EVENTO_INVALIDO', "
        f"obtenido: {resultado.codigo}."
    )
    assert isinstance(resultado.id_evento, uuid.UUID), (
        "id_evento del rechazo debe ser un UUID válido"
    )

    # D6' (2) — Verificar que el AUDITORIA_EVENTO_INVALIDO existe en sesión
    eventos_inv = [
        obj for obj in candidatos
        if getattr(obj, "tipo_evento", None) == "AUDITORIA_EVENTO_INVALIDO"
    ]
    assert len(eventos_inv) >= 1, (
        "RF-73 Flujo E1: debe emitirse al menos un AUDITORIA_EVENTO_INVALIDO"
    )
    ultimo_inv = eventos_inv[-1]
    assert ultimo_inv.severidad_evento == "ERROR", (
        f"severidad esperada ERROR, obtenida {ultimo_inv.severidad_evento}"
    )
    assert ultimo_inv.resultado_operacion == "FALLIDO", (
        f"resultado_operacion esperado FALLIDO, "
        f"obtenido {ultimo_inv.resultado_operacion}"
    )
    assert ultimo_inv.id_evento == resultado.id_evento, (
        "el id_evento del dataclass debe corresponder al del evento emitido"
    )

    # D8 — Campos inválidos específicos
    assert len(resultado.campos_invalidos) > 0, (
        "RF-73 CA-15: la tupla de campos_invalidos no debe estar vacía."
    )
    assert "payload_evento" in resultado.campos_invalidos, (
        f"RF-73 CA-15: falta 'payload_evento' en {resultado.campos_invalidos}."
    )
