"""Modelo ORM para `modulo9.dashboard_layouts_default` — layout base por rol (RF-28).

Una fila por rol. Reemplaza al diccionario vacío que estaba quemado en la entidad
de dominio y que dejaba fuera a todo rol creado después del seed inicial.
"""
from __future__ import annotations

from sqlalchemy import ARRAY, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class DashboardLayoutDefaultModel(Base):
    __tablename__ = 'dashboard_layouts_default'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_rol'],
            ['modulo1.roles.id_rol'],
            name='fk_dashboard_layouts_default_rol',
            ondelete='CASCADE',
        ),
        PrimaryKeyConstraint('id_rol', name='dashboard_layouts_default_pkey'),
        {'schema': 'modulo9'},
    )

    id_rol: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    active_widget: Mapped[list] = mapped_column(ARRAY(String), nullable=False)
