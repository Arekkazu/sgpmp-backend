"""Implementación SQLAlchemy de AuditoriaUmbralRepository (append-only)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

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
