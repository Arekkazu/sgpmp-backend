# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-14 | Arekkazu | INC-M06-365-G21 RF-84: costos de venta por especie y región |
"""INC-M06-365-G21 / RF-84 precondición 3: los costos de venta se configuran por especie y región.

Sin región, el parámetro es el GENERAL, que vale para las regiones sin uno propio (lo configurado antes sigue
aplicando)."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.financial_valuation.application.use_cases.configuracion.guardar_costos_venta_use_case import (
    GuardarCostosVentaUseCase,
)
from src.financial_valuation.infrastructure.dto.m06_dto import CostosVentaDTO

D = Decimal


@pytest.mark.parametrize("region, guardada", [
    (None, "GENERAL"), ("", "GENERAL"), ("general", "GENERAL"), ("  Córdoba ", "Córdoba"), ("Huila", "Huila"),
])
def test_la_region_se_guarda_y_queda_en_la_auditoria(region, guardada) -> None:
    guardados, eventos = [], []
    caso = GuardarCostosVentaUseCase(
        db=SimpleNamespace(commit=lambda: None, rollback=lambda: None),
        config=SimpleNamespace(guardar_costos_venta=lambda *a: guardados.append(a) or 9),
        auditoria=SimpleNamespace(registrar=eventos.append))

    assert caso.execute(2, D("0.05"), D("0"), D("0"), 1, region) == 9
    assert guardados[0][:2] == (2, guardada)
    assert eventos[0].payload["region"] == guardada


def test_el_dto_acepta_la_region_y_rechaza_una_en_blanco() -> None:
    assert CostosVentaDTO(pct_transporte=D("0.05"), pct_comisiones=D("0"), pct_impuestos=D("0")).region is None
    assert CostosVentaDTO(pct_transporte=D("0.05"), pct_comisiones=D("0"), pct_impuestos=D("0"),
                          region="Huila").region == "Huila"
    with pytest.raises(ValidationError):
        CostosVentaDTO(pct_transporte=D("0.05"), pct_comisiones=D("0"), pct_impuestos=D("0"), region="   ")
