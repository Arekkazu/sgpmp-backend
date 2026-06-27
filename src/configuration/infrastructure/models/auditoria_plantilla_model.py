"""Modelo ORM para la tabla `modulo9.auditorias_plantillas`.

Registro append-only de operaciones sobre plantillas de configuración (RF-31).
Solo registra CREATE ya que las plantillas son inmutables.
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Integer, PrimaryKeyConstraint, Sequence, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class AuditoriaPlantillaModel(Base):
    __tablename__ = 'auditorias_plantillas'
    __table_args__ = (
        CheckConstraint(
            "tipo_operacion = 'CREATE'",
            name='chk_tipo_operacion_plantilla',
        ),
        PrimaryKeyConstraint('id_auditoria_plantilla', name='auditorias_plantillas_pkey'),
        {'schema': 'modulo9'},
    )

    id_auditoria_plantilla: Mapped[int] = mapped_column(
        Integer,
        Sequence('auditorias_plantillas_id_auditoria_plantilla_seq', schema='modulo9'),
        primary_key=True,
    )
    id_plantilla: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment='Plantilla sobre la que se realizó la operación.',
    )
    id_usuario: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment='Usuario que ejecutó la operación.',
    )
    tipo_operacion: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment='Solo CREATE (plantillas inmutables).',
    )
    valores_anteriores: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment='Siempre NULL en CREATE.',
    )
    valores_nuevos: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment='Snapshot de la plantilla creada.',
    )
    fecha_gestion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text('now()'),
        comment='Timestamp UTC de la operación.',
    )
