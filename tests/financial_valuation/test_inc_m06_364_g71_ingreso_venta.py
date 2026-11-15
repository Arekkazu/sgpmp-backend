# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-15 | Arekkazu | INC-M06-364-G71 RF-45/RF-93: ingreso por venta de activos en el estado de resultados |
"""INC-M06-364-G71 / RF-93: lo recibido por una venta es ingreso; su valor en libros sigue en GASTOS.

Con valor en libros X y venta por Y, el estado muestra Y en ingresos y X en gastos: el neto es Y − X, la utilidad
(o la pérdida) de la venta. No hay línea de asiento por la venta: la factura va a la contabilidad externa."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.biological_assets.infrastructure.dto.registrar_evento_baja_dto import RegistrarEventoBajaDTO
from src.financial_valuation.application.services.reportes import ConstructorEstadoResultados
from src.financial_valuation.domain.services.consolidacion import INGRESOS, MovimientoResultado, estado_resultados

D = Decimal


def _baja(sentido: str, valor: str, venta: str | None = None, reverso: bool = False) -> MovimientoResultado:
    return MovimientoResultado("BAJA_ACTIVO", sentido, D(valor), reverso, D(venta) if venta is not None else None)


@pytest.mark.parametrize("venta, neto", [("1500", D("500")), ("800", D("-200"))])  # utilidad y pérdida
def test_la_venta_es_ingreso_y_su_valor_en_libros_gasto(venta, neto) -> None:
    estado = estado_resultados([_baja("UNICO", "1000", venta)], [])

    assert "ingresos_venta_activos" in INGRESOS
    assert estado.componentes["ingresos_venta_activos"] == D(venta)
    assert estado.componentes["bajas_activos"] == D("1000")
    assert estado.resultado_neto == neto


def test_sin_valor_de_venta_o_sin_venta_no_hay_ingreso_y_el_reverso_resta() -> None:
    estado = estado_resultados([_baja("UNICO", "700"),                          # sacrificio o venta sin valor
                                _baja("PERDIDA", "300"),                        # muerte
                                _baja("UNICO", "1000", "1500"),
                                _baja("UNICO", "1000", "1500", reverso=True)], [])

    assert estado.componentes["ingresos_venta_activos"] == 0
    assert estado.componentes["bajas_activos"] == D("700")
    assert estado.componentes["perdidas_bajas_sin_recuperacion"] == D("300")


def test_el_estado_avisa_cuantas_ventas_no_tienen_valor() -> None:
    movimientos = [
        {"tipo_hecho": "BAJA_ACTIVO", "sentido": "UNICO", "valor": "1000", "es_reverso": False,
         "tipo_baja": "venta", "valor_venta": D("1500")},
        {"tipo_hecho": "BAJA_ACTIVO", "sentido": "UNICO", "valor": "400", "es_reverso": False,
         "tipo_baja": "venta", "valor_venta": None},
        {"tipo_hecho": "BAJA_ACTIVO", "sentido": "UNICO", "valor": "200", "es_reverso": False,
         "tipo_baja": "sacrificio", "valor_venta": None},
    ]
    constructor = ConstructorEstadoResultados(SimpleNamespace(movimientos=lambda *a: movimientos),
                                              SimpleNamespace(del_periodo=lambda *a: []))

    calculo = constructor.calcular(4, {})

    assert calculo["componentes"]["ingresos_venta_activos"] == "1500.0000"
    assert calculo["ventas_sin_valor"] == 1  # el sacrificio no es venta
    assert calculo["resultado_neto"] == D("-100.0000")  # 1.500 − (1.000 + 400 + 200)


def _dto(**extra) -> RegistrarEventoBajaDTO:
    return RegistrarEventoBajaDTO(fecha_baja=date(2026, 11, 14), motivo_baja="Venta en feria", **extra)


def test_la_baja_por_venta_acepta_valor_y_referencia() -> None:
    dto = _dto(tipo_baja="venta", valor_venta=D("4500000"), referencia_venta="  FE-1023 ")
    assert (dto.valor_venta, dto.referencia_venta) == (D("4500000"), "FE-1023")
    assert _dto(tipo_baja="venta").valor_venta is None  # opcional: las ventas sin valor siguen registrándose
    assert _dto(tipo_baja="venta", referencia_venta="   ").referencia_venta is None


@pytest.mark.parametrize("extra", [
    {"tipo_baja": "muerte", "valor_venta": D("100")},            # solo una venta tiene valor
    {"tipo_baja": "sacrificio", "referencia_venta": "FE-1"},
    {"tipo_baja": "venta", "valor_venta": D("0")},               # mayor que cero
    {"tipo_baja": "venta", "valor_venta": D("10.123")},          # dos decimales
])
def test_valor_o_referencia_invalidos_se_rechazan(extra) -> None:
    with pytest.raises(ValidationError):
        _dto(**extra)
