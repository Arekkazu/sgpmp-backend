"""Modelo ORM para `modulo9.tipos_dispositivo_iot` (RF-23).

Catálogo de tipos de dispositivo con los rangos min/max permitidos para cada
parámetro configurable (frecuencia de captura, intervalo de transmisión).
"""
from __future__ import annotations

import datetime

from sqlalchemy import CheckConstraint, Integer, PrimaryKeyConstraint, Sequence, String, TIMESTAMP, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base_model import Base


class TipoDispositivoIotModel(Base):
    __tablename__ = 'tipos_dispositivo_iot'
    __table_args__ = (
        PrimaryKeyConstraint('id_tipo_dispositivo', name='tipos_dispositivo_iot_pkey'),
        UniqueConstraint('nombre', name='tipos_dispositivo_iot_nombre_key'),
        CheckConstraint(
            'frecuencia_captura_min >= 1 AND frecuencia_captura_max >= frecuencia_captura_min',
            name='tipos_dispositivo_iot_frecuencia_check',
        ),
        CheckConstraint(
            'intervalo_transmision_min >= 1 AND intervalo_transmision_max >= intervalo_transmision_min',
            name='tipos_dispositivo_iot_intervalo_check',
        ),
        {'schema': 'modulo9'},
    )

    id_tipo_dispositivo: Mapped[int] = mapped_column(
        Integer,
        Sequence('tipos_dispositivo_iot_id_tipo_dispositivo_seq', schema='modulo9'),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)
    frecuencia_captura_min: Mapped[int] = mapped_column(Integer, nullable=False)
    frecuencia_captura_max: Mapped[int] = mapped_column(Integer, nullable=False)
    intervalo_transmision_min: Mapped[int] = mapped_column(Integer, nullable=False)
    intervalo_transmision_max: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
