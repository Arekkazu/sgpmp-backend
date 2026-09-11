"""Modelo ORM para `modulo9.configuraciones_globales` (RF-18).

Configuración operativa global única del sistema: frecuencia de muestreo
y heartbeat IoT. Solo puede existir un registro activo a la vez.
"""
from __future__ import annotations

import datetime

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class ConfiguracionGlobalModel(Base):
    __tablename__ = 'configuraciones_globales'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='configuraciones_globales_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_configuracion_global', name='configuraciones_globales_pkey'),
        {'schema': 'modulo9'},
    )

    id_configuracion_global: Mapped[int] = mapped_column(
        Integer,
        Sequence('configuraciones_globales_id_configuracion_global_seq', schema='modulo9'),
        primary_key=True,
    )
    frecuencia_muestreo: Mapped[int] = mapped_column(Integer, nullable=False)
    heartbeat: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_actualizacion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False)
