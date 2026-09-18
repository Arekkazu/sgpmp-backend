from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.telemetry.domain.entities.monitoreo import EstadoSensorActual, ResumenUnidadProductiva


class MonitoreoRepository(ABC):

    @abstractmethod
    def actualizar_estado_semaforo_si_vigente(
        self,
        id_sensor: int,
        timestamp_captura: datetime,
        estado_semaforo: str,
    ) -> None:
        """Sobrescribe `estado_semaforo` en el caché del sensor (INC-M09-106-G31).

        Solo aplica si `timestamp_captura` no es anterior al último dato cacheado —
        evita que una vinculación corregida tiempo después sobre una lectura vieja
        pise el semáforo calculado para una lectura más reciente del mismo sensor.
        """

    @abstractmethod
    def obtener_estados_sensores(
        self,
        id_infraestructura: Optional[int],
        pagina: int,
        por_pagina: int,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> tuple[list[EstadoSensorActual], int]:
        """Devuelve (sensores, total) del estado actual con contexto M09."""

    @abstractmethod
    def obtener_resumen_unidades(
        self,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> list[ResumenUnidadProductiva]:
        """Devuelve estado agregado por unidad productiva (para encabezado del dashboard)."""
