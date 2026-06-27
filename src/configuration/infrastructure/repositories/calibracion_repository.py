"""Implementación SQLAlchemy del puerto ``CalibracionRepository``."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from src.configuration.domain.entities.calibracion import Calibracion
from src.configuration.domain.repositories.calibracion_repository import CalibracionRepository
from src.configuration.infrastructure.models.calibracion_model import CalibracionModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyCalibracionRepository(CalibracionRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: CalibracionModel) -> Calibracion:
        return Calibracion(
            id_calibracion=orm.id_calibracion,
            id_dispositivo_iot=orm.id_dispositivo_iot,
            id_sensor=orm.id_sensor,
            valor_referencia=Decimal(str(orm.valor_referencia)),
            fecha_calibracion=orm.fecha_calibracion,
            id_usuario=orm.id_usuario,
            observaciones=orm.observaciones,
        )

    def guardar(self, calibracion: Calibracion) -> Calibracion:
        orm = CalibracionModel(
            id_dispositivo_iot=calibracion.id_dispositivo_iot,
            id_sensor=calibracion.id_sensor,
            valor_referencia=calibracion.valor_referencia,
            fecha_calibracion=calibracion.fecha_calibracion,
            id_usuario=calibracion.id_usuario,
            observaciones=calibracion.observaciones,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def listar_por_sensor(self, id_sensor: int) -> list[Calibracion]:
        return [
            self._a_entidad(orm)
            for orm in (
                self.db.query(CalibracionModel)
                .filter(CalibracionModel.id_sensor == id_sensor)
                .order_by(CalibracionModel.fecha_calibracion.desc())
                .all()
            )
        ]
