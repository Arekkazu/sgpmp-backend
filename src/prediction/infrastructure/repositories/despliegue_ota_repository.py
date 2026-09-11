from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.prediction.domain.entities.despliegue_ota import DespliegueOta
from src.prediction.domain.repositories.despliegue_ota_repository import DespliegueOtaRepository
from src.prediction.infrastructure.models.despliegue_ota_model import DespliegueOtaModel


class SqlAlchemyDespliegueOtaRepository(DespliegueOtaRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def obtener_por_version(
        self,
        id_version: int,
        id_dispositivo: Optional[int] = None,
        estado: Optional[str] = None,
    ) -> list[DespliegueOta]:
        stmt = select(DespliegueOtaModel).where(
            DespliegueOtaModel.id_version_modelo == id_version
        )
        if id_dispositivo is not None:
            stmt = stmt.where(DespliegueOtaModel.id_dispositivo_iot == id_dispositivo)
        if estado is not None:
            stmt = stmt.where(DespliegueOtaModel.estado_despliegue == estado)
        stmt = stmt.order_by(DespliegueOtaModel.fecha_inicio.desc())
        return [self._a_entidad(row) for row in self._db.execute(stmt).scalars().all()]

    def listar(
        self,
        id_version: Optional[int] = None,
        id_dispositivo: Optional[int] = None,
        estado: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[DespliegueOta], int]:
        base = select(DespliegueOtaModel)
        if id_version is not None:
            base = base.where(DespliegueOtaModel.id_version_modelo == id_version)
        if id_dispositivo is not None:
            base = base.where(DespliegueOtaModel.id_dispositivo_iot == id_dispositivo)
        if estado is not None:
            base = base.where(DespliegueOtaModel.estado_despliegue == estado)

        total = self._db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()

        rows = self._db.execute(
            base.order_by(DespliegueOtaModel.fecha_inicio.desc()).limit(limit).offset(offset)
        ).scalars().all()

        return [self._a_entidad(r) for r in rows], total

    def obtener_por_id(self, id_despliegue: int) -> Optional[DespliegueOta]:
        orm = self._db.get(DespliegueOtaModel, id_despliegue)
        return self._a_entidad(orm) if orm else None

    def _a_entidad(self, orm: DespliegueOtaModel) -> DespliegueOta:
        return DespliegueOta(
            id_despliegue_ota=orm.id_despliegue_ota,
            id_version_modelo=orm.id_version_modelo,
            id_dispositivo_iot=orm.id_dispositivo_iot,
            tipo_modelo=orm.tipo_modelo,
            modo_distribucion=orm.modo_distribucion,
            estado_despliegue=orm.estado_despliegue,
            hash_modelo_sha256=orm.hash_modelo_sha256,
            resultado_validacion_hash=orm.resultado_validacion_hash,
            id_version_modelo_anterior=orm.id_version_modelo_anterior,
            rollback_ejecutado=orm.rollback_ejecutado,
            intentos_descarga=orm.intentos_descarga,
            max_reintentos=orm.max_reintentos,
            tamano_modelo_bytes=orm.tamano_modelo_bytes,
            tamano_descargado_bytes=orm.tamano_descargado_bytes,
            duracion_proceso_ms=orm.duracion_proceso_ms,
            ventana_inicio=orm.ventana_inicio,
            ventana_fin=orm.ventana_fin,
            nivel_bateria_al_inicio=orm.nivel_bateria_al_inicio,
            fecha_inicio=orm.fecha_inicio,
            fecha_fin=orm.fecha_fin,
            motivo_fallo=orm.motivo_fallo,
        )
