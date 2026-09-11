"""Pruebas de BaseDTO (INC-M02-57-G06).

Un byte nulo embebido en un campo de texto libre no lo rechazaba ninguna
validación de entrada; llegaba hasta psycopg2, que lo rechaza con un
ValueError de Python plano no reconocido por el traductor de errores de base
de datos, y salía como 500 en vez del 400/422 controlado.
"""
import pytest
from pydantic import ValidationError

from src.shared.base_dto import BaseDTO


class _DTOConTexto(BaseDTO):
    nombre: str
    etiquetas: list[str] = []


def test_rechaza_byte_nulo_en_un_campo_de_texto() -> None:
    with pytest.raises(ValidationError, match="caracteres nulos"):
        _DTOConTexto(nombre="hola\x00mundo")


def test_rechaza_byte_nulo_dentro_de_una_lista_de_texto() -> None:
    with pytest.raises(ValidationError, match="caracteres nulos"):
        _DTOConTexto(nombre="ok", etiquetas=["bien", "mal\x00o"])


def test_acepta_texto_normal() -> None:
    dto = _DTOConTexto(nombre="Especie Bovina", etiquetas=["carne", "leche"])

    assert dto.nombre == "Especie Bovina"
    assert dto.etiquetas == ["carne", "leche"]
