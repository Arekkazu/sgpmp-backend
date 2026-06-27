"""Modelo ORM para `modulo9.sensores` (RF-22).

La columna `categoria` mapea al enum PG `enum_reglas_alertas_tipo_sensor`
(HUMEDAD, TEMPERATURA, OXIGENO, PH, AMONIACO, SALINIDAD, LUMINOSIDAD).
Se usa String para evitar conflicto con el tipo enum existente en la DB.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base


class SensorModel(Base):
    __tablename__ = 'sensores'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_dispositivo_iot'],
            ['modulo9.dispositivos_iot.id_dispositivo_iot'],
            name='sensores_id_dispositivo_iot_fkey',
        ),
        PrimaryKeyConstraint('id_sensores', name='sensores_pkey'),
        {'schema': 'modulo9'},
    )

    id_sensores: Mapped[int] = mapped_column(
        Integer,
        Sequence('sensores_id_sensores_seq', schema='modulo9'),
        primary_key=True,
    )
    id_dispositivo_iot: Mapped[int] = mapped_column(Integer, nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    categoria: Mapped[Optional[str]] = mapped_column(String(30))
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False)

    dispositivo: Mapped['DispositivoIotModel'] = relationship(
        'DispositivoIotModel',
        back_populates='sensores',
    )
    asociaciones: Mapped[list] = relationship(
        'SensorAreaModel',
        back_populates='sensor',
        lazy='selectin',
    )
