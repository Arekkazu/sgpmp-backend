"""Modelo ORM para `modulo9.configuraciones_remotas` (RF-23).

Cada fila representa un comando de configuración. La tabla es el historial
de configuraciones enviadas/pendientes. Estado: PENDIENTE / APLICADA / FALLIDA.
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base


class ConfiguracionRemotaModel(Base):
    __tablename__ = 'configuraciones_remotas'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_dispositivo_iot'],
            ['modulo9.dispositivos_iot.id_dispositivo_iot'],
            name='configuraciones_remotas_id_dispositivo_iot_fkey',
        ),
        PrimaryKeyConstraint('id_configuracion_remota', name='configuraciones_remotas_pkey'),
        {'schema': 'modulo9'},
    )

    id_configuracion_remota: Mapped[int] = mapped_column(
        Integer,
        Sequence('configuraciones_remotas_id_configuracion_remota_seq', schema='modulo9'),
        primary_key=True,
    )
    id_dispositivo_iot: Mapped[int] = mapped_column(Integer, nullable=False)
    frecuencia_captura: Mapped[int] = mapped_column(Integer, nullable=False)
    intervalo_transmision: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'PENDIENTE'"))
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer)
    fecha_creacion: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), server_default=text('now()'),
    )
    fecha_aplicacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))

    dispositivo: Mapped['DispositivoIotModel'] = relationship(
        'DispositivoIotModel',
        back_populates='configuraciones_remotas',
    )
