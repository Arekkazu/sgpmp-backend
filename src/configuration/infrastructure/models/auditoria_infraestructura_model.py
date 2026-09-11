"""Modelo ORM para `modulo9.auditorias_infraestructuras`."""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class AuditoriaInfraestructuraModel(Base):
    __tablename__ = 'auditorias_infraestructuras'
    __table_args__ = (
        CheckConstraint(
            "tipo_operacion IN ('CREATE','UPDATE','DEACTIVATE')",
            name='chk_tipo_operacion_infraestructura',
        ),
        ForeignKeyConstraint(
            ['id_infraestructura'],
            ['modulo9.infraestructuras.id_infraestructura'],
            name='auditoria_infra_id_infra_fkey',
        ),
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='auditoria_infra_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_auditoria_infraestructura', name='auditorias_infraestructuras_pkey'),
        {'schema': 'modulo9'},
    )

    id_auditoria_infraestructura: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_infraestructura: Mapped[int] = mapped_column(Integer, nullable=False)
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_operacion: Mapped[str] = mapped_column(String(20), nullable=False)
    valores_anteriores: Mapped[Optional[dict]] = mapped_column(JSONB)
    valores_nuevos: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fecha_gestion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text('now()'),
    )
