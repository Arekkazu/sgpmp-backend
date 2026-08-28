"""Implementación SQLAlchemy del puerto ``AuditoriaCalibracionRepository`` (RF-24 / RF-10)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.repositories.auditoria_calibracion_repository import AuditoriaCalibracionRepository
from src.configuration.infrastructure.models.auditoria_calibracion_model import AuditoriaCalibracionModel


class SqlAlchemyAuditoriaCalibracionRepository(AuditoriaCalibracionRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(
        self,
        *,
        id_calibracion: int,
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict,
        valores_anteriores: Optional[dict] = None,
    ) -> None:
        orm = AuditoriaCalibracionModel(
            id_calibracion=id_calibracion,
            id_usuario=id_usuario,
            tipo_operacion=tipo_operacion,
            valores_nuevos=valores_nuevos,
            valores_anteriores=valores_anteriores,
        )
        self.db.add(orm)
        self.db.flush()
