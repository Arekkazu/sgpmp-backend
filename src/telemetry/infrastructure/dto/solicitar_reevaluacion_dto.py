# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo y DTO |
"""DTO para solicitar la reevaluación de las lecturas de un sensor en un rango.

Incluye la causa documentada y, opcionalmente, los parámetros correctos con
los que debe repetirse la evaluación.
"""

from pydantic import Field

from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc


class SolicitarReevaluacionDTO(BaseDTO):
    """Datos de una solicitud de reevaluación de lecturas."""

    id_sensor: int = Field(..., gt=0)
    fecha_desde: FechaHoraUtc
    fecha_hasta: FechaHoraUtc
    causa_documentada: str = Field(..., min_length=10, max_length=1000)
    parametros_correctos: dict | None = None
