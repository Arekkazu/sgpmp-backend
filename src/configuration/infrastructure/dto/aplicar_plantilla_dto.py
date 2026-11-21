# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""DTO de entrada para aplicar una plantilla a una especie destino (RF-32)."""
from __future__ import annotations

from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc


class AplicarPlantillaDTO(BaseDTO):
    """Campos requeridos para aplicar una plantilla.

    Attributes:
        id_especie_destino: Especie sobre la que se aplica la plantilla.
        fecha_actualizacion_especie_destino: Timestamp de última actualización de la
            especie destino, tal como lo vio el cliente. Usado para detección de
            concurrencia optimista: si la especie fue modificada entre que el usuario
            vio el resumen y confirmó, se rechaza.
    """

    id_especie_destino: int
    fecha_actualizacion_especie_destino: FechaHoraUtc | None
