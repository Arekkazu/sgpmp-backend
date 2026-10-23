# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-22 RF-20: quita id_especie/capacidad_maxima, agrega nivel_criticidad y la puente de especies |
"""Modelo ORM para `modulo9.infraestructuras` (RF-20).

El tipo de área (`tipo`) referencia por nombre el catálogo administrable
`modulo9.tipos_area` (ver migración `2dbb6d44046f`); antes de esa migración
era un enum fijo de Postgres.

RFC-012 (DB-06): el área deja de tener una sola especie y una capacidad
configurable; sus especies viven en ``modulo9.infraestructuras_especies`` y la
capacidad se deriva (``capacidad_efectiva``).
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Identity, Index, Integer, Numeric, PrimaryKeyConstraint, Sequence, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base


class InfraestructuraModel(Base):
    __tablename__ = 'infraestructuras'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_finca'],
            ['modulo9.fincas.id_finca'],
            name='infraestructuras_id_finca_fkey',
        ),
        PrimaryKeyConstraint('id_infraestructura', name='infraestructuras_pkey'),
        UniqueConstraint('id_finca', 'nombre', name='uq_infraestructura_nombre'),
        {'schema': 'modulo9'},
    )

    id_infraestructura: Mapped[int] = mapped_column(
        Integer,
        Sequence('infraestructuras_id_infraestructura_seq', schema='modulo9'),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(String(100))
    id_finca: Mapped[int] = mapped_column(Integer, nullable=False)
    superficie: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    fecha_actualizacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    # RF-20 v1.1 (RFC-009): uno de los 5 modelos asignables, coherente con la especie.
    tipo_modelo_asignado: Mapped[Optional[str]] = mapped_column(String(30))
    # RFC-016 (DB-07): ALTA / MEDIA / BAJA, CHECK en la BD.
    nivel_criticidad: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'MEDIA'"))

    especies: Mapped[list[InfraestructuraEspecieModel]] = relationship(
        back_populates='infraestructura',
        cascade='all, delete-orphan',
        lazy='selectin',
        order_by='InfraestructuraEspecieModel.id_infraestructuras_especies',
    )


class InfraestructuraEspecieModel(Base):
    """Especie habilitada en un área (RFC-012, tabla puente N:M de DB-06)."""
    __tablename__ = 'infraestructuras_especies'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_especie'], ['modulo9.especies.id_especie'],
            ondelete='RESTRICT', name='fk_infraestructuras_especies_especie',
        ),
        ForeignKeyConstraint(
            ['id_infraestructura'], ['modulo9.infraestructuras.id_infraestructura'],
            ondelete='CASCADE', name='fk_infraestructuras_especies_infraestructura',
        ),
        PrimaryKeyConstraint('id_infraestructuras_especies', name='infraestructuras_especies_pkey'),
        UniqueConstraint('id_infraestructura', 'id_especie', name='uq_infraestructuras_especies'),
        Index('idx_infraestructuras_especies_id_especie', 'id_especie'),
        {'schema': 'modulo9'},
    )

    id_infraestructuras_especies: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    id_infraestructura: Mapped[int] = mapped_column(Integer, nullable=False)
    id_especie: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text('now()'),
    )

    infraestructura: Mapped[InfraestructuraModel] = relationship(back_populates='especies')
