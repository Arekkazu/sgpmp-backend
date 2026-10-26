# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: expone causa y snapshot DB-13 |
# | 2026-10-25 | Arekkazu | USAB-M03 T-18 RF-61: nombres de activo, área, finca, variable y usuario (read-model) |
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
    # T-18: nombres para no mostrar solo IDs. Los IDs siguen para filtrar y resolver.
    nombre_activo: Optional[str] = None
    especie_activo: Optional[str] = None  # para nombrar activos sin identificador
    nombre_infraestructura: Optional[str] = None
    nombre_finca: Optional[str] = None
    nombre_variable: Optional[str] = None
    nombre_sensor: Optional[str] = None
    valor_lectura: Optional[float] = None
    unidad_lectura: Optional[str] = None
    fecha_lectura: Optional[datetime] = None
    nombre_usuario: Optional[str] = None

    model_config = {'from_attributes': True}


class ListaVinculacionesSchema(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    items: List[VinculacionLecturaSchema]
