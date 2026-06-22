"""Modelo ORM para `modulo9.dispositivos_iot` (RF-21).

El serial es único en el sistema. El dispositivo se asocia obligatoriamente
a un área productiva (id_infraestructura).
"""
from __future__ import annotations

import datetime

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base


class DispositivoIotModel(Base):
    __tablename__ = 'dispositivos_iot'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_infraestructura'],
            ['modulo9.infraestructuras.id_infraestructura'],
            name='dispositivos_iot_id_infraestructura_fkey',
        ),
        PrimaryKeyConstraint('id_dispositivo_iot', name='dispositivos_iot_pkey'),
        UniqueConstraint('serial', name='uq_dispositivo_iot_serial'),
        {'schema': 'modulo9'},
    )

    id_dispositivo_iot: Mapped[int] = mapped_column(
        Integer,
        Sequence('dispositivos_iot_id_dispositivo_iot_seq', schema='modulo9'),
        primary_key=True,
    )
    serial: Mapped[str] = mapped_column(String(50), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(100), nullable=False)
    id_infraestructura: Mapped[int] = mapped_column(Integer, nullable=False)
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    sensores: Mapped[list] = relationship(
        'SensorModel',
        back_populates='dispositivo',
        lazy='selectin',
    )
    configuraciones_remotas: Mapped[list] = relationship(
        'ConfiguracionRemotaModel',
        back_populates='dispositivo',
        lazy='selectin',
    )
