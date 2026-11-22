# | Fecha      | Nombre   | Que se hizo                                                      |
# |------------|----------|------------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M03-135-G01 RF-49: especies compatibles de un sensor desde M09 |
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.configuration.domain.repositories.compatibilidad_sensor_especie_repository import (
    CompatibilidadSensorEspecieRepository,
)
from src.configuration.infrastructure.models.compatibilidad_sensor_especie_model import CompatibilidadSensorEspecieModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyCompatibilidadSensorEspecieRepository(CompatibilidadSensorEspecieRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def listar_especies(self, id_sensor: int) -> list[int]:
        m = CompatibilidadSensorEspecieModel
        return list(self.db.execute(
            select(m.id_especie).where(m.id_sensor == id_sensor).order_by(m.id_especie)
        ).scalars())

    def reemplazar(self, id_sensor: int, ids_especies: list[int]) -> None:
        # Delete-then-insert: la especie es la identidad de cada fila (patrón de hijos del repo).
        m = CompatibilidadSensorEspecieModel
        try:
            self.db.execute(delete(m).where(m.id_sensor == id_sensor))
            self.db.add_all(m(id_sensor=id_sensor, id_especie=id_especie) for id_especie in ids_especies)
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
