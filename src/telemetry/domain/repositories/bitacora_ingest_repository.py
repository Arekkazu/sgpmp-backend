from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional


class BitacoraIngestRepository(ABC):

    @abstractmethod
    def registrar_exito(
        self,
        id_telemetria: int,
        id_sensor: int,
        id_dispositivo_iot: int,
        estado_calidad: str,
        timestamp_captura: datetime,
        gateway_id: Optional[str] = None,
    ) -> None:
        """Registra evento de procesamiento exitoso (DATOS_PROCESADOS)."""

    @abstractmethod
    def registrar_error(
        self,
        estado_calidad: str,
        descripcion: str,
        payload: Optional[dict[str, Any]],
        id_sensor: Optional[int] = None,
        id_dispositivo_iot: Optional[int] = None,
        timestamp_captura: Optional[datetime] = None,
        gateway_id: Optional[str] = None,
    ) -> None:
        """Registra evento de rechazo o error en ingesta (ERROR_PROCESAMIENTO)."""
