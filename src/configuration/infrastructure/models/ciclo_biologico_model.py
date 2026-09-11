"""Modelo ORM para la tabla `modulo9.ciclos_biologicos`.

Representa las etapas del ciclo productivo configuradas por especie (RF-16).
La unicidad del nombre se valida en aplicación (case-insensitive) por especie.
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence, String
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class CicloBiologicoModel(Base):
    __tablename__ = 'ciclos_biologicos'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_especie'],
            ['modulo9.especies.id_especie'],
            name='ciclos_biologicos_id_especie_fkey',
        ),
        PrimaryKeyConstraint('id_ciclo_biologico', name='ciclos_biologicos_pkey'),
        {'schema': 'modulo9'},
    )

    id_ciclo_biologico: Mapped[int] = mapped_column(
        Integer,
        Sequence('ciclos_biologicos_id_ciclo_biologico_seq', schema='modulo9'),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        comment='Nombre de la etapa. Único por especie (case-insensitive, validado en aplicación).',
    )
    descripcion: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment='Descripción opcional de la etapa.',
    )
    duracion_dias: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment='Duración estimada de la etapa en días. Debe ser mayor a 0.',
    )
    id_especie: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment='Especie a la que pertenece esta etapa.',
    )
    es_activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment='Indica si la etapa está disponible para su uso.',
    )
    fecha_actualizacion: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        comment='Timestamp de última modificación. Usado para concurrencia optimista (FA-07).',
    )
