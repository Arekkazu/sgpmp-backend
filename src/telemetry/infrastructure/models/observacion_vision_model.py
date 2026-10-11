"""Modelo ORM de `modulo3.observaciones_vision` (RF-53/RF-62 v2.0, migración `88496bce07b6`)."""
from __future__ import annotations

import datetime
import decimal

from sqlalchemy import (
    Boolean, DateTime, ForeignKeyConstraint, Integer, Numeric, PrimaryKeyConstraint, SmallInteger, String,
    UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class ObservacionVisionModel(Base):
    __tablename__ = 'observaciones_vision'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_dispositivo_iot'], ['modulo9.dispositivos_iot.id_dispositivo_iot'],
            ondelete='RESTRICT', onupdate='CASCADE', name='observaciones_vision_id_dispositivo_iot_fkey',
        ),
        ForeignKeyConstraint(
            ['id_infraestructura'], ['modulo9.infraestructuras.id_infraestructura'],
            ondelete='RESTRICT', onupdate='CASCADE', name='observaciones_vision_id_infraestructura_fkey',
        ),
        PrimaryKeyConstraint('id_observacion_vision', name='observaciones_vision_pkey'),
        UniqueConstraint(
            'id_dispositivo_iot', 'fecha_observacion',
            name='uq_observacion_vision_id_dispositivo_iot_fecha_observacion',
        ),
        {'schema': 'modulo3'},
    )

    id_observacion_vision: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_dispositivo_iot: Mapped[int] = mapped_column(Integer, nullable=False)
    id_infraestructura: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_observacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False)
    cobertura_ventana: Mapped[decimal.Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    cantidad_tracks: Mapped[int] = mapped_column(Integer, nullable=False)
    cantidad_tracks_perdidos: Mapped[int] = mapped_column(Integer, nullable=False)
    fps_efectivo: Mapped[decimal.Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    estado_calibracion: Mapped[str] = mapped_column(String(15), nullable=False)
    json_vector: Mapped[dict] = mapped_column(JSONB, nullable=False)
    indice_calidad: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    clasificacion_calidad: Mapped[str] = mapped_column(String(20), nullable=False)
    es_apto_para_ia: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text('now()')
    )
