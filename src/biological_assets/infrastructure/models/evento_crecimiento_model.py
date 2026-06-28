from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Integer, Numeric, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base

if TYPE_CHECKING:
    from .evento_activo_model import EventoActivoModel


class EventoCrecimientoModel(Base):
    # El nombre de la tabla tiene typo intencional en la BD
    __tablename__ = 'eventos_crecimeinto'
    __table_args__ = (
        CheckConstraint("unidad_medida IN ('kg','gr','lb','cm','m','kg/m2')", name='chk_crecimiento_unidad_valida'),
        CheckConstraint('valor_medicion > 0', name='chk_crecimiento_valor_positivo'),
        ForeignKeyConstraint(['id_evento'], ['modulo2.eventos_activos.id_eventos'], name='eventos_crecimeinto_id_evento_fkey'),
        PrimaryKeyConstraint('id_evento', name='eventos_crecimeinto_pkey'),
        {'schema': 'modulo2'},
    )

    id_evento: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador del evento de crecimiento')
    tipo_medicion: Mapped[str] = mapped_column(String(55), nullable=False, comment='Tipo de medición realizada (peso, talla, etc.)')
    valor_medicion: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment='Valor registrado de la medición')
    unidad_medida: Mapped[str] = mapped_column(String(5), nullable=False, comment='Unidad de medida utilizada')
    tipo_agregacion: Mapped[str] = mapped_column(String(55), nullable=False, comment='Tipo de agregación de la medición')
    frecuencia: Mapped[str] = mapped_column(String(55), nullable=False, comment='Frecuencia de medición')

    evento: Mapped[EventoActivoModel] = relationship(
        'EventoActivoModel',
        back_populates='evento_crecimiento',
    )
