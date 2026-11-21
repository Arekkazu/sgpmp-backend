"""TC-M04-G042 — TC-M04-004.

La matriz original señala que Wfs/Wfa/Wfd no están en el texto de RF-65.
En este repositorio sí existen en ConfigurarMotorDTO / ConfigurarMotorUseCase
como w_factor_sanitario, w_factor_ambiental y w_factor_densidad (suma = 1.0).
No hay validación de rango individual 0–1.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

from src.shared.errors import BusinessRuleError

_MOD4 = Path(__file__).resolve().parents[2]
if str(_MOD4) not in sys.path:
    sys.path.insert(0, str(_MOD4))
from rf65_dobles import dto_motor, ensamblar  # noqa: E402


def test_tc_m04_004_pesos_validos_suma_uno() -> None:
    uc, repo, _, _, _, _ = ensamblar()
    entidad, _ = uc.execute(
        dto_motor(
            w_factor_sanitario=Decimal("0.400"),
            w_factor_ambiental=Decimal("0.300"),
            w_factor_densidad=Decimal("0.300"),
        ),
        id_usuario=1,
    )
    assert entidad.w_factor_sanitario + entidad.w_factor_ambiental + entidad.w_factor_densidad == Decimal("1.000")
    assert repo.obtener_por_tipo(entidad.tipo_modelo).w_factor_sanitario == Decimal("0.400")


def test_tc_m04_004_suma_distinta_de_uno_rechaza() -> None:
    uc, repo, _, _, _, _ = ensamblar()
    uc.execute(dto_motor(), id_usuario=1)
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(
            dto_motor(
                w_factor_sanitario=Decimal("0.500"),
                w_factor_ambiental=Decimal("0.300"),
                w_factor_densidad=Decimal("0.300"),
            ),
            id_usuario=1,
        )
    assert exc.value.code == "PESOS_CONTAGIO_INVALIDOS"
    assert repo.obtener_por_tipo("MODELO_ESPECIES_GRANDES").config_version == 1


def test_tc_m04_004_rango_individual_0_1_no_esta_en_el_use_case() -> None:
    """Hallazgo: suma 1.0 con peso negativo es aceptada. La matriz exige rango 0–1."""
    uc, _, _, _, _, _ = ensamblar()
    entidad, _ = uc.execute(
        dto_motor(
            w_factor_sanitario=Decimal("-0.100"),
            w_factor_ambiental=Decimal("0.600"),
            w_factor_densidad=Decimal("0.500"),
        ),
        id_usuario=1,
    )
    assert entidad.w_factor_sanitario == Decimal("-0.100")
