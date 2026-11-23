# | Fecha      | Nombre  | Que se hizo                                         |
# |------------|---------|-----------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-30 RF-57: deriva CERRADA a validacion de dominio  |
# | 2026-10-28 | destroyerban | INC-M03-172-G79 RF-57 CA-11: estado no catalogado (FINALIZADA, vacío, null) → 422 TRANSICION_INVALIDA |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, DTO y validador |
"""DTO de entrada para cambiar el estado de una alerta (RF-57).

El estado no catalogado se rechaza en el caso de uso como transición inválida
(422); aquí solo se valida la forma y se normaliza a mayúsculas.
"""
from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator

from src.shared.base_dto import BaseDTO


class ActualizarEstadoAlertaDTO(BaseDTO):
    """Datos para transicionar una alerta a un nuevo estado, con motivo opcional."""

    # CA-11 (RFC-008): un estado no catalogado —CERRADA, FINALIZADA, vacío o null— no es un error de
    # forma sino una transición inválida; lo rechaza el caso de uso con 422 TRANSICION_INVALIDA.
    # El campo sigue siendo obligatorio y de texto: omitirlo o mandar otro tipo es 400 VAL_ENTRADA.
    nuevo_estado: Optional[str] = Field(..., max_length=50)
    motivo: Optional[str] = Field(default=None, max_length=500)

    @field_validator('nuevo_estado')
    @classmethod
    def normalizar_estado(cls, v: Optional[str]) -> Optional[str]:
        """Normaliza el estado a mayúsculas; ``None`` se conserva."""
        return v.upper() if v is not None else None
