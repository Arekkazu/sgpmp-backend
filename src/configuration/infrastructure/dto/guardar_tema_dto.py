"""DTO de entrada para guardar la preferencia de tema visual (PATCH RF-27)."""
from pydantic import field_validator

from src.shared.base_dto import BaseDTO


class GuardarTemaDTO(BaseDTO):
    theme_mode: int

    @field_validator("theme_mode")
    @classmethod
    def validar_theme_mode(cls, v: int) -> int:
        if v not in (1, 2, 3):
            raise ValueError(
                f"El identificador de tema '{v}' no es válido. "
                "Los valores permitidos son 1 (Claro), 2 (Oscuro) o 3 (Automático)."
            )
        return v
