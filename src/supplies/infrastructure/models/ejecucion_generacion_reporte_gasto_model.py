"""Modelo ORM para ``modulo5.ejecuciones_generacion_reportes_gastos`` (RF-77 / motor async).

Generado con sqlacodegen y adaptado (Base compartida, sin relationships). Registra
cada intento de procesamiento de un trabajo de ``cola_generacion_reportes_gastos``.
``resultado_json`` guarda el desglose temporal (SEMANAL/MENSUAL) y la tendencia vs
período anterior, que no caben en las columnas fijas de ``reporte_gastos_acumulados``.
"""
from typing import Optional
import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class EjecucionGeneracionReporteGastoModel(Base):
    __tablename__ = 'ejecuciones_generacion_reportes_gastos'
    __table_args__ = (
        ForeignKeyConstraint(['id_cola'], ['modulo5.cola_generacion_reportes_gastos.id_cola'], name='ejecuciones_generacion_reportes_gastos_id_cola_fkey'),
        ForeignKeyConstraint(['id_reporte_resultado'], ['modulo5.reporte_gastos_acumulados.id_reporte_gasto_acumulado'], name='ejecuciones_generacion_reportes_gasto_id_reporte_resultado_fkey'),
        PrimaryKeyConstraint('id_ejecucion', name='ejecuciones_generacion_reportes_gastos_pkey'),
        Index('idx_ejec_reportes_gastos_cola', 'id_cola'),
        {'schema': 'modulo5'}
    )

    id_ejecucion: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_cola: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'EN_PROCESO'::character varying"))
    intento: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    hora_inicio: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    hora_fin: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    id_reporte_resultado: Mapped[Optional[int]] = mapped_column(Integer)
    resultado_json: Mapped[Optional[dict]] = mapped_column(JSONB)
