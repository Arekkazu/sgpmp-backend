from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.prediction.domain.entities.version_modelo import VersionModelo
from src.prediction.domain.repositories.version_modelo_repository import VersionModeloRepository
from src.prediction.infrastructure.models.historial_estado_modelo_model import HistorialEstadoModeloModel
from src.prediction.infrastructure.models.version_modelo_model import VersionModeloModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyVersionModeloRepository(VersionModeloRepository):

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Mapeo ORM → entidad
    # ------------------------------------------------------------------

    def _a_entidad(self, orm: VersionModeloModel) -> VersionModelo:
        return VersionModelo(
            id_version_modelo=orm.id_version_modelo,
            nombre_version=orm.nombre_version,
            tipo_modelo=orm.tipo_modelo,
            estado_version=orm.estado_version,
            formato_artefacto=orm.formato_artefacto,
            ruta_artefacto=orm.ruta_artefacto,
            tamanio_artefacto_bytes=orm.tamanio_artefacto_bytes,
            hash_artefacto_sha256=orm.hash_artefacto_sha256,
            dataset_entrenamiento_hash=orm.dataset_entrenamiento_hash,
            id_proceso_rf71=orm.id_proceso_rf71,
            version_referencia=orm.version_referencia,
            f1_score=Decimal(str(orm.f1_score)) if orm.f1_score is not None else None,
            recall_clase_riesgo_alto=(
                Decimal(str(orm.recall_clase_riesgo_alto))
                if orm.recall_clase_riesgo_alto is not None
                else None
            ),
            precision_modelo=(
                Decimal(str(orm.precision_modelo)) if orm.precision_modelo is not None else None
            ),
            accuracy=Decimal(str(orm.accuracy)) if orm.accuracy is not None else None,
            roc_auc_score=(
                Decimal(str(orm.roc_auc_score)) if orm.roc_auc_score is not None else None
            ),
            recall_por_clase=orm.recall_por_clase,
            matriz_confusion=orm.matriz_confusion,
            compatibilidad_variables=orm.compatibilidad_variables,
            notas_validacion=orm.notas_validacion,
            detalle_validacion=orm.detalle_validacion,
            id_usuario=orm.id_usuario,
            esta_produccion=orm.esta_produccion,
            fecha_entrenamiento=orm.fecha_entrenamiento,
            fecha_registro=orm.fecha_registro,
            fecha_despliegue=orm.fecha_despliegue,
        )

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------

    def guardar(self, entidad: VersionModelo) -> VersionModelo:
        try:
            orm = VersionModeloModel(
                nombre_version=entidad.nombre_version,
                tipo_modelo=entidad.tipo_modelo,
                estado_version=entidad.estado_version,
                formato_artefacto=entidad.formato_artefacto,
                ruta_artefacto=entidad.ruta_artefacto,
                tamanio_artefacto_bytes=entidad.tamanio_artefacto_bytes,
                hash_artefacto_sha256=entidad.hash_artefacto_sha256,
                dataset_entrenamiento_hash=entidad.dataset_entrenamiento_hash,
                id_proceso_rf71=entidad.id_proceso_rf71,
                version_referencia=entidad.version_referencia,
                f1_score=entidad.f1_score,
                recall_clase_riesgo_alto=entidad.recall_clase_riesgo_alto,
                precision_modelo=entidad.precision_modelo,
                accuracy=entidad.accuracy,
                roc_auc_score=entidad.roc_auc_score,
                recall_por_clase=entidad.recall_por_clase,
                matriz_confusion=entidad.matriz_confusion,
                compatibilidad_variables=entidad.compatibilidad_variables,
                notas_validacion=entidad.notas_validacion,
                detalle_validacion=entidad.detalle_validacion,
                id_usuario=entidad.id_usuario,
                esta_produccion=entidad.esta_produccion,
                fecha_entrenamiento=entidad.fecha_entrenamiento,
                fecha_despliegue=entidad.fecha_despliegue,
            )
            self._db.add(orm)
            self._db.flush()
            self._db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def actualizar(self, entidad: VersionModelo) -> VersionModelo:
        try:
            orm = self._db.get(VersionModeloModel, entidad.id_version_modelo)
            orm.estado_version = entidad.estado_version
            orm.notas_validacion = entidad.notas_validacion
            orm.detalle_validacion = entidad.detalle_validacion
            orm.esta_produccion = entidad.esta_produccion
            orm.fecha_despliegue = entidad.fecha_despliegue
            self._db.flush()
            self._db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def registrar_historial(
        self,
        *,
        id_version_modelo: int,
        estado_anterior: Optional[str],
        estado_nuevo: str,
        tipo_actor: str,
        id_usuario: Optional[int] = None,
        id_sistema: Optional[str] = None,
        id_proceso_rf71: Optional[uuid.UUID] = None,
        correlacion_id: Optional[uuid.UUID] = None,
        motivo: Optional[str] = None,
    ) -> None:
        try:
            historial = HistorialEstadoModeloModel(
                id_version_modelo=id_version_modelo,
                estado_anterior=estado_anterior,
                estado_nuevo=estado_nuevo,
                tipo_actor=tipo_actor,
                id_usuario=id_usuario,
                id_sistema=id_sistema,
                id_proceso_rf71=id_proceso_rf71,
                correlacion_id=correlacion_id,
                motivo=motivo,
            )
            self._db.add(historial)
            self._db.flush()
        except Exception as exc:
            raise_from_db_error(exc)

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    def obtener_por_id(self, id_version: int) -> Optional[VersionModelo]:
        orm = self._db.get(VersionModeloModel, id_version)
        return self._a_entidad(orm) if orm else None

    def obtener_activo_por_tipo(self, tipo_modelo: str) -> Optional[VersionModelo]:
        orm = self._db.execute(
            select(VersionModeloModel).where(
                VersionModeloModel.tipo_modelo == tipo_modelo,
                VersionModeloModel.estado_version == "ACTIVO",
            )
        ).scalar_one_or_none()
        return self._a_entidad(orm) if orm else None

    def listar(
        self,
        *,
        tipo_modelo: Optional[str] = None,
        estado: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[VersionModelo], int]:
        base = select(VersionModeloModel)
        count_q = select(func.count()).select_from(VersionModeloModel)

        if tipo_modelo:
            base = base.where(VersionModeloModel.tipo_modelo == tipo_modelo)
            count_q = count_q.where(VersionModeloModel.tipo_modelo == tipo_modelo)
        if estado:
            base = base.where(VersionModeloModel.estado_version == estado)
            count_q = count_q.where(VersionModeloModel.estado_version == estado)

        total = self._db.execute(count_q).scalar_one()
        orms = self._db.execute(
            base.order_by(VersionModeloModel.id_version_modelo.desc()).limit(limit).offset(offset)
        ).scalars().all()
        return [self._a_entidad(o) for o in orms], total
