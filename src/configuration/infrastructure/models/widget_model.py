"""Modelo ORM para `modulo9.widgets` — catálogo de widgets del dashboard (RF-28).

``id_recurso`` apunta al recurso de ``modulo1.recursos`` cuyo permiso de lectura
habilita el widget. ``fuente_datos`` nombra la vista que lo alimenta; NULL
significa "todavía sin fuente", no error.
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKeyConstraint,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class WidgetModel(Base):
    __tablename__ = 'widgets'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_recurso'],
            ['modulo1.recursos.id_recurso'],
            name='fk_widgets_recurso',
        ),
        PrimaryKeyConstraint('id_widget', name='widgets_pkey'),
        UniqueConstraint('clave', name='widgets_clave_key'),
        CheckConstraint('span_predeterminado IN (1, 2)', name='widgets_span_predeterminado_check'),
        {'schema': 'modulo9'},
    )

    id_widget: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    clave: Mapped[str] = mapped_column(String(40), nullable=False)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    grupo: Mapped[str] = mapped_column(String(40), nullable=False)
    span_predeterminado: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    id_recurso: Mapped[int] = mapped_column(Integer, nullable=False)
    fuente_datos: Mapped[str | None] = mapped_column(String(60), nullable=True)
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
