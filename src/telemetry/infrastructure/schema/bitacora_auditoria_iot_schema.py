# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-47 RF-63: distingue compromiso evidencia incompleta y avisos |
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EventoAuditoriaIotSchema(BaseModel):
    """componente_origen no se expone al usuario (campo interno de enrutamiento)."""

    model_config = ConfigDict(from_attributes=True)

    id_evento: UUID
    id_usuario: Optional[int]
    nombre_usuario: Optional[str]
    tipo_evento: str
    modulo: str
    descripcion: Optional[str]
    resultado: str
    direccion_ip: Optional[str]
    user_agent: Optional[str]
    id_sesion: Optional[UUID]
    fecha_hora: datetime
    accion_detallada: Optional[dict]
    entidad_afectada_tipo: Optional[str]
    entidad_afectada_id: Optional[str]
    severidad_log: str
    hash_integridad: str
    clasificacion_registro: str
    retencion_aplicable: int
    registro_incompleto: bool
    timestamp_registro: Optional[datetime]
    integridad_comprometida: bool = False


class ListaAuditoriaIotSchema(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    items: list[EventoAuditoriaIotSchema]


class VerificacionIntegridadSchema(BaseModel):
    total_verificados: int
    comprometidos: int
    ids_comprometidos: list[str]
    ids_sin_hash: list[str] = Field(default_factory=list)
    ids_incompletos: list[str] = Field(default_factory=list)
    incidentes_creados: int = 0
    notificaciones_pendientes: int = 0
