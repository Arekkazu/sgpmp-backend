# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: persistencia de solicitudes y archivos de reportes  |
"""Implementación SQLAlchemy de :class:`SolicitudReporteRepository` (RF-104).

La RLS de ``modulo8`` deja ver a cada usuario sus solicitudes (y al usuario de servicio todas). ``obtener`` busca
como sistema para poder responder 403 —no 404— cuando el reporte es de otro usuario (CA-14)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session, load_only

from src.reporting.domain.repositories.solicitud_reporte_repository import SolicitudReporteRepository
from src.reporting.domain.reportes.solicitud import EN_PROCESO, GENERADO, ArchivoReporte, SolicitudReporte
from src.reporting.infrastructure.models.solicitud_reporte_model import ArchivoReporteModel, SolicitudReporteModel
from src.shared.database import como_sistema
from src.shared.db_error_translator import raise_from_db_error

_CAMPOS = ("id_usuario", "tipo_reporte", "formato", "estado", "zona_horaria", "numero_registros", "numero_partes",
           "tamano_archivo_kb", "checksum_sha256", "intentos", "mensaje_error", "fecha_snapshot", "fecha_generacion",
           "fecha_proximo_intento", "fecha_expiracion", "fecha_eliminacion")


def _a_entidad(orm: SolicitudReporteModel) -> SolicitudReporte:
    return SolicitudReporte(id_solicitud_reporte=orm.id_solicitud_reporte, filtros=dict(orm.json_filtros or {}),
                            fecha_solicitud=orm.fecha_solicitud, **{c: getattr(orm, c) for c in _CAMPOS})


def _archivo(orm: ArchivoReporteModel, con_contenido: bool = True) -> ArchivoReporte:
    return ArchivoReporte(numero_parte=orm.numero_parte, nombre_archivo=orm.nombre_archivo,
                          tipo_contenido=orm.tipo_contenido, contenido=orm.contenido if con_contenido else None,
                          tamano_bytes=orm.tamano_bytes, checksum_sha256=orm.checksum_sha256)


class SqlAlchemySolicitudReporteRepository(SolicitudReporteRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def guardar(self, solicitud: SolicitudReporte) -> SolicitudReporte:
        try:
            orm = (self.db.get(SolicitudReporteModel, solicitud.id_solicitud_reporte)
                   if solicitud.id_solicitud_reporte else None)
            if orm is None:
                orm = SolicitudReporteModel(id_solicitud_reporte=solicitud.id_solicitud_reporte)
                self.db.add(orm)
            for campo in _CAMPOS:
                setattr(orm, campo, getattr(solicitud, campo))
            orm.json_filtros = solicitud.filtros
            self.db.flush()
            self.db.refresh(orm)
            return _a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def guardar_archivos(self, id_solicitud: UUID, partes: list[ArchivoReporte]) -> None:
        try:
            for p in partes:
                self.db.add(ArchivoReporteModel(
                    id_solicitud_reporte=id_solicitud, numero_parte=p.numero_parte, nombre_archivo=p.nombre_archivo,
                    tipo_contenido=p.tipo_contenido, contenido=p.contenido, tamano_bytes=p.tamano_bytes,
                    checksum_sha256=p.checksum_sha256))
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)

    def obtener(self, id_solicitud: UUID, *, bloquear: bool = False) -> Optional[SolicitudReporte]:
        consulta = select(SolicitudReporteModel).where(SolicitudReporteModel.id_solicitud_reporte == id_solicitud)
        if bloquear:
            consulta = consulta.with_for_update()
        with como_sistema(self.db):
            orm = self.db.execute(consulta).scalar_one_or_none()
        return _a_entidad(orm) if orm else None

    def obtener_archivo(self, id_solicitud: UUID, numero_parte: int) -> Optional[ArchivoReporte]:
        orm = self.db.execute(select(ArchivoReporteModel).where(
            ArchivoReporteModel.id_solicitud_reporte == id_solicitud,
            ArchivoReporteModel.numero_parte == numero_parte)).scalar_one_or_none()
        return _archivo(orm) if orm else None

    def listar_archivos(self, id_solicitud: UUID) -> list[ArchivoReporte]:
        filas = self.db.execute(
            select(ArchivoReporteModel)
            .options(load_only(ArchivoReporteModel.numero_parte, ArchivoReporteModel.nombre_archivo,
                               ArchivoReporteModel.tipo_contenido, ArchivoReporteModel.tamano_bytes,
                               ArchivoReporteModel.checksum_sha256))
            .where(ArchivoReporteModel.id_solicitud_reporte == id_solicitud)
            .order_by(ArchivoReporteModel.numero_parte)).scalars()
        return [_archivo(f, con_contenido=False) for f in filas]

    def listar_por_usuario(self, id_usuario: int, limite: int) -> list[SolicitudReporte]:
        filas = self.db.execute(
            select(SolicitudReporteModel).where(SolicitudReporteModel.id_usuario == id_usuario)
            .order_by(SolicitudReporteModel.fecha_solicitud.desc()).limit(limite)).scalars()
        return [_a_entidad(f) for f in filas]

    def tomar_pendientes(self, ahora: datetime, limite: int) -> list[SolicitudReporte]:
        filas = self.db.execute(
            select(SolicitudReporteModel)
            .where(SolicitudReporteModel.estado == EN_PROCESO, SolicitudReporteModel.fecha_proximo_intento <= ahora)
            .order_by(SolicitudReporteModel.fecha_proximo_intento).limit(limite)
            .with_for_update(skip_locked=True)).scalars()
        return [_a_entidad(f) for f in filas]

    def tomar_vencidas(self, ahora: datetime, limite: int) -> list[SolicitudReporte]:
        filas = self.db.execute(
            select(SolicitudReporteModel)
            .where(SolicitudReporteModel.estado == GENERADO, SolicitudReporteModel.fecha_expiracion <= ahora)
            .limit(limite).with_for_update(skip_locked=True)).scalars()
        return [_a_entidad(f) for f in filas]

    def borrar_contenido(self, id_solicitud: UUID) -> None:
        try:
            self.db.execute(update(ArchivoReporteModel)
                            .where(ArchivoReporteModel.id_solicitud_reporte == id_solicitud)
                            .values(contenido=None))
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
