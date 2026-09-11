from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class DespliegueOta:
    id_despliegue_ota: int
    id_version_modelo: int
    id_dispositivo_iot: int
    tipo_modelo: str
    modo_distribucion: str
    estado_despliegue: str
    hash_modelo_sha256: str
    resultado_validacion_hash: Optional[bool]
    id_version_modelo_anterior: Optional[int]
    rollback_ejecutado: bool
    intentos_descarga: int
    max_reintentos: int
    tamano_modelo_bytes: Optional[int]
    tamano_descargado_bytes: Optional[int]
    duracion_proceso_ms: Optional[int]
    ventana_inicio: Optional[datetime]
    ventana_fin: Optional[datetime]
    nivel_bateria_al_inicio: Optional[Decimal]
    fecha_inicio: datetime
    fecha_fin: Optional[datetime]
    motivo_fallo: Optional[str]
