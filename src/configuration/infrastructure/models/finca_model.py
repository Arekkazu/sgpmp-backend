"""Modelo ORM para `modulo9.fincas` (RF-19)."""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, Numeric, PrimaryKeyConstraint, Sequence, String, column, select, table
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, column_property, mapped_column

from .base_model import Base

_usuarios_fincas = table(
    'usuarios_fincas',
    column('id_usuario_finca'), column('id_usuario'), column('id_finca'), column('es_activo'),
    schema='modulo9',
)


class FincaModel(Base):
    __tablename__ = 'fincas'
    __table_args__ = (
        PrimaryKeyConstraint('id_finca', name='finca_pkey'),
        {'schema': 'modulo9'},
    )

    id_finca: Mapped[int] = mapped_column(
        Integer,
        Sequence('finca_id_finca_seq', schema='modulo9'),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(String(55), nullable=False)
    ubicacion: Mapped[dict] = mapped_column(JSONB, nullable=False)
    tamano_h: Mapped[float] = mapped_column(Numeric, nullable=False)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_actualizacion: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    es_activo: Mapped[Optional[bool]] = mapped_column(Boolean)
    # F3 (315eaa6c5dc1) retiró la columna: el acceso vive en ``usuarios_fincas``.
    # ``id_usuario`` es ahora el primer acceso activo —el usuario asignado al
    # registrar la finca— y es de solo lectura.
    id_usuario: Mapped[Optional[int]] = column_property(
        select(_usuarios_fincas.c.id_usuario)
        .where(_usuarios_fincas.c.id_finca == id_finca, _usuarios_fincas.c.es_activo.is_(True))
        .order_by(_usuarios_fincas.c.id_usuario_finca)
        .limit(1)
        .correlate_except(_usuarios_fincas)
        .scalar_subquery()
    )
