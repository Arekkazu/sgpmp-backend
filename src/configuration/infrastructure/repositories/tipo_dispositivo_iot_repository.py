"""Implementación SQLAlchemy del puerto ``TipoDispositivoIotRepository`` (RF-23)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.tipo_dispositivo_iot import TipoDispositivoIot
from src.configuration.domain.repositories.tipo_dispositivo_iot_repository import TipoDispositivoIotRepository
from src.configuration.infrastructure.models.tipo_dispositivo_iot_model import TipoDispositivoIotModel


class SqlAlchemyTipoDispositivoIotRepository(TipoDispositivoIotRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: TipoDispositivoIotModel) -> TipoDispositivoIot:
        return TipoDispositivoIot(
            id_tipo_dispositivo=orm.id_tipo_dispositivo,
            nombre=orm.nombre,
            frecuencia_captura_min=orm.frecuencia_captura_min,
            frecuencia_captura_max=orm.frecuencia_captura_max,
            intervalo_transmision_min=orm.intervalo_transmision_min,
            intervalo_transmision_max=orm.intervalo_transmision_max,
        )

    def obtener_por_id(self, id_tipo_dispositivo: int) -> Optional[TipoDispositivoIot]:
        orm = self.db.get(TipoDispositivoIotModel, id_tipo_dispositivo)
        return self._a_entidad(orm) if orm else None

    def listar(self) -> list[TipoDispositivoIot]:
        orms = self.db.query(TipoDispositivoIotModel).order_by(TipoDispositivoIotModel.nombre).all()
        return [self._a_entidad(orm) for orm in orms]
