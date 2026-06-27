"""Modelo ORM para la tabla `modulo9.especies_patologias`.

Tabla pivot que asocia patologías globales a especies específicas.
La combinación (id_patologia, id_especie) es única (uq_especie_patologia).
"""
from __future__ import annotations

from sqlalchemy import ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class EspeciePatologiaModel(Base):
    __tablename__ = 'especies_patologias'
    __table_args__ = (
        UniqueConstraint('id_patologia', 'id_especie', name='uq_especie_patologia'),
        ForeignKeyConstraint(
            ['id_patologia'],
            ['modulo9.patologias.id_patologia'],
            name='especies_patologias_id_patologia_fkey',
        ),
        ForeignKeyConstraint(
            ['id_especie'],
            ['modulo9.especies.id_especie'],
            name='especies_patologias_id_especie_fkey',
        ),
        PrimaryKeyConstraint('id_especies_patologias', name='especies_patologias_pkey'),
        {'schema': 'modulo9'},
    )

    id_especies_patologias: Mapped[int] = mapped_column(
        Integer,
        Sequence('especies_patologias_id_especies_patologias_seq', schema='modulo9'),
        primary_key=True,
    )
    id_patologia: Mapped[int] = mapped_column(Integer, nullable=False)
    id_especie: Mapped[int] = mapped_column(Integer, nullable=False)
