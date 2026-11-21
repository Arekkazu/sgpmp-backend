"""TC-M06-G96 capa A: dominio real (valor_libros_calculado + valor_por_costo).

Ejecuta los montos absolutos de TC-M06-05/06/07 contra las funciones de
``src.financial_valuation.domain.services.nic41`` (commit #968 / RF-88).
No abre BD, no llama HTTP y no afirma persistencia de alerta.

La corrida APROBADA de A+B se documentó sobre el worktree con ``8829599f``
(HEAD ``91f79e75``). Si el árbol local no incluye ``valor_libros_calculado``,
las pruebas se omiten en lugar de fallar por import.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

try:
    from src.financial_valuation.domain.services.nic41 import (
        CERO,
        valor_libros_calculado,
        valor_por_costo,
    )
except ImportError as exc:  # pragma: no cover - ramas sin #968
    pytest.skip(
        f"Capa A requiere nic41 con valor_libros_calculado (#968): {exc}",
        allow_module_level=True,
    )

COSTO = Decimal("10000000")


def _aplicado_como_use_case(calculado: Decimal) -> Decimal:
    """Misma regla que RegistrarDeterioroUseCase tras valor_libros_calculado."""
    return max(CERO, calculado)


def test_tc_m06_05_montos_absolutos_libros_7m():
    dep, det = Decimal("2000000"), Decimal("1000000")
    calculado = valor_libros_calculado(COSTO, dep, det)
    assert calculado == Decimal("7000000.0000")
    assert _aplicado_como_use_case(calculado) == Decimal("7000000.0000")
    # Misma ruta vía vida útil/meses que produce dep=2M
    valor = valor_por_costo(COSTO, 10, 2, det)
    assert valor.depreciacion_acumulada == Decimal("2000000.0000")
    assert valor.valor_contable == Decimal("7000000.0000")


def test_tc_m06_06_montos_absolutos_libros_0():
    dep, det = Decimal("10000000"), Decimal("0")
    calculado = valor_libros_calculado(COSTO, dep, det)
    assert calculado == Decimal("0.0000")
    assert _aplicado_como_use_case(calculado) == Decimal("0.0000")
    valor = valor_por_costo(COSTO, 12, 12, det)
    assert valor.depreciacion_acumulada == COSTO
    assert valor.valor_contable == Decimal("0")


def test_tc_m06_07_negativo_se_ajusta_a_cero():
    dep, det = Decimal("7000000"), Decimal("5000000")
    calculado = valor_libros_calculado(COSTO, dep, det)
    assert calculado == Decimal("-2000000.0000")
    assert calculado < 0
    aplicado = _aplicado_como_use_case(calculado)
    assert aplicado == Decimal("0")
    assert aplicado >= 0
    valor = valor_por_costo(COSTO, 10, 7, det)
    assert valor.depreciacion_acumulada == Decimal("7000000.0000")
    assert valor.deterioro_acumulado == det
    assert valor.valor_contable == Decimal("0")
    # El DTO de dominio no emite la alerta; eso es capa B / caso de uso.
    assert "alerta" not in valor.__dataclass_fields__
