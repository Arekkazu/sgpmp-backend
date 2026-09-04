"""Modelo ORM para la tabla `modulo9.tipos_area` (RF-20).

Catálogo administrable de tipos de área productiva. Reemplaza el enum fijo
`enum_tipo_infraestructura` que antes restringía `infraestructuras.tipo`.
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Identity, Integer, PrimaryKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class TipoAreaModel(Base):
    __tablename__ = 'tipos_area'
    __table_args__ = (
        PrimaryKeyConstraint('id_tipo_area', name='tipos_area_pkey'),
        UniqueConstraint('nombre', name='uq_tipo_area_nombre'),
        {'schema': 'modulo9'},
    )

    id_tipo_area: Mapped[int] = mapped_column(
        Integer,
        Identity(start=1, increment=1),
        primary_key=True,
        comment='Identificador único del tipo de área.',
    )
    nombre: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment='Nombre del tipo de área. Único en el catálogo (validación case-insensitive en aplicación).',
    )
    es_activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment='Indica si el tipo de área está disponible para registrar nuevas áreas productivas.',
    )
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment='Fecha y hora en que se registró el tipo de área.',
    )
    fecha_actualizacion: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        comment='Fecha y hora de la última desactivación/reactivación.',
    )
