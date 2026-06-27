"""Modelo ORM para la tabla `modulo9.plantillas`.

Registro inmutable de plantillas de configuración reutilizables (RF-31).
Una vez creada, una plantilla no se modifica: la versión es la identidad.
"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class PlantillaModel(Base):
    __tablename__ = 'plantillas'
    __table_args__ = (
        UniqueConstraint(
            'template_name', 'version',
            name='uq_plantillas_nombre_version',
        ),
        ForeignKeyConstraint(
            ['id_especie'],
            ['modulo9.especies.id_especie'],
            name='plantillas_id_especie_fkey',
        ),
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='plantillas_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_plantilla', name='plantillas_pkey'),
        {'schema': 'modulo9'},
    )

    id_plantilla: Mapped[int] = mapped_column(
        Integer,
        Sequence('plantillas_id_plantilla_seq', schema='modulo9'),
        primary_key=True,
    )
    id_especie: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment='Especie de origen de la plantilla.',
    )
    id_usuario: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment='Usuario que creó la plantilla.',
    )
    template_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment='Nombre de la plantilla. Único junto con version.',
    )
    params_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment='Snapshot de parámetros productivos y umbrales (schema_version + categorías).',
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment='Número de versión. Auto-incrementado por la aplicación.',
    )
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment='Timestamp UTC de creación.',
    )
