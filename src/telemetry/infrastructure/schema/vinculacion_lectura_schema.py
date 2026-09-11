from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class VinculacionLecturaSchema(BaseModel):
    id_vinculacion_lectura: int
    id_telemetria: int
    modelo_manejo: str
    id_activo_biologico: Optional[int] = None
    id_infraestructura: int
    fecha_inicio_vinculacion: datetime
    fecha_fin_vinculacion: Optional[datetime] = None
    mecanismo_vinculacion: str
    estado_vinculacion: str
    id_usuario: Optional[int] = None
    motivo_correccion: Optional[str] = None
    id_vinculacion_reemplazada: Optional[int] = None
    fecha_creacion: datetime

    model_config = {'from_attributes': True}


class ListaVinculacionesSchema(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    items: List[VinculacionLecturaSchema]
