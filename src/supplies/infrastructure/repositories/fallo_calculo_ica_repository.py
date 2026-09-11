"""Implementación SQLAlchemy de :class:`FalloCalculoICARepository` (RF-74 / E5)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.entities.fallo_calculo_ica import FalloCalculoICA
from src.supplies.domain.repositories.fallo_calculo_ica_repository import FalloCalculoICARepository
from src.supplies.domain.value_objects.eficiencia_enums import PeriodoEvaluacion
from src.supplies.infrastructure.models.fallo_calculo_ica_model import FalloCalculoIcaModel


class SqlAlchemyFalloCalculoICARepository(FalloCalculoICARepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: FalloCalculoIcaModel) -> FalloCalculoICA:
        return FalloCalculoICA(
            id_fallo=orm.id_fallo,
            id_activo_biologico=orm.id_activo_biologico,
            causa_fallo=orm.causa_fallo or "",
            intentos=orm.intentos,
            periodo_evaluacion=PeriodoEvaluacion(orm.periodo_evaluacion) if orm.periodo_evaluacion else None,
            timestamp_ultimo_intento=orm.timestamp_ultimo_intento,
            id_ejecucion_batch=orm.id_ejecucion_batch,
            resuelto=orm.resuelto,
            fecha_resolucion=orm.fecha_resolucion,
            tipo_resolucion=orm.tipo_resolucion,
        )

    def _buscar_orm_abierto(
        self, id_activo_biologico: int, periodo: Optional[PeriodoEvaluacion]
    ) -> Optional[FalloCalculoIcaModel]:
        query = self.db.query(FalloCalculoIcaModel).filter(
            FalloCalculoIcaModel.id_activo_biologico == id_activo_biologico,
            FalloCalculoIcaModel.resuelto.is_(False),
        )
        if periodo is None:
            query = query.filter(FalloCalculoIcaModel.periodo_evaluacion.is_(None))
        else:
            query = query.filter(FalloCalculoIcaModel.periodo_evaluacion == periodo.value)
        return query.one_or_none()

    def registrar(self, fallo: FalloCalculoICA) -> FalloCalculoICA:
        try:
            existente = self._buscar_orm_abierto(fallo.id_activo_biologico, fallo.periodo_evaluacion)
            if existente is not None:
                existente.intentos = fallo.intentos
                existente.causa_fallo = fallo.causa_fallo
                existente.timestamp_ultimo_intento = fallo.timestamp_ultimo_intento or datetime.now(timezone.utc)
                existente.id_ejecucion_batch = fallo.id_ejecucion_batch
                self.db.flush()
                self.db.refresh(existente)
                return self._a_entidad(existente)

            orm = FalloCalculoIcaModel(
                id_activo_biologico=fallo.id_activo_biologico,
                periodo_evaluacion=fallo.periodo_evaluacion.value if fallo.periodo_evaluacion else None,
                causa_fallo=fallo.causa_fallo,
                intentos=fallo.intentos,
                timestamp_ultimo_intento=fallo.timestamp_ultimo_intento or datetime.now(timezone.utc),
                id_ejecucion_batch=fallo.id_ejecucion_batch,
                resuelto=False,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def obtener_abierto(
        self, id_activo_biologico: int, periodo: Optional[PeriodoEvaluacion]
    ) -> Optional[FalloCalculoICA]:
        orm = self._buscar_orm_abierto(id_activo_biologico, periodo)
        return self._a_entidad(orm) if orm else None

    def listar_no_resueltos(self) -> list[FalloCalculoICA]:
        registros = (
            self.db.query(FalloCalculoIcaModel)
            .filter(FalloCalculoIcaModel.resuelto.is_(False))
            .order_by(FalloCalculoIcaModel.timestamp_ultimo_intento.desc().nullslast())
            .all()
        )
        return [self._a_entidad(o) for o in registros]

    def marcar_resuelto(self, id_fallo: int, *, tipo_resolucion: str, cuando: datetime) -> None:
        orm = self.db.get(FalloCalculoIcaModel, id_fallo)
        if orm is None:
            return
        orm.resuelto = True
        orm.tipo_resolucion = tipo_resolucion
        orm.fecha_resolucion = cuando
        try:
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc, {})
