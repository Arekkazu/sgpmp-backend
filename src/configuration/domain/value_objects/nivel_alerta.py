"""Value object: nivel de alerta semafórica (normal / precaucion / critico)."""
from __future__ import annotations

from enum import Enum

from src.shared.errors import ValidationError


class NivelAlerta(str, Enum):
    normal = 'normal'
    precaucion = 'precaucion'
    critico = 'critico'

    @classmethod
    def desde_string(cls, valor: str) -> 'NivelAlerta':
        try:
            return cls(valor.lower())
        except ValueError:
            validos = ', '.join(m.value for m in cls)
            raise ValidationError(
                code='NIVEL_ALERTA_INVALIDO',
                message=f"Nivel de alerta inválido: '{valor}'. Valores permitidos: {validos}.",
                field='nivel',
            )
