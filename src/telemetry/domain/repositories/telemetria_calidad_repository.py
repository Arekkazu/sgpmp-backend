# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-24 | Arekkazu | USAB-M03 M3-14 RF-62: calidad limitada a las fincas del usuario |
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.telemetry.domain.entities.telemetria_calidad import TelemetriaCalidad


class TelemetriaCalidadRepository(ABC):

    @abstractmethod
    def guardar(self, evaluacion: TelemetriaCalidad) -> TelemetriaCalidad: ...

    @abstractmethod
    def obtener_por_lectura(self, id_telemetria: int) -> Optional[TelemetriaCalidad]:
        """Evaluación vigente no superada; única fuente de aptitud escalar."""

    @abstractmethod
    def listar(
        self,
        id_sensor: Optional[int] = None,
        clasificacion: Optional[str] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        estado_evaluacion: Optional[str] = None,
        pagina: int = 1,
        por_pagina: int = 50,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> tuple[list[TelemetriaCalidad], int]:
        """Lista vigentes por defecto; SUPERADA permite consultar el histórico.

        ``ids_fincas_permitidas`` None = alcance global (Administrador).
        """

    @abstractmethod
    def marcar_superada(self, id_evaluacion: UUID, motivo: str) -> None: ...

    @abstractmethod
    def listar_vigentes_por_sensor_rango(
        self,
        id_sensor: int,
        fecha_desde: datetime,
        fecha_hasta: datetime,
    ) -> list[TelemetriaCalidad]: ...
