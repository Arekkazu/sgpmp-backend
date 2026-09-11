"""Implementación SQLAlchemy del puerto ``AuditoriaDispositivoIotRepository``."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.repositories.auditoria_dispositivo_iot_repository import AuditoriaDispositivoIotRepository
from src.configuration.infrastructure.models.auditoria_dispositivo_iot_model import AuditoriaDispositivoIotModel


class SqlAlchemyAuditoriaDispositivoIotRepository(AuditoriaDispositivoIotRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(
        self,
        *,
        id_dispositivo_iot: int,
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict,
        valores_anteriores: Optional[dict] = None,
    ) -> None:
        orm = AuditoriaDispositivoIotModel(
            id_dispositivo_iot=id_dispositivo_iot,
            id_usuario=id_usuario,
            tipo_operacion=tipo_operacion,
            valores_nuevos=valores_nuevos,
            valores_anteriores=valores_anteriores,
        )
        self.db.add(orm)
        self.db.flush()
