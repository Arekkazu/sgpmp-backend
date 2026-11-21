# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: modelos de solicitudes y archivos de reportes (sqlacodegen) |
"""Modelos ORM de ``modulo8.solicitudes_reportes`` y ``modulo8.archivos_reportes`` (migración ``a7c3e91f5b20``).

Generados con sqlacodegen; las columnas de tipo ENUM de PostgreSQL se mapean como ``String`` (el tipo ya existe
en la BD y SQLAlchemy no debe intentar crearlo)."""
import datetime
import uuid
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Integer, LargeBinary, SmallInteger, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.base_model import Base


class SolicitudReporteModel(Base):
    __tablename__ = "solicitudes_reportes"
    __table_args__ = {"schema": "modulo8"}

    id_solicitud_reporte: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True,
                                                            server_default=text("gen_random_uuid()"))
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)  # FK en la BD (solicitudes_reportes_id_usuario_fkey)
    tipo_reporte: Mapped[str] = mapped_column(String(40), nullable=False)
    formato: Mapped[str] = mapped_column(String(10), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'EN_PROCESO'"))
    json_filtros: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    zona_horaria: Mapped[str] = mapped_column(String(64), nullable=False, server_default=text("'UTC'"))
    numero_partes: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    intentos: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    fecha_solicitud: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False,
                                                               server_default=text("now()"))
    numero_registros: Mapped[Optional[int]] = mapped_column(Integer)
    tamano_archivo_kb: Mapped[Optional[int]] = mapped_column(Integer)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64))
    mensaje_error: Mapped[Optional[str]] = mapped_column(String(500))
    fecha_snapshot: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    fecha_generacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    fecha_proximo_intento: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    fecha_expiracion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    fecha_eliminacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))


class ArchivoReporteModel(Base):
    __tablename__ = "archivos_reportes"
    __table_args__ = {"schema": "modulo8"}

    id_archivo_reporte: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_solicitud_reporte: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("modulo8.solicitudes_reportes.id_solicitud_reporte", ondelete="CASCADE"), nullable=False)
    numero_parte: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    nombre_archivo: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo_contenido: Mapped[str] = mapped_column(String(100), nullable=False)
    tamano_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    contenido: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
