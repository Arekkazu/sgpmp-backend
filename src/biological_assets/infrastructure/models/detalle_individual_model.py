# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-20 RF-33: fecha_nacimiento opcional y advertencia de edad (RFC-014) |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""Modelo ORM de ``modulo2.detalles_activos_individuales``: raza, sexo, nacimiento y
peso de un activo INDIVIDUAL.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Identity, Integer, Numeric, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base

if TYPE_CHECKING:
    from .activo_biologico_model import ActivoBiologicoModel


class DetalleActivoIndividualModel(Base):
    __tablename__ = 'detalles_activos_individuales'
    __table_args__ = (
        PrimaryKeyConstraint('id_detalle_activo_individual', name='detalles_activos_individuales_pkey'),
        {'schema': 'modulo2'},
    )

    id_detalle_activo_individual: Mapped[int] = mapped_column(
        Integer,
        Identity(start=1, increment=1),
        primary_key=True,
    )
    id_activo_biologico: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo2.activos_biologicos.id_activo_biologico'),
        nullable=False,
    )
    raza: Mapped[str] = mapped_column(String(50), nullable=False)
    sexo: Mapped[str] = mapped_column(String(10), nullable=False)
    # Columna con typo en DB — se respeta tal cual
    # DB-07 / RFC-014: opcional.
    fecha_nacimeinto: Mapped[Optional[date]] = mapped_column(Date, nullable=True)  # día calendario, sin zona
    peso_inicial: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_actualizacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer)

    activo: Mapped[ActivoBiologicoModel] = relationship(
        'ActivoBiologicoModel',
        back_populates='detalle_individual',
    )
