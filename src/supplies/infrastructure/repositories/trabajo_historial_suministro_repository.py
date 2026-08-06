"""Implementación SQLAlchemy de :class:`TrabajoHistorialSuministroRepository` (RF-81)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.entities.trabajo_historial_suministro import (
    EjecucionHistorialSuministro,
    TrabajoHistorialSuministro,
)
from src.supplies.domain.repositories.trabajo_historial_suministro_repository import (
    TrabajoHistorialSuministroRepository,
)
from src.supplies.domain.value_objects.estado_trabajo_async import EstadoTrabajoAsync
from src.supplies.infrastructure.models.cola_trabajo_historial_suministro_model import (
    ColaTrabajoHistorialSuministroModel,
)
from src.supplies.infrastructure.models.ejecucion_trabajo_historial_suministro_model import (
    EjecucionTrabajoHistorialSuministroModel,
)

_ACTIVOS = (EstadoTrabajoAsync.PENDIENTE.value, EstadoTrabajoAsync.EN_PROCESO.value)


class SqlAlchemyTrabajoHistorialSuministroRepository(TrabajoHistorialSuministroRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _trabajo_a_entidad(orm: ColaTrabajoHistorialSuministroModel) -> TrabajoHistorialSuministro:
        return TrabajoHistorialSuministro(
            id_cola=orm.id_cola,
            tipo_trabajo=orm.tipo_trabajo,
            parametros=orm.parametros,
            id_usuario_solicitante=orm.id_usuario_solicitante,
            estado=EstadoTrabajoAsync(orm.estado),
            fecha_solicitud=orm.fecha_solicitud,
            fecha_procesado=orm.fecha_procesado,
        )

    @staticmethod
    def _ejecucion_a_entidad(orm: EjecucionTrabajoHistorialSuministroModel) -> EjecucionHistorialSuministro:
        return EjecucionHistorialSuministro(
            id_ejecucion=orm.id_ejecucion,
            id_cola=orm.id_cola,
            estado=EstadoTrabajoAsync(orm.estado),
            intento=orm.intento,
            hora_inicio=orm.hora_inicio,
            hora_fin=orm.hora_fin,
            total_registros=orm.total_registros,
            resultado_json=orm.resultado_json,
            contenido_csv=orm.contenido_csv,
            nombre_archivo=orm.nombre_archivo,
        )

    def encolar(self, trabajo: TrabajoHistorialSuministro) -> TrabajoHistorialSuministro:
        try:
            orm = ColaTrabajoHistorialSuministroModel(
                tipo_trabajo=trabajo.tipo_trabajo,
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

    def contar_activos(self, tipo_trabajo: str) -> int:
        return (
            self.db.query(ColaTrabajoHistorialSuministroModel)
            .filter(
                ColaTrabajoHistorialSuministroModel.tipo_trabajo == tipo_trabajo,
                ColaTrabajoHistorialSuministroModel.estado.in_(_ACTIVOS),
            )
            .count()
        )

    def obtener(self, id_cola: int) -> Optional[TrabajoHistorialSuministro]:
        orm = self.db.get(ColaTrabajoHistorialSuministroModel, id_cola)
        return self._trabajo_a_entidad(orm) if orm else None

    def listar_pendientes(self, limite: int) -> list[TrabajoHistorialSuministro]:
        registros = (
            self.db.query(ColaTrabajoHistorialSuministroModel)
            .filter(ColaTrabajoHistorialSuministroModel.estado == EstadoTrabajoAsync.PENDIENTE.value)
            .order_by(ColaTrabajoHistorialSuministroModel.fecha_solicitud.asc())
            .limit(limite)
            .all()
        )
        return [self._trabajo_a_entidad(o) for o in registros]

    def marcar_estado(
        self, id_cola: int, estado: EstadoTrabajoAsync, *, fecha_procesado: Optional[datetime] = None
    ) -> None:
        orm = self.db.get(ColaTrabajoHistorialSuministroModel, id_cola)
        if orm is None:
            return
        orm.estado = estado.value
        if fecha_procesado is not None:
            orm.fecha_procesado = fecha_procesado
        try:
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc, {})

    def crear_ejecucion(self, ejecucion: EjecucionHistorialSuministro) -> EjecucionHistorialSuministro:
        try:
            orm = EjecucionTrabajoHistorialSuministroModel(
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

    def guardar_ejecucion(self, ejecucion: EjecucionHistorialSuministro) -> EjecucionHistorialSuministro:
        orm = self.db.get(EjecucionTrabajoHistorialSuministroModel, ejecucion.id_ejecucion)
        if orm is None:
            raise_from_db_error(ValueError(f"Ejecución {ejecucion.id_ejecucion} inexistente"), {})
        orm.estado = ejecucion.estado.value
        orm.hora_fin = ejecucion.hora_fin
        orm.total_registros = ejecucion.total_registros
        orm.resultado_json = ejecucion.resultado_json
        orm.contenido_csv = ejecucion.contenido_csv
        orm.nombre_archivo = ejecucion.nombre_archivo
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._ejecucion_a_entidad(orm)

    def obtener_ultima_ejecucion(self, id_cola: int) -> Optional[EjecucionHistorialSuministro]:
        orm = (
            self.db.query(EjecucionTrabajoHistorialSuministroModel)
            .filter(EjecucionTrabajoHistorialSuministroModel.id_cola == id_cola)
            .order_by(EjecucionTrabajoHistorialSuministroModel.intento.desc())
            .first()
        )
        return self._ejecucion_a_entidad(orm) if orm else None
