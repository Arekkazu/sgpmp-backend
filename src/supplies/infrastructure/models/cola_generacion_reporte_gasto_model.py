"""Modelo ORM para ``modulo5.cola_generacion_reportes_gastos`` (RF-77 / motor async).

Generado con sqlacodegen y adaptado (Base compartida, sin relationships). Cola de
trabajos de generación de reportes de gastos que requieren procesamiento async
(rango > 12 meses, o > 6 meses en consultas agregadas). ``parametros`` guarda los
filtros del reporte solicitado (activo/infraestructura/especie, fechas, categorías,
granularidad) — ver ``anotaciones/modulo_5/cu04_gaps_bd_rf77_rf81.md`` Gap 4.
"""
from typing import Optional
import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class ColaGeneracionReporteGastoModel(Base):
    __tablename__ = 'cola_generacion_reportes_gastos'
    __table_args__ = (
        ForeignKeyConstraint(['id_usuario_solicitante'], ['modulo1.usuarios.id_usuario'], name='cola_generacion_reportes_gastos_id_usuario_solicitante_fkey'),
        PrimaryKeyConstraint('id_cola', name='cola_generacion_reportes_gastos_pkey'),
        Index('idx_cola_reportes_gastos_estado', 'estado', 'fecha_solicitud'),
        {'schema': 'modulo5'}
    )

    id_cola: Mapped[int] = mapped_column(Integer, primary_key=True)
    parametros: Mapped[dict] = mapped_column(JSONB, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'PENDIENTE'::character varying"))
    id_usuario_solicitante: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_solicitud: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    fecha_procesado: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
