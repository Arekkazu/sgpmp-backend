"""Modelo ORM para ``modulo5.ejecuciones_trabajos_historial_suministros`` (RF-81 / motor async).

Generado con sqlacodegen y adaptado (Base compartida, sin relationships).
``resultado_json`` guarda metadatos + primera página para ``CONSULTA_PESADA``;
``contenido_csv`` guarda el payload completo para ``EXPORTACION``.
"""
from typing import Optional
import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class EjecucionTrabajoHistorialSuministroModel(Base):
    __tablename__ = 'ejecuciones_trabajos_historial_suministros'
    __table_args__ = (
        ForeignKeyConstraint(['id_cola'], ['modulo5.cola_trabajos_historial_suministros.id_cola'], name='ejecuciones_trabajos_historial_suministros_id_cola_fkey'),
        PrimaryKeyConstraint('id_ejecucion', name='ejecuciones_trabajos_historial_suministros_pkey'),
        Index('idx_ejec_hist_sum_cola', 'id_cola'),
        {'schema': 'modulo5'}
    )

    id_ejecucion: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_cola: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'EN_PROCESO'::character varying"))
    intento: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    hora_inicio: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    hora_fin: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    total_registros: Mapped[Optional[int]] = mapped_column(Integer)
    resultado_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    contenido_csv: Mapped[Optional[str]] = mapped_column(Text)
    nombre_archivo: Mapped[Optional[str]] = mapped_column(String(120))
