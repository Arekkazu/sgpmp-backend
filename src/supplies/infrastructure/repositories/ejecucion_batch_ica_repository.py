"""Implementación SQLAlchemy de :class:`EjecucionBatchICARepository` (RF-74)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.entities.ejecucion_batch_ica import EjecucionBatchICA
from src.supplies.domain.repositories.ejecucion_batch_ica_repository import EjecucionBatchICARepository
from src.supplies.domain.value_objects.eficiencia_enums import EstadoEjecucionBatch
from src.supplies.infrastructure.models.ejecucion_batch_ica_model import EjecucionBatchIcaModel


class SqlAlchemyEjecucionBatchICARepository(EjecucionBatchICARepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: EjecucionBatchIcaModel) -> EjecucionBatchICA:
        return EjecucionBatchICA(
            id_ejecucion=orm.id_ejecucion,
            tipo_disparo=orm.tipo_disparo,
            hora_inicio=orm.hora_inicio,
            num_workers=orm.num_workers,
            limite_configurado=orm.limite_configurado,
            estado=EstadoEjecucionBatch(orm.estado),
            cantidad_activos_total=orm.cantidad_activos_total,
            cantidad_activos_procesados=orm.cantidad_activos_procesados,
            cantidad_activos_pendientes=orm.cantidad_activos_pendientes,
            cantidad_fallidos=orm.cantidad_fallidos,
            hora_fin=orm.hora_fin,
            hora_corte=orm.hora_corte,
            causa_interrupcion=orm.causa_interrupcion,
            id_usuario_disparo=orm.id_usuario_disparo,
            id_usuario_interrupcion=orm.id_usuario_interrupcion,
        )

    def crear(self, ejecucion: EjecucionBatchICA) -> EjecucionBatchICA:
        try:
            orm = EjecucionBatchIcaModel(
                estado=ejecucion.estado.value,
                tipo_disparo=ejecucion.tipo_disparo,
                hora_inicio=ejecucion.hora_inicio,
                num_workers=ejecucion.num_workers,
                limite_configurado=ejecucion.limite_configurado,
                cantidad_activos_total=ejecucion.cantidad_activos_total,
                cantidad_activos_procesados=ejecucion.cantidad_activos_procesados,
                cantidad_activos_pendientes=ejecucion.cantidad_activos_pendientes,
                cantidad_fallidos=ejecucion.cantidad_fallidos,
                id_usuario_disparo=ejecucion.id_usuario_disparo,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def guardar(self, ejecucion: EjecucionBatchICA) -> EjecucionBatchICA:
        orm = self.db.get(EjecucionBatchIcaModel, ejecucion.id_ejecucion)
        if orm is None:
            raise_from_db_error(ValueError(f"Ejecución {ejecucion.id_ejecucion} inexistente"), {})
        orm.estado = ejecucion.estado.value
        orm.hora_fin = ejecucion.hora_fin
        orm.hora_corte = ejecucion.hora_corte
        orm.causa_interrupcion = ejecucion.causa_interrupcion
        orm.num_workers = ejecucion.num_workers
        orm.cantidad_activos_total = ejecucion.cantidad_activos_total
        orm.cantidad_activos_procesados = ejecucion.cantidad_activos_procesados
        orm.cantidad_activos_pendientes = ejecucion.cantidad_activos_pendientes
        orm.cantidad_fallidos = ejecucion.cantidad_fallidos
        orm.id_usuario_interrupcion = ejecucion.id_usuario_interrupcion
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def obtener(self, id_ejecucion: int) -> Optional[EjecucionBatchICA]:
        orm = self.db.get(EjecucionBatchIcaModel, id_ejecucion)
        return self._a_entidad(orm) if orm else None

    def obtener_en_ejecucion(self) -> Optional[EjecucionBatchICA]:
        orm = (
            self.db.query(EjecucionBatchIcaModel)
            .filter(EjecucionBatchIcaModel.estado == EstadoEjecucionBatch.EN_EJECUCION.value)
            .order_by(EjecucionBatchIcaModel.hora_inicio.desc())
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def listar_recientes(self, limite: int = 20) -> list[EjecucionBatchICA]:
        registros = (
            self.db.query(EjecucionBatchIcaModel)
            .order_by(EjecucionBatchIcaModel.hora_inicio.desc())
            .limit(limite)
            .all()
        )
        return [self._a_entidad(o) for o in registros]
