"""DTO de entrada para anular un registro de suministro (RF-75 / RF-76).

La validación estricta de longitud (mínimo 20) la realiza el value object
``JustificacionAnulacion`` en el caso de uso, para producir un error de dominio
uniforme.
"""
from __future__ import annotations

from src.shared.base_dto import BaseDTO


class AnularRegistroDTO(BaseDTO):
    """Justificación obligatoria para anular un registro VALIDADO."""

    justificacion_anulacion: str
