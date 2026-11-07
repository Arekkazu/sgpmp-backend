# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-53: captura de la cámara que reenvía el broker                |
"""Captura de una ventana de visión: la manda el nodo junto al sobre D4 y el broker la separa."""
from typing import Optional

from pydantic import AwareDatetime, Field, StrictInt, StrictStr

from src.shared.base_dto import BaseDTO


class CapturaVisionDTO(BaseDTO):
    serial: StrictStr = Field(min_length=1, max_length=50)
    area_id: StrictInt = Field(gt=0)
    ventana_fin: AwareDatetime
    n_individuos_observados: Optional[StrictInt] = Field(default=None, ge=0)
    # 500 KB de JPEG son ~667 000 caracteres en base64.
    imagen_jpeg_base64: StrictStr = Field(min_length=4, max_length=700_000)
