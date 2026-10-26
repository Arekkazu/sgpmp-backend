# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-42 RF-60: bloquea estados y verifica alcance de finca |
# | 2026-10-24 | Arekkazu | USAB-M03 M3-10 RF-60: listado de dispositivos con estado, batería y señal |
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.dispositivo_con_estado import DispositivoConEstado
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.domain.repositories.estado_dispositivo_iot_repository import EstadoDispositivoIoTRepository
from src.telemetry.infrastructure.models.estado_dispositivo_iot_model import EstadoDispositivoIoTModel


class SqlAlchemyEstadoDispositivoIoTRepository(EstadoDispositivoIoTRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def bloquear_por_dispositivo(self, id_dispositivo_iot):
        self.db.execute(text('SELECT pg_advisory_xact_lock(3505, :id)'), {'id': id_dispositivo_iot})
        orm = self.db.execute(select(EstadoDispositivoIoTModel).where(
            EstadoDispositivoIoTModel.id_dispositivo_iot == id_dispositivo_iot
        ).order_by(EstadoDispositivoIoTModel.id_estado_dispositivo_iot.desc())
          .limit(1).with_for_update().execution_options(populate_existing=True)).scalars().first()
        return self._a_entidad(orm) if orm else None

    def pertenece_a_fincas(self, id_dispositivo_iot, fincas):
        return bool(self.db.execute(text('''SELECT EXISTS (
            SELECT 1 FROM modulo9.dispositivos_iot d JOIN modulo9.infraestructuras i
              ON i.id_infraestructura=d.id_infraestructura
            WHERE d.id_dispositivo_iot=:id AND i.id_finca=ANY(:fincas))'''),
            {'id': id_dispositivo_iot, 'fincas': fincas}).scalar_one())

    def listar_con_estado(self, ids_fincas_permitidas, estado=None):
        # M3-10: el estado vigente es el más reciente (UNIQUE en BD, LIMIT 1 por si un
        # entorno conserva duplicados); batería y señal salen del último heartbeat.
        filas = self.db.execute(text('''
            SELECT d.id_dispositivo_iot, d.serial, d.descripcion, d.id_infraestructura,
                   i.nombre AS nombre_infraestructura, f.nombre AS nombre_finca,
                   coalesce(e.estado_actual::text, 'DESCONOCIDO') AS estado_actual,
                   e.fecha_ultimo_contacto, h.nivel_bateria_pct, h.calidad_senal_rssi
            FROM modulo9.dispositivos_iot d
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
            JOIN modulo9.fincas f ON f.id_finca = i.id_finca
            LEFT JOIN LATERAL (
                SELECT x.estado_actual, x.fecha_ultimo_contacto, x.id_ultimo_heardbeat
                FROM modulo3.estados_dispositivos_iot x
                WHERE x.id_dispositivo_iot = d.id_dispositivo_iot
                ORDER BY x.fecha_ultima_actualizacion DESC LIMIT 1
            ) e ON true
            LEFT JOIN modulo3.heartbeats h ON h.id_heartbeat = e.id_ultimo_heardbeat
            WHERE d.es_activo
              AND (CAST(:fincas AS int[]) IS NULL OR i.id_finca = ANY(CAST(:fincas AS int[])))
              AND (CAST(:estado AS text) IS NULL OR coalesce(e.estado_actual::text, 'DESCONOCIDO') = :estado)
            ORDER BY CASE coalesce(e.estado_actual::text, 'DESCONOCIDO')
                       WHEN 'SIN_SEÑAL' THEN 0 WHEN 'INACTIVO' THEN 1 WHEN 'DESCONOCIDO' THEN 2
                       WHEN 'BUFFER_ACTIVO' THEN 3 WHEN 'EN_MANTENIMIENTO' THEN 4 ELSE 5 END,
                     f.nombre, i.nombre, d.serial
        '''), {'fincas': ids_fincas_permitidas, 'estado': estado}).mappings().all()
        return [DispositivoConEstado(**dict(f)) for f in filas]

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
            ).order_by(EstadoDispositivoIoTModel.id_dispositivo_iot)
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
