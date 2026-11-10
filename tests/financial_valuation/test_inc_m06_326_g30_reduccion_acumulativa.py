# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-09 | destroyerban | INC-M06-326-G30 RF-85: la magnitud del activo descuenta lo cosechado desde el último pesaje |
"""INC-M06-326-G30 / RF-85 CA-2, CA-6 y postcondición 2: la reducción del activo de consumo es acumulativa.

Antes, tres cosechas del mismo día de 400, 400 y 300 kg sobre un activo de 1.000 kg (18.800.000) se reconocían
todas: antes de cada una M06 volvía a medir el activo con los 1.000 kg de M02, que no bajan con las cosechas. Las
reducciones sumaban 20.680.000 (más que el activo), el activo quedaba en 13.160.000 y se registraba una ganancia
falsa por transformación biológica."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from src.financial_valuation.application.services.medidor import Medidor
from src.financial_valuation.application.services.valorador import Valorador
from src.financial_valuation.application.use_cases.valoracion.procesar_eventos_m02_use_case import (
    ProcesarEventosM02UseCase,
)
from src.financial_valuation.domain.entities.activo_financiero import DatosActivo
from src.financial_valuation.domain.entities.valoracion import CalculoValor
from src.financial_valuation.domain.repositories.evento_m02_port import EventoM02
from src.financial_valuation.domain.services.precios import Precio

D = Decimal
ACTIVO = DatosActivo(
    id_activo_biologico=7, identificador="TRU-007", tipo="INDIVIDUAL", id_especie=2, especie="Trucha", estado="ACTIVO",
    id_infraestructura=4, id_finca=3, finca="La Esperanza", numero_id_tributaria="900123456", razon_social="Finca SAS",
    fecha_ingreso=date(2026, 10, 1), origen_financiero="nacimiento", costo_adquisicion=None, soporte_documental=None,
    cantidad_actual=None, peso_kg=D("1000"), id_evento_peso=10, id_dispositivo_iot=None)


def test_magnitud_descuenta_lo_cosechado() -> None:
    assert replace(ACTIVO, kg_cosechados=D("400")).magnitud("PESO_KG") == (D("600"), "kg")
    assert replace(ACTIVO, kg_cosechados=D("1200")).magnitud("PESO_KG") == (D("0"), "kg")  # nunca negativa
    assert ACTIVO.magnitud("PESO_KG") == (D("1000"), "kg")


class _Mundo:
    """Repositorio en memoria: los productos de consumo suben los kg cosechados que el adaptador de M02 descuenta."""

    def __init__(self) -> None:
        self.calculos = [CalculoValor(
            id_activo_biologico=7, id_precio_mercado=12, id_periodo_contable=4, magnitud=D("1000.0000"),
            unidad_magnitud="kg", precio_unitario=D("20000"), valor_razonable_bruto=D("20000000.0000"),
            costo_transporte=D("1200000.0000"), costo_comisiones=D("0"), costo_impuestos_transaccion=D("0"),
            otros_costos_disposicion=D("0"), valor_neto=D("18800000.0000"), metodo_costo="PARAMETRIZADO",
            json_metodo_costo={}, id_usuario=1, id_evento_magnitud=10, id_calculo_valor_razonable=1)]
        self.productos, self.lineas, self.variaciones, self.procesados = [], [], [], []

    def activo(self, _id):
        return replace(ACTIVO, kg_cosechados=sum((D(p["cantidad_cosechada"]) for p in self.productos), D(0)))

    def agregar_calculo(self, calculo):
        calculo.id_calculo_valor_razonable = len(self.calculos) + 1
        self.calculos.append(calculo)
        return calculo.id_calculo_valor_razonable


def _procesador(mundo: _Mundo) -> ProcesarEventosM02UseCase:
    precio = Precio(id_precio_mercado=12, id_especie=2, categoria="PESO_KG", precio_unitario=D("20000"),
                    unidad_medida="kg", fuente="MERCADO_ACTIVO", fecha_vigencia=date(2026, 9, 1))
    config = SimpleNamespace(
        costos_venta_vigentes=lambda _e: SimpleNamespace(pct_transporte=D("0.06"), pct_comisiones=D("0"),
                                                         pct_impuestos=D("0"), id_parametro_costo_venta=1),
        parametro_especie=lambda _e: None)
    valoraciones = SimpleNamespace(
        ultimo_calculo=lambda _id: mundo.calculos[-1], agregar_calculo=mundo.agregar_calculo,
        agregar_medicion=lambda m: 1, agregar_variacion=lambda v: mundo.variaciones.append(v) or 1,
        valoracion_costo_activa=lambda _id: None,
        reconocimiento_confirmado=lambda _id: SimpleNamespace(clasificacion="CONSUMO"),
        agregar_producto=lambda d: mundo.productos.append(d) or len(mundo.productos))
    contabilizador = SimpleNamespace(periodo_para=lambda *a: SimpleNamespace(id_periodo_contable=4),
                                     asentar=lambda linea, _u: mundo.lineas.append(linea), auditar=lambda _e: None)
    medidor = Medidor(Valorador(SimpleNamespace(de_especie=lambda *a: [precio]), config), valoraciones, contabilizador)
    eventos = [EventoM02(id_evento=500 + i, id_activo_biologico=7, tipo="PRODUCTIVO",
                         fecha=datetime(2026, 11, 9, 10 + i, tzinfo=timezone.utc),
                         datos={"cantidad_producida": kg, "id_metrica_produccion": 3})
               for i, kg in enumerate(("400", "400", "300"))]
    return ProcesarEventosM02UseCase(
        db=SimpleNamespace(commit=lambda: None, rollback=lambda: None),
        eventos=SimpleNamespace(pendientes=lambda _l: eventos,
                                registrar_procesamiento=lambda i, r, d: mundo.procesados.append((i, r, d))),
        activos=SimpleNamespace(obtener=mundo.activo,
                                metrica_produccion=lambda _id: {"id_metrica_produccion": 3, "nombre": "Trucha entera",
                                                                "unidad_medida": "kg"}),
        valoraciones=valoraciones, precios=None, medidor=medidor, contabilizador=contabilizador, id_usuario_servicio=1)


def test_tres_cosechas_del_mismo_dia_reducen_de_forma_acumulativa() -> None:
    mundo = _Mundo()

    _procesador(mundo).execute()

    assert [r for _, r, _ in mundo.procesados] == ["PROCESADO", "PROCESADO", "MEDICION_PENDIENTE"]
    assert [p["valor_reduccion_activo"] for p in mundo.productos] == [D("7520000.00"), D("7520000.00")]
    assert sum(p["valor_reduccion_activo"] for p in mundo.productos) <= D("18800000")
    assert "La cantidad cosechada (300 kg) supera la cantidad disponible del activo TRU-007 (200 kg)" in mundo.procesados[2][2]
    base = mundo.calculos[-1]  # lo que queda: 200 kg por 3.760.000
    assert (base.magnitud, base.valor_neto) == (D("200.0000"), D("3760000.0000"))
    assert mundo.variaciones == []  # sin ganancia falsa por transformación al volver a medir
    assert all(linea.tipo_hecho == "PRODUCTO_AGRICOLA" for linea in mundo.lineas)
