"""Modelo ORM para `modulo9.niveles_alerta_ambientales` (hijos del agregado umbral)."""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKeyConstraint, Numeric, PrimaryKeyConstraint, Sequence, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base

if TYPE_CHECKING:
    from .umbral_ambiental_model import UmbralAmbientalModel


class NivelAlertaAmbientalModel(Base):
    __tablename__ = 'niveles_alerta_ambientales'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_umbral_ambiental'],
            ['modulo9.umbrales_ambientales.id_umbral_ambiental'],
            name='niveles_alerta_ambientales_id_umbral_ambiental_fkey',
        ),
        PrimaryKeyConstraint('id_nivel_alerta_ambiental', name='niveles_alerta_ambientales_pkey'),
        {'schema': 'modulo9'},
    )

    id_nivel_alerta_ambiental: Mapped[int] = mapped_column(
        Sequence('niveles_alerta_ambientales_id_nivel_alerta_ambiental_seq', schema='modulo9'),
        primary_key=True,
    )
    id_umbral_ambiental: Mapped[int] = mapped_column(nullable=False)
    nivel: Mapped[str] = mapped_column(String(20), nullable=False)
    # NUMERIC(5, 2): misma capacidad que umbrales_ambientales.valor_min/valor_max — un nivel
    # siempre cae dentro de [valor_min, valor_max] (INC-M09-103-G28, hallazgo adicional: la
    # columna real seguía en NUMERIC(8,2) aunque el padre ya se corrigió a NUMERIC(5,2)).
    limite_inferior: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    limite_superior: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    umbral: Mapped['UmbralAmbientalModel'] = relationship(
        'UmbralAmbientalModel',
        back_populates='niveles',
    )
