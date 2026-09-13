"""Tipo primitivo esperado para un atributo dinámico configurado en RF-16."""
from __future__ import annotations

from enum import Enum

from src.shared.errors import ValidationError


class TipoDatoAtributo(str, Enum):
    NUMERICO = "NUMERICO"
    ENTERO = "ENTERO"
    TEXTO = "TEXTO"
    BOOLEANO = "BOOLEANO"

    @classmethod
    def desde_string(cls, valor: str) -> "TipoDatoAtributo":
        normalizado = valor.strip().upper()
        try:
            return cls(normalizado)
        except ValueError as exc:
            opciones = ", ".join(item.value for item in cls)
            raise ValidationError(
                code="TIPO_DATO_ATRIBUTO_INVALIDO",
                message=f"El tipo de dato debe ser uno de: {opciones}.",
                field="tipo_dato",
            ) from exc

    @classmethod
    def inferir_desde_tipo_medicion(cls, tipo_medicion: str) -> "TipoDatoAtributo":
        """Conserva compatibilidad con configuraciones creadas antes de #208."""
        normalizado = tipo_medicion.strip().upper()
        if normalizado == "CONTEO":
            return cls.ENTERO
        if normalizado in {"PESO", "VOLUMEN", "LONGITUD"}:
            return cls.NUMERICO
        return cls.TEXTO
