# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""DTO de entrada de ``POST /activos-biologicos/{id_activo}/eventos/reproductivo``
(RF-42).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc


class RegistrarEventoReproductivoDTO(BaseDTO):
    """Evento reproductivo.

    ``categoria``: ``servicio`` | ``inseminacion`` | ``diagnostico`` | ``parto`` | ``aborto`` |
    ``nacimiento``. ``resultado``: ``exitoso`` | ``fallido``. ``numero_crias`` (>= 1) es
    obligatorio en ``parto``, ``aborto`` y ``nacimiento``.
    """
    categoria: Literal['servicio', 'inseminacion', 'diagnostico', 'parto', 'aborto', 'nacimiento']
    resultado: Literal['exitoso', 'fallido']
    fecha: Optional[FechaHoraUtc] = None
    id_padre: Optional[int] = Field(default=None, gt=0)
    id_madre: Optional[int] = Field(default=None, gt=0)
    numero_crias: int = Field(default=0, ge=0)
    descripcion: Optional[str] = None
