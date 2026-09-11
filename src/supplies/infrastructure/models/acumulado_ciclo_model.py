"""Modelo ORM para ``modulo5.acumulado_ciclo`` (RF-78 / CU-05).

Generado con sqlacodegen y adaptado (Base compartida, sin ``relationship``
cross-module). Una fila por instancia real de ciclo productivo de un activo
(``id_gestion_fases`` — no ``id_ciclo_productivo``, que es un catálogo
reutilizable entre activos, ver ``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md``
Gap 1). Mantenida atómicamente por el trigger ``trg_acumular_costo_ciclo``
(AFTER INSERT en ``registro_suministro``, ``INSERT ... ON CONFLICT DO UPDATE``)
— la app solo la lee; la escritura de mutación ocurre exclusivamente vía ese
trigger, nunca con un ``UPDATE`` directo desde Python.
"""
from typing import Optional
import datetime
import decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class AcumuladoCicloModel(Base):
    __tablename__ = 'acumulado_ciclo'
    __table_args__ = (
        CheckConstraint('acumulado_total_ciclo >= 0::numeric', name='chk_acumulado_no_negativo'),
        ForeignKeyConstraint(['id_activo_biologico'], ['modulo2.activos_biologicos.id_activo_biologico'], name='fk_acumulado_ciclo_activo'),
        ForeignKeyConstraint(['id_ciclo_productivo'], ['modulo9.ciclos_productivos.id_ciclo_productivo'], name='fk_acumulado_ciclo_ciclo_productivo'),
        ForeignKeyConstraint(['id_gestion_fases'], ['modulo2.gestiones_fases.id_gestion_fases'], name='fk_acumulado_ciclo_gestion_fases'),
        PrimaryKeyConstraint('id_acumulado_ciclo', name='acumulado_ciclo_pkey'),
        UniqueConstraint('id_gestion_fases', name='idx_acumulado_ciclo_uniq'),
        Index('idx_acumulado_ciclo_activo', 'id_activo_biologico'),
        {'schema': 'modulo5'}
    )

    id_acumulado_ciclo: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_ciclo_productivo: Mapped[int] = mapped_column(Integer, nullable=False)
    id_activo_biologico: Mapped[int] = mapped_column(Integer, nullable=False)
    id_gestion_fases: Mapped[int] = mapped_column(Integer, nullable=False)
    version_acumulado: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    acumulado_total_ciclo: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric, server_default=text('0'))
    acumulado_por_categoria: Mapped[Optional[dict]] = mapped_column(JSONB)
    fecha_ultima_actualizacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    estado: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'ACTIVO'::character varying"))
