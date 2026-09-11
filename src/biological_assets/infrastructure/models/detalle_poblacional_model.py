from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Identity, Integer, Numeric, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base

if TYPE_CHECKING:
    from .activo_biologico_model import ActivoBiologicoModel


class DetalleActivoPoblacionalModel(Base):
    __tablename__ = 'detalles_activos_biologicos_poblacionales'
    __table_args__ = (
        PrimaryKeyConstraint('id_detalle_activo_biologico_poblacional', name='detalles_activos_biologicos_poblacionales_pkey'),
        {'schema': 'modulo2'},
    )

    id_detalle_activo_biologico_poblacional: Mapped[int] = mapped_column(
        Integer,
        Identity(start=1, increment=1),
        primary_key=True,
    )
    id_activo_biologico: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo2.activos_biologicos.id_activo_biologico'),
        nullable=False,
    )
    cantidad_inicial: Mapped[int] = mapped_column(Integer, nullable=False)
    # cantidad_actual nullable — se inicializa = cantidad_inicial en el use case
    cantidad_actual: Mapped[Optional[int]] = mapped_column(Integer)
    # Campos que se calculan en CU06; nullable hasta entonces
    peso_promedio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    biomasa_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    densidad: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    # Inmutable una vez registrado (RF-33)
    peso_promedio_inicial: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))

    activo: Mapped[ActivoBiologicoModel] = relationship(
        'ActivoBiologicoModel',
        back_populates='detalle_poblacional',
    )
