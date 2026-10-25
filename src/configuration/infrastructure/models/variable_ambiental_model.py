# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-25 RF-17: mapea es_critica (RFC-016) |
# | 2026-10-21 | Leandro  | DEV-40 RF-53: mapea metadatos de catalogo dinamico |
"""Modelo ORM para `modulo9.variables_ambientales` (catálogo de M09; solo `es_critica` es editable)."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, Numeric, PrimaryKeyConstraint, Sequence, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class VariableAmbientalModel(Base):
    __tablename__ = 'variables_ambientales'
    __table_args__ = (
        PrimaryKeyConstraint('id_variable_ambiental', name='variables_ambientales_pkey'),
        UniqueConstraint('codigo_telemetria', name='uq_variable_ambiental_codigo_telemetria'),
        CheckConstraint("codigo_telemetria IS NULL OR codigo_telemetria ~ '^[A-Z][A-Z0-9_]{1,39}$'", name='ck_variable_ambiental_codigo_telemetria'),
        CheckConstraint("categoria_variable IS NULL OR categoria_variable IN ('AMBIENTAL','ANIMAL','HIDRICA')", name='ck_variable_ambiental_categoria_variable'),
        {'schema': 'modulo9'},
    )

    id_variable_ambiental: Mapped[int] = mapped_column(
        Sequence('variables_ambientales_id_variable_ambiental_seq', schema='modulo9'),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    unidad: Mapped[str] = mapped_column(String, nullable=False)
    valor_fisico_min: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    valor_fisico_max: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # RFC-016 B.7: la lectura de una variable crítica entra como crítica en la cola del broker.
    es_critica: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    codigo_telemetria: Mapped[Optional[str]] = mapped_column(String(40))
    categoria_variable: Mapped[Optional[str]] = mapped_column(String(20))
