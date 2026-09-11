"""Entidad de dominio :class:`ItemColaICA` (RF-74 / cola persistente).

Un activo encolado para cálculo ICA (FA-07 límite superado, FA-06 ventana excedida,
reactivación manual).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.supplies.domain.value_objects.eficiencia_enums import EstadoItemCola


@dataclass(eq=False)
class ItemColaICA:
    """Activo dentro de la cola de cálculo ICA."""

    id_activo_biologico: int
    prioridad: int = 100
    estado: EstadoItemCola = EstadoItemCola.EN_COLA
    motivo: Optional[str] = None
    id_ejecucion_batch: Optional[int] = None
    fecha_encolado: Optional[datetime] = None
    fecha_procesado: Optional[datetime] = None
    id_cola: Optional[int] = None
