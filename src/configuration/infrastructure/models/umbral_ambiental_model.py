"""Modelo ORM para `modulo9.umbrales_ambientales` (agregado raíz de CU03 RF-17)."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Numeric, PrimaryKeyConstraint, Sequence, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base

if TYPE_CHECKING:
    from .nivel_alerta_ambiental_model import NivelAlertaAmbientalModel


class UmbralAmbientalModel(Base):
    __tablename__ = 'umbrales_ambientales'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_especie'],
            ['modulo9.especies.id_especie'],
            name='umbrales_ambientales_id_especie_fkey',
        ),
        ForeignKeyConstraint(
            ['id_variable_ambiental'],
            ['modulo9.variables_ambientales.id_variable_ambiental'],
            name='umbrales_ambientales_id_variable_ambiental_fkey',
        ),
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='umbrales_ambientales_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_umbral_ambiental', name='umbrales_ambientales_pkey'),
        {'schema': 'modulo9'},
    )

    id_umbral_ambiental: Mapped[int] = mapped_column(
        Sequence('umbrales_ambientales_id_umbral_ambiental_seq', schema='modulo9'),
        primary_key=True,
    )
    id_especie: Mapped[int] = mapped_column(nullable=False)
    id_variable_ambiental: Mapped[int] = mapped_column(nullable=False)
    id_usuario: Mapped[Optional[int]] = mapped_column()
    unidad_medida: Mapped[str] = mapped_column(String, nullable=False)
    nombre: Mapped[Optional[str]] = mapped_column(String)
    descripcion: Mapped[Optional[str]] = mapped_column(String)
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    valor_min: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    valor_max: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    fecha_actualizacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    # INC-M09-104-G29 (RF-17): estado de la propagación hacia el Nodo Edge.
    # Mismo vocabulario que configuraciones_remotas (RF-23): PENDIENTE (recién
    # guardado o broker inalcanzable) / APLICADA (ACK del Edge) / NO_CONF (se
    # publicó pero no hubo ACK a tiempo).
    estado_sincronizacion: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'PENDIENTE'"))
    fecha_ultima_sincronizacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    motivo_fallo_sincronizacion: Mapped[Optional[str]] = mapped_column(Text)

    niveles: Mapped[List['NivelAlertaAmbientalModel']] = relationship(
        'NivelAlertaAmbientalModel',
        back_populates='umbral',
        cascade='all, delete-orphan',
        lazy='selectin',
    )
