from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, Numeric, PrimaryKeyConstraint, String
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
    fecha_nacimeinto: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    peso_inicial: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_actualizacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer)

    activo: Mapped[ActivoBiologicoModel] = relationship(
        'ActivoBiologicoModel',
        back_populates='detalle_individual',
    )
