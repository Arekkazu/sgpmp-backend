# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-08 | destroyerban | INC-M06-307-G11 RF-83: componentes menores a 0,01 se registran sin línea de valor 0 |
"""INC-M06-307-G11: un componente que trunca a 0,00 no descarta la medición ni el reconocimiento.

(a) Precio 0,01/kg, 400 kg → 400,01 kg: la variación es +0,0001; antes salía MEDICION_SIN_VARIACION y el
valor vigente quedaba en 4,0000. (b) Bruto 1.000 y costos 999,9999: neto 0,0001; antes la línea de
0,00 chocaba con ``ck_linea_asiento_nic41_valor_positivo`` (400 VALOR_NO_PERMITIDO)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.financial_valuation.application.services.medidor import Medidor
from src.financial_valuation.application.services.propuesta_reconocimiento import ProponedorReconocimiento, _hecho
from src.financial_valuation.domain.entities.contabilidad import Periodo
from src.financial_valuation.domain.entities.valoracion import CalculoValor

D = Decimal


def _calculo(magnitud: str, neto: str, id_calculo=None) -> CalculoValor:
    return CalculoValor(
        id_activo_biologico=7, id_precio_mercado=1, id_periodo_contable=3, magnitud=D(magnitud), unidad_magnitud="kg",
        precio_unitario=D("0.01"), valor_razonable_bruto=D(neto), costo_transporte=D(0), costo_comisiones=D(0),
        costo_impuestos_transaccion=D(0), otros_costos_disposicion=D(0), valor_neto=D(neto), metodo_costo="PARAMETRIZADO",
        json_metodo_costo={}, id_usuario=1, id_calculo_valor_razonable=id_calculo,
    )


class ValoracionesFake:
    def __init__(self, anterior: CalculoValor) -> None:
        self.anterior, self.calculos, self.mediciones, self.variaciones = anterior, [], [], []

    def ultimo_calculo(self, _id):
        return self.anterior

    def agregar_calculo(self, calculo):
        self.calculos.append(calculo)
        return 100 + len(self.calculos)

    def agregar_medicion(self, medicion):
        self.mediciones.append(medicion)
        return 200 + len(self.mediciones)

    def agregar_variacion(self, variacion):
        self.variaciones.append(variacion)
        return 300 + len(self.variaciones)


class ContabilizadorFake:
    def __init__(self) -> None:
        self.lineas, self.eventos = [], []

    def asentar(self, linea, _id_usuario):
        self.lineas.append(linea)
        return linea

    def auditar(self, evento):
        self.eventos.append(evento)


def _medir(anterior: CalculoValor, nuevo: CalculoValor):
    valorador = SimpleNamespace(valorar=lambda *a, **k: SimpleNamespace(
        es_valido=True, calculo=nuevo, precio=SimpleNamespace(fuente="MANUAL")))
    valoraciones, contabilizador = ValoracionesFake(anterior), ContabilizadorFake()
    activo = SimpleNamespace(id_activo_biologico=7, id_especie=2, id_finca=4, numero_id_tributaria="900")
    periodo = Periodo(id_periodo_contable=3, numero_id_tributaria="900", tipo_cierre="MENSUAL",
                      fecha_inicio=date(2026, 11, 1), fecha_fin=date(2026, 11, 30), estado="ABIERTO")
    resultado = Medidor(valorador, valoraciones, contabilizador).medir(
        activo, periodo, date(2026, 11, 8), origen="EVENTO", id_usuario=1, id_usuario_auditoria=1, id_evento=55)
    return resultado, valoraciones, contabilizador


@pytest.mark.parametrize("magnitud, neto, signo", [("400.01", "4.0001", 1), ("399.99", "3.9999", -1)])
def test_variacion_de_0_0001_registra_calculo_y_medicion_sin_linea(magnitud, neto, signo) -> None:
    resultado, valoraciones, contabilizador = _medir(_calculo("400", "4.0000", 90), _calculo(magnitud, neto))

    assert resultado.estado == "MEDIDO"
    assert resultado.calculo.valor_neto == D(neto)  # el valor vigente avanza
    assert resultado.variacion_total == D("0.0001") * signo
    assert len(valoraciones.calculos) == 1 and len(valoraciones.mediciones) == 1
    assert valoraciones.variaciones == [] and contabilizador.lineas == []  # nada que asentar a 2 decimales
    tipos = [e.tipo_evento for e in contabilizador.eventos]
    assert "MEDICION_SIN_VARIACION" not in tipos and tipos[-1] == "MEDICION_POSTERIOR"
    assert contabilizador.eventos[-1].payload["componentes_sin_asiento"] == [
        {"componente": "TRANSFORMACION_BIOLOGICA", "monto": str(D("0.0001") * signo)}]


def test_sin_variacion_real_sigue_siendo_medicion_sin_variacion() -> None:
    resultado, valoraciones, contabilizador = _medir(_calculo("400", "4.0000", 90), _calculo("400", "4.0000"))

    assert resultado.estado == "SIN_VARIACION"
    assert valoraciones.calculos == [] and valoraciones.mediciones == []
    assert [e.tipo_evento for e in contabilizador.eventos] == ["MEDICION_SIN_VARIACION"]


def test_variacion_de_un_centavo_o_mas_sigue_con_variacion_y_linea() -> None:
    _, valoraciones, contabilizador = _medir(_calculo("400", "4.0000", 90), _calculo("401", "4.0100"))

    assert len(valoraciones.variaciones) == 1
    [linea] = contabilizador.lineas
    assert linea.valor == D("0.01") and linea.sentido == "GANANCIA"


def test_hecho_que_trunca_a_cero_no_genera_linea() -> None:
    assert _hecho("RECONOCIMIENTO_NACIMIENTO", "UNICO", D("0.0001")) == []
    assert _hecho("RECONOCIMIENTO_NACIMIENTO", "UNICO", D("0.0099")) == []
    assert _hecho("RECONOCIMIENTO_NACIMIENTO", "UNICO", D("12.3456")) == [
        ("RECONOCIMIENTO_NACIMIENTO", "UNICO", D("12.34"))]


@pytest.mark.parametrize("origen", ["nacimiento", "donacion", "transferencia_interna"])
def test_reconocimiento_con_neto_0_0001_queda_sin_linea(origen) -> None:
    assert ProponedorReconocimiento._hechos_valor_razonable(origen, D("0.0001"), D("0")) == []


def test_reconocimiento_de_compra_con_diferencia_menor_a_un_centavo_queda_sin_linea() -> None:
    assert ProponedorReconocimiento._hechos_valor_razonable("compra", D("1000.0000"), D("999.9999")) == []
