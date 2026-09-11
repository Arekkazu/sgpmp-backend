"""Modelo ORM para la tabla `modulo9.aplicaciones_plantillas`.

Registro de cada aplicación de una plantilla sobre una configuración destino
(RF-32). Sirve de audit trail: almacena before/after snapshots.
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class AplicacionPlantillaModel(Base):
    __tablename__ = 'aplicaciones_plantillas'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_plantilla'],
            ['modulo9.plantillas.id_plantilla'],
            name='aplicaciones_plantillas_id_plantilla_fkey',
        ),
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='aplicaciones_plantillas_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_aplicacion_plantilla', name='aplicaciones_plantillas_pkey'),
        {'schema': 'modulo9'},
    )

    id_aplicacion_plantilla: Mapped[int] = mapped_column(
        Integer,
        Sequence('aplicaciones_plantillas_id_aplicacion_plantilla_seq', schema='modulo9'),
        primary_key=True,
    )
    id_usuario: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment='Usuario que ejecutó la aplicación.',
    )
    id_plantilla: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment='Plantilla aplicada.',
    )
    target_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment='Identificador de la configuración destino. Ej: {"id_especie": 5}.',
    )
    before_snapshot: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment='Estado de la configuración destino antes de la aplicación.',
    )
    after_snapshot: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment='Estado de la configuración destino después de la aplicación.',
    )
    fecha_aplicacion: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        comment='Timestamp UTC de la aplicación.',
    )
