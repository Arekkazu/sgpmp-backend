"""Modelo ORM para `modulo9.auditorias_visuales` (RF-26)."""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class AuditoriaIdentidadVisualModel(Base):
    __tablename__ = 'auditorias_visuales'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='auditorias_visuales_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_auditoria_visual', name='auditorias_visuales_pkey'),
        {'schema': 'modulo9'},
    )

    id_auditoria_visual: Mapped[int] = mapped_column(
        Integer,
        Sequence('auditorias_visuales_id_auditoria_visual_seq', schema='modulo9'),
        primary_key=True,
    )
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    valor_anterior: Mapped[dict] = mapped_column(JSONB, nullable=False)
    valor_nuevo: Mapped[dict] = mapped_column(JSONB, nullable=False)
