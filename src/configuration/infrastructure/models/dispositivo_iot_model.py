"""Modelo ORM para `modulo9.dispositivos_iot` (RF-21).

El serial es único en el sistema. El dispositivo se asocia obligatoriamente
a un área productiva (id_infraestructura).
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, Numeric, PrimaryKeyConstraint, Sequence, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base
from .tipo_dispositivo_iot_model import TipoDispositivoIotModel


class DispositivoIotModel(Base):
    __tablename__ = 'dispositivos_iot'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_infraestructura'],
            ['modulo9.infraestructuras.id_infraestructura'],
            name='dispositivos_iot_id_infraestructura_fkey',
        ),
        ForeignKeyConstraint(
            ['id_tipo_dispositivo'],
            ['modulo9.tipos_dispositivo_iot.id_tipo_dispositivo'],
            name='dispositivos_iot_id_tipo_dispositivo_fkey',
        ),
        ForeignKeyConstraint(
            ['id_dispositivo_gateway'],
            ['modulo9.dispositivos_iot.id_dispositivo_iot'],
            name='dispositivos_iot_id_dispositivo_gateway_fkey',
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
    id_tipo_dispositivo: Mapped[int] = mapped_column(Integer, nullable=False)
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # RF-21: Gateway Edge que atiende a este dispositivo (autorreferencia N:1).
    id_dispositivo_gateway: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # RF-21 v2.0 (RFC-011): atributos de visión, solo para tipos de categoría CAMARA.
    resolucion: Mapped[Optional[str]] = mapped_column(String(20))
    fps: Mapped[Optional[int]] = mapped_column(SmallInteger)
    area_cobertura_m2: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    # RF-21 v2.0 (RFC-011): la categoría (SENSOR | CAMARA) es del tipo, no del dispositivo.
    tipo: Mapped[TipoDispositivoIotModel] = relationship(lazy='joined', viewonly=True)
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
