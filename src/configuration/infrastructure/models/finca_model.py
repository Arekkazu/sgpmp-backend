"""Modelo ORM para `modulo9.fincas` (RF-19)."""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, Numeric, PrimaryKeyConstraint, Sequence, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class FincaModel(Base):
    __tablename__ = 'fincas'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='finca_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_finca', name='finca_pkey'),
        {'schema': 'modulo9'},
    )

    id_finca: Mapped[int] = mapped_column(
        Integer,
        Sequence('finca_id_finca_seq', schema='modulo9'),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(String(55), nullable=False)
    ubicacion: Mapped[dict] = mapped_column(JSONB, nullable=False)
    tamano_h: Mapped[float] = mapped_column(Numeric, nullable=False)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_actualizacion: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer)
    es_activo: Mapped[Optional[bool]] = mapped_column(Boolean)
