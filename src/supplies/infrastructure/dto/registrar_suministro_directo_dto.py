# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-78: entradas del RF y errores 422      |
"""DTO de entrada para registrar un suministro en el ledger de RF-78.

- SERVICIO_VETERINARIO / INSEMINACION: cantidad, unidad, fecha y precio llegan
  aquí; el precio es MANUAL (no hay fuente M40) y exige ``justificacion_precio``.
- ALIMENTO / MEDICAMENTO: solo ``id_registro_rf75`` / ``id_registro_rf76``; el
  resto se toma del registro de RF-75/RF-76 (Fase 1b).

Las reglas de negocio (tipo fuera del catálogo E4, justificación E2, fecha E3,
costo ≤ 0 Fase 6) se validan en el caso de uso para responder 422 como pide
el RF, no 400.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import Field

from src.shared.base_dto import BaseDTO


class RegistrarSuministroDirectoDTO(BaseDTO):
    id_activo_biologico: int = Field(gt=0)
    tipo_suministro: str = Field(min_length=1, max_length=30)
    id_idempotencia: UUID
    cantidad: Optional[Decimal] = None
    unidad_medida: Optional[str] = Field(default=None, max_length=20)
    precio_unitario: Optional[Decimal] = None
    fecha_aplicacion: Optional[date] = None
    justificacion_precio: Optional[str] = None
    observacion: Optional[str] = Field(default=None, max_length=500)
    id_registro_rf75: Optional[UUID] = None
    id_registro_rf76: Optional[UUID] = None
