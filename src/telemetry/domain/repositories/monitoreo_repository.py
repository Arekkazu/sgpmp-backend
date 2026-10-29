# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | USAB-M03 M3-08 RF-58: conteo del semáforo sobre todos los sensores, no la página |
# | 2026-10-28 | destroyerban | INC-M03-177-G57B RF-58: conteo del semáforo sin repetir la consulta de estados |
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.telemetry.domain.entities.monitoreo import EstadoSensorActual, ResumenUnidadProductiva, SemaforoBaseSensor


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
        por_pagina: Optional[int],
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> tuple[list[EstadoSensorActual], int]:
        """Devuelve (sensores, total) del estado actual con contexto M09. ``por_pagina`` None = todos."""

    @abstractmethod
    def obtener_semaforos_sensores(
        self,
        id_infraestructura: Optional[int],
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> list[SemaforoBaseSensor]:
        """Semáforo base de todos los sensores del alcance, sin lecturas (G57B, conteo M3-08)."""

    @abstractmethod
    def obtener_resumen_unidades(
        self,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> list[ResumenUnidadProductiva]:
        """Devuelve estado agregado por unidad productiva (para encabezado del dashboard)."""
