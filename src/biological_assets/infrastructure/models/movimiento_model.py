from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class MovimientoModel(Base):
    __tablename__ = 'movimientos'
    __table_args__ = {'schema': 'modulo2'}

    id_movimiento: Mapped[int] = mapped_column(
        Integer,
        Identity(start=1, increment=1),
        primary_key=True,
    )
    id_activo_biologico: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo2.activos_biologicos.id_activo_biologico'),
        nullable=False,
    )
    id_infraestructura_origen: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo9.infraestructuras.id_infraestructura'),
        nullable=False,
    )
    id_infraestructura_destino: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo9.infraestructuras.id_infraestructura'),
        nullable=False,
    )
    fecha_transferencia: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    id_usuario: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo1.usuarios.id_usuario'),
        nullable=False,
    )
    motivo_transferencia: Mapped[Optional[str]] = mapped_column(Text)
    fecha_registro: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fecha_fin: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
