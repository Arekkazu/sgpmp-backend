from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass
class HistoricoTransicionDispositivo:
    id_transaccion: Optional[int]
    id_dispositivo_iot: int
    estado_anterior: str
    estado_nuevo: str
    causa_primaria: Optional[str]
    causa_secundaria: Optional[Any]
    id_usuario_responsable: Optional[int]
    notas: Optional[str]
    fecha_transicion: datetime
