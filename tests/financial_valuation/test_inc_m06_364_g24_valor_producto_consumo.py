# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-14 | Arekkazu | INC-M06-364-G24 RF-85: el producto de consumo se valora con su precio y la diferencia va a resultados |
"""INC-M06-364-G24 / RF-85 pasos 3 a 7 y CA-5: el producto de consumo vale su precio (RF-89) menos costos de venta.

Activo de 1.000 kg a 20.000 con 6 % de costos (18.800.000); cosecha de 250 kg. El activo se reduce en 4.700.000 y
sale contra el inventario (traslado); el producto entra a su valor y la diferencia es ganancia o pérdida."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.financial_valuation.application.services.medidor import Medidor
from src.financial_valuation.application.services.valorador import Valorador
from src.financial_valuation.application.use_cases.valoracion.procesar_eventos_m02_use_case import (
    ProcesarEventosM02UseCase,
)
from src.financial_valuation.domain.entities.activo_financiero import DatosActivo
from src.financial_valuation.domain.entities.valoracion import CalculoValor
from src.financial_valuation.domain.repositories.evento_m02_port import EventoM02
from src.financial_valuation.domain.services.consolidacion import MovimientoResultado, estado_resultados
from src.financial_valuation.domain.services.precios import Precio

D = Decimal
ACTIVO = DatosActivo(
    id_activo_biologico=7, identificador="TRU-007", tipo="INDIVIDUAL", id_especie=2, especie="Trucha", estado="ACTIVO",
    id_infraestructura=4, id_finca=3, finca="La Esperanza", numero_id_tributaria="900123456", razon_social="Finca SAS",
    fecha_ingreso=date(2026, 10, 1), origen_financiero="nacimiento", costo_adquisicion=None, soporte_documental=None,
    cantidad_actual=None, peso_kg=D("1000"), id_evento_peso=10, id_dispositivo_iot=None)
PRECIO_ACTIVO = Precio(id_precio_mercado=12, id_especie=2, categoria="PESO_KG", precio_unitario=D("20000"),
                       unidad_medida="kg", fuente="MERCADO_ACTIVO", fecha_vigencia=date(2026, 9, 1))


def _cosechar(precio_producto: str | None):
    calculos = [CalculoValor(
        id_activo_biologico=7, id_precio_mercado=12, id_periodo_contable=4, magnitud=D("1000.0000"),
        unidad_magnitud="kg", precio_unitario=D("20000"), valor_razonable_bruto=D("20000000.0000"),
        costo_transporte=D("1200000.0000"), costo_comisiones=D("0"), costo_impuestos_transaccion=D("0"),
        otros_costos_disposicion=D("0"), valor_neto=D("18800000.0000"), metodo_costo="PARAMETRIZADO",
        json_metodo_costo={}, id_usuario=1, id_evento_magnitud=10, id_calculo_valor_razonable=1)]
    productos, lineas = [], []
    producto = [] if precio_producto is None else [Precio(
        id_precio_mercado=40, id_especie=2, categoria="PRODUCTO", precio_unitario=D(precio_producto), unidad_medida="kg",
        fuente="MERCADO_ACTIVO", fecha_vigencia=date(2026, 11, 1), id_metrica_produccion=3)]
    config = SimpleNamespace(
        costos_venta_vigentes=lambda _e, _r=None: SimpleNamespace(pct_transporte=D("0.06"), pct_comisiones=D("0"),
                                                                pct_impuestos=D("0"), id_parametro_costo_venta=1),
        parametro_especie=lambda _e: None)
    valoraciones = SimpleNamespace(
        ultimo_calculo=lambda _id: calculos[-1], agregar_calculo=lambda c: calculos.append(c) or len(calculos),
        agregar_medicion=lambda m: 1, agregar_variacion=lambda v: 1, valoracion_costo_activa=lambda _id: None,
        reconocimiento_confirmado=lambda _id: SimpleNamespace(clasificacion="CONSUMO"),
        agregar_producto=lambda d: productos.append(d) or len(productos))
    contabilizador = SimpleNamespace(periodo_cerrado_en=lambda *a: None,
                                     periodo_para=lambda *a: SimpleNamespace(id_periodo_contable=4),
                                     asentar=lambda linea, _u: lineas.append(linea), auditar=lambda _e: None)
    medidor = Medidor(Valorador(SimpleNamespace(de_especie=lambda *a: [PRECIO_ACTIVO]), config), valoraciones, contabilizador)
    caso = ProcesarEventosM02UseCase(
        db=SimpleNamespace(commit=lambda: None, rollback=lambda: None), eventos=None,
        activos=SimpleNamespace(obtener=lambda _id: ACTIVO,
                                metrica_produccion=lambda _id: {"id_metrica_produccion": 3, "nombre": "Trucha entera",
                                                                "unidad_medida": "kg"}),
        valoraciones=valoraciones, precios=SimpleNamespace(de_especie=lambda *a: producto), medidor=medidor,
        contabilizador=contabilizador, id_usuario_servicio=1)
    evento = EventoM02(id_evento=500, id_activo_biologico=7, tipo="PRODUCTIVO",
                       fecha=datetime(2026, 11, 13, 15, tzinfo=timezone.utc),
                       datos={"cantidad_producida": "250", "id_metrica_produccion": 3})
    resultado = caso._procesar(evento)
    return resultado, productos, [(linea.sentido, linea.valor) for linea in lineas]


@pytest.mark.parametrize("precio, valor_producto, costo_unitario, diferencia", [
    ("12000", D("2820000.00"), D("720.0000"), ("PERDIDA", D("1880000.00"))),   # caso de QA: vale menos que el activo
    ("25000", D("5875000.00"), D("1500.0000"), ("UNICO", D("1175000.00"))),    # vale más: ganancia (¶28)
])
def test_el_producto_vale_su_precio_y_la_diferencia_va_a_resultados(precio, valor_producto, costo_unitario,
                                                                     diferencia) -> None:
    resultado, productos, lineas = _cosechar(precio)

    assert resultado == ("PROCESADO", None)
    producto = productos[0]
    assert producto["precio_mercado_producto"] == D(precio)
    assert producto["costo_venta_producto"] == costo_unitario
    assert producto["valor_producto"] == valor_producto
    assert producto["valor_reduccion_activo"] == D("4700000.00")
    assert lineas == [("TRASLADO", D("4700000.00")), diferencia]
    # Inventario = traslado ± diferencia = valor del producto: el asiento cuadra.
    signo = 1 if diferencia[0] == "UNICO" else -1
    assert lineas[0][1] + signo * diferencia[1] == valor_producto


def test_sin_precio_del_producto_vale_lo_que_se_redujo_el_activo() -> None:
    resultado, productos, lineas = _cosechar(None)

    assert resultado == ("PROCESADO", None)
    assert productos[0]["valor_producto"] == productos[0]["valor_reduccion_activo"] == D("4700000.00")
    assert productos[0]["precio_mercado_producto"] == D("20000.0000")
    assert lineas == [("TRASLADO", D("4700000.00"))]


def test_la_perdida_del_producto_es_gasto_y_la_ganancia_ingreso() -> None:
    estado = estado_resultados([MovimientoResultado("PRODUCTO_AGRICOLA", "PERDIDA", D("1880000")),
                                MovimientoResultado("PRODUCTO_AGRICOLA", "UNICO", D("1175000")),
                                MovimientoResultado("PRODUCTO_AGRICOLA", "TRASLADO", D("4700000"))], [])

    assert estado.componentes["perdida_reconocimiento_inicial"] == D("1880000")
    assert estado.componentes["ingresos_productos_agricolas"] == D("1175000")
    assert estado.resultado_neto == D("-705000")  # el traslado no es resultado
