# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |

from pydantic import Field

from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc


class SolicitarReevaluacionDTO(BaseDTO):
    id_sensor: int = Field(..., gt=0)
    fecha_desde: FechaHoraUtc
    fecha_hasta: FechaHoraUtc
    causa_documentada: str = Field(..., min_length=10, max_length=1000)
    parametros_correctos: dict | None = None
