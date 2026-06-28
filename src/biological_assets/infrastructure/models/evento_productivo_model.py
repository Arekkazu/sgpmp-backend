from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Integer, Numeric, PrimaryKeyConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base

if TYPE_CHECKING:
    from .evento_activo_model import EventoActivoModel


class EventoProductivoModel(Base):
    __tablename__ = 'eventos_productivos'
    __table_args__ = (
        CheckConstraint('cantidad > 0', name='chk_productivo_cantidad_positiva'),
        ForeignKeyConstraint(['id_evento'], ['modulo2.eventos_activos.id_eventos'], name='eventos_productivos_id_evento_fkey'),
        ForeignKeyConstraint(['id_ciclo_productivo'], ['modulo9.ciclos_productivos.id_ciclo_productivo'], name='eventos_productivos_id_ciclo_productivo_fkey'),
        ForeignKeyConstraint(['id_metrica_produccion'], ['modulo9.metricas_produccion.id_metrica_produccion'], name='fk_evento_metrica'),
        PrimaryKeyConstraint('id_evento', name='eventos_productivos_pkey'),
        {'schema': 'modulo2'},
    )

    id_evento: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador del evento productivo')
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, comment='Cantidad producida o registrada')
    id_metrica_produccion: Mapped[int] = mapped_column(Integer, nullable=False, comment='Métrica de producción asociada')
    id_ciclo_productivo: Mapped[int] = mapped_column(Integer, nullable=False, comment='Ciclo productivo asociado')
    condiciones: Mapped[Optional[str]] = mapped_column(Text, comment='Condiciones del evento productivo')

    evento: Mapped[EventoActivoModel] = relationship(
        'EventoActivoModel',
        back_populates='evento_productivo',
    )
