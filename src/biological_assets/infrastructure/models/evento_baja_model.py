from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base

if TYPE_CHECKING:
    from .evento_activo_model import EventoActivoModel


class EventoBajaModel(Base):
    __tablename__ = 'eventos_bajas'
    __table_args__ = (
        CheckConstraint('cantidad_afectada > 0', name='chk_baja_cantidad_positiva'),
        ForeignKeyConstraint(['id_evento'], ['modulo2.eventos_activos.id_eventos'], name='eventos_bajas_id_evento_fkey'),
        PrimaryKeyConstraint('id_evento', name='eventos_bajas_pkey'),
        {'schema': 'modulo2'},
    )

    id_evento: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador del evento de baja')
    cantidad_afectada: Mapped[int] = mapped_column(Integer, nullable=False, comment='Cantidad de activos afectados')
    # PG enum enum_evento_bajas_tipo — mapeado como String para evitar conflicto con tipo existente
    tipo: Mapped[str] = mapped_column(String(30), nullable=False, comment='Tipo de baja (muerte, venta, sacrificio, perdida, descarte_sanitario)')
    detalles: Mapped[Optional[str]] = mapped_column(Text, comment='Detalles del evento de baja')

    evento: Mapped[EventoActivoModel] = relationship(
        'EventoActivoModel',
        back_populates='evento_baja',
    )
