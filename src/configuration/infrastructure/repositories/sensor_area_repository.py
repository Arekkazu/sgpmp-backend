"""Implementación SQLAlchemy del puerto ``SensorAreaRepository``."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.sensor_area import SensorArea
from src.configuration.domain.repositories.sensor_area_repository import SensorAreaRepository
from src.configuration.domain.value_objects.punto_instalacion import PuntoInstalacion
from src.configuration.infrastructure.models.sensor_area_model import SensorAreaModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemySensorAreaRepository(SensorAreaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: SensorAreaModel) -> SensorArea:
        return SensorArea(
            id_sensores_area_asociada=orm.id_sensores_area_asociada,
            id_sensor=orm.id_sensor,
            id_dispositivo_iot=orm.id_dispositivo_iot,
            id_infraestructura=orm.id_infraestructura,
            punto_instalacion=PuntoInstalacion(orm.punto_instalacion),
            tiene_estado=orm.tiene_estado,
            fecha_asociacion=orm.fecha_asociacion,
            fecha_finalizacion=orm.fecha_finalizacion,
            id_usuario=orm.id_usuario,
        )

    def obtener_asociacion_activa(self, id_sensor: int) -> Optional[SensorArea]:
        orm = (
            self.db.query(SensorAreaModel)
            .filter(
                SensorAreaModel.id_sensor == id_sensor,
                SensorAreaModel.tiene_estado.is_(True),
            )
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def guardar(self, sensor_area: SensorArea) -> SensorArea:
        orm = SensorAreaModel(
            id_sensor=sensor_area.id_sensor,
            id_dispositivo_iot=sensor_area.id_dispositivo_iot,
            id_infraestructura=sensor_area.id_infraestructura,
            punto_instalacion=sensor_area.punto_instalacion.valor,
            tiene_estado=sensor_area.tiene_estado,
            fecha_asociacion=sensor_area.fecha_asociacion,
            fecha_finalizacion=sensor_area.fecha_finalizacion,
            id_usuario=sensor_area.id_usuario,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def actualizar(self, sensor_area: SensorArea) -> SensorArea:
        orm = self.db.get(SensorAreaModel, sensor_area.id_sensores_area_asociada)
        orm.tiene_estado = sensor_area.tiene_estado
        orm.fecha_finalizacion = sensor_area.fecha_finalizacion
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def listar_por_sensor(self, id_sensor: int) -> list[SensorArea]:
        return [
            self._a_entidad(orm)
            for orm in (
                self.db.query(SensorAreaModel)
                .filter(SensorAreaModel.id_sensor == id_sensor)
                .order_by(SensorAreaModel.fecha_asociacion.desc())
                .all()
            )
        ]
