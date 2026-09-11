"""DTO de entrada para generar la versión siguiente de una plantilla (RF-30, RF-31)."""
from __future__ import annotations

from typing import Any

from pydantic import field_validator

from src.configuration.domain.esquema_plantilla import validar_snapshot
from src.shared.base_dto import BaseDTO


class VersionarPlantillaDTO(BaseDTO):
    """Parámetros de la versión nueva.

    Solo viaja el snapshot: el nombre y la especie identifican a la plantilla y
    los hereda de la versión anterior. Cambiarlos sería crear otra plantilla,
    no versionar esta — y el RF exige que el nombre siga siendo el mismo para
    que la familia de versiones tenga sentido.
    """

    params_snapshot: dict[str, Any]

    @field_validator('params_snapshot')
    @classmethod
    def validar_estructura_snapshot(cls, v: dict) -> dict:
        """Mismo esquema que al crear: una versión nueva no relaja las reglas."""
        errores = validar_snapshot(v)
        if errores:
            raise ValueError(' '.join(errores))
        return v
