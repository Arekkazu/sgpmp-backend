"""Implementación SQLAlchemy del puerto ``AuditoriaSensorAreaRepository``."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.repositories.auditoria_sensor_area_repository import AuditoriaSensorAreaRepository
from src.configuration.infrastructure.models.auditoria_sensor_area_model import AuditoriaSensorAreaModel


class SqlAlchemyAuditoriaSensorAreaRepository(AuditoriaSensorAreaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(
        self,
        *,
        id_sensores_area_asociada: int,
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict,
        valores_anteriores: Optional[dict] = None,
    ) -> None:
        orm = AuditoriaSensorAreaModel(
            id_sensores_area_asociada=id_sensores_area_asociada,
            id_usuario=id_usuario,
            tipo_operacion=tipo_operacion,
            valores_nuevos=valores_nuevos,
            valores_anteriores=valores_anteriores,
        )
        self.db.add(orm)
        self.db.flush()
