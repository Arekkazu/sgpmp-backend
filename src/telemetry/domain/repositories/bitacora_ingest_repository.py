# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-19 | Arekkazu | SEG-M03-01 RF-53: retira registrar_exito, sin llamadores (el éxito lo registra fn_ingesta_telemetria) |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de la bitácora de ingesta de telemetría."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional


class BitacoraIngestRepository(ABC):
    """Puerto para registrar errores y rechazos de ingesta."""

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
