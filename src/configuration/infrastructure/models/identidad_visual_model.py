"""Modelo ORM para `modulo9.identidad_visuales` (RF-26).

Identidad visual institucional por finca. La concurrencia optimista se
controla con el campo ``version`` (entero). El registro más reciente
por finca es el activo (según ``vw_rf26_identidad_visual_activa``).
"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence, String
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class IdentidadVisualModel(Base):
    __tablename__ = 'identidad_visuales'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_finca'],
            ['modulo9.fincas.id_finca'],
            name='identidad_visuales_id_finca_fkey',
        ),
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='identidad_visuales_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_identidad_visual', name='identidad_visuales_pkey'),
        {'schema': 'modulo9'},
    )

    id_identidad_visual: Mapped[int] = mapped_column(
        Integer,
        Sequence('identidad_visuales_id_identidad_visual_seq', schema='modulo9'),
        primary_key=True,
    )
    id_finca: Mapped[int] = mapped_column(Integer, nullable=False)
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    logo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    secondary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    org_display_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fecha_creacion: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
