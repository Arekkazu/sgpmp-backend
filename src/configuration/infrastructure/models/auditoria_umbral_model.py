"""Modelo ORM para `modulo9.auditorias_umbrales_ambientales` (append-only, CU03 RF-17)."""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class AuditoriaUmbralModel(Base):
    __tablename__ = 'auditorias_umbrales_ambientales'
    __table_args__ = (
        CheckConstraint(
            "tipo_operacion::text = ANY (ARRAY['CREATE'::text, 'UPDATE'::text, 'DEACTIVATE'::text])",
            name='auditorias_umbrales_ambientales_tipo_operacion_check',
        ),
        ForeignKeyConstraint(
            ['id_umbral_ambiental'],
            ['modulo9.umbrales_ambientales.id_umbral_ambiental'],
            name='auditorias_umbrales_ambientales_id_umbral_ambiental_fkey',
        ),
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='auditorias_umbrales_ambientales_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_auditoria_umbral', name='auditorias_umbrales_ambientales_pkey'),
        {'schema': 'modulo9'},
    )

    id_auditoria_umbral: Mapped[int] = mapped_column(
        Integer,
        Sequence('auditorias_umbrales_ambientales_id_auditoria_umbral_seq', schema='modulo9'),
        primary_key=True,
    )
    id_umbral_ambiental: Mapped[int] = mapped_column(Integer, nullable=False)
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer)
    tipo_operacion: Mapped[str] = mapped_column(String(20), nullable=False)
    valores_anteriores: Mapped[Optional[dict]] = mapped_column(JSONB)
    valores_nuevos: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fecha_gestion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text('now()'),
    )
