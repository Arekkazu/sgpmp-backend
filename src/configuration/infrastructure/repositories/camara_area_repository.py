"""Implementación SQLAlchemy del puerto ``CamaraAreaRepository`` (RF-21 v2.0 / RF-22)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.repositories.camara_area_repository import CamaraAreaRepository
from src.configuration.infrastructure.models.dispositivo_iot_model import DispositivoIotModel
from src.configuration.infrastructure.models.tipo_dispositivo_iot_model import TipoDispositivoIotModel
from src.configuration.infrastructure.repositories.dispositivo_iot_repository import (
    SqlAlchemyDispositivoIotRepository,
)


class SqlAlchemyCamaraAreaRepository(CamaraAreaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def listar_por_area(self, id_infraestructura: int) -> list[DispositivoIot]:
        # RF-22 v1.2: la asociación cámara → área es el id_infraestructura del dispositivo.
        filas = (
            self.db.query(DispositivoIotModel)
            .join(
                TipoDispositivoIotModel,
                DispositivoIotModel.id_tipo_dispositivo == TipoDispositivoIotModel.id_tipo_dispositivo,
            )
            .filter(
                DispositivoIotModel.id_infraestructura == id_infraestructura,
                TipoDispositivoIotModel.categoria == "CAMARA",
            )
            .order_by(DispositivoIotModel.id_dispositivo_iot)
            .all()
        )
        return [SqlAlchemyDispositivoIotRepository._a_entidad(orm) for orm in filas]
