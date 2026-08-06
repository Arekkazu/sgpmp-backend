"""Implementación SQLAlchemy de :class:`FalloReporteGastoRepository` (RF-77)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.entities.trabajo_reporte_gasto import FalloReporteGasto
from src.supplies.domain.repositories.fallo_reporte_gasto_repository import FalloReporteGastoRepository
from src.supplies.infrastructure.models.fallo_generacion_reporte_gasto_model import (
    FalloGeneracionReporteGastoModel,
)


class SqlAlchemyFalloReporteGastoRepository(FalloReporteGastoRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: FalloGeneracionReporteGastoModel) -> FalloReporteGasto:
        return FalloReporteGasto(
            id_fallo=orm.id_fallo,
            id_cola=orm.id_cola,
            causa_fallo=orm.causa_fallo or "",
            intentos=orm.intentos,
            timestamp_ultimo_intento=orm.timestamp_ultimo_intento,
            resuelto=orm.resuelto,
        )

    def registrar(self, fallo: FalloReporteGasto) -> FalloReporteGasto:
        try:
            orm = FalloGeneracionReporteGastoModel(
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

    def listar_no_resueltos(self) -> list[FalloReporteGasto]:
        registros = (
            self.db.query(FalloGeneracionReporteGastoModel)
            .filter(FalloGeneracionReporteGastoModel.resuelto.is_(False))
            .order_by(FalloGeneracionReporteGastoModel.timestamp_ultimo_intento.desc().nullslast())
            .all()
        )
        return [self._a_entidad(o) for o in registros]
