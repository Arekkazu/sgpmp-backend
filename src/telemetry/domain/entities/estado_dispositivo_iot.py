from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from src.shared.errors import BusinessRuleError

# Umbrales por defecto en segundos (RF-60 Restricción 12)
UMBRAL_ACTIVO_SEG: int = 300       # 5 min
UMBRAL_SIN_SENAL_SEG: int = 1800   # 30 min
UMBRAL_INACTIVO_SEG: int = 86400   # 24 h


@dataclass
class EstadoDispositivoIoT:
    id_estado_dispositivo_iot: Optional[int]
    id_dispositivo_iot: int
    estado_actual: str
    fecha_ultimo_contacto: Optional[datetime]
    id_ultimo_heartbeat: Optional[int]
    tiempo_sin_contacto: Optional[int]
    causa_primaria: Optional[str]
    causas_secundarias: Optional[Any]
    fecha_ultima_actualizacion: datetime
    id_usuario: Optional[int]

    def evaluar_transicion(
        self,
        tiempo_sin_contacto_seg: int,
        estado_local_buffer: Optional[str],
        umbral_activo: int = UMBRAL_ACTIVO_SEG,
        umbral_sin_senal: int = UMBRAL_SIN_SENAL_SEG,
        umbral_inactivo: int = UMBRAL_INACTIVO_SEG,
    ) -> Optional[str]:
        """Algoritmo de 4 pasos RF-60 Restricción 12.
        Retorna el nuevo estado si hay transición, None si no cambia.
        No evalúa EN_MANTENIMIENTO (estado manual).
        """
        if self.estado_actual == 'EN_MANTENIMIENTO':
            return None

        if tiempo_sin_contacto_seg < umbral_activo:
            nuevo = 'ACTIVO'
        elif tiempo_sin_contacto_seg < umbral_sin_senal:
            nuevo = 'SIN_SEÑAL'
        elif estado_local_buffer == 'A':
            nuevo = 'BUFFER_ACTIVO'
        elif tiempo_sin_contacto_seg >= umbral_inactivo:
            nuevo = 'INACTIVO'
        else:
            nuevo = 'SIN_SEÑAL'

        return nuevo if nuevo != self.estado_actual else None

    def aplicar_transicion(
        self,
        nuevo_estado: str,
        causa: Optional[str],
        ahora: datetime,
        id_heartbeat: Optional[int] = None,
        id_usuario: Optional[int] = None,
    ) -> None:
        if nuevo_estado not in (
            'ACTIVO', 'SIN_SEÑAL', 'BUFFER_ACTIVO', 'INACTIVO', 'EN_MANTENIMIENTO', 'DESCONOCIDO'
        ):
            raise BusinessRuleError(
                code='ESTADO_DISPOSITIVO_INVALIDO',
                message=f'Estado de dispositivo no válido: {nuevo_estado}',
            )
        self.estado_actual = nuevo_estado
        self.causa_primaria = causa
        self.fecha_ultima_actualizacion = ahora
        if id_heartbeat is not None:
            self.id_ultimo_heartbeat = id_heartbeat
        if id_usuario is not None:
            self.id_usuario = id_usuario
