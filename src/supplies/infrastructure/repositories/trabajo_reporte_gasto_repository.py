"""Implementación SQLAlchemy de :class:`TrabajoReporteGastoRepository` (RF-77)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.entities.trabajo_reporte_gasto import EjecucionReporteGasto, TrabajoReporteGasto
from src.supplies.domain.repositories.trabajo_reporte_gasto_repository import TrabajoReporteGastoRepository
from src.supplies.domain.value_objects.estado_trabajo_async import EstadoTrabajoAsync
from src.supplies.infrastructure.models.cola_generacion_reporte_gasto_model import (
    ColaGeneracionReporteGastoModel,
)
from src.supplies.infrastructure.models.ejecucion_generacion_reporte_gasto_model import (
    EjecucionGeneracionReporteGastoModel,
)

_ACTIVOS = (EstadoTrabajoAsync.PENDIENTE.value, EstadoTrabajoAsync.EN_PROCESO.value)


class SqlAlchemyTrabajoReporteGastoRepository(TrabajoReporteGastoRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _trabajo_a_entidad(orm: ColaGeneracionReporteGastoModel) -> TrabajoReporteGasto:
        return TrabajoReporteGasto(
            id_cola=orm.id_cola,
            parametros=orm.parametros,
            id_usuario_solicitante=orm.id_usuario_solicitante,
            estado=EstadoTrabajoAsync(orm.estado),
            fecha_solicitud=orm.fecha_solicitud,
            fecha_procesado=orm.fecha_procesado,
        )

    @staticmethod
    def _ejecucion_a_entidad(orm: EjecucionGeneracionReporteGastoModel) -> EjecucionReporteGasto:
        return EjecucionReporteGasto(
            id_ejecucion=orm.id_ejecucion,
            id_cola=orm.id_cola,
            estado=EstadoTrabajoAsync(orm.estado),
            intento=orm.intento,
            hora_inicio=orm.hora_inicio,
            hora_fin=orm.hora_fin,
            id_reporte_resultado=orm.id_reporte_resultado,
            resultado_json=orm.resultado_json,
        )

    def encolar(self, trabajo: TrabajoReporteGasto) -> TrabajoReporteGasto:
        try:
            orm = ColaGeneracionReporteGastoModel(
                parametros=trabajo.parametros,
                id_usuario_solicitante=trabajo.id_usuario_solicitante,
                estado=trabajo.estado.value,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._trabajo_a_entidad(orm)

    def contar_activos(self) -> int:
        return (
            self.db.query(ColaGeneracionReporteGastoModel)
            .filter(ColaGeneracionReporteGastoModel.estado.in_(_ACTIVOS))
            .count()
        )

    def obtener(self, id_cola: int) -> Optional[TrabajoReporteGasto]:
        orm = self.db.get(ColaGeneracionReporteGastoModel, id_cola)
        return self._trabajo_a_entidad(orm) if orm else None

    def listar_pendientes(self, limite: int) -> list[TrabajoReporteGasto]:
        registros = (
            self.db.query(ColaGeneracionReporteGastoModel)
            .filter(ColaGeneracionReporteGastoModel.estado == EstadoTrabajoAsync.PENDIENTE.value)
            .order_by(ColaGeneracionReporteGastoModel.fecha_solicitud.asc())
            .limit(limite)
            .all()
        )
        return [self._trabajo_a_entidad(o) for o in registros]

    def marcar_estado(
        self, id_cola: int, estado: EstadoTrabajoAsync, *, fecha_procesado: Optional[datetime] = None
    ) -> None:
        orm = self.db.get(ColaGeneracionReporteGastoModel, id_cola)
        if orm is None:
            return
        orm.estado = estado.value
        if fecha_procesado is not None:
            orm.fecha_procesado = fecha_procesado
        try:
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc, {})

    def crear_ejecucion(self, ejecucion: EjecucionReporteGasto) -> EjecucionReporteGasto:
        try:
            orm = EjecucionGeneracionReporteGastoModel(
                id_cola=ejecucion.id_cola,
                estado=ejecucion.estado.value,
                intento=ejecucion.intento,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._ejecucion_a_entidad(orm)

    def guardar_ejecucion(self, ejecucion: EjecucionReporteGasto) -> EjecucionReporteGasto:
        orm = self.db.get(EjecucionGeneracionReporteGastoModel, ejecucion.id_ejecucion)
        if orm is None:
            raise_from_db_error(ValueError(f"Ejecución {ejecucion.id_ejecucion} inexistente"), {})
        orm.estado = ejecucion.estado.value
        orm.hora_fin = ejecucion.hora_fin
        orm.id_reporte_resultado = ejecucion.id_reporte_resultado
        orm.resultado_json = ejecucion.resultado_json
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._ejecucion_a_entidad(orm)

    def obtener_ultima_ejecucion(self, id_cola: int) -> Optional[EjecucionReporteGasto]:
        orm = (
            self.db.query(EjecucionGeneracionReporteGastoModel)
            .filter(EjecucionGeneracionReporteGastoModel.id_cola == id_cola)
            .order_by(EjecucionGeneracionReporteGastoModel.intento.desc())
            .first()
        )
        return self._ejecucion_a_entidad(orm) if orm else None
