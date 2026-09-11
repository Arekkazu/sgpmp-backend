from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base

if TYPE_CHECKING:
    from .activo_biologico_model import ActivoBiologicoModel


class HistorialInfraestructuraActivoModel(Base):
    __tablename__ = 'historial_infraestructura_activo'
    __table_args__ = (
        PrimaryKeyConstraint('id_historial', name='historial_infraestructura_activo_pkey'),
        {'schema': 'modulo2'},
    )

    id_historial: Mapped[int] = mapped_column(
        Integer,
        Identity(start=1, increment=1),
        primary_key=True,
    )
    id_activo_biologico: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo2.activos_biologicos.id_activo_biologico'),
        nullable=False,
    )
    id_infraestructura: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo9.infraestructuras.id_infraestructura'),
        nullable=False,
    )
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # fecha_fin = None indica la asociación activa actual
    fecha_fin: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    id_usuario_registro: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo1.usuarios.id_usuario'),
        nullable=False,
    )

    activo: Mapped[ActivoBiologicoModel] = relationship(
        'ActivoBiologicoModel',
        back_populates='historial_infraestructura',
    )
