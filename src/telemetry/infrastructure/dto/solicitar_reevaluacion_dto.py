from datetime import datetime

from pydantic import Field

from src.shared.base_dto import BaseDTO


class SolicitarReevaluacionDTO(BaseDTO):
    id_sensor: int = Field(..., gt=0)
    fecha_desde: datetime
    fecha_hasta: datetime
    causa_documentada: str = Field(..., min_length=10, max_length=1000)
    parametros_correctos: dict | None = None
