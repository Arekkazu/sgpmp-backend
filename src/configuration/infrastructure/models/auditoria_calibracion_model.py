"""Modelo ORM para `modulo9.auditorias_calibraciones` (RF-24 / RF-10).

Historial de auditoría inmutable de las calibraciones (triggers de BD bloquean
UPDATE/DELETE). Mismo esquema que las demás auditorías de módulo 9.
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class AuditoriaCalibracionModel(Base):
    __tablename__ = 'auditorias_calibraciones'
    __table_args__ = (
        CheckConstraint(
            "tipo_operacion IN ('CREATE','GET')",
            name='chk_tipo_operacion_calibracion',
        ),
        ForeignKeyConstraint(
            ['id_calibracion'],
            ['modulo9.calibraciones.id_calibracion'],
            name='auditoria_calibracion_id_calibracion_fkey',
        ),
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='auditoria_calibracion_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_auditoria_calibracion', name='auditorias_calibraciones_pkey'),
        {'schema': 'modulo9'},
    )

    id_auditoria_calibracion: Mapped[int] = mapped_column(
        Integer,
        Sequence('auditorias_calibraciones_id_auditoria_calibracion_seq', schema='modulo9'),
        primary_key=True,
    )
    id_calibracion: Mapped[int] = mapped_column(Integer, nullable=False)
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_operacion: Mapped[str] = mapped_column(String(20), nullable=False)
    valores_anteriores: Mapped[Optional[dict]] = mapped_column(JSONB)
    valores_nuevos: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fecha_gestion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text('now()'),
    )
