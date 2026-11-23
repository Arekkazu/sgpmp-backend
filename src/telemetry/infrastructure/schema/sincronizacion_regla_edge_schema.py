# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo y schemas |
"""Schemas del estado de sincronización de reglas con los Gateway Edge (RF-55).

Detalla, por nodo y de forma consolidada, si la versión vigente de una regla ya
fue aplicada, está pendiente o no se confirmó.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SincronizacionReglaNodoSchema(BaseModel):
    """Estado de sincronización de una regla en un Gateway Edge concreto."""

    id_dispositivo_iot: int
    serial: str
    version_regla: int = Field(description="Versión de la regla que se envió en el último intento.")
    estado_sincronizacion: str = Field(description="APLICADA | PENDIENTE | NO_CONF")
    mensaje: Optional[str] = None
    intentos_sincronizacion: int
    fecha_ultimo_intento: datetime
    fecha_aplicacion: Optional[datetime] = Field(
        default=None, description="Última vez que este Gateway confirmó la regla con ACK_REGLA."
    )

    model_config = {'from_attributes': True}


class SincronizacionReglaSchema(BaseModel):
    """Estado consolidado de sincronización de una regla con todos sus nodos."""

    id_regla_alertas: int
    version_regla: int = Field(description="Versión vigente de la regla.")
    estado: str = Field(description="Estado consolidado: APLICADA | PENDIENTE | NO_CONF")
    mensaje: str
    nodos: List[SincronizacionReglaNodoSchema]

    model_config = {'from_attributes': True}
