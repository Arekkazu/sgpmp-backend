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
    limite_inferior: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    limite_superior: Mapped[Decimal] = mapped_column(Numeric, nullable=False)

    umbral: Mapped['UmbralAmbientalModel'] = relationship(
        'UmbralAmbientalModel',
        back_populates='niveles',
    )
