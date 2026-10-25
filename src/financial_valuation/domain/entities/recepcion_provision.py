# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79: M06 provisional (recepción)        |
"""Entidad ``RecepcionProvision``: una provisión de costos recibida de M05 (RF-79)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.shared.errors import BusinessRuleError

# R13 / RNF-08: se soportan las dos últimas versiones MAJOR del contrato.
VERSIONES_MAJOR_SOPORTADAS = {"1"}
MODALIDADES = {"INCREMENTAL", "CONSOLIDADO"}


@dataclass(frozen=True)
class RecepcionProvision:
    id_evento_provision: UUID
    modalidad: str
    schema_version: str
    id_activo_biologico: int
    contenido: dict
    id_gestion_fases: Optional[int] = None
    fecha_recepcion: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.schema_version.split(".")[0] not in VERSIONES_MAJOR_SOPORTADAS:
            raise BusinessRuleError(
                code="SCHEMA_VERSION_NO_SOPORTADA",
                message=f"La versión de contrato {self.schema_version} no es compatible con M06.",
            )
        if self.modalidad not in MODALIDADES:
            raise BusinessRuleError(
                code="MODALIDAD_PROVISION_INVALIDA",
                message=f"Modalidad de provisión desconocida: {self.modalidad}.",
            )
