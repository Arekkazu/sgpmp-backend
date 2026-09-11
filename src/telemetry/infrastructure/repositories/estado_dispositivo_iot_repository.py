from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.domain.repositories.estado_dispositivo_iot_repository import EstadoDispositivoIoTRepository
from src.telemetry.infrastructure.models.estado_dispositivo_iot_model import EstadoDispositivoIoTModel


class SqlAlchemyEstadoDispositivoIoTRepository(EstadoDispositivoIoTRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_por_dispositivo(self, id_dispositivo_iot: int) -> Optional[EstadoDispositivoIoT]:
        # Un estado actual por dispositivo (garantizado por UNIQUE en DB). Se ordena y
        # limita a 1 para no romper con 500 si algún entorno todavía tuviera duplicados.
        orm = self.db.execute(
            select(EstadoDispositivoIoTModel)
            .where(EstadoDispositivoIoTModel.id_dispositivo_iot == id_dispositivo_iot)
            .order_by(
                EstadoDispositivoIoTModel.fecha_ultima_actualizacion.desc(),
                EstadoDispositivoIoTModel.fecha_ultimo_contacto.desc().nullslast(),
                EstadoDispositivoIoTModel.id_estado_dispositivo_iot.desc(),
            )
            .limit(1)
        ).scalars().first()
        return self._a_entidad(orm) if orm else None

    def listar_activos(self) -> List[EstadoDispositivoIoT]:
        rows = self.db.execute(
            select(EstadoDispositivoIoTModel).where(
                EstadoDispositivoIoTModel.estado_actual != 'EN_MANTENIMIENTO'
            )
        ).scalars().all()
        return [self._a_entidad(r) for r in rows]

    def guardar(self, estado: EstadoDispositivoIoT) -> EstadoDispositivoIoT:
        try:
            orm = EstadoDispositivoIoTModel(
                id_dispositivo_iot=estado.id_dispositivo_iot,
                estado_actual=estado.estado_actual,
                fecha_ultimo_contacto=estado.fecha_ultimo_contacto,
                id_ultimo_heardbeat=estado.id_ultimo_heartbeat,
                tiempo_sin_contacto=estado.tiempo_sin_contacto,
                causa_primaria=estado.causa_primaria,
                causas_secundarias=estado.causas_secundarias,
                fecha_ultima_actualizacion=estado.fecha_ultima_actualizacion,
                id_usuario=estado.id_usuario,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def actualizar(self, estado: EstadoDispositivoIoT) -> EstadoDispositivoIoT:
        try:
            orm = self.db.get(EstadoDispositivoIoTModel, estado.id_estado_dispositivo_iot)
            orm.estado_actual = estado.estado_actual
            orm.fecha_ultimo_contacto = estado.fecha_ultimo_contacto
            orm.id_ultimo_heardbeat = estado.id_ultimo_heartbeat
            orm.tiempo_sin_contacto = estado.tiempo_sin_contacto
            orm.causa_primaria = estado.causa_primaria
            orm.causas_secundarias = estado.causas_secundarias
            orm.fecha_ultima_actualizacion = estado.fecha_ultima_actualizacion
            orm.id_usuario = estado.id_usuario
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    @staticmethod
    def _a_entidad(orm: EstadoDispositivoIoTModel) -> EstadoDispositivoIoT:
        return EstadoDispositivoIoT(
            id_estado_dispositivo_iot=orm.id_estado_dispositivo_iot,
            id_dispositivo_iot=orm.id_dispositivo_iot,
            estado_actual=orm.estado_actual,
            fecha_ultimo_contacto=orm.fecha_ultimo_contacto,
            id_ultimo_heartbeat=orm.id_ultimo_heardbeat,
            tiempo_sin_contacto=orm.tiempo_sin_contacto,
            causa_primaria=orm.causa_primaria,
            causas_secundarias=orm.causas_secundarias,
            fecha_ultima_actualizacion=orm.fecha_ultima_actualizacion,
            id_usuario=orm.id_usuario,
        )
