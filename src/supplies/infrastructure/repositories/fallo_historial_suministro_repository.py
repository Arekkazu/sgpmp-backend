"""Implementación SQLAlchemy de :class:`FalloHistorialSuministroRepository` (RF-81)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.entities.trabajo_historial_suministro import FalloHistorialSuministro
from src.supplies.domain.repositories.fallo_historial_suministro_repository import (
    FalloHistorialSuministroRepository,
)
from src.supplies.infrastructure.models.fallo_trabajo_historial_suministro_model import (
    FalloTrabajoHistorialSuministroModel,
)


class SqlAlchemyFalloHistorialSuministroRepository(FalloHistorialSuministroRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: FalloTrabajoHistorialSuministroModel) -> FalloHistorialSuministro:
        return FalloHistorialSuministro(
            id_fallo=orm.id_fallo,
            id_cola=orm.id_cola,
            causa_fallo=orm.causa_fallo or "",
            intentos=orm.intentos,
            timestamp_ultimo_intento=orm.timestamp_ultimo_intento,
            resuelto=orm.resuelto,
        )

    def registrar(self, fallo: FalloHistorialSuministro) -> FalloHistorialSuministro:
        try:
            orm = FalloTrabajoHistorialSuministroModel(
                id_cola=fallo.id_cola,
                causa_fallo=fallo.causa_fallo,
                intentos=fallo.intentos,
                timestamp_ultimo_intento=fallo.timestamp_ultimo_intento or datetime.now(timezone.utc),
                resuelto=False,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def listar_no_resueltos(self) -> list[FalloHistorialSuministro]:
        registros = (
            self.db.query(FalloTrabajoHistorialSuministroModel)
            .filter(FalloTrabajoHistorialSuministroModel.resuelto.is_(False))
            .order_by(FalloTrabajoHistorialSuministroModel.timestamp_ultimo_intento.desc().nullslast())
            .all()
        )
        return [self._a_entidad(o) for o in registros]
