# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-204-G43/207-G46 RF-70: modo PROGRAMADO espera su ventana (E1) |
"""Implementación SQLAlchemy de ``DistribucionOtaRepository`` (DB-04, DEV-15)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.prediction.domain.entities.distribucion_ota import ESTADO_EN_CURSO, DistribucionOta
from src.prediction.domain.repositories.distribucion_ota_repository import DistribucionOtaRepository
from src.prediction.infrastructure.models.distribucion_ota_model import DistribucionOtaModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyDistribucionOtaRepository(DistribucionOtaRepository):

    def __init__(self, db: Session) -> None:
        self._db = db

    def guardar(self, entidad: DistribucionOta) -> DistribucionOta:
        try:
            orm = DistribucionOtaModel(
                id_version_modelo=entidad.id_version_modelo,
                tipo_modelo=entidad.tipo_modelo,
                componente=entidad.componente,
                modo_distribucion=entidad.modo_distribucion,
                ventana_inicio=entidad.ventana_inicio,
                ventana_fin=entidad.ventana_fin,
                nivel_bateria_minimo=entidad.nivel_bateria_minimo,
                tamano_fragmento_bytes=entidad.tamano_fragmento_bytes,
                max_reintentos_descarga=entidad.max_reintentos_descarga,
                fase_rollout=entidad.fase_rollout,
                porcentaje_parcial=entidad.porcentaje_parcial,
                estado_distribucion=entidad.estado_distribucion,
                id_usuario=entidad.id_usuario,
            )
            self._db.add(orm)
            self._db.flush()
            self._db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def obtener_por_id(self, id_distribucion: int, *, bloquear: bool = False) -> Optional[DistribucionOta]:
        orm = self._db.get(DistribucionOtaModel, id_distribucion, with_for_update=bloquear or None)
        return self._a_entidad(orm) if orm else None

    def actualizar(self, entidad: DistribucionOta) -> DistribucionOta:
        try:
            orm = self._db.get(DistribucionOtaModel, entidad.id_distribucion_ota)
            orm.fase_rollout = entidad.fase_rollout
            orm.estado_distribucion = entidad.estado_distribucion
            orm.fecha_actualizacion = entidad.fecha_actualizacion
            self._db.flush()
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def listar_programadas_en_ventana(self, ahora: datetime) -> list[DistribucionOta]:
        stmt = select(DistribucionOtaModel).where(
            DistribucionOtaModel.modo_distribucion == "PROGRAMADO",
            DistribucionOtaModel.estado_distribucion == ESTADO_EN_CURSO,
            DistribucionOtaModel.ventana_inicio <= ahora,
            DistribucionOtaModel.ventana_fin >= ahora,
        )
        return [self._a_entidad(r) for r in self._db.execute(stmt).scalars().all()]

    @staticmethod
    def _a_entidad(orm: DistribucionOtaModel) -> DistribucionOta:
        return DistribucionOta(
            id_distribucion_ota=orm.id_distribucion_ota,
            id_version_modelo=orm.id_version_modelo,
            tipo_modelo=orm.tipo_modelo,
            componente=orm.componente,
            modo_distribucion=orm.modo_distribucion,
            ventana_inicio=orm.ventana_inicio,
            ventana_fin=orm.ventana_fin,
            nivel_bateria_minimo=orm.nivel_bateria_minimo,
            tamano_fragmento_bytes=orm.tamano_fragmento_bytes,
            max_reintentos_descarga=orm.max_reintentos_descarga,
            fase_rollout=orm.fase_rollout,
            porcentaje_parcial=orm.porcentaje_parcial,
            estado_distribucion=orm.estado_distribucion,
            id_usuario=orm.id_usuario,
            fecha_creacion=orm.fecha_creacion,
            fecha_actualizacion=orm.fecha_actualizacion,
        )
