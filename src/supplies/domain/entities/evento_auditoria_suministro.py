# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-08 | Leandro | INC-M05-278-G39 RF-80: transportar UUID y versión del hash sin objetos ORM. |
# | 2026-11-11 | Arekkazu | USAB-M05-M06 T-01 RF-75/76/80: nombre del activo y del usuario en las consultas, no su id |
"""Entidad de lectura de un evento de ``modulo5.auditorias_suministros`` (RF-80, CU-06).

Distinta de ``EventoAuditoriaSuministro`` (``auditoria_suministro_port.py``),
que es el DTO angosto de escritura de RF-78/79 sin PK/hash/fechas. Esta
entidad refleja la fila completa tal como la persistió el trigger
``trg_audit_hash`` (hash, retención, timestamps).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class EventoAuditoriaSuministroConsulta:
    id_auditoria_suministro: int
    entidad_afectada: str
    tipo_operacion: str
    id_usuario: int
    resultado: str
    fecha_evento: datetime
    datos_anteriores: Optional[dict]
    datos_nuevos: Optional[dict]
    ip_origen: Optional[str]
    id_sesion: Optional[int]
    fecha_emision: Optional[datetime]
    id_activo_biologico: Optional[int]
    id_ciclo_productivo: Optional[int]
    costo_afectado: Optional[Decimal]
    origen_precio: Optional[str]
    clasificacion_registro: Optional[str]
    retencion_aplicable: Optional[str]
    hash_integridad: Optional[str]
    registro_incompleto: Optional[bool]
    detalle_causa: Optional[str]
    numero_reintentos: Optional[int]
    fecha_intentos: Optional[list[datetime]]
    id_gestion_fases: Optional[int]
    id_evento_m05: Optional[UUID] = None
    version_hash_integridad: int = 1
    # Nombres visibles (los llena la consulta); el del usuario queda en None si la RLS no deja leerlo.
    nombre_activo: Optional[str] = None
    nombre_usuario: Optional[str] = None
