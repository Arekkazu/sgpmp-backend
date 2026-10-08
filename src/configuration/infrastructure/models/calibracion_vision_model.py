"""Modelos ORM de la calibración por visión (RF-24 v2.0, migración `d7a41c9e2b58`).

- `modulo9.calibraciones_vision`: historial inmutable de cada intento.
- `modulo9.lineas_base_vision`: línea base vigente por (área, especie).
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class CalibracionVisionModel(Base):
    __tablename__ = 'calibraciones_vision'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_infraestructura'],
            ['modulo9.infraestructuras.id_infraestructura'],
            name='calibraciones_vision_id_infraestructura_fkey',
        ),
        ForeignKeyConstraint(
            ['id_especie'],
            ['modulo9.especies.id_especie'],
            name='calibraciones_vision_id_especie_fkey',
        ),
        PrimaryKeyConstraint('id_calibracion_vision', name='calibraciones_vision_pkey'),
        {'schema': 'modulo9'},
    )

    id_calibracion_vision: Mapped[int] = mapped_column(
        Integer,
        Sequence('calibraciones_vision_id_calibracion_vision_seq', schema='modulo9'),
        primary_key=True,
    )
    id_infraestructura: Mapped[int] = mapped_column(Integer, nullable=False)
    id_especie: Mapped[int] = mapped_column(Integer, nullable=False)
    origen_disparo: Mapped[str] = mapped_column(String(10), nullable=False)
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer)
    json_ventana_observacion: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fecha_calibracion: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado: Mapped[str] = mapped_column(String(15), nullable=False)
    etapa_fallo: Mapped[Optional[str]] = mapped_column(String(15))
    motivo: Mapped[Optional[str]] = mapped_column(Text)
    json_linea_base: Mapped[Optional[dict]] = mapped_column(JSONB)
    n_observaciones: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    n_observaciones_validas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    iteraciones: Mapped[Optional[int]] = mapped_column(Integer)
    observaciones: Mapped[Optional[str]] = mapped_column(Text)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text('now()')
    )


class LineaBaseVisionModel(Base):
    __tablename__ = 'lineas_base_vision'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_infraestructura'],
            ['modulo9.infraestructuras.id_infraestructura'],
            name='lineas_base_vision_id_infraestructura_fkey',
        ),
        ForeignKeyConstraint(
            ['id_especie'],
            ['modulo9.especies.id_especie'],
            name='lineas_base_vision_id_especie_fkey',
        ),
        ForeignKeyConstraint(
            ['id_calibracion_vision'],
            ['modulo9.calibraciones_vision.id_calibracion_vision'],
            name='lineas_base_vision_id_calibracion_vision_fkey',
        ),
        PrimaryKeyConstraint('id_infraestructura', 'id_especie', name='lineas_base_vision_pkey'),
        {'schema': 'modulo9'},
    )

    id_infraestructura: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_especie: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_calibracion_vision: Mapped[int] = mapped_column(Integer, nullable=False)
    json_valor: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fecha_publicacion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text('now()')
    )
