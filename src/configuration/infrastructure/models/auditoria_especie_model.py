"""Modelo ORM para la tabla `modulo9.auditorias_especies`.

Registro append-only de todas las operaciones sobre el catálogo de especies.
Almacena actor, timestamp, tipo de operación y snapshot JSONB antes/después.
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, Sequence, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class AuditoriaEspecieModel(Base):
    __tablename__ = 'auditorias_especies'
    __table_args__ = (
        CheckConstraint(
            "tipo_operacion::text = ANY (ARRAY['CREATE'::text, 'UPDATE'::text, 'DEACTIVATE'::text])",
            name='chk_tipo_operacion_especie',
        ),
        ForeignKeyConstraint(
            ['id_especie'],
            ['modulo9.especies.id_especie'],
            name='auditorias_especies_id_especie_fkey',
        ),
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='auditorias_especies_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_auditoria_especie', name='auditorias_especies_pkey'),
        Index('idx_audit_especie_fecha', 'fecha_gestion'),
        Index('idx_audit_especie_id', 'id_especie'),
        Index('idx_audit_especie_tipo', 'tipo_operacion'),
        Index('idx_audit_especie_usuario', 'id_usuario'),
        {'schema': 'modulo9'},
    )

    id_auditoria_especie: Mapped[int] = mapped_column(
        Integer,
        Sequence('auditorias_especies_id_auditoria_especie_seq', schema='modulo9'),
        primary_key=True,
    )
    id_especie: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment='Especie sobre la que se realizó la operación.',
    )
    id_usuario: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment='Usuario que ejecutó la operación.',
    )
    tipo_operacion: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment='Tipo de operación ejecutada: CREATE, UPDATE o DEACTIVATE.',
    )
    valores_anteriores: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment='Snapshot del estado de la especie antes de la operación. NULL en CREATE.',
    )
    valores_nuevos: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment='Snapshot del estado de la especie después de la operación.',
    )
    fecha_gestion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text('now()'),
        comment='Timestamp UTC de la operación.',
    )
