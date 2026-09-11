"""Caso de uso: Registrar sensor en un dispositivo IoT (POST /{id}/sensores).

Los sensores deben existir antes de poder asociarlos a áreas productivas (precondición RF-22).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.sensor import Sensor
from src.configuration.domain.repositories.dispositivo_iot_repository import DispositivoIotRepository
from src.configuration.domain.repositories.sensor_repository import SensorRepository
from src.configuration.infrastructure.dto.registrar_sensor_dto import RegistrarSensorDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


class RegistrarSensorUseCase:

    def __init__(
        self,
        db: Session,
        sensor_repo: SensorRepository,
        dispositivo_repo: DispositivoIotRepository,
    ) -> None:
        self.db = db
        self.sensor_repo = sensor_repo
        self.dispositivo_repo = dispositivo_repo

    def execute(self, id_dispositivo_iot: int, dto: RegistrarSensorDTO, usuario_actual: UsuarioActual) -> Sensor:
        dispositivo = self.dispositivo_repo.obtener_por_id(id_dispositivo_iot)
        if dispositivo is None:
            raise NotFoundError(
                code="DISPOSITIVO_NO_ENCONTRADO",
                message=f"No existe un dispositivo IoT con ID {id_dispositivo_iot}.",
            )

        sensor = Sensor.crear(
            nombre=dto.nombre,
            id_dispositivo_iot=id_dispositivo_iot,
            categoria=dto.categoria,
        )

        try:
            sensor_guardado = self.sensor_repo.guardar(sensor)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return sensor_guardado


class ConsultarSensoresUseCase:

    def __init__(self, db: Session, sensor_repo: SensorRepository) -> None:
        self.db = db
        self.sensor_repo = sensor_repo

    def listar_por_dispositivo(self, id_dispositivo_iot: int) -> list[Sensor]:
        return self.sensor_repo.listar_por_dispositivo(id_dispositivo_iot)
