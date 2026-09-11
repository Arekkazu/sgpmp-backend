from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field

from src.shared.base_dto import BaseDTO


class RegistrarEventoReproductivoDTO(BaseDTO):
    categoria: Literal['servicio', 'inseminacion', 'diagnostico', 'parto', 'aborto', 'nacimiento']
    resultado: Literal['exitoso', 'fallido']
    fecha: Optional[datetime] = None
    id_padre: Optional[int] = Field(default=None, gt=0)
    id_madre: Optional[int] = Field(default=None, gt=0)
    numero_crias: int = Field(default=0, ge=0)
    descripcion: Optional[str] = None
