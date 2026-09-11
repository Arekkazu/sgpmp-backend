from __future__ import annotations

from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.periodo_inactividad import PeriodoInactividad
from src.telemetry.domain.repositories.periodo_inactividad_repository import PeriodoInactividadRepository
from src.telemetry.infrastructure.models.periodo_inactividad_model import PeriodoInactividadModel


class SqlAlchemyPeriodoInactividadRepository(PeriodoInactividadRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def abrir(self, periodo: PeriodoInactividad) -> PeriodoInactividad:
        try:
            orm = PeriodoInactividadModel(
                id_dispositivo_iot=periodo.id_dispositivo_iot,
                sensores_afectados=periodo.sensores_afectados,
                fecha_inicio=periodo.fecha_inicio,
                fecha_fin=periodo.fecha_fin,
                duracion_min=periodo.duracion_min,
                estado_durante_periodo=periodo.estado_durante_periodo,
                causa_primaria=periodo.causa_primaria,
                caso_diagnosticado=periodo.caso_diagnosticado or {},
                buffer_activo_durante=periodo.buffer_activo_durante,
                id_alerta=periodo.id_alerta,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def obtener_abierto_por_dispositivo(self, id_dispositivo_iot: int) -> Optional[PeriodoInactividad]:
        orm = self.db.execute(
            select(PeriodoInactividadModel).where(
                PeriodoInactividadModel.id_dispositivo_iot == id_dispositivo_iot,
                PeriodoInactividadModel.fecha_fin.is_(None),
            ).order_by(desc(PeriodoInactividadModel.fecha_inicio))
        ).scalars().first()
        return self._a_entidad(orm) if orm else None

    def cerrar(self, periodo: PeriodoInactividad) -> PeriodoInactividad:
        try:
            orm = self.db.get(PeriodoInactividadModel, periodo.id_periodo_inactividad)
            orm.fecha_fin = periodo.fecha_fin
            orm.duracion_min = periodo.duracion_min
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    @staticmethod
    def _a_entidad(orm: PeriodoInactividadModel) -> PeriodoInactividad:
        return PeriodoInactividad(
            id_periodo_inactividad=orm.id_periodo_inactividad,
            id_dispositivo_iot=orm.id_dispositivo_iot,
            sensores_afectados=list(orm.sensores_afectados or []),
            fecha_inicio=orm.fecha_inicio,
            fecha_fin=orm.fecha_fin,
            duracion_min=orm.duracion_min,
            estado_durante_periodo=orm.estado_durante_periodo,
            causa_primaria=orm.causa_primaria,
            caso_diagnosticado=orm.caso_diagnosticado,
            buffer_activo_durante=orm.buffer_activo_durante,
            id_alerta=orm.id_alerta,
        )
