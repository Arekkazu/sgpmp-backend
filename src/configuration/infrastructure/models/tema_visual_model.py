"""Modelo ORM para `modulo9.temas_visuales` (RF-27)."""
from __future__ import annotations

import datetime

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class TemaVisualModel(Base):
    __tablename__ = 'temas_visuales'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='temas_visuales_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_tema_visual', name='temas_visuales_pkey'),
        {'schema': 'modulo9'},
    )

    id_tema_visual: Mapped[int] = mapped_column(
        Integer,
        Sequence('temas_visuales_id_tema_visual_seq', schema='modulo9'),
        primary_key=True,
    )
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    theme_mode: Mapped[int] = mapped_column(Integer, nullable=False)
    es_global: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fecha_actualizacion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
