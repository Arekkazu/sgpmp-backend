"""Modelo ORM para `modulo9.sensores_areas_asociadas` (RF-22).

`tiene_estado=True` indica asociación activa. `fecha_finalizacion` se
establece cuando la asociación se termina (reasignación o desactivación).
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base


class SensorAreaModel(Base):
    __tablename__ = 'sensores_areas_asociadas'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_sensor'],
            ['modulo9.sensores.id_sensores'],
            name='sensores_areas_asociadas_id_sensor_fkey',
        ),
        ForeignKeyConstraint(
            ['id_dispositivo_iot'],
            ['modulo9.dispositivos_iot.id_dispositivo_iot'],
            name='sensores_areas_asociadas_id_dispositivo_iot_fkey',
        ),
        ForeignKeyConstraint(
            ['id_infraestructura'],
            ['modulo9.infraestructuras.id_infraestructura'],
            name='sensores_areas_asociadas_id_infraestructura_fkey',
        ),
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='sensores_areas_asociadas_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_sensores_area_asociada', name='sensores_areas_asociadas_pkey'),
        {'schema': 'modulo9'},
    )

    id_sensores_area_asociada: Mapped[int] = mapped_column(
        Integer,
        Sequence('sensores_areas_asociadas_id_sensores_area_asociada_seq', schema='modulo9'),
        primary_key=True,
    )
    id_sensor: Mapped[int] = mapped_column(Integer, nullable=False)
    id_dispositivo_iot: Mapped[int] = mapped_column(Integer, nullable=False)
    id_infraestructura: Mapped[int] = mapped_column(Integer, nullable=False)
    punto_instalacion: Mapped[str] = mapped_column(String(100), nullable=False)
    tiene_estado: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fecha_asociacion: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_finalizacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)

    sensor: Mapped['SensorModel'] = relationship(
        'SensorModel',
        back_populates='asociaciones',
    )
