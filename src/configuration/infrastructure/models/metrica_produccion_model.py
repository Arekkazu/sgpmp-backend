"""Modelo ORM para la tabla `modulo9.metricas_produccion`.

M09 CU02 gestiona las columnas agregadas por RF-16: id_especie, es_activo,
aplica_a_tipo_activo y fecha_actualizacion. Las columnas legacy (nombre,
unidad_medida, tipo_medicion, tiene_estado) existían antes para M04.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, Numeric, PrimaryKeyConstraint, Sequence, String
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class MetricaProduccionModel(Base):
    __tablename__ = 'metricas_produccion'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_especie'],
            ['modulo9.especies.id_especie'],
            name='metricas_produccion_id_especie_fkey',
        ),
        PrimaryKeyConstraint('id_metrica_produccion', name='metricas_produccion_pkey'),
        {'schema': 'modulo9'},
    )

    id_metrica_produccion: Mapped[int] = mapped_column(
        Integer,
        Sequence('metricas_produccion_id_metricas_produccion_seq', schema='modulo9'),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        comment='Nombre de la métrica. Único por especie (case-insensitive, validado en aplicación).',
    )
    unidad_medida: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment='Unidad de medida. Debe ser coherente con tipo_medicion (FA-10).',
    )
    tipo_medicion: Mapped[str] = mapped_column(
        String(55),
        nullable=False,
        comment='Tipo de medición: PESO, VOLUMEN, LONGITUD, CONTEO u OTRO.',
    )
    tiene_estado: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment='Campo legacy de M04. No usar en M09 — usar es_activo.',
    )
    # Columnas agregadas por RF-16 (M09 CU02)
    id_especie: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment='Especie a la que pertenece esta métrica.',
    )
    aplica_a_tipo_activo: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default='AMBOS',
        comment='Scope de aplicación: INDIVIDUAL, LOTE o AMBOS.',
    )
    es_activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default='true',
        comment='Estado de disponibilidad de la métrica.',
    )
    fecha_actualizacion: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        comment='Timestamp de última modificación. Usado para concurrencia optimista.',
    )
    valor_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    valor_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
