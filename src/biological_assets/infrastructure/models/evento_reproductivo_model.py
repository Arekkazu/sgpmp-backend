from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base

if TYPE_CHECKING:
    from .evento_activo_model import EventoActivoModel


class EventoReproductivoModel(Base):
    __tablename__ = 'eventos_reproductivos'
    __table_args__ = (
        CheckConstraint('numero_cria >= 0', name='chk_reproductivo_numero_cria_no_negativo'),
        CheckConstraint('(id_padre <> id_madre) OR (id_madre IS NULL)', name='chk_reproductivo_padre_diferente_madre'),
        ForeignKeyConstraint(
            ['id_evento_reproductivo'],
            ['modulo2.eventos_activos.id_eventos'],
            name='eventos_reproductivos_id_evento_reproductivo_fkey',
        ),
        ForeignKeyConstraint(
            ['id_padre'],
            ['modulo2.activos_biologicos.id_activo_biologico'],
            name='eventos_reproductivos_id_padre_fkey',
        ),
        ForeignKeyConstraint(
            ['id_madre'],
            ['modulo2.activos_biologicos.id_activo_biologico'],
            name='eventos_reproductivos_id_madre_fkey',
        ),
        PrimaryKeyConstraint('id_evento_reproductivo', name='eventos_reproductivos_pkey'),
        {'schema': 'modulo2'},
    )

    id_evento_reproductivo: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        comment='Identificador del evento reproductivo (FK a eventos_activos)',
    )
    # PG enum enum_evento_reproductivo_categoria — mapeado como String
    categoria: Mapped[str] = mapped_column(String(20), nullable=False, comment='Categoría del evento reproductivo')
    resultado: Mapped[str] = mapped_column(String(20), nullable=False, comment='Resultado: exitoso o fallido')
    numero_cria: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='Número de crías')
    id_padre: Mapped[Optional[int]] = mapped_column(Integer, comment='Activo padre (semental) relacionado')
    id_madre: Mapped[Optional[int]] = mapped_column(Integer, comment='Activo madre relacionada')

    evento: Mapped[EventoActivoModel] = relationship(
        'EventoActivoModel',
        back_populates='evento_reproductivo',
    )
