"""Modelo ORM para `modulo9.dashboard_layouts` (RF-28).

El JSONB ``config`` almacena ``{"grid": [...WidgetConfig...]}``.
El array ``active_widget`` contiene los identificadores de widgets visibles.
"""
from __future__ import annotations

import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class DashboardLayoutModel(Base):
    __tablename__ = 'dashboard_layouts'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='dashboard_layouts_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_dashboard_layout', name='dashboard_layouts_pkey'),
        {'schema': 'modulo9'},
    )

    id_dashboard_layout: Mapped[int] = mapped_column(
        Integer,
        Sequence('dashboard_layouts_id_dashboard_layout_seq', schema='modulo9'),
        primary_key=True,
    )
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    active_widget: Mapped[list] = mapped_column(ARRAY(String), nullable=False)
    fecha_actualizacion: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
