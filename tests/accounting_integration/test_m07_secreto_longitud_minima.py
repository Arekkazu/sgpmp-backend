"""RNF-101.1: un secreto provisto debe tener al menos 256 bits."""
import pytest

from src.accounting_integration.domain.value_objects import secreto_cliente
from src.shared.errors import ValidationError


def test_rechaza_un_secreto_de_16_caracteres():
    with pytest.raises(ValidationError):
        secreto_cliente.hashear("a" * 16)


def test_rechaza_42_y_acepta_43():
    with pytest.raises(ValidationError):
        secreto_cliente.hashear("a" * 42)
    assert secreto_cliente.coincide("a" * 43, secreto_cliente.hashear("a" * 43))


def test_un_secreto_generado_cumple_el_minimo():
    generado = secreto_cliente.generar()
    assert len(generado) >= secreto_cliente.LONGITUD_MINIMA
    assert secreto_cliente.coincide(generado, secreto_cliente.hashear(generado))
