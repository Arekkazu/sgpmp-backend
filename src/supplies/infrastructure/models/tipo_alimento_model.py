"""Modelo ORM para la tabla ``modulo5.tipos_alimentos``.

Generado con sqlacodegen (reflexión de la BD) y adaptado a las convenciones del
repo: Base compartida, nombre de clase ``<Agregado>Model`` y el enum PG
``enum_tipo_alimento_estado`` mapeado como ``String`` (CLAUDE.md — evita que
SQLAlchemy intente recrear el tipo). En el CU-01 solo se lee.
"""
from typing import Optional
import datetime
import decimal

from sqlalchemy import DateTime, Integer, Numeric, PrimaryKeyConstraint, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class TipoAlimentoModel(Base):
    __tablename__ = 'tipos_alimentos'
    __table_args__ = (
        PrimaryKeyConstraint('id_tipo_elemento', name='tipos_alimentos_pkey'),
        UniqueConstraint('nombre', name='uq_tipo_alimento_nombre'),
        {'schema': 'modulo5'}
    )

    id_tipo_elemento: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    costo_unitario: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unidad_medida: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    fecha_actualizacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    estado: Mapped[Optional[str]] = mapped_column(String(20))
    justificacion_estado: Mapped[Optional[str]] = mapped_column(String(160))
