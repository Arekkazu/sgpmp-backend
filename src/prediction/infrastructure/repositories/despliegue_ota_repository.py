from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.prediction.domain.entities.despliegue_ota import DespliegueOta
from src.prediction.domain.repositories.despliegue_ota_repository import DespliegueOtaRepository
from src.prediction.infrastructure.models.despliegue_ota_model import DespliegueOtaModel
from src.shared.db_error_translator import raise_from_db_error


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

    def obtener_por_id(self, id_despliegue: int, *, bloquear: bool = False) -> Optional[DespliegueOta]:
        # bloquear: dos reportes del mismo nodo no deben pisarse (FOR UPDATE).
        orm = self._db.get(DespliegueOtaModel, id_despliegue, with_for_update=bloquear or None)
        return self._a_entidad(orm) if orm else None

    # ── DEV-15: orquestador OTA ─────────────────────────────────────────────

    def crear(self, entidad: DespliegueOta) -> DespliegueOta:
        try:
            orm = DespliegueOtaModel(
                id_version_modelo=entidad.id_version_modelo,
                id_dispositivo_iot=entidad.id_dispositivo_iot,
                tipo_modelo=entidad.tipo_modelo,
                componente=entidad.componente,
                modo_distribucion=entidad.modo_distribucion,
                estado_despliegue=entidad.estado_despliegue,
                hash_modelo_sha256=entidad.hash_modelo_sha256,
                id_version_modelo_anterior=entidad.id_version_modelo_anterior,
                rollback_ejecutado=False,
                intentos_descarga=0,
                max_reintentos=entidad.max_reintentos,
                tamano_modelo_bytes=entidad.tamano_modelo_bytes,
                ventana_inicio=entidad.ventana_inicio,
                ventana_fin=entidad.ventana_fin,
                id_distribucion_ota=entidad.id_distribucion_ota,
                fase_rollout=entidad.fase_rollout,
            )
            self._db.add(orm)
            self._db.flush()
            self._db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def actualizar(self, entidad: DespliegueOta) -> DespliegueOta:
        try:
            orm = self._db.get(DespliegueOtaModel, entidad.id_despliegue_ota)
            orm.estado_despliegue = entidad.estado_despliegue
            orm.resultado_validacion_hash = entidad.resultado_validacion_hash
            orm.rollback_ejecutado = entidad.rollback_ejecutado
            orm.intentos_descarga = entidad.intentos_descarga
            orm.tamano_descargado_bytes = entidad.tamano_descargado_bytes
            orm.duracion_proceso_ms = entidad.duracion_proceso_ms
            orm.nivel_bateria_al_inicio = entidad.nivel_bateria_al_inicio
            orm.fecha_fin = entidad.fecha_fin
            orm.motivo_fallo = entidad.motivo_fallo
            orm.fecha_expiracion_url = entidad.fecha_expiracion_url
            orm.id_mensaje_notify = entidad.id_mensaje_notify
            self._db.flush()
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def listar_por_distribucion(self, id_distribucion: int, fase: Optional[str] = None) -> list[DespliegueOta]:
        stmt = select(DespliegueOtaModel).where(DespliegueOtaModel.id_distribucion_ota == id_distribucion)
        if fase is not None:
            stmt = stmt.where(DespliegueOtaModel.fase_rollout == fase)
        stmt = stmt.order_by(DespliegueOtaModel.id_despliegue_ota)
        return [self._a_entidad(r) for r in self._db.execute(stmt).scalars().all()]

    def nodos_con_despliegue_vigente(
        self, ids_dispositivo: list[int], tipo_modelo: str, componente: Optional[str]
    ) -> list[int]:
        stmt = select(DespliegueOtaModel.id_dispositivo_iot).distinct().where(
            DespliegueOtaModel.id_dispositivo_iot.in_(ids_dispositivo),
            DespliegueOtaModel.tipo_modelo == tipo_modelo,
            DespliegueOtaModel.componente.is_not_distinct_from(componente),
            DespliegueOtaModel.estado_despliegue.in_(("PENDIENTE", "EN_PROCESO")),
        )
        return sorted(self._db.execute(stmt).scalars().all())

    def version_instalada(self, id_dispositivo: int, tipo_modelo: str, componente: Optional[str]) -> Optional[int]:
        stmt = (
            select(DespliegueOtaModel.id_version_modelo)
            .where(
                DespliegueOtaModel.id_dispositivo_iot == id_dispositivo,
                DespliegueOtaModel.tipo_modelo == tipo_modelo,
                DespliegueOtaModel.componente.is_not_distinct_from(componente),
                DespliegueOtaModel.estado_despliegue == "EXITOSO",
            )
            .order_by(DespliegueOtaModel.fecha_fin.desc().nulls_last(), DespliegueOtaModel.id_despliegue_ota.desc())
            .limit(1)
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def _a_entidad(self, orm: DespliegueOtaModel) -> DespliegueOta:
        return DespliegueOta(
            id_despliegue_ota=orm.id_despliegue_ota,
            id_version_modelo=orm.id_version_modelo,
            id_dispositivo_iot=orm.id_dispositivo_iot,
            tipo_modelo=orm.tipo_modelo,
            componente=orm.componente,
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
            id_distribucion_ota=orm.id_distribucion_ota,
            fase_rollout=orm.fase_rollout,
            fecha_expiracion_url=orm.fecha_expiracion_url,
            id_mensaje_notify=orm.id_mensaje_notify,
        )
