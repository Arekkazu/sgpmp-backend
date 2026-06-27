"""Modelo ORM para `modulo9.calibraciones` (RF-24).

Cada fila es un evento de calibración inmutable. La tabla es el historial
de trazabilidad; no se requiere tabla de auditoría separada.
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, Numeric, PrimaryKeyConstraint, Sequence, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class CalibracionModel(Base):
    __tablename__ = 'calibraciones'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_dispositivo_iot'],
            ['modulo9.dispositivos_iot.id_dispositivo_iot'],
            name='calibraciones_id_dispositivo_iot_fkey',
        ),
        ForeignKeyConstraint(
            ['id_sensor'],
            ['modulo9.sensores.id_sensores'],
            name='calibraciones_id_sensor_fkey',
        ),
        PrimaryKeyConstraint('id_calibracion', name='calibraciones_pkey'),
        {'schema': 'modulo9'},
    )

    id_calibracion: Mapped[int] = mapped_column(
        Integer,
        Sequence('calibraciones_id_calibracion_seq', schema='modulo9'),
        primary_key=True,
    )
    id_dispositivo_iot: Mapped[int] = mapped_column(Integer, nullable=False)
    id_sensor: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_calibracion: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valor_referencia: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    observaciones: Mapped[Optional[str]] = mapped_column(Text)
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
