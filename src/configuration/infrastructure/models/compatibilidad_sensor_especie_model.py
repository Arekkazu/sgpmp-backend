"""Modelo M09 de compatibilidad biologica sensor-especie (RF-49)."""
from __future__ import annotations

import datetime

from sqlalchemy import (
    DateTime,
    ForeignKeyConstraint,
    Identity,
    Integer,
    PrimaryKeyConstraint,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class CompatibilidadSensorEspecieModel(Base):
    __tablename__ = 'compatibilidad_sensores_especies'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_sensor'],
            ['modulo9.sensores.id_sensores'],
            name='compatibilidad_sensores_especies_id_sensor_fkey',
        ),
        ForeignKeyConstraint(
            ['id_especie'],
            ['modulo9.especies.id_especie'],
            name='compatibilidad_sensores_especies_id_especie_fkey',
        ),
        PrimaryKeyConstraint(
            'id_compatibilidad_sensor_especie',
            name='compatibilidad_sensores_especies_pkey',
        ),
        UniqueConstraint(
            'id_sensor',
            'id_especie',
            name='uq_compatibilidad_sensor_especie',
        ),
        {'schema': 'modulo9'},
    )

    id_compatibilidad_sensor_especie: Mapped[int] = mapped_column(
        Integer,
        Identity(),
        primary_key=True,
    )
    id_sensor: Mapped[int] = mapped_column(Integer, nullable=False)
    id_especie: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
