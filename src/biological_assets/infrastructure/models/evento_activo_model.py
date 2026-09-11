from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Identity, Index, Integer, PrimaryKeyConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base

if TYPE_CHECKING:
    from .evento_baja_model import EventoBajaModel
    from .evento_crecimiento_model import EventoCrecimientoModel
    from .evento_productivo_model import EventoProductivoModel
    from .evento_reproductivo_model import EventoReproductivoModel
    from .evento_sanitario_model import EventoSanitarioModel


class EventoActivoModel(Base):
    __tablename__ = 'eventos_activos'
    __table_args__ = (
        CheckConstraint('fecha <= now()', name='chk_eventos_fecha_no_futura'),
        PrimaryKeyConstraint('id_eventos', name='eventos_activos_pkey'),
        Index('idx_eventos_activos_activo_fecha', 'id_activo_biologico', 'fecha'),
        {'schema': 'modulo2'},
    )

    id_eventos: Mapped[int] = mapped_column(
        Integer,
        Identity(start=1, increment=1),
        primary_key=True,
        comment='Identificador del evento',
    )
    id_activo_biologico: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo2.activos_biologicos.id_activo_biologico', name='eventos_activos_id_activo_biologico_fkey'),
        nullable=False,
        comment='Activo biológico asociado al evento',
    )
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment='Fecha en que ocurre el evento',
    )
    descripcion: Mapped[Optional[str]] = mapped_column(Text, comment='Descripción del evento registrado')
    id_usuario: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey('modulo1.usuarios.id_usuario', name='eventos_activos_id_usuario_fkey'),
        comment='Usuario que registra el evento',
    )

    # ── Relaciones hacia subtablas de evento ────────────────────────────────
    evento_crecimiento: Mapped[Optional[EventoCrecimientoModel]] = relationship(
        'EventoCrecimientoModel',
        back_populates='evento',
        cascade='all, delete-orphan',
        lazy='selectin',
        uselist=False,
    )
    evento_baja: Mapped[Optional[EventoBajaModel]] = relationship(
        'EventoBajaModel',
        back_populates='evento',
        cascade='all, delete-orphan',
        lazy='selectin',
        uselist=False,
    )
    evento_sanitario: Mapped[Optional[EventoSanitarioModel]] = relationship(
        'EventoSanitarioModel',
        back_populates='evento',
        cascade='all, delete-orphan',
        lazy='selectin',
        uselist=False,
    )
    evento_productivo: Mapped[Optional[EventoProductivoModel]] = relationship(
        'EventoProductivoModel',
        back_populates='evento',
        cascade='all, delete-orphan',
        lazy='selectin',
        uselist=False,
    )
    evento_reproductivo: Mapped[Optional[EventoReproductivoModel]] = relationship(
        'EventoReproductivoModel',
        back_populates='evento',
        cascade='all, delete-orphan',
        lazy='selectin',
        uselist=False,
    )
