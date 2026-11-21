# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-24 | Arekkazu | USAB-M03 M3-10 RF-60: read-model del listado de dispositivos con su estado |
"""Read-model del listado de dispositivos (RF-60, M3-10).

Antes la pantalla solo consultaba un dispositivo por ID y no había forma de ver
cuáles estaban inactivos, que es el objetivo del RF.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class DispositivoConEstado:
    id_dispositivo_iot: int
    serial: str
    descripcion: Optional[str]
    id_infraestructura: int
    nombre_infraestructura: str
    nombre_finca: str
    estado_actual: str
    fecha_ultimo_contacto: Optional[datetime] = None
    nivel_bateria_pct: Optional[Decimal] = None
    calidad_senal_rssi: Optional[Decimal] = None
