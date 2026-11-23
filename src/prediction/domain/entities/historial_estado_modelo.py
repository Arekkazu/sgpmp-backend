# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Entidad de cambio de estado de una versión de modelo."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(eq=False)
class HistorialEstadoModelo:
    """Cambio de estado de una versión de modelo."""
    id_version_modelo: int
    estado_nuevo: str
    tipo_actor: str
    fecha_transicion: datetime

    id_historial_estado_modelo: Optional[int] = None
    estado_anterior: Optional[str] = None
    id_usuario: Optional[int] = None
    id_sistema: Optional[str] = None
    id_proceso_rf71: Optional[uuid.UUID] = None
    correlacion_id: Optional[uuid.UUID] = None
    motivo: Optional[str] = None
