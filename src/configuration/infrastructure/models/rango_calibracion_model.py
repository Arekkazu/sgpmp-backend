"""Modelo ORM para `modulo9.rangos_calibracion` (RF-24).

Catálogo del rango de seguridad (min/max) permitido para el valor de
calibración de un sensor, indexado por su `categoria` (tipo de sensor).
Solo lectura desde la app; los rangos se gestionan por seed/SQL.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Integer, Numeric, PrimaryKeyConstraint, Sequence, String, TIMESTAMP, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base_model import Base


class RangoCalibracionModel(Base):
    __tablename__ = 'rangos_calibracion'
    __table_args__ = (
        PrimaryKeyConstraint('id_rango_calibracion', name='rangos_calibracion_pkey'),
        UniqueConstraint('categoria', name='rangos_calibracion_categoria_key'),
        CheckConstraint('valor_max >= valor_min', name='rangos_calibracion_min_max_check'),
        {'schema': 'modulo9'},
    )

    id_rango_calibracion: Mapped[int] = mapped_column(
        Integer,
        Sequence('rangos_calibracion_id_rango_calibracion_seq', schema='modulo9'),
        primary_key=True,
    )
    categoria: Mapped[str] = mapped_column(String(30), nullable=False)
    valor_min: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    valor_max: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
