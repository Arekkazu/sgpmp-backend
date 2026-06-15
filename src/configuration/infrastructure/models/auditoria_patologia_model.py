"""Modelo ORM para la tabla `modulo9.auditorias_patologias`.

Registro append-only de operaciones sobre el catálogo de patologías (RF-16).
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class AuditoriaPatologiaModel(Base):
    __tablename__ = 'auditorias_patologias'
    __table_args__ = (
        CheckConstraint(
            "tipo_operacion::text = ANY (ARRAY['CREATE'::text, 'UPDATE'::text, 'DEACTIVATE'::text])",
            name='auditorias_patologias_tipo_operacion_check',
        ),
        ForeignKeyConstraint(
            ['id_patologia'],
            ['modulo9.patologias.id_patologia'],
            name='auditorias_patologias_id_patologia_fkey',
        ),
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='auditorias_patologias_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_auditoria_patologia', name='auditorias_patologias_pkey'),
        {'schema': 'modulo9'},
    )

    id_auditoria_patologia: Mapped[int] = mapped_column(
        Integer,
        Sequence('auditorias_patologias_id_auditoria_patologia_seq', schema='modulo9'),
        primary_key=True,
    )
    id_patologia: Mapped[int] = mapped_column(Integer, nullable=False)
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_operacion: Mapped[str] = mapped_column(String(20), nullable=False)
    valores_anteriores: Mapped[Optional[dict]] = mapped_column(JSONB)
    valores_nuevos: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fecha_gestion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text('now()'),
    )
