"""Modelo ORM para `modulo9.auditorias_dispositivos_iot`."""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class AuditoriaDispositivoIotModel(Base):
    __tablename__ = 'auditorias_dispositivos_iot'
    __table_args__ = (
        CheckConstraint(
            "tipo_operacion IN ('CREATE','DEACTIVATE','GET')",
            name='chk_tipo_operacion_dispositivo_iot',
        ),
        ForeignKeyConstraint(
            ['id_dispositivo_iot'],
            ['modulo9.dispositivos_iot.id_dispositivo_iot'],
            name='auditoria_disp_iot_id_dispositivo_fkey',
        ),
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='auditoria_disp_iot_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_auditoria_dispositivo_iot', name='auditorias_dispositivos_iot_pkey'),
        {'schema': 'modulo9'},
    )

    id_auditoria_dispositivo_iot: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_dispositivo_iot: Mapped[int] = mapped_column(Integer, nullable=False)
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_operacion: Mapped[str] = mapped_column(String(20), nullable=False)
    valores_anteriores: Mapped[Optional[dict]] = mapped_column(JSONB)
    valores_nuevos: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fecha_gestion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text('now()'),
    )
