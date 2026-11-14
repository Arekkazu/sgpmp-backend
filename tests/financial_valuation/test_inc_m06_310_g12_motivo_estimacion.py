# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-08 | destroyerban | INC-M06-310-G12 RF-83: motivo de la estimación y precio usado |
"""INC-M06-310-G12 / RF-83 FA-1: el evento ``MEDICION_CON_ESTIMACION`` dice por qué la medición es estimada
y con qué precio, en vez de dejarlo solo en ``supuestos_aplicados`` de la medición."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.financial_valuation.application.services.medidor import Medidor
from src.financial_valuation.application.services.valorador import Valorador
from src.financial_valuation.domain.entities.contabilidad import Periodo
from src.financial_valuation.domain.entities.valoracion import CalculoValor
from src.financial_valuation.domain.services.precios import Precio, motivo_estimacion

D = Decimal
DIA = date(2026, 11, 8)
PERIODO = Periodo(id_periodo_contable=3, numero_id_tributaria="900", tipo_cierre="MENSUAL",
                  fecha_inicio=date(2026, 11, 1), fecha_fin=date(2026, 11, 30), estado="ABIERTO")


def _precio(fuente="MERCADO_ACTIVO", vence=None) -> Precio:
    return Precio(id_precio_mercado=12, id_especie=2, categoria="PESO_KG", precio_unitario=D("9500"),
                  unidad_medida="kg", fuente=fuente, fecha_vigencia=date(2026, 9, 1), fecha_vencimiento=vence)


def test_motivo_de_la_estimacion() -> None:
    assert motivo_estimacion(_precio(vence=date(2026, 10, 31)), DIA) == "SIN_PRECIO_VIGENTE"
    assert motivo_estimacion(_precio("ESTIMADA", vence=date(2026, 10, 31)), DIA) == "SIN_PRECIO_VIGENTE"
    assert motivo_estimacion(_precio("ESTIMADA"), DIA) == "FUENTE_ESTIMADA"
    assert motivo_estimacion(_precio(), DIA) is None


def _calculo(magnitud, neto, *, estimado=False, id_calculo=None) -> CalculoValor:
    return CalculoValor(
        id_activo_biologico=7, id_precio_mercado=12, id_periodo_contable=3, magnitud=D(magnitud), unidad_magnitud="kg",
        precio_unitario=D("9500"), valor_razonable_bruto=D(neto), costo_transporte=D(0), costo_comisiones=D(0),
        costo_impuestos_transaccion=D(0), otros_costos_disposicion=D(0), valor_neto=D(neto), metodo_costo="PARAMETRIZADO",
        json_metodo_costo={}, id_usuario=1, tiene_valor_estimado=estimado, id_calculo_valor_razonable=id_calculo,
    )


class ValoracionesFake:
    def ultimo_calculo(self, _id):
        return _calculo("400", "3800000", id_calculo=90)

    def agregar_calculo(self, _c):
        return 101

    def agregar_medicion(self, _m):
        return 201

    def agregar_variacion(self, _v):
        return 301


class ContabilizadorFake:
    def __init__(self) -> None:
        self.eventos = []

    def asentar(self, linea, _id):
        return linea

    def auditar(self, evento):
        self.eventos.append(evento)


def _evento_medicion(precio: Precio, estimado: bool):
    valorador = SimpleNamespace(valorar=lambda *a, **k: SimpleNamespace(
        es_valido=True, calculo=_calculo("410", "3895000", estimado=estimado), precio=precio))
    contabilizador = ContabilizadorFake()
    activo = SimpleNamespace(id_activo_biologico=7, identificador="BOV-007", especie="Bovino", id_especie=2, id_finca=4,
                             numero_id_tributaria="900")
    Medidor(valorador, ValoracionesFake(), contabilizador).medir(
        activo, PERIODO, DIA, origen="EVENTO", id_usuario=1, id_usuario_auditoria=None, id_evento=55)
    return next(e for e in contabilizador.eventos if e.tipo_evento.startswith("MEDICION_") and "origen" in e.payload)


def test_evento_con_estimacion_trae_motivo_y_precio_historico_usado() -> None:
    evento = _evento_medicion(_precio(vence=date(2026, 10, 31)), estimado=True)

    assert evento.tipo_evento == "MEDICION_CON_ESTIMACION"
    assert evento.payload["motivo_estimacion"] == "SIN_PRECIO_VIGENTE"
    assert evento.payload["descripcion_motivo"] == (
        "No había precio de mercado vigente para la especie Bovino el 2026-11-08: se usó el último precio "
        "conocido, vigente desde el 2026-09-01.")
    assert evento.payload["precio_usado"] == {
        "id_precio_mercado": 12, "precio_unitario": "9500", "unidad_medida": "kg", "fuente": "MERCADO_ACTIVO",
        "fecha_vigencia": "2026-09-01", "fecha_vencimiento": "2026-10-31"}
    # lo que ya traía se conserva
    assert {"origen", "valor_anterior", "valor_actual", "transformacion", "precio"} <= evento.payload.keys()


def test_evento_con_precio_vigente_de_fuente_estimada() -> None:
    evento = _evento_medicion(_precio("ESTIMADA"), estimado=True)

    assert evento.payload["motivo_estimacion"] == "FUENTE_ESTIMADA"
    assert evento.payload["descripcion_motivo"] == (
        "El precio vigente de la especie Bovino es una estimación registrada por el Contador.")


def test_medicion_no_estimada_no_agrega_motivo() -> None:
    evento = _evento_medicion(_precio(), estimado=False)

    assert evento.tipo_evento == "MEDICION_POSTERIOR"
    assert "motivo_estimacion" not in evento.payload and "precio_usado" not in evento.payload


@pytest.mark.parametrize("precio, estimado", [
    (_precio(vence=date(2026, 10, 31)), True),   # cierre que incluye activos sin precio vigente
    (_precio("ESTIMADA"), True),
    (_precio(), False),
])
def test_valorador_marca_estimado_el_precio_congelado_vencido(precio, estimado) -> None:
    config = SimpleNamespace(
        costos_venta_vigentes=lambda _e: SimpleNamespace(pct_transporte=D(0), pct_comisiones=D(0), pct_impuestos=D(0),
                                                         id_parametro_costo_venta=1),
        parametro_especie=lambda _e: None)
    activo = SimpleNamespace(id_activo_biologico=7, identificador="BOV-007", especie="Bovino", id_especie=2,
                             cabezas=1, id_evento_peso=None, magnitud=lambda _c: (D("410"), "kg"))

    resultado = Valorador(None, config).valorar(activo, DIA, 3, 1, precio_congelado=precio)

    assert resultado.es_valido and resultado.calculo.tiene_valor_estimado is estimado
