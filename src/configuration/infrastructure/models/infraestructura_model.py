"""Modelo ORM para `modulo9.infraestructuras` (RF-20).

El tipo de área (`tipo`) es un enum de PostgreSQL mapeado como String
para evitar conflicto con el tipo existente en DB (patrón del proyecto).
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, Numeric, PrimaryKeyConstraint, Sequence, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class InfraestructuraModel(Base):
    __tablename__ = 'infraestructuras'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_finca'],
            ['modulo9.fincas.id_finca'],
            name='infraestructuras_id_finca_fkey',
        ),
        PrimaryKeyConstraint('id_infraestructura', name='infraestructuras_pkey'),
        UniqueConstraint('id_finca', 'nombre', name='uq_infraestructura_nombre'),
        {'schema': 'modulo9'},
    )

    id_infraestructura: Mapped[int] = mapped_column(
        Integer,
        Sequence('infraestructuras_id_infraestructura_seq', schema='modulo9'),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(String(100))
    id_finca: Mapped[int] = mapped_column(Integer, nullable=False)
    superficie: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_actualizacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
