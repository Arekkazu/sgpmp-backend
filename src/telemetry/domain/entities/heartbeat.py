# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-126-G27 RF-54: transportar el snapshot opcional de métricas del buffer sin ORM. |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo y clase pública |
"""Entidad de dominio del heartbeat de un dispositivo IoT (RF-54).

Transporta el reporte periódico del Edge (batería, señal, buffer, firmware,
sensores y reloj) desde la infraestructura hacia la aplicación sin depender
del ORM. Es un dataclass puro.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional


@dataclass
class Heartbeat:
    """Reporte periódico de salud y estado de un dispositivo IoT.

    El Edge lo envía con el estado local del buffer, los sensores operativos y
    las métricas opcionales del buffer. ``fecha_registro`` es la hora del
    dispositivo y ``fecha_recepcion`` la del servidor.
    """

    id_heartbeat: Optional[int]
    id_dispositivo_iot: int
    tipo_mensaje: str
    nivel_bateria_pct: Optional[Decimal]
    calidad_senal_rssi: Optional[Decimal]
    calidad_senal_snr: Optional[Decimal]
    estado_local_buffer: Optional[str]
    datos_pendientes_buffer: int
    version_firmware: Optional[str]
    coordenadas: Optional[Any]
    fecha_registro: datetime
    fecha_recepcion: datetime
    reloj_sincronizado: bool
    sensores_operativos: Optional[list[dict[str, Any]]] = None
    temperatura_dispositivo: Optional[Decimal] = None
    metricas_buffer: Optional[dict[str, Any]] = None
