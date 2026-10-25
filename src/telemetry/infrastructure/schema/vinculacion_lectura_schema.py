# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: expone causa y snapshot DB-13 |
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
    causa: Optional[str] = None
    contexto_activo: Optional[dict] = None

    model_config = {'from_attributes': True}


class ListaVinculacionesSchema(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    items: List[VinculacionLecturaSchema]
