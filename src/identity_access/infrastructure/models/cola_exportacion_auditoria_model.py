"""Modelos ORM de la cola asíncrona de exportaciones de auditoría (RF-10)."""
import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.base_model import Base


class ColaExportacionAuditoria(Base):
    """Solicitud de exportación pendiente de procesar."""

    __tablename__ = 'cola_exportaciones_auditoria'
    __table_args__ = {'schema': 'modulo1'}

    id_cola: Mapped[int] = mapped_column(Integer, primary_key=True)
    parametros: Mapped[dict] = mapped_column(JSONB, nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'PENDIENTE'::character varying")
    )
    id_usuario_solicitante: Mapped[int] = mapped_column(
        ForeignKey('modulo1.usuarios.id_usuario'), nullable=False
    )
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    error: Mapped[Optional[str]] = mapped_column(Text)
    fecha_solicitud: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text('now()')
    )
    fecha_procesado: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))


class EjecucionExportacionAuditoria(Base):
    """Resultado de una exportación ya generada, listo para descargar."""

    __tablename__ = 'ejecuciones_exportaciones_auditoria'
    __table_args__ = {'schema': 'modulo1'}

    id_ejecucion: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_cola: Mapped[int] = mapped_column(
        ForeignKey('modulo1.cola_exportaciones_auditoria.id_cola', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    )
    contenido_csv: Mapped[str] = mapped_column(Text, nullable=False)
    nombre_archivo: Mapped[str] = mapped_column(String(120), nullable=False)
    total_exportado: Mapped[int] = mapped_column(Integer, nullable=False)
    total_disponible: Mapped[int] = mapped_column(Integer, nullable=False)
    creado_en: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text('now()')
    )


class ConfiguracionBatchExportacionAuditoria(Base):
    """Fila única con los parámetros operativos del poller."""

    __tablename__ = 'configuracion_batch_exportacion_auditoria'
    __table_args__ = {'schema': 'modulo1'}

    id_configuracion: Mapped[int] = mapped_column(Integer, primary_key=True)
    num_workers_max: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('2'))
    max_reintentos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('3'))
    umbral_exportacion_async: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text('10000')
    )
    limite_concurrencia: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('3'))
    intervalo_poll_segundos: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text('15')
    )
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    actualizado_en: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text('now()')
    )
