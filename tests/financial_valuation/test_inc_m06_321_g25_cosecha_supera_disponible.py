# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-09 | destroyerban | INC-M06-321-G25 RF-85: no se reconoce una cosecha mayor que lo disponible del activo |
# | 2026-11-10 | Arekkazu | Lote M05/M06: fakes al día con el lote integrado (elegibilidad, alertas, período cerrado, referencia documental) |
"""INC-M06-321-G25 / RF-85 R2: la cosecha de un producto de consumo no puede superar lo que tiene el activo.

Antes, 1.000,1 kg sobre un activo de 1.000 kg (100,01 %) se reconocía sin aviso: la proporción se recortaba a 1
con ``min(1, cantidad/magnitud)`` y el producto quedaba con 1.000,1 kg, 18.800.000 y un costo unitario de 1.199,88."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.financial_valuation.application.use_cases.valoracion.procesar_eventos_m02_use_case import (
    ProcesarEventosM02UseCase,
)
from src.financial_valuation.domain.entities.valoracion import CalculoValor
from src.financial_valuation.domain.repositories.evento_m02_port import EventoM02

D = Decimal


def _base() -> CalculoValor:  # 1.000 kg a 20.000 menos 6 % de costos de venta = 18.800.000
    return CalculoValor(
        id_activo_biologico=7, id_precio_mercado=12, id_periodo_contable=4, magnitud=D("1000.0000"),
        unidad_magnitud="kg", precio_unitario=D("20000"), valor_razonable_bruto=D("20000000"),
        costo_transporte=D("1200000"), costo_comisiones=D("0"), costo_impuestos_transaccion=D("0"),
        otros_costos_disposicion=D("0"), valor_neto=D("18800000"), metodo_costo="PARAMETRIZADO", json_metodo_costo={},
        id_usuario=1, id_calculo_valor_razonable=90)


def _procesar(cantidad: str):
    activo = SimpleNamespace(estado="ACTIVO", es_valorable=True, id_activo_biologico=7, identificador="TRU-007", id_especie=2, id_finca=3,
                             numero_id_tributaria="900123456", id_dispositivo_iot=None)
    evento = EventoM02(id_evento=500, id_activo_biologico=7, tipo="PRODUCTIVO",
                       fecha=datetime(2026, 11, 9, 15, tzinfo=timezone.utc),
                       datos={"cantidad_producida": cantidad, "id_metrica_produccion": 3})
    productos, lineas, eventos, procesados = [], [], [], []
    caso = ProcesarEventosM02UseCase(
        db=SimpleNamespace(commit=lambda: None, rollback=lambda: None),
        eventos=SimpleNamespace(pendientes=lambda _l: [evento],
                                registrar_procesamiento=lambda i, r, d: procesados.append((r, d))),
        activos=SimpleNamespace(obtener=lambda _id: activo,
                                metrica_produccion=lambda _id: {"id_metrica_produccion": 3, "nombre": "Trucha entera",
                                                                "unidad_medida": "kg"}),
        valoraciones=SimpleNamespace(valoracion_costo_activa=lambda _id: None, ultimo_calculo=lambda _id: _base(),
                                     reconocimiento_confirmado=lambda _id: SimpleNamespace(clasificacion="CONSUMO"),
                                     agregar_producto=lambda d: productos.append(d) or 70,
                                     agregar_calculo=lambda c: 91),
        precios=None,
        medidor=SimpleNamespace(tomar_alertas=lambda: [], valorador=SimpleNamespace(categoria=lambda _e: "PESO_KG"),
                                medir=lambda *a, **k: SimpleNamespace(estado="MEDIDO", id_medicion=33, mensaje=None, motivo=None)),
        contabilizador=SimpleNamespace(periodo_cerrado_en=lambda *a: None, periodo_para=lambda *a: SimpleNamespace(id_periodo_contable=4),
                                       asentar=lambda linea, _u: lineas.append(linea), auditar=eventos.append),
        id_usuario_servicio=1,
    )
    caso.execute()
    return procesados, productos, lineas, eventos


def test_cosecha_mayor_que_lo_disponible_no_se_reconoce_y_se_avisa() -> None:
    procesados, productos, lineas, eventos = _procesar("1000.1")

    resultado, detalle = procesados[0]
    assert resultado == "MEDICION_PENDIENTE"
    assert detalle.startswith("La cantidad cosechada (1000.1 kg) supera la cantidad disponible del activo TRU-007 (1000 kg).")
    assert productos == [] and lineas == []  # ni producto ni reducción del activo
    aviso, = eventos
    assert aviso.tipo_evento == "RECONOCIMIENTO_PRODUCTO_PENDIENTE" and aviso.severidad == "WARNING"
    assert aviso.payload["mensaje"] == detalle


@pytest.mark.parametrize("cantidad, proporcion, reduccion", [
    ("1000", D("1"), D("18800000.00")),    # exactamente lo disponible: cosecha total válida (FA-4)
    ("999.9", D("0.9999"), D("18798120.00")),
])
def test_cosecha_hasta_lo_disponible_se_reconoce(cantidad, proporcion, reduccion) -> None:
    procesados, productos, lineas, _ = _procesar(cantidad)

    assert procesados[0] == ("PROCESADO", None)
    producto, = productos
    assert producto["proporcion_cosechada"] == proporcion
    assert producto["valor_reduccion_activo"] == reduccion and lineas[0].valor == reduccion
