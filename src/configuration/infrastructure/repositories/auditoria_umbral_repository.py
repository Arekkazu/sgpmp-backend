"""Implementación SQLAlchemy de AuditoriaUmbralRepository (append-only)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.configuration.domain.entities.auditoria_umbral import AuditoriaUmbral
from src.configuration.domain.repositories.auditoria_umbral_repository import AuditoriaUmbralRepository
from src.configuration.infrastructure.models.auditoria_umbral_model import AuditoriaUmbralModel


class SqlAlchemyAuditoriaUmbralRepository(AuditoriaUmbralRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def registrar(
        self,
        id_umbral_ambiental: int,
        id_usuario: Optional[int],
        tipo_operacion: str,
        valores_nuevos: dict,
        valores_anteriores: Optional[dict] = None,
    ) -> None:
        registro = AuditoriaUmbralModel(
            id_umbral_ambiental=id_umbral_ambiental,
            id_usuario=id_usuario,
            tipo_operacion=tipo_operacion,
            valores_nuevos=valores_nuevos,
            valores_anteriores=valores_anteriores,
        )
        self._db.add(registro)
        self._db.flush()

    def listar_por_umbral(self, id_umbral_ambiental: int) -> list[AuditoriaUmbral]:
        stmt = (
            select(AuditoriaUmbralModel)
            .where(AuditoriaUmbralModel.id_umbral_ambiental == id_umbral_ambiental)
            .order_by(AuditoriaUmbralModel.fecha_gestion.desc())
        )
        filas = self._db.scalars(stmt).all()
        return [self._a_entidad(f) for f in filas]

    @staticmethod
    def _a_entidad(orm: AuditoriaUmbralModel) -> AuditoriaUmbral:
        return AuditoriaUmbral(
            id_auditoria_umbral=orm.id_auditoria_umbral,
            id_umbral_ambiental=orm.id_umbral_ambiental,
            id_usuario=orm.id_usuario,
            tipo_operacion=orm.tipo_operacion,
            valores_anteriores=orm.valores_anteriores,
            valores_nuevos=orm.valores_nuevos,
            fecha_gestion=orm.fecha_gestion,
        )
