# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-15 | Arekkazu | QA-M06 v5 RF-85/87/88/90/COT: hallazgos de prioridad media y baja |
"""Hallazgos de prioridad media y baja del reporte de QA M06 (re-prueba de la v5, 15-11)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.financial_valuation.application.use_cases.costos.registrar_costo_use_case import SolicitudCosto
from src.financial_valuation.application.use_cases.valoracion.procesar_eventos_m02_use_case import dia_del_evento
from src.financial_valuation.infrastructure.adapters.notificacion_financiera_m01_adapter import (
    NotificacionFinancieraM01Adapter,
)
from src.shared.errors import AppError
from tests.integration.test_inc_m06_365_g93_auditoria_alcance import _reconocido
from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401 (fixtures)
    HOY,
    _activo,
    _configurar,
    _evento_sanitario,
    _finca,
    _matriz,
    _pesaje,
    _precio,
    contador,
    m06,
)


def test_dia_del_evento_productivo_no_se_corre_por_la_zona(en_colombia):
    """CU04 H-01: M02 guarda la leche «del 15/11» como medianoche UTC; en Colombia eso era el 14/11 a las 19:00."""
    assert str(dia_del_evento(datetime(2026, 11, 15, tzinfo=timezone.utc))) == "2026-11-15"
    assert str(dia_del_evento(datetime(2026, 11, 15, 3, 0, tzinfo=timezone.utc))) == "2026-11-14"  # un instante sí


@pytest.mark.integration
def test_factura_con_fecha_fuera_del_periodo_abierto_se_rechaza(db_session, m06, contador):
    """CU09 H-02: RF-90 v2.0 exige factura_fecha dentro del período abierto."""
    uid = contador["id_usuario"]
    _configurar(m06, uid, 2)
    _precio(m06, uid, 2, "8000", HOY - timedelta(days=5))
    activo, _ = _reconocido(db_session, m06, uid, "860069804", "2")
    with pytest.raises(AppError) as fuera:
        m06.registrar_costo().execute(SolicitudCosto(
            subtipo_costo="VETERINARIO", origen_costo="SERVICIO_TERCERO", monto_costo=D("40000"), fecha_costo=HOY,
            id_activo_biologico=activo, tercero_nit="900123456", tercero_dv="7", tercero_razon_social="QA Veterinaria",
            factura_numero="QASG0057", fecha_factura=HOY - timedelta(days=40), fecha_vencimiento_factura=HOY), uid)
    assert (fuera.value.status_code, fuera.value.code, fuera.value.field) == (422, "FECHA_FACTURA_FUERA_PERIODO",
                                                                             "fecha_factura")
    assert "período abierto" in fuera.value.message and "None" not in fuera.value.message


@pytest.mark.integration
def test_deterioro_mayor_que_el_valor_registra_lo_aplicado(db_session, m06, contador):
    """CU07 H-01: costo 2.000.000 y deterioro pedido 2.500.000 → deterioro y asiento por 2.000.000, valor 0."""
    uid = contador["id_usuario"]
    _configurar(m06, uid, 3, vida=96)  # especie sin precios: modelo de costo
    activo = _activo(db_session, _finca(db_session, uid), uid, especie=3, origen="compra", costo=D("2000000"))
    _pesaje(db_session, activo, "300")
    m06.confirmar_reconocimiento().execute(activo, uid)
    justificacion = "Control preventivo con hallazgo de pérdida total de la capacidad productiva"

    resultado = m06.registrar_deterioro().execute(activo, _evento_sanitario(db_session, activo), D("2500000"),
                                                  justificacion, uid)

    costo = m06.valoraciones.valoracion_costo_activa(activo)
    assert resultado["valor_contable"] == 0 and costo.deterioro_acumulado == D("2000000")
    registrado = db_session.execute(text("""SELECT impacto_economico_cop FROM modulo6.deterioros_activos
                                            WHERE id_deterioro_activo = :d"""), {"d": resultado["id_deterioro_activo"]})
    assert registrado.scalar_one() == D("2000000")
    [linea] = [ln for ln in m06.asientos.del_activo(activo) if ln.tipo_hecho == "DETERIORO_ACTIVO_COSTO"]
    assert linea.valor == D("2000000.00")
    monto = db_session.execute(text("""SELECT monto_afectado FROM modulo6.auditorias_financieras
                                       WHERE tipo_evento = 'DETERIORO_REGISTRADO' AND id_referencia = :d"""),
                               {"d": resultado["id_deterioro_activo"]}).scalar_one()
    assert monto == D("2000000")

    with pytest.raises(AppError) as sin_valor:  # ya en cero: nada más que deteriorar
        m06.registrar_deterioro().execute(activo, _evento_sanitario(db_session, activo), D("1000"), justificacion, uid)
    assert (sin_valor.value.status_code, sin_valor.value.code) == (422, "DETERIORO_SIN_VALOR_EN_LIBROS")


@pytest.mark.integration
def test_eventos_de_cotizacion_quedan_asociados_al_activo_y_su_monto(db_session, m06, contador):
    """CU-COT H-02: registro, modificación y anulación llevan el activo cotizado y el valor propuesto."""
    uid = contador["id_usuario"]
    _configurar(m06, uid, 2)
    _matriz(m06, uid)
    _precio(m06, uid, 2, "9500", HOY - timedelta(days=10))
    activo, _ = _reconocido(db_session, m06, uid, "900123456", "8")
    cotizar = m06.registrar_cotizacion()
    modificada = cotizar.execute([activo], D("3800000"), None, None, uid)["id_cotizacion"]
    anulada = cotizar.execute([activo], D("400000"), None, None, uid)["id_cotizacion"]
    version = lambda c: m06.cotizaciones.obtener(c)["version"]  # noqa: E731
    m06.modificar_cotizacion().modificar(modificada, version(modificada), {"valor_cotizacion_propuesto": D("3900000")},
                                         "Ajuste acordado con el comprador", uid)
    m06.modificar_cotizacion().anular(anulada, version(anulada), "QA SG CP67 anulacion de prueba sin acuerdo", uid)

    eventos = db_session.execute(text("""
        SELECT tipo_evento::text AS tipo, id_activo_biologico, monto_afectado FROM modulo6.auditorias_financieras
        WHERE tipo_evento::text LIKE 'COTIZACION_%' AND id_referencia IN (:m, :a) ORDER BY id_auditoria_financiera
    """), {"m": modificada, "a": anulada}).mappings().all()
    assert [(e["tipo"], e["id_activo_biologico"], e["monto_afectado"]) for e in eventos] == [
        ("COTIZACION_REGISTRADA", activo, D("3800000")), ("COTIZACION_REGISTRADA", activo, D("400000")),
        ("COTIZACION_MODIFICADA", activo, D("3900000")), ("COTIZACION_ANULADA", activo, D("400000"))]


@pytest.mark.integration
def test_cada_contador_recibe_el_aviso_con_su_propio_evento(db_session, crear_usuario_db):
    """CU06 H-02: la bandeja une la notificación con su evento y la RLS solo deja ver el propio. Con un evento
    compartido, el aviso del cierre solo le llegaba al primer Contador."""
    contadores = [crear_usuario_db(id_rol=5, estado=2)["id_usuario"] for _ in range(2)]
    marca = {"id_periodo_contable": 987654321, "motivo": "QA_CU06_H02"}
    NotificacionFinancieraM01Adapter(
        lambda: Session(bind=db_session.connection(), join_transaction_mode="create_savepoint"),
    ).a_contadores("ALERTA_FINANCIERA_NIC41", "Período 2026-11 cerrado.", marca)

    filas = db_session.execute(text("""
        SELECT n.id_usuario, e.id_usuario AS dueno_evento FROM modulo1.notificaciones n
        JOIN modulo1.eventos e ON e.id_evento = n.id_evento
        WHERE n.id_usuario = ANY(:u) AND e.detalle @> CAST(:d AS jsonb)
    """), {"u": contadores, "d": '{"motivo": "QA_CU06_H02"}'}).mappings().all()
    assert sorted(f["id_usuario"] for f in filas) == sorted(contadores)
    assert all(f["id_usuario"] == f["dueno_evento"] for f in filas)
