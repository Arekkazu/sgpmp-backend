"""Modelo ORM para la tabla `modulo9.patologias`.

Catálogo global de patologías. Los campos de M04 (nombre_tecnico, etiologia,
categoria, codigo_cie, etc.) son gestionados por el módulo de Predicción IA.
M09 CU02 solo gestiona nombre, descripcion y es_activo.
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base
from .enums_models import EnumPatologiaCategoria


class PatologiaModel(Base):
    __tablename__ = 'patologias'
    __table_args__ = (
        UniqueConstraint('nombre', name='uq_enfermedad_nombre'),
        ForeignKeyConstraint(
            ['id_usuario_creador'],
            ['modulo1.usuarios.id_usuario'],
            name='fk_patologias_usuario_creador',
        ),
        PrimaryKeyConstraint('id_patologia', name='patologias_pkey'),
        {'schema': 'modulo9'},
    )

    id_patologia: Mapped[int] = mapped_column(
        Integer,
        Sequence('patologias_id_patologias_seq', schema='modulo9'),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        comment='Nombre único global de la patología.',
    )
    descripcion: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment='Descripción general de la patología (gestionada por M09).',
    )
    es_activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text('true'),
        comment='Estado de disponibilidad de la patología.',
    )
    fecha_actualizacion: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        comment='Timestamp de última modificación. Usado para concurrencia optimista.',
    )
    # Campos de M04 — gestionados por Módulo de Predicción IA
    nombre_tecnico: Mapped[Optional[str]] = mapped_column(String(150))
    etiologia: Mapped[Optional[str]] = mapped_column(Text)
    categoria: Mapped[Optional[EnumPatologiaCategoria]] = mapped_column(
        ENUM(EnumPatologiaCategoria, name='enum_patologia_categoria', schema='modulo9', create_type=False),
    )
    codigo_cie: Mapped[Optional[str]] = mapped_column(String(150))
    es_base: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    version_catalogo: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    descripcion_clinica: Mapped[Optional[str]] = mapped_column(Text)
    especie_aplicable: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'TODAS'"),
    )
    fecha_creacion_m04: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text('now()'),
    )
    id_usuario_creador: Mapped[Optional[int]] = mapped_column(Integer)
