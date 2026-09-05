"""Response schemas para la bitácora de auditoría de M05 (RF-80, CU-06)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import ConfigDict

from src.shared.base_dto import BaseDTO


class EventoAuditoriaSuministroResponse(BaseDTO):
    model_config = ConfigDict(from_attributes=True)

    id_auditoria_suministro: int
    entidad_afectada: str
    tipo_operacion: str
    id_usuario: int
    resultado: str
    fecha_evento: datetime
    datos_anteriores: Optional[dict] = None
    datos_nuevos: Optional[dict] = None
    ip_origen: Optional[str] = None
    id_sesion: Optional[int] = None
    fecha_emision: Optional[datetime] = None
    id_activo_biologico: Optional[int] = None
    id_ciclo_productivo: Optional[int] = None
    costo_afectado: Optional[Decimal] = None
    origen_precio: Optional[str] = None
    clasificacion_registro: Optional[str] = None
    retencion_aplicable: Optional[str] = None
    hash_integridad: Optional[str] = None
    registro_incompleto: Optional[bool] = None
    detalle_causa: Optional[str] = None
    numero_reintentos: Optional[int] = None
    fecha_intentos: Optional[list[datetime]] = None
    id_gestion_fases: Optional[int] = None


class AuditoriaSuministrosListResponse(BaseDTO):
    total: int
    pagina: int
    registros_por_pagina: int
    items: list[EventoAuditoriaSuministroResponse]
