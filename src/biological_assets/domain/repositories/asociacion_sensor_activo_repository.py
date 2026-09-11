from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.biological_assets.domain.entities.activo_biologico import AsociacionSensorActivo


class AsociacionSensorActivoRepository(ABC):

    @abstractmethod
    def guardar(self, entidad: AsociacionSensorActivo) -> AsociacionSensorActivo:
        """Inserta una nueva asociación y retorna la entidad con id asignado."""

    @abstractmethod
    def obtener_por_id(self, id_asociacion: int) -> Optional[AsociacionSensorActivo]:
        """Retorna la asociación por PK, o None si no existe."""

    @abstractmethod
    def obtener_activa_por_sensor_y_activo(
        self,
        sensor_id: int,
        id_activo_biologico: int,
    ) -> Optional[AsociacionSensorActivo]:
        """Retorna la asociación ACTIVA para el par sensor+activo, o None."""

    @abstractmethod
    def listar_activas_por_sensor(
        self,
        sensor_id: int,
        tipo_asociacion: Optional[str] = None,
    ) -> list[AsociacionSensorActivo]:
        """Lista todas las asociaciones ACTIVA para el sensor dado, opcionalmente filtradas por tipo."""

    @abstractmethod
    def listar_activas_por_activo(
        self,
        id_activo_biologico: int,
        tipo_asociacion: Optional[str] = None,
    ) -> list[AsociacionSensorActivo]:
        """Lista todas las asociaciones ACTIVA para el activo dado, opcionalmente filtradas por tipo."""

    @abstractmethod
    def actualizar_estado(self, entidad: AsociacionSensorActivo) -> AsociacionSensorActivo:
        """Actualiza estado, fecha_fin y motivo de una asociación existente."""

    @abstractmethod
    def registrar_auditoria(
        self,
        id_asociacion: int,
        id_usuario: int,
        tipo_op: str,
        valores_anteriores: Optional[dict],
        valores_nuevos: dict,
    ) -> None:
        """Inserta un registro de auditoría para la operación dada."""
