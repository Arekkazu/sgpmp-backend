# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | DEV-36 RF-65: versión de la configuración del motor (historial append-only R5) |
"""Read-model de una versión de la configuración del motor de IA (RF-65 Restricción 5).

La vigente sale de ``modulo4.configuraciones_motor_ia``; las anteriores, del log
append-only ``modulo4.configuracion_ia_log`` (DB-14), donde cada fila es la
configuración tal como estaba antes de un UPDATE o DELETE.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.prediction.domain.entities.configuracion_motor_ia import ConfiguracionMotorIA


@dataclass(frozen=True)
class VersionConfiguracionMotor:
    configuracion: ConfiguracionMotorIA
    es_vigente: bool
    # UPDATE / DELETE: operación que reemplazó esta versión (None en la vigente).
    operacion: Optional[str] = None
    # Quién y cuándo la reemplazó (None en la vigente).
    id_usuario_cambio: Optional[int] = None
    fecha_cambio: Optional[datetime] = None
