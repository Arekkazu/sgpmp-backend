from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    PrimaryKeyConstraint,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base


class AuditoriaAsociacionSensorModel(Base):
    __tablename__ = 'auditorias_asociaciones_sensor_activo'
    __table_args__ = (
        CheckConstraint(
            "tipo_operacion = ANY (ARRAY['CREATE','DEACTIVATE','UPDATE'])",
            name='auditorias_asociaciones_sensor_activo_tipo_operacion_check',
        ),
        ForeignKeyConstraint(
            ['id_asociacion_activo_sensor'],
            ['modulo2.asociaciones_activos_sensores.id_asociacion_activo_sensor'],
            name='auditorias_asociaciones_sensor_id_asociacion_activo_sensor_fkey',
        ),
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='auditorias_asociaciones_sensor_activo_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_auditoria', name='auditorias_asociaciones_sensor_activo_pkey'),
        {'schema': 'modulo2'},
    )

    id_auditoria: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_asociacion_activo_sensor: Mapped[int] = mapped_column(Integer, nullable=False)
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_operacion: Mapped[str] = mapped_column(String(20), nullable=False)
    valores_nuevos: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fecha_gestion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text('now()'),
    )
    valores_anteriores: Mapped[Optional[dict]] = mapped_column(JSONB)

    asociacion: Mapped['AsociacionSensorActivoModel'] = relationship(
        'AsociacionSensorActivoModel',
        back_populates='auditoria',
    )
