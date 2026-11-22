# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-83..93: pruebas del núcleo de cálculo NIC 41 |
"""Pruebas del núcleo NIC 41 (sin BD)."""
from datetime import date
from decimal import Decimal as D

import pytest

from src.financial_valuation.domain.services.consolidacion import (
    CostoPeriodo,
    LineaContable,
    MovimientoResultado,
    consolidar_comprobantes,
    estado_resultados,
)
from src.financial_valuation.domain.services.nic41 import (
    costos_venta,
    descomponer_variacion,
    meses_transcurridos,
    periodo_siguiente,
    rango_periodo,
    repartir,
    sentido_por_signo,
    valor_neto,
    valor_por_costo,
)
from src.financial_valuation.domain.services.precios import Precio, estado_precio, precio_vigente, ultimo_precio_conocido
from src.financial_valuation.domain.value_objects.nic41 import Sentido, TipoCierre


def _precio(i, fuente, vigencia, vence=None, valor="8000"):
    return Precio(i, 1, "PESO_KG", D(valor), "kg", fuente, vigencia, vence)


def test_valor_neto_resta_costos_de_venta_parametrizados_y_manuales():
    costos = costos_venta(D("4000000"), D("0.02"), D("0.03"), None, {"otros": D("10000")})
    vn = valor_neto(D("500"), D("8000"), costos)
    assert vn.bruto == D("4000000.0000")
    assert (costos.transporte, costos.comisiones, costos.impuestos) == (D("80000.0000"), D("120000.0000"), D("0"))
    assert vn.neto == D("3790000.0000")
    assert costos.metodo_global == "MIXTO" and "impuestos" not in costos.metodos


def test_descomposicion_precio_y_transformacion_suma_la_variacion_total():
    # 500 kg a 8.000 → 520 kg a 8.500, con 5 % de costos de venta.
    f = D("0.95")
    vn_ant, vn_act = D(500) * 8000 * f, D(520) * 8500 * f
    v = descomponer_variacion(vn_ant, vn_act, D(500), D(520), hubo_evento_biologico=True)
    assert v.precio == D(500) * (8500 - 8000) * f  # efecto precio con la magnitud anterior
    assert v.transformacion == D(20) * 8500 * f  # 20 kg nuevos al precio actual
    assert v.precio + v.transformacion == v.total == vn_act - vn_ant


def test_sin_evento_biologico_toda_la_variacion_es_precio():
    v = descomponer_variacion(D("100"), D("90"), D(10), D(10), hubo_evento_biologico=False)
    assert (v.precio, v.transformacion) == (D("-10.0000"), D("0"))


def test_linea_de_perdida_tiene_valor_positivo_y_truncado():
    assert sentido_por_signo(D("-600000.019")) == (Sentido.PERDIDA, D("600000.01"))
    assert sentido_por_signo(D("4600000")) == (Sentido.GANANCIA, D("4600000.00"))
    assert sentido_por_signo(D("0.004")) is None


def test_reparto_por_cabezas_cuadra_y_asigna_residuo_al_mayor():
    assert repartir(D("1000000"), {1: D(1), 2: D(9)}) == {1: D("100000.00"), 2: D("900000.00")}
    partes = repartir(D("100"), {3: D(1), 4: D(1), 5: D(1)})
    assert sum(partes.values()) == D("100") and partes[3] == D("33.34")


def test_valor_por_costo_no_baja_de_cero():
    v = valor_por_costo(D("1200000"), 24, 6)
    assert (v.depreciacion_acumulada, v.valor_contable) == (D("300000.0000"), D("900000.0000"))
    assert valor_por_costo(D("1000"), 12, 12, D("500")).valor_contable == 0
    assert meses_transcurridos(date(2026, 1, 31), date(2026, 3, 31)) == 2


def test_periodos_calendario():
    assert rango_periodo(date(2026, 11, 4), TipoCierre.MENSUAL) == (date(2026, 11, 1), date(2026, 11, 30))
    assert rango_periodo(date(2026, 11, 4), TipoCierre.TRIMESTRAL) == (date(2026, 10, 1), date(2026, 12, 31))
    assert periodo_siguiente(date(2026, 12, 31), TipoCierre.MENSUAL) == (date(2027, 1, 1), date(2027, 1, 31))


def test_prioridad_de_fuente_prevalece_sobre_fecha_y_vencimiento():
    hoy = date(2026, 11, 4)
    mercado = _precio(1, "MERCADO_ACTIVO", date(2026, 10, 1))
    upra = _precio(2, "UPRA", date(2026, 11, 1))
    assert precio_vigente([mercado, upra], hoy) == mercado  # CA-14
    vencido = _precio(3, "MERCADO_ACTIVO", date(2026, 9, 1), vence=date(2026, 10, 1))
    assert precio_vigente([vencido, upra], hoy) == upra
    assert precio_vigente([vencido], hoy) is None
    assert ultimo_precio_conocido([vencido], hoy) == vencido  # estimación de RF-83 FA-1
    programado = _precio(4, "UPRA", date(2026, 12, 1))
    assert precio_vigente([programado], hoy) is None
    assert estado_precio(programado, [upra, programado], hoy) == "PROGRAMADO"
    assert estado_precio(_precio(5, "UPRA", date(2026, 10, 1)), [upra, _precio(5, "UPRA", date(2026, 10, 1))], hoy) == "SUPERADO"


def test_comprobante_agrupa_por_titular_tipo_especie_y_par_de_cuentas():
    lineas = [
        LineaContable(1, "VARIACION_VR_TB", "GANANCIA", "900123456", 1, "1586", "4250", D("100")),
        LineaContable(2, "VARIACION_VR_TB", "GANANCIA", "900123456", 1, "1586", "4250", D("50")),
        LineaContable(3, "VARIACION_VR_TB", "PERDIDA", "900123456", 1, "5250", "1586", D("30")),
    ]
    [c] = consolidar_comprobantes(lineas, date(2026, 11, 30))
    assert c.codigo == "NIC-900123456-202611-VARIACION_VR_TB-1"
    assert c.lineas == [{"cuenta_debito": "1586", "cuenta_credito": "4250", "valor": "150"},
                        {"cuenta_debito": "5250", "cuenta_credito": "1586", "valor": "30"}]
    assert len(c.hash_integridad) == 64 and c.ids_lineas == [1, 2, 3]


def test_estado_de_resultados_no_cuenta_dos_veces_los_consumos_de_m05():
    movimientos = [
        MovimientoResultado("VARIACION_VR_TB", "GANANCIA", D("4600000")),
        MovimientoResultado("VARIACION_VR_PM", "PERDIDA", D("600000")),
        MovimientoResultado("CONSUMO_INSUMO", "UNICO", D("300000")),  # ya está en costos
        MovimientoResultado("RECONOCIMIENTO_NACIMIENTO", "UNICO", D("900000")),
    ]
    costos = [CostoPeriodo("MANTENIMIENTO", "GASTO", D("300000")), CostoPeriodo("INVERSION", "CAPITALIZAR", D("1")),
              CostoPeriodo("VENTA", None, D("50000")), CostoPeriodo("MANTENIMIENTO", "GASTO", D("100000"), es_reverso=True)]
    er = estado_resultados(movimientos, costos)
    assert er.total_ingresos == D("5500000")
    assert er.total_gastos == D("800000")  # 600.000 pérdida precio + 200.000 mantenimiento neto
    assert er.resultado_neto == D("4700000")


@pytest.mark.parametrize("negativo", [D("-1")])
def test_costo_manual_negativo_se_rechaza(negativo):
    with pytest.raises(ValueError):
        costos_venta(D("100"), None, None, None, {"transporte": negativo})
