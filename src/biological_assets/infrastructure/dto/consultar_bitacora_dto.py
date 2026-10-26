# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""Filtros de ``GET /activos-biologicos/auditoria`` (RF-52)."""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc


class ConsultarBitacoraDTO(BaseDTO):
    """Filtros opcionales de la bitácora de M02; ``page_size`` máximo 100."""
    rf_origen: Optional[str] = None
    tipo_evento: Optional[str] = None
    id_activo_biologico: Optional[int] = None
    clasificacion_biologica: Optional[str] = None
    resultado: Optional[str] = None
    severidad_log: Optional[str] = None
    id_usuario_responsable: Optional[int] = Field(default=None, ge=1)
    fecha_inicio: Optional[FechaHoraUtc] = None
    fecha_fin: Optional[FechaHoraUtc] = None
    pagina: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
