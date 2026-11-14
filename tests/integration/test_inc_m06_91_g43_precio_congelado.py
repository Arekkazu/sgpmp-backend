# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-13 | Arekkazu | INC-M06-91-G43 RF-87/83: precio congelado al iniciar el cierre y estimado marcado aunque no varíe |
# | 2026-11-13 | Arekkazu | Lote M05/M06 13-11: el cierre de la prueba sigue a la trazabilidad de RF-91 (#1115) |
"""INC-M06-91-G43 contra el esquema real.

G43-05 (RF-87 CA-1): el cierre usa el precio vigente cuando empezó; un precio registrado mientras el
período espera en EN_CIERRE no lo cambia y queda para los cierres siguientes.
G43-03 (RF-83 v1.2, RF-87 FA-2): el activo que el Contador decide estimar sale en ``activos_estimados``,
su medición queda marcada como estimada (aunque la variación sea cero) y el Contador recibe la alerta."""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from tests.integration.test_inc_m06_lote_2026_11_10 import ESPECIE, _codigo, _reconocido
from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401 (fixtures)
    HOY,
    _activo,
    _configurar,
    _pesaje,
    _precio,
    contador,
    m06,
)

pytestmark = pytest.mark.integration
OTRA_ESPECIE = 3


def _vencer_precios(db, especie) -> None:
    db.execute(text("SET LOCAL session_replication_role = replica"))
    db.execute(text("UPDATE modulo6.precios_mercado SET fecha_vencimiento = :d WHERE id_especie = :e"),
               {"d": HOY - timedelta(days=1), "e": especie})
    db.execute(text("SET LOCAL session_replication_role = origin"))


def test_precio_registrado_durante_el_cierre_no_cambia_el_precio_congelado(db_session, m06, contador):
    uid = contador["id_usuario"]
    finca, activo, periodo = _reconocido(db_session, m06, uid)
    [inicial] = [p for p in m06.precios.de_especie(ESPECIE, "PESO_KG")]
    # Un activo de otra especie sin precio vigente deja el cierre esperando la decisión del Contador.
    _configurar(m06, uid, OTRA_ESPECIE)
    otro = _activo(db_session, finca, uid, especie=OTRA_ESPECIE, origen="compra", costo=1000000)
    _pesaje(db_session, otro, "100", -timedelta(minutes=4))
    _precio(m06, uid, OTRA_ESPECIE, "5000", HOY - timedelta(days=10))
    m06.confirmar_reconocimiento().execute(otro, uid)
    _vencer_precios(db_session, OTRA_ESPECIE)
    p = periodo.id_periodo_contable

    assert _codigo(lambda: m06.cierre().execute(p, uid))[0] == "EXCLUSION_REQUIERE_AUTORIZACION"
    nuevo = _precio(m06, uid, ESPECIE, "9000", HOY)  # durante EN_CIERRE (RF-89 sigue abierto)
    assert {a["id_activo_biologico"] for a in m06.cierre().prevalidar(periodo).activos_sin_precio} == {otro}

    cierre = m06.cierre().execute(p, uid, autorizar_exclusiones=True)

    assert cierre["estado"] == "CERRADO"
    # Con el precio congelado el activo no varía; con el de 9.000 habría registrado una ganancia por precio.
    assert m06.valoraciones.ultimo_calculo(activo).id_precio_mercado == inicial.id_precio_mercado
    assert not [v for v in m06.valoraciones.historial_activo(activo)["mediciones"] if v["id_periodo_contable"] == p]
    congelado = {x["id_especie"]: x for x in m06.periodos.ultima_ejecucion(p)["precios_congelados"]}[ESPECIE]
    assert congelado["id_precio_mercado"] == inicial.id_precio_mercado != nuevo["id_precio_mercado"]
    assert congelado["fecha_vigencia"] == inicial.fecha_vigencia.isoformat() and congelado["estimacion"] is False


def test_activo_estimado_queda_marcado_y_alerta_aunque_no_varie(db_session, m06, contador):
    uid = contador["id_usuario"]
    _, activo, periodo = _reconocido(db_session, m06, uid)
    [vencido] = m06.precios.de_especie(ESPECIE, "PESO_KG")
    _vencer_precios(db_session, ESPECIE)
    p = periodo.id_periodo_contable

    cierre = m06.cierre().execute(p, uid, activos_estimados=[activo], autorizar_exclusiones=True)

    assert cierre["estado"] == "CERRADO" and cierre["activos_excluidos"] == []
    [estimado] = cierre["activos_estimados"]
    assert estimado["id_activo_biologico"] == activo and estimado["id_precio_mercado"] == vencido.id_precio_mercado
    [medicion] = m06.valoraciones.mediciones_del_periodo(p, tiene_valor_estimado=True)
    assert medicion["id_medicion_posterior"] == estimado["id_medicion"]
    assert m06.valoraciones.ultimo_calculo(activo).id_precio_mercado == vencido.id_precio_mercado
    tipos = [r[0] for r in db_session.execute(text(
        "SELECT tipo_evento::text FROM modulo6.auditorias_financieras WHERE id_activo_biologico = :a AND id_periodo_contable = :p"),
        {"a": activo, "p": p})]
    assert "MEDICION_CON_ESTIMACION" in tipos and "MEDICION_PENDIENTE" in tipos and "MEDICION_SIN_VARIACION" not in tipos
    assert any("precio estimado" in aviso for aviso in m06.notificador.avisos)
