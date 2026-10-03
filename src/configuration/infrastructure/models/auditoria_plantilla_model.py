"""Modelo ORM para la tabla `modulo9.auditorias_plantillas`.

Registro append-only de operaciones sobre plantillas de configuración: creación,
versionado, consulta y aplicación -- exitosas o fallidas (RF-30, RF-31, INC-M09-01-109).
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
            "tipo_operacion IN ('CREATE', 'READ', 'APPLY')",
            name='ck_auditoria_plantilla_tipo_operacion',
        ),
        CheckConstraint(
            "resultado IN ('EXITOSO', 'FALLIDO')",
            name='ck_auditoria_plantilla_resultado',
        ),
        PrimaryKeyConstraint('id_auditoria_plantilla', name='auditorias_plantillas_pkey'),
        {'schema': 'modulo9'},
    )

    id_auditoria_plantilla: Mapped[int] = mapped_column(
        Integer,
        Sequence('auditorias_plantillas_id_auditoria_plantilla_seq', schema='modulo9'),
        primary_key=True,
    )
    id_plantilla: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment='Plantilla sobre la que se realizó la operación. NULL si el fallo ocurrió antes de crearla.',
    )
    id_usuario: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment='Usuario que ejecutó la operación.',
    )
    tipo_operacion: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment='CREATE, READ o APPLY.',
    )
    resultado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'EXITOSO'"),
        comment='EXITOSO o FALLIDO.',
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
