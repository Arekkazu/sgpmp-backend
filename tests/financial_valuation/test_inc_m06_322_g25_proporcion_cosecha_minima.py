# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-09 | destroyerban | INC-M06-322-G25 RF-85: la proporción cosechada se guarda a 6 decimales y nunca en 0 |
"""INC-M06-322-G25 / RF-85: una cantidad cosechada que M02 acepta (mínimo 0,001 kg) se reconoce en M06.

Antes, 0,001 kg sobre un activo de 1.000 kg daba proporción 0,000001, que se guardaba redondeada a 4 decimales
(0,0000). ``chk_prod_agricola_proporcion_rango`` exige > 0, así que el evento terminaba en ERROR y no había producto."""
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
from src.financial_valuation.domain.services.nic41 import proporcion_registrada

D = Decimal


@pytest.mark.parametrize("exacta, registrada", [
    (D("0.000001"), D("0.000001")),        # 0,001 kg de 1.000 kg (el caso del ticket)
    (D("0.00000001"), D("0.000001")),      # menor que lo representable: el mínimo, nunca 0
    (D("0.3333333"), D("0.333333")),       # 6 decimales, no 4
    (D("0.9999996"), D("0.999999")),       # una parcial no se redondea a 1 (1 es la cosecha total, FA-4)
    (D("1"), D("1")),
    (D("0"), D("0")),
])
def test_proporcion_registrada(exacta, registrada) -> None:
    assert proporcion_registrada(exacta) == registrada


def _base() -> CalculoValor:  # 1.000 kg a 20.000 menos 6 % de costos de venta = 18.800.000
    return CalculoValor(
        id_activo_biologico=7, id_precio_mercado=12, id_periodo_contable=4, magnitud=D("1000.0000"),
        unidad_magnitud="kg", precio_unitario=D("20000"), valor_razonable_bruto=D("20000000"),
        costo_transporte=D("1200000"), costo_comisiones=D("0"), costo_impuestos_transaccion=D("0"),
        otros_costos_disposicion=D("0"), valor_neto=D("18800000"), metodo_costo="PARAMETRIZADO", json_metodo_costo={},
        id_usuario=1, id_calculo_valor_razonable=90)


def test_cosecha_de_0_001_kg_se_reconoce() -> None:
    activo = SimpleNamespace(id_activo_biologico=7, identificador="TRU-007", id_especie=2, id_finca=3,
                             numero_id_tributaria="900123456", id_dispositivo_iot=None)
    evento = EventoM02(id_evento=500, id_activo_biologico=7, tipo="PRODUCTIVO",
                       fecha=datetime(2026, 11, 9, 15, tzinfo=timezone.utc),
                       datos={"cantidad_producida": "0.001", "id_metrica_produccion": 3})
    productos, lineas, procesados = [], [], []
    ProcesarEventosM02UseCase(
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
        medidor=SimpleNamespace(valorador=SimpleNamespace(categoria=lambda _e: "PESO_KG"),
                                medir=lambda *a, **k: SimpleNamespace(estado="MEDIDO", id_medicion=33, mensaje=None)),
        contabilizador=SimpleNamespace(periodo_para=lambda *a: SimpleNamespace(id_periodo_contable=4),
                                       asentar=lambda linea, _u: lineas.append(linea), auditar=lambda _e: None),
        id_usuario_servicio=1,
    ).execute()

    assert procesados == [("PROCESADO", None)]
    p, = productos
    assert p["proporcion_cosechada"] == D("0.000001") and p["cantidad_cosechada"] == D("0.001")
    assert p["valor_reduccion_activo"] == D("18.80") and lineas[0].valor == D("18.80")
    # chk_prod_agricola_valor_coherente: |valor − (precio − costo) × cantidad| ≤ 1
    assert abs(p["valor_producto"] - (p["precio_mercado_producto"] - p["costo_venta_producto"]) * p["cantidad_cosechada"]) <= 1
