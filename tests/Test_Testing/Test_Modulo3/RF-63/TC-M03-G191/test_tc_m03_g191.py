"""TC-M03-G191 — Tests de CA-13 (tolerancia a eventos incompletos).

Origen: migracion de Newman a Pytest por Restriccion 4.4 de RF-63
(bus interno no expuesto via HTTP).
"""

import pytest

try:
    from .helpers_tc_m03_g191 import (
        construir_use_case,
        payload_base_completo,
        buscar_evento_por_descripcion,
    )
    from .spec_tc_m03_g191 import CASOS
except (ImportError, ValueError):
    from helpers_tc_m03_g191 import (
        construir_use_case,
        payload_base_completo,
        buscar_evento_por_descripcion,
    )
    from spec_tc_m03_g191 import CASOS


# ═══════════════════════════════════════════════════════════════
# 367a — Evento SIN tipo_evento -> debe registrarse incompleto (CA-13)
# ═══════════════════════════════════════════════════════════════
def test_367a_sin_tipo_evento_se_registra_incompleto(db_session):
    """CA-13: evento sin tipo_evento debe persistirse, no rechazarse."""
    use_case = construir_use_case(db_session)
    payload = payload_base_completo()
    payload["tipo_evento"] = None  # <- campo faltante
    payload["descripcion"] = "TEST_367a_sin_tipo_evento"

    try:
        use_case.execute(**payload)
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        pytest.fail(
            f"CA-13 INCUMPLIDO: use case rechazo evento sin tipo_evento. "
            f"Excepcion: {type(e).__name__}: {e}. "
            f"Se esperaba persistencia con registro_incompleto=true."
        )

    registro = buscar_evento_por_descripcion(db_session, "TEST_367a_sin_tipo_evento")
    assert registro is not None, (
        "CA-13 INCUMPLIDO: evento sin tipo_evento NO fue persistido. "
        "El use case hizo rollback interno en lugar de registrar con "
        "registro_incompleto=true. GAP: tipo_evento NOT NULL en BD."
    )
    assert registro.registro_incompleto is True, (
        f"registro_incompleto esperado=True, obtenido={registro.registro_incompleto}"
    )


# ═══════════════════════════════════════════════════════════════
# 367b — Evento SIN componente_origen -> debe registrarse incompleto
# ═══════════════════════════════════════════════════════════════
def test_367b_sin_componente_origen_se_registra_incompleto(db_session):
    """CA-13: evento sin componente_origen debe persistirse."""
    use_case = construir_use_case(db_session)
    payload = payload_base_completo()
    payload["componente_origen"] = None
    payload["registro_incompleto"] = True  # debe venir del llamador
    payload["accion_detallada"] = {"campo_faltante": "componente_origen"}
    payload["descripcion"] = "TEST_367b_sin_componente_origen"

    try:
        use_case.execute(**payload)
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        pytest.fail(
            f"CA-13 INCUMPLIDO: use case rechazo evento sin componente_origen. "
            f"Excepcion: {type(e).__name__}: {e}. "
            f"Se esperaba persistencia con registro_incompleto=true."
        )

    registro = buscar_evento_por_descripcion(db_session, "TEST_367b_sin_componente_origen")
    assert registro is not None, "Evento sin componente_origen NO persistido"
    assert registro.registro_incompleto is True
    assert registro.componente_origen is None


# ═══════════════════════════════════════════════════════════════
# 367c — Evento SIN timestamp_evento -> NO parametrizable
# ═══════════════════════════════════════════════════════════════
def test_367c_sin_timestamp_se_registra_incompleto(db_session):
    """CA-13: evento sin timestamp_evento debe persistirse.
    GAP conocido: use_case autogenera fecha_hora con now(). No es
    parametrizable. El test no es ejecutable sin ese parametro.
    """
    pytest.skip(
        "GAP 2: use_case.execute() no expone parametro fecha_hora; "
        "siempre asigna datetime.now(). No es posible simular 'evento sin "
        "timestamp_evento' desde el llamador. Requiere cambio en el use case."
    )


# ═══════════════════════════════════════════════════════════════
# 367d — Evento COMPLETO -> registro_incompleto=false
# ═══════════════════════════════════════════════════════════════
def test_367d_evento_completo_registra_incompleto_false(db_session):
    """CA-13 control positivo: evento completo debe tener registro_incompleto=false."""
    use_case = construir_use_case(db_session)
    payload = payload_base_completo()
    payload["descripcion"] = "TEST_367d_evento_completo"

    try:
        use_case.execute(**payload)
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        pytest.fail(f"Evento completo fallo al persistir: {type(e).__name__}: {e}")

    registro = buscar_evento_por_descripcion(db_session, "TEST_367d_evento_completo")
    assert registro is not None, "Evento completo NO persistido"
    assert registro.registro_incompleto is False


# ═══════════════════════════════════════════════════════════════
# 367e — POST manual por usuario debe rechazarse
# ═══════════════════════════════════════════════════════════════
def test_367e_post_manual_rechazado(sandbox_client):
    """Restriccion 4.4: ningun usuario puede insertar eventos manualmente."""
    resp = sandbox_client.post(
        "/iot/auditoria",
        json={"tipo_evento": "TEST", "descripcion": "intento manual"},
    )
    assert resp.status_code in (403, 404, 405), (
        f"POST manual a /iot/auditoria retorno {resp.status_code}, "
        f"se esperaba 403/404/405. Si retorna 201, la Restriccion 4.4 "
        f"esta VIOLADA (usuario puede inyectar eventos)."
    )
