# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-13 | Arekkazu | TC-M06-G74 RF-93 FA-2: conciliación del estado de resultados con sus fuentes (hechos sin asiento) |
"""TC-M06-G74 / RF-93 paso 5 y FA-2 contra Postgres real.

El estado de resultados se arma con las líneas de asiento del período. Si una variación de valor razonable
(RF-86) o un producto agrícola (RF-85) del período no tiene su línea, el estado no cuadra con sus fuentes:
el cierre termina con el estado pendiente, la generación a pedido responde 422 y en ambos casos queda
ERROR_CONCILIACION en la auditoría y se avisa al Contador. Corregido el hecho, el estado se genera."""
from __future__ import annotations

from decimal import Decimal as D

import pytest
from sqlalchemy import text

from src.financial_valuation.application.services.reportes import ConciliacionError
from tests.integration.test_inc_m06_lote_2026_11_10 import _reconocido
from tests.integration.test_m06_flujo_nic41_integration import _escalar, contador, m06  # noqa: F401 (fixtures)

pytestmark = pytest.mark.integration


def _variacion_sin_asiento(db, activo: int, periodo: int, usuario: int) -> int:
    db.execute(text("SET LOCAL session_replication_role = replica"))
    id_variacion = _escalar(db, """
        INSERT INTO modulo6.variaciones_valor_razonable (id_activo_biologico, tipo, monto_variacion, variacion_transformacion,
               variacion_precio_mercado, valor_razonable_anterior, valor_razonable_nuevo, id_periodo_contable, id_usuario,
               id_precio_mercado)
        VALUES (:a, 'GANANCIA_TRANSFORMACION_BIOLOGICA', 50000, 50000, 0, 3040000, 3090000, :p, :u,
                (SELECT max(id_precio_mercado) FROM modulo6.precios_mercado))
        RETURNING id_variacion_valor_razonable""", a=activo, p=periodo, u=usuario)
    db.execute(text("SET LOCAL session_replication_role = origin"))
    return id_variacion


def _errores_conciliacion(db, periodo: int) -> int:
    return _escalar(db, """SELECT count(*) FROM modulo6.auditorias_financieras
                           WHERE tipo_evento = 'ERROR_CONCILIACION' AND id_periodo_contable = :p AND severidad = 'CRITICAL'""",
                    p=periodo)


def test_hecho_sin_asiento_deja_el_estado_pendiente_y_se_genera_al_corregirlo(db_session, m06, contador):
    uid = contador["id_usuario"]
    _, activo, periodo = _reconocido(db_session, m06, uid)
    p = periodo.id_periodo_contable
    huerfana = _variacion_sin_asiento(db_session, activo, p, uid)

    cierre = m06.cierre().execute(p, uid, autorizar_exclusiones=True)

    assert cierre["estado"] == "CERRADO"
    assert cierre["reportes"]["estado_resultados"] == "PENDIENTE_GENERACION"
    motivo = cierre["reportes"]["motivo_estado_resultados"]
    assert "no cuadra con sus fuentes" in motivo and "la variación de valor razonable" in motivo
    assert motivo in m06.notificador.avisos
    assert _errores_conciliacion(db_session, p) == 1
    assert m06.reportes.listar_estados(p) == []

    with pytest.raises(ConciliacionError) as error:
        m06.estado_resultados().generar(p, {}, uid)
    assert error.value.code == "ESTADO_RESULTADOS_NO_CONCILIA" and error.value.status_code == 422
    assert [f["id_origen"] for f in error.value.faltantes] == [huerfana]
    assert _errores_conciliacion(db_session, p) == 2  # la discrepancia queda aunque la generación se revierta

    db_session.execute(text("SET LOCAL session_replication_role = replica"))
    db_session.execute(text("DELETE FROM modulo6.variaciones_valor_razonable WHERE id_variacion_valor_razonable = :v"),
                       {"v": huerfana})
    db_session.execute(text("SET LOCAL session_replication_role = origin"))
    generado = m06.estado_resultados().generar(p, {}, uid)
    assert generado["id_estado"] and D(generado["resultado_neto"]) == D(generado["total_ingresos"]) - D(generado["total_gastos"])
