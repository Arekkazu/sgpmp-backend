"""Read-model de la auditoría de identidad visual (RF-26)."""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AuditoriaIdentidadVisual:
    """Cambio trazable de la identidad visual de una finca."""

    id_auditoria_visual: int
    id_finca: int
    id_usuario: int
    usuario: str
    fecha_creacion: datetime.datetime
    tipo_operacion: str
    valor_anterior: dict[str, Any]
    valor_nuevo: dict[str, Any]
