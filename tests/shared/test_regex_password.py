# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-11-24 | Arekkazu         | RF-01: * cuenta como especial en la contraseña |
"""La política de contraseña del registro acepta los mismos especiales que muestra el front."""
import pytest

from src.shared.regex import PASSWORD


@pytest.mark.parametrize("especial", list("@#$%^&+=!*"))
def test_cada_especial_del_front_cumple_la_politica(especial):
    assert PASSWORD.match(f"Clave123{especial}")


def test_sin_especial_se_rechaza():
    assert not PASSWORD.match("Clave1234")
