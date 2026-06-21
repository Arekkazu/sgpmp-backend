"""Modelo ORM para `modulo9.variables_ambientales` (catálogo, solo lectura desde M09)."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Numeric, PrimaryKeyConstraint, Sequence, String
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class VariableAmbientalModel(Base):
    __tablename__ = 'variables_ambientales'
    __table_args__ = (
        PrimaryKeyConstraint('id_variable_ambiental', name='variables_ambientales_pkey'),
        {'schema': 'modulo9'},
    )

    id_variable_ambiental: Mapped[int] = mapped_column(
        Sequence('variables_ambientales_id_variable_ambiental_seq', schema='modulo9'),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    unidad: Mapped[str] = mapped_column(String, nullable=False)
    valor_fisico_min: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    valor_fisico_max: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False)
