# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-16 | Arekkazu | QA-M06 v6 RF-84/87/88: período cerrado en el modelo de costo y cálculo validado manualmente |
"""Hallazgos del reporte de QA M06 del 16-11 (re-evaluación v6) que corrige este lote."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import text

from src.financial_valuation.domain.entities.contabilidad import Periodo
from src.shared.errors import AppError
from tests.integration.test_inc_m06_365_g93_auditoria_alcance import _reconocido
from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401 (fixtures)
    HOY,
    _activo,
    _configurar,
    _evento_sanitario,
    _finca,
    _pesaje,
    _precio,
    contador,
    m06,
)

_JUSTIFICACION = "Control preventivo con hallazgo de pérdida total de la capacidad productiva"


def _activo_al_costo(db_session, m06, uid) -> int:
    _configurar(m06, uid, 3, vida=96)  # especie sin precios: modelo de costo
    activo = _activo(db_session, _finca(db_session, uid), uid, especie=3, origen="compra", costo=D("2000000"))
    _pesaje(db_session, activo, "300")
    m06.confirmar_reconocimiento().execute(activo, uid)
    return activo


def _cerrar_periodo_de_hoy(db_session) -> None:
    """Cierre anticipado, como el de noviembre de QA SG (15/11): el período de hoy queda cerrado antes de su fin."""
    db_session.execute(text("""UPDATE modulo6.periodos_contables SET estado = 'CERRADO', fecha_cierre = now()
                               WHERE numero_id_tributaria = '900123456' AND :h BETWEEN fecha_inicio AND fecha_fin"""),
                       {"h": HOY})


def _lineas(db_session, activo: int, tipo: str) -> int:
    return db_session.execute(text("""SELECT count(*) FROM modulo6.lineas_asiento_nic41
                                      WHERE id_activo_biologico = :a AND tipo_hecho = CAST(:t AS
                                            modulo6.enum_linea_asiento_nic41_tipo_hecho)"""),
                              {"a": activo, "t": tipo}).scalar_one()


@pytest.mark.integration
def test_deterioro_con_el_periodo_de_hoy_cerrado_se_rechaza(db_session, m06, contador):
    """CU07 H-02: con el período de hoy cerrado el deterioro pasaba al período abierto siguiente. Ahora se rechaza,
    y antes que la regla del valor en cero: QA re-prueba con EQU-01, que ya vale $ 0."""
    uid = contador["id_usuario"]
    activo = _activo_al_costo(db_session, m06, uid)
    evento = _evento_sanitario(db_session, activo)
    m06.registrar_deterioro().execute(activo, evento, D("2500000"), _JUSTIFICACION, uid)  # valor en libros → 0
    _cerrar_periodo_de_hoy(db_session)

    with pytest.raises(AppError) as cerrado:
        m06.registrar_deterioro().execute(activo, evento, D("100000"), _JUSTIFICACION, uid)

    assert (cerrado.value.status_code, cerrado.value.code) == (422, "PERIODO_CONTABLE_CERRADO")
    assert "está cerrado" in cerrado.value.message and "None" not in cerrado.value.message
    assert _lineas(db_session, activo, "DETERIORO_ACTIVO_COSTO") == 1  # solo el primero


@pytest.mark.integration
def test_paso_a_valor_razonable_con_el_periodo_de_hoy_cerrado_se_rechaza(db_session, m06, contador):
    """CU07 H-02 (misma pantalla): el paso a valor razonable también es un hecho de hoy."""
    uid = contador["id_usuario"]
    activo = _activo_al_costo(db_session, m06, uid)
    _precio(m06, uid, 3, "8000", HOY - timedelta(days=1))
    _cerrar_periodo_de_hoy(db_session)

    with pytest.raises(AppError) as cerrado:
        m06.cambiar_a_valor_razonable().execute(activo, uid)

    assert cerrado.value.code == "PERIODO_CONTABLE_CERRADO"
    assert m06.valoraciones.valoracion_costo_activa(activo) is not None  # sigue al costo


@pytest.mark.integration
def test_calculo_validado_se_lista_como_validado_manualmente(db_session, m06, contador):
    """CU03 H-01: el cálculo con neto ≤ 0 que el Contador valida queda marcado, no como un «Calculado» más."""
    uid = contador["id_usuario"]
    _configurar(m06, uid, 2)
    _precio(m06, uid, 2, "8000", HOY - timedelta(days=5))
    activo, periodo = _reconocido(db_session, m06, uid, "900123456", "8")
    id_calculo = db_session.execute(text("""UPDATE modulo6.calculos_valor_razonable SET estado = 'REVISION_REQUERIDA'
                                            WHERE id_activo_biologico = :a RETURNING id_calculo_valor_razonable"""),
                                    {"a": activo}).scalar_one()

    m06.validar_calculo().execute(id_calculo, "Costos de transporte extraordinarios documentados", uid)

    [fila] = [c for c in m06.valoraciones.calculos_del_periodo(periodo) if c["id_calculo_valor_razonable"] == id_calculo]
    assert fila["estado"] == "VALIDADO_MANUALMENTE"
    assert fila["justificacion_validacion"] == "Costos de transporte extraordinarios documentados"
    guardado = db_session.execute(text("SELECT estado::text FROM modulo6.calculos_valor_razonable "
                                       "WHERE id_calculo_valor_razonable = :c"), {"c": id_calculo}).scalar_one()
    assert guardado == "CALCULADO"  # la base de las mediciones no cambia


def test_nombre_del_periodo():
    mensual = Periodo(1, "901555123", "MENSUAL", date(2026, 11, 1), date(2026, 11, 30), "CERRADO")
    trimestral = Periodo(2, "901555123", "TRIMESTRAL", date(2026, 10, 1), date(2026, 12, 31), "ABIERTO")
    assert mensual.nombre == "Noviembre de 2026"
    assert trimestral.nombre == "01/10/2026 – 31/12/2026"
