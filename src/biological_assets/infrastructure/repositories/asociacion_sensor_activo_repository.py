from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import AsociacionSensorActivo
from src.biological_assets.domain.repositories.asociacion_sensor_activo_repository import (
    AsociacionSensorActivoRepository,
)
from src.biological_assets.infrastructure.models.asociacion_sensor_activo_model import AsociacionSensorActivoModel
from src.biological_assets.infrastructure.models.auditoria_asociacion_sensor_model import (
    AuditoriaAsociacionSensorModel,
)
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyAsociacionSensorActivoRepository(AsociacionSensorActivoRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: AsociacionSensorActivoModel) -> AsociacionSensorActivo:
        return AsociacionSensorActivo(
            id_asociacion_activo_sensor=orm.id_asociacion_activo_sensor,
            id_activo_biologico=orm.id_activo_biologico,
            tipo_activo=orm.tipo_activo,
            tipo_asociacion=orm.tipo,
            dispositivo_iot_id=orm.dispositivo_iot_id,
            sensor_id=orm.id_sensor,
            id_infraestructura=orm.id_infraestructura,
            id_usuario=orm.id_usuario,
            fecha_inicio=orm.fecha_inicio,
            estado_asociacion=orm.estado_asociacion,
            fecha_fin=orm.fecha_fin,
            motivo=orm.motivo,
        )

    def guardar(self, entidad: AsociacionSensorActivo) -> AsociacionSensorActivo:
        try:
            orm = AsociacionSensorActivoModel(
                id_activo_biologico=entidad.id_activo_biologico,
                tipo_activo=entidad.tipo_activo,
                tipo=entidad.tipo_asociacion,
                dispositivo_iot_id=entidad.dispositivo_iot_id,
                id_sensor=entidad.sensor_id,
                id_infraestructura=entidad.id_infraestructura,
                id_usuario=entidad.id_usuario,
                fecha_inicio=entidad.fecha_inicio,
                fecha_fin=entidad.fecha_fin,
                motivo=entidad.motivo,
                estado_asociacion=entidad.estado_asociacion,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def obtener_por_id(self, id_asociacion: int) -> Optional[AsociacionSensorActivo]:
        orm = self.db.get(AsociacionSensorActivoModel, id_asociacion)
        return self._a_entidad(orm) if orm else None

    def obtener_activa_por_sensor_y_activo(
        self,
        sensor_id: int,
        id_activo_biologico: int,
    ) -> Optional[AsociacionSensorActivo]:
        orm = (
            self.db.query(AsociacionSensorActivoModel)
            .filter(
                AsociacionSensorActivoModel.id_sensor == sensor_id,
                AsociacionSensorActivoModel.id_activo_biologico == id_activo_biologico,
                AsociacionSensorActivoModel.estado_asociacion == 'ACTIVA',
                AsociacionSensorActivoModel.fecha_fin.is_(None),
            )
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def listar_activas_por_sensor(
        self,
        sensor_id: int,
        tipo_asociacion: Optional[str] = None,
    ) -> list[AsociacionSensorActivo]:
        q = self.db.query(AsociacionSensorActivoModel).filter(
            AsociacionSensorActivoModel.id_sensor == sensor_id,
            AsociacionSensorActivoModel.estado_asociacion == 'ACTIVA',
            AsociacionSensorActivoModel.fecha_fin.is_(None),
        )
        if tipo_asociacion is not None:
            q = q.filter(AsociacionSensorActivoModel.tipo == tipo_asociacion)
        return [self._a_entidad(o) for o in q.all()]

    def listar_activas_por_activo(
        self,
        id_activo_biologico: int,
        tipo_asociacion: Optional[str] = None,
    ) -> list[AsociacionSensorActivo]:
        q = self.db.query(AsociacionSensorActivoModel).filter(
            AsociacionSensorActivoModel.id_activo_biologico == id_activo_biologico,
            AsociacionSensorActivoModel.estado_asociacion == 'ACTIVA',
            AsociacionSensorActivoModel.fecha_fin.is_(None),
        )
        if tipo_asociacion is not None:
            q = q.filter(AsociacionSensorActivoModel.tipo == tipo_asociacion)
        return [self._a_entidad(o) for o in q.all()]

    def actualizar_estado(self, entidad: AsociacionSensorActivo) -> AsociacionSensorActivo:
        try:
            orm = self.db.get(AsociacionSensorActivoModel, entidad.id_asociacion_activo_sensor)
            if orm is None:
                from src.shared.errors import NotFoundError
                raise NotFoundError(
                    code='ASOCIACION_NO_ENCONTRADA',
                    message=f'No existe asociación con id {entidad.id_asociacion_activo_sensor}.',
                )
            orm.estado_asociacion = entidad.estado_asociacion
            orm.fecha_fin = entidad.fecha_fin
            orm.motivo = entidad.motivo
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def registrar_auditoria(
        self,
        id_asociacion: int,
        id_usuario: int,
        tipo_op: str,
        valores_anteriores: Optional[dict],
        valores_nuevos: dict,
    ) -> None:
        try:
            self.db.add(AuditoriaAsociacionSensorModel(
                id_asociacion_activo_sensor=id_asociacion,
                id_usuario=id_usuario,
                tipo_operacion=tipo_op,
                valores_anteriores=valores_anteriores,
                valores_nuevos=valores_nuevos,
            ))
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
