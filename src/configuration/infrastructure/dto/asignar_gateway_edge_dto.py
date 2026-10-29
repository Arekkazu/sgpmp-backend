"""DTO de entrada para asignar o quitar el Gateway Edge de un dispositivo IoT (RF-21)."""
from __future__ import annotations

from typing import Optional

from pydantic import PositiveInt

from src.shared.base_dto import BaseDTO


class AsignarGatewayEdgeDTO(BaseDTO):
    """Gateway Edge del que cuelga el dispositivo; ``null`` lo desasigna."""
    # null: el dispositivo deja de depender de un Gateway Edge.
    id_dispositivo_gateway: Optional[PositiveInt] = None
