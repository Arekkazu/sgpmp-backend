# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-36 RF-65: concurrencia optimista (config_version) e historial append-only |
"""Read-models del historial de la configuración del motor (RF-65 Restricción 5, DEV-36)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class VersionConfiguracionMotor:
    """Una versión de la configuración de un tipo_modelo.

    Las anteriores salen de ``modulo4.configuracion_ia_log`` (DB-14): cada fila es
    la versión que estaba vigente hasta ``vigente_hasta``, cuando ``id_usuario_cambio``
    la reemplazó. La vigente sale de ``configuraciones_motor_ia``.
    """

    config_version: int
    vigente: bool
    id_usuario_responsable: int
    configuracion: dict
    fecha_creacion_config: Optional[datetime] = None
    operacion: Optional[str] = None
    vigente_desde: Optional[datetime] = None
    vigente_hasta: Optional[datetime] = None
    id_usuario_cambio: Optional[int] = None


@dataclass
class HistorialConfiguracionMotor:
    tipo_modelo: str
    config_version_vigente: Optional[int]
    versiones: list[VersionConfiguracionMotor]

    @property
    def total(self) -> int:
        return len(self.versiones)
