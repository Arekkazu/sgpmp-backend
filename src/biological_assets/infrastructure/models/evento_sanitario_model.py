from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Integer, Numeric, PrimaryKeyConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base

if TYPE_CHECKING:
    from .evento_activo_model import EventoActivoModel


class EventoSanitarioModel(Base):
    __tablename__ = 'eventos_sanitarios'
    __table_args__ = (
        CheckConstraint('dosis > 0', name='chk_sanitario_dosis_positiva'),
        CheckConstraint('frecuencia IS NULL OR frecuencia > 0', name='chk_sanitario_frecuencia_positiva'),
        CheckConstraint(
            "tipo <> 'TRATAMIENTO' OR (medicamento IS NOT NULL AND dosis IS NOT NULL AND frecuencia IS NOT NULL AND duracion IS NOT NULL)",
            name='check_tratamiento',
        ),
        CheckConstraint(
            "tipo <> 'VACUNACION' OR (medicamento IS NOT NULL AND dosis IS NOT NULL)",
            name='check_vacunacion',
        ),
        CheckConstraint(
            "tipo <> 'DIAGNOSTICO' OR diagnostico IS NOT NULL",
            name='check_diagnostico',
        ),
        CheckConstraint(
            "tipo <> 'CONTROL_PREVENTIVO' OR observaciones IS NOT NULL",
            name='check_control',
        ),
        ForeignKeyConstraint(['id_evento'], ['modulo2.eventos_activos.id_eventos'], name='eventos_sanitarios_id_evento_fkey'),
        PrimaryKeyConstraint('id_evento', name='eventos_sanitarios_pkey'),
        {'schema': 'modulo2'},
    )

    id_evento: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador del evento sanitario')
    # PG enum enum_evento_sanitario_tipo — mapeado como String
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    diagnostico: Mapped[Optional[str]] = mapped_column(Text, comment='Diagnóstico registrado')
    medicamento: Mapped[Optional[str]] = mapped_column(String(100), comment='Medicamento aplicado')
    dosis: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), comment='Cantidad administrada del medicamento')
    unidad_dosis: Mapped[Optional[str]] = mapped_column(String(5), comment='Unidad de la dosis aplicada')
    frecuencia: Mapped[Optional[int]] = mapped_column(Integer, comment='Frecuencia de aplicación del tratamiento')
    duracion: Mapped[Optional[int]] = mapped_column(Integer, comment='Duración del tratamiento en días')
    observaciones: Mapped[Optional[str]] = mapped_column(Text, comment='Observaciones del control preventivo')

    evento: Mapped[EventoActivoModel] = relationship(
        'EventoActivoModel',
        back_populates='evento_sanitario',
    )
