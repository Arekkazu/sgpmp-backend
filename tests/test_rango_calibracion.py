"""Test unitario del rango de seguridad de calibración por tipo de sensor (RF-24).

Pura lógica de dominio, sin DB. Ejecutable con `pytest` o `python -m`.
"""
from decimal import Decimal

from src.configuration.domain.entities.rango_calibracion import RangoCalibracion


def test_verificar_rango_calibracion() -> None:
    rango = RangoCalibracion(categoria="TEMPERATURA", valor_min=Decimal("0"), valor_max=Decimal("45"))

    # Dentro de rango (incluye los extremos) -> None
    assert rango.verificar(Decimal("0")) is None
    assert rango.verificar(Decimal("25.5")) is None
    assert rango.verificar(Decimal("45")) is None

    # Fuera de rango -> dict con min/max/valor (el caso del RF: offset de 500 °C)
    viol = rango.verificar(Decimal("500"))
    assert viol == {"min": Decimal("0"), "max": Decimal("45"), "valor": Decimal("500")}

    # Negativo fuera de rango (ej. pH -5 con un rango PH 0..14)
    ph = RangoCalibracion(categoria="PH", valor_min=Decimal("0"), valor_max=Decimal("14"))
    assert ph.verificar(Decimal("-5")) is not None


if __name__ == "__main__":
    test_verificar_rango_calibracion()
    print("OK")
