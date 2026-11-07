# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021 RF-110 C21.1: modelo ORM de modulo9.aristas_transmision  |
"""Modelo ORM de `modulo9.aristas_transmision` (migración 33ae7f41e560). Los enums de PostgreSQL se
mapean como `String` (convención del proyecto)."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class AristaTransmisionModel(Base):
    __tablename__ = 'aristas_transmision'
    __table_args__ = {'schema': 'modulo9'}

    id_arista_transmision: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_infraestructura_origen: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo9.infraestructuras.id_infraestructura'), nullable=False)
    id_infraestructura_destino: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo9.infraestructuras.id_infraestructura'), nullable=False)
    via: Mapped[str] = mapped_column(String(20), nullable=False)
    direccion: Mapped[str] = mapped_column(String(15), nullable=False, server_default=text("'DIRIGIDA'"))
    intensidad: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    factor_barrera: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False, server_default=text('1'))
    origen_dato: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'DECLARADA'"))
    descripcion: Mapped[Optional[str]] = mapped_column(String(200))
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    #: La FK a modulo1.usuarios la tiene la BD; el ORM de M09 no carga los modelos de M01.
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text('now()'))
    fecha_actualizacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
