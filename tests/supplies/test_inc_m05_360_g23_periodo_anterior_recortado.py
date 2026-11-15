# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-13 | Arekkazu | INC-M05-360-G23 RF-77: nota de recorte con el período anterior entero antes del ciclo |
"""INC-M05-360-G23 / RF-77 paso 6: si el período anterior equivalente cae antes del inicio del ciclo, el
reporte lo recorta y lo dice, también cuando el recorte lo deja vacío (antes salía solo «sin base comparativa»)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.supplies.application.use_cases.reporte_gastos.generar_reporte_gastos_use_case import (
    GenerarReporteGastosUseCase,
)
from src.supplies.domain.entities.reporte_gasto import FiltrosReporteGasto
from src.supplies.domain.services.calculadora_reporte_gasto import CalculadoraReporteGasto

NOTA_RECORTE = "El período anterior fue recortado al inicio del ciclo productivo (2026-01-01)."


def _caso(consultas: list) -> GenerarReporteGastosUseCase:
    detalle = SimpleNamespace(consultar=lambda **k: consultas.append(k) or [SimpleNamespace(monto=Decimal("4"))])
    return GenerarReporteGastosUseCase(None, detalle, None, None, None, None, None, None)


def test_periodo_anterior_entero_antes_del_ciclo_se_nota_como_recortado() -> None:
    consultas: list = []
    filtros = FiltrosReporteGasto(date(2026, 1, 1), date(2026, 7, 31), "MENSUAL", id_activo_biologico=57)

    gasto, recortado, fecha = _caso(consultas)._periodo_anterior(
        filtros, SimpleNamespace(fecha_inicio_ciclo=date(2026, 1, 1)), None)

    assert (gasto, recortado, fecha) == (Decimal(0), True, date(2026, 1, 1))
    assert consultas == []  # no hay rango que consultar
    tendencia = CalculadoraReporteGasto()._tendencia(Decimal(10), gasto, recortado, fecha)
    assert tendencia.estado == "SIN_BASE_COMPARATIVA"
    assert tendencia.nota == ("No existen gastos registrados en el período anterior equivalente. No es posible "
                              f"calcular variación porcentual. {NOTA_RECORTE}")


@pytest.mark.parametrize("inicio_ciclo, recorte", [(date(2025, 12, 1), date(2025, 12, 1)), (date(2025, 1, 1), None)])
def test_recorte_parcial_y_sin_recorte_siguen_igual(inicio_ciclo, recorte) -> None:
    consultas: list = []
    filtros = FiltrosReporteGasto(date(2026, 1, 1), date(2026, 7, 31), "MENSUAL", id_activo_biologico=57)

    gasto, recortado, fecha = _caso(consultas)._periodo_anterior(
        filtros, SimpleNamespace(fecha_inicio_ciclo=inicio_ciclo), None)

    assert (gasto, recortado, fecha) == (Decimal(4), recorte is not None, recorte)
    assert consultas[0]["fecha_inicio"] == (recorte or date(2025, 6, 3))
    assert consultas[0]["fecha_fin"] == date(2025, 12, 31)
