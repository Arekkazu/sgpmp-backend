"""Modelo ORM para la tabla `modulo9.especies`.

Catálogo maestro de especies productivas gestionadas en la plataforma.
Es la entidad de mayor centralidad del sistema (19 dependencias salientes, RF-15).
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Identity, Integer, PrimaryKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class EspecieModel(Base):
    __tablename__ = 'especies'
    __table_args__ = (
        PrimaryKeyConstraint('id_especie', name='especies_pkey'),
        UniqueConstraint('nombre', name='uq_especie_nombre'),
        # fk_ri_especies omitida — auto-FK (id_especie → id_especie) sin propósito funcional
        {'schema': 'modulo9'},
    )

    id_especie: Mapped[int] = mapped_column(
        Integer,
        Identity(start=1, increment=1),
        primary_key=True,
        comment='Identificador único de la especie.',
    )
    nombre: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment='Nombre de la especie. Único en el catálogo (validación case-insensitive en aplicación).',
    )
    descripcion: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment='Descripción general de la especie y sus características relevantes.',
    )
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment='Fecha y hora en que se registró la especie.',
    )
    fecha_actualizacion: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        comment='Fecha y hora de la última modificación. Usada para control de concurrencia optimista.',
    )
    es_activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment='Indica si la especie está activa y disponible para su uso en otros módulos.',
    )
