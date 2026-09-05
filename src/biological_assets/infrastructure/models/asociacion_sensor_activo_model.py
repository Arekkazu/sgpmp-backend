from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Sequence,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base


class AsociacionSensorActivoModel(Base):
    __tablename__ = 'asociaciones_activos_sensores'
    __table_args__ = (
        CheckConstraint(
            "estado_asociacion = ANY (ARRAY['ACTIVA','INACTIVA','SUPERADA'])",
            name='asociaciones_activos_sensores_estado_asociacion_check',
        ),
        CheckConstraint(
            "tipo_activo = ANY (ARRAY['INDIVIDUAL','LOTE'])",
            name='asociaciones_activos_sensores_tipo_activo_check',
        ),
        CheckConstraint(
            'fecha_inicio < fecha_fin',
            name='chk_asociacion_fechas_coherentes',
        ),
        ForeignKeyConstraint(
            ['id_activo_biologico'],
            ['modulo2.activos_biologicos.id_activo_biologico'],
            name='fk_asociacion_activo_biologico',
        ),
        ForeignKeyConstraint(
            ['id_sensor'],
            ['modulo9.sensores.id_sensores'],
            name='asociaciones_activos_sensores_id_sensor_fkey',
        ),
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='asociaciones_activos_sensores_id_usuario_fkey',
        ),
        ForeignKeyConstraint(
            ['dispositivo_iot_id'],
            ['modulo9.dispositivos_iot.id_dispositivo_iot'],
            name='asociaciones_activos_sensores_dispositivo_iot_id_fkey',
        ),
        ForeignKeyConstraint(
            ['id_infraestructura'],
            ['modulo9.infraestructuras.id_infraestructura'],
            name='asociaciones_activos_sensores_id_infraestructura_fkey',
        ),
        PrimaryKeyConstraint('id_asociacion_activo_sensor', name='asociaciones_activos_sensores_pkey'),
        # Índice parcial: un sensor solo puede tener una asociación ACTIVA por activo (fecha_fin IS NULL)
        Index(
            'uix_asociacion_sensor_activo_vigente',
            'id_sensor',
            'id_activo_biologico',
            unique=True,
            postgresql_where='fecha_fin IS NULL',
        ),
        {'schema': 'modulo2'},
    )

    id_asociacion_activo_sensor: Mapped[int] = mapped_column(
        Integer,
        Sequence('asociaciones_activos_sensores_id_asociacion_activo_sensor_seq', schema='modulo2'),
        primary_key=True,
    )
    id_sensor: Mapped[int] = mapped_column(Integer, nullable=False)
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_inicio: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado_asociacion: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'ACTIVA'"),
    )
    # PG enum enum_asociaciones_activos_sensores_tipo — usar String para no conflictuar
    tipo: Mapped[Optional[str]] = mapped_column(String(20))
    tipo_activo: Mapped[Optional[str]] = mapped_column(String(20))
    dispositivo_iot_id: Mapped[Optional[int]] = mapped_column(Integer)
    id_infraestructura: Mapped[Optional[int]] = mapped_column(Integer)
    fecha_fin: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    motivo: Mapped[Optional[str]] = mapped_column(Text)
    id_activo_biologico: Mapped[Optional[int]] = mapped_column(Integer)

    auditoria: Mapped[list['AuditoriaAsociacionSensorModel']] = relationship(
        'AuditoriaAsociacionSensorModel',
        back_populates='asociacion',
        lazy='select',
    )
