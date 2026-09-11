"""Modelo ORM para la tabla `modulo9.especies_patologias`.

Entidad M09 de patologías por especie (RF-16): nombre, descripción y estado son
propios de cada especie. El nombre es único por especie, case-insensitive
(índice funcional `uq_especie_patologia_nombre` sobre ``(id_especie, lower(nombre))``,
creado en la migración). El vínculo ``id_patologia`` al catálogo clínico M04 es
opcional (nullable).
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class EspeciePatologiaModel(Base):
    __tablename__ = 'especies_patologias'
    __table_args__ = (
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
    id_especie: Mapped[int] = mapped_column(Integer, nullable=False)
    id_patologia: Mapped[Optional[int]] = mapped_column(Integer)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(String(255))
    es_activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text('true'),
    )
    fecha_actualizacion: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
    )
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text('now()'),
    )
