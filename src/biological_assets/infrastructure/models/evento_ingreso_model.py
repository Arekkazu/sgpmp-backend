from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base

if TYPE_CHECKING:
    from .evento_activo_model import EventoActivoModel


class EventoIngresoModel(Base):
    """RF-36: alta de individuos a un lote POBLACIONAL. Mismo patrón que
    EventoBajaModel -- sub-tabla 1:1 de eventos_activos."""

    __tablename__ = 'eventos_ingresos'
    __table_args__ = (
        CheckConstraint('cantidad_ingresada > 0', name='chk_ingreso_cantidad_positiva'),
        ForeignKeyConstraint(['id_evento'], ['modulo2.eventos_activos.id_eventos'], name='eventos_ingresos_id_evento_fkey'),
        PrimaryKeyConstraint('id_evento', name='eventos_ingresos_pkey'),
        {'schema': 'modulo2'},
    )

    id_evento: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador del evento de ingreso')
    cantidad_ingresada: Mapped[int] = mapped_column(Integer, nullable=False, comment='Cantidad de individuos que ingresan al lote')
    # PG enum enum_evento_ingreso_tipo — mapeado como String, mismo patrón que EventoBajaModel.tipo
    tipo: Mapped[str] = mapped_column(String(30), nullable=False, comment='Tipo de ingreso (compra, nacimiento, donacion, transferencia_interna)')
    detalles: Mapped[Optional[str]] = mapped_column(Text, comment='Detalles del evento de ingreso')

    evento: Mapped[EventoActivoModel] = relationship(
        'EventoActivoModel',
        back_populates='evento_ingreso',
    )
