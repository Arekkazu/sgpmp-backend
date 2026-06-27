"""Modelo ORM para `modulo9.auditorias_sensores_areas`."""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class AuditoriaSensorAreaModel(Base):
    __tablename__ = 'auditorias_sensores_areas'
    __table_args__ = (
        CheckConstraint(
            "tipo_operacion IN ('CREATE','GET')",
            name='chk_tipo_operacion_sensor_area',
        ),
        ForeignKeyConstraint(
            ['id_sensores_area_asociada'],
            ['modulo9.sensores_areas_asociadas.id_sensores_area_asociada'],
            name='auditoria_sensor_area_id_asoc_fkey',
        ),
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='auditoria_sensor_area_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_auditoria_sensor_area', name='auditorias_sensores_areas_pkey'),
        {'schema': 'modulo9'},
    )

    id_auditoria_sensor_area: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_sensores_area_asociada: Mapped[int] = mapped_column(Integer, nullable=False)
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_operacion: Mapped[str] = mapped_column(String(20), nullable=False)
    valores_anteriores: Mapped[Optional[dict]] = mapped_column(JSONB)
    valores_nuevos: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fecha_gestion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text('now()'),
    )
