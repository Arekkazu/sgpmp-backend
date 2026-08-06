"""Modelo ORM para ``modulo5.cola_trabajos_historial_suministros`` (RF-81 / motor async).

Generado con sqlacodegen y adaptado (Base compartida, sin relationships). Cola de
trabajos pesados de historial de suministros: ``tipo_trabajo`` distingue
``CONSULTA_PESADA`` (nivel de volumen 3/4) de ``EXPORTACION`` (> 10.000 registros).
``parametros`` guarda los filtros de ``FiltrosHistorialSuministro`` (+ formato si
es exportación) — ver ``anotaciones/modulo_5/cu04_gaps_bd_rf77_rf81.md`` Gap 5.
"""
from typing import Optional
import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class ColaTrabajoHistorialSuministroModel(Base):
    __tablename__ = 'cola_trabajos_historial_suministros'
    __table_args__ = (
        ForeignKeyConstraint(['id_usuario_solicitante'], ['modulo1.usuarios.id_usuario'], name='cola_trabajos_historial_suministros_id_usuario_solicitante_fkey'),
        PrimaryKeyConstraint('id_cola', name='cola_trabajos_historial_suministros_pkey'),
        Index('idx_cola_hist_sum_estado', 'estado', 'fecha_solicitud'),
        {'schema': 'modulo5'}
    )

    id_cola: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo_trabajo: Mapped[str] = mapped_column(String(20), nullable=False)
    parametros: Mapped[dict] = mapped_column(JSONB, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'PENDIENTE'::character varying"))
    id_usuario_solicitante: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_solicitud: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    fecha_procesado: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
