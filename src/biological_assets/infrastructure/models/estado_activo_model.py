# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Modelo ORM del catálogo ``modulo2.estados_activos_biologicos`` (ver
``EstadoActivo``).
"""

from __future__ import annotations

from sqlalchemy import Identity, Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class EstadoActivoBiologicoModel(Base):
    """Modelo ORM del catálogo de estados de activo (tabla ``modulo2.estados_activos_biologicos``)."""
    __tablename__ = 'estados_activos_biologicos'
    __table_args__ = (
        PrimaryKeyConstraint('id_estado_activo_biologico', name='estados_activos_biologicos_pkey'),
        {'schema': 'modulo2'},
    )

    id_estado_activo_biologico: Mapped[int] = mapped_column(
        Integer,
        Identity(start=1, increment=1),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)
