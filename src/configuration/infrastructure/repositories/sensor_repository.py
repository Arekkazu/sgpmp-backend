"""Implementación SQLAlchemy del puerto ``SensorRepository``."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.sensor import Sensor
from src.configuration.domain.repositories.sensor_repository import SensorRepository
from src.configuration.infrastructure.models.sensor_model import SensorModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemySensorRepository(SensorRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: SensorModel) -> Sensor:
        return Sensor(
            id_sensores=orm.id_sensores,
            nombre=orm.nombre,
            id_dispositivo_iot=orm.id_dispositivo_iot,
            es_activo=orm.es_activo,
            categoria=orm.categoria,
        )

    def obtener_por_id(self, id_sensor: int) -> Optional[Sensor]:
        orm = self.db.get(SensorModel, id_sensor)
        return self._a_entidad(orm) if orm else None

    def guardar(self, sensor: Sensor) -> Sensor:
        orm = SensorModel(
            nombre=sensor.nombre,
            id_dispositivo_iot=sensor.id_dispositivo_iot,
            es_activo=sensor.es_activo,
            categoria=sensor.categoria,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def listar_por_dispositivo(self, id_dispositivo_iot: int) -> list[Sensor]:
        return [
            self._a_entidad(orm)
            for orm in (
                self.db.query(SensorModel)
                .filter(SensorModel.id_dispositivo_iot == id_dispositivo_iot)
                .order_by(SensorModel.nombre)
                .all()
            )
        ]
