# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M03-134-G192 RF-62: columnas DB-09 y evaluación de calidad pendiente |
"""Observaciones de visión: 88496bce07b6, DB-03 (65541db23c71), DB-09 (be29f17bb7fc) y RF-62 (8c4e2a6f1b93)."""
from __future__ import annotations

import datetime
import decimal
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKeyConstraint, Integer, Numeric, PrimaryKeyConstraint, String,
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
    fecha_inicio_ventana: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    version_cascada: Mapped[Optional[dict]] = mapped_column('json_version_cascada', JSONB(none_as_null=True))
    cobertura_ventana: Mapped[decimal.Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    cantidad_tracks: Mapped[Optional[int]] = mapped_column(Integer)
    cantidad_tracks_perdidos: Mapped[int] = mapped_column(Integer, nullable=False)
    fps_efectivo: Mapped[decimal.Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    estado_calibracion: Mapped[str] = mapped_column(String(15), nullable=False)
    json_vector: Mapped[dict] = mapped_column(JSONB, nullable=False)
    n_individuos_observados: Mapped[Optional[int]] = mapped_column(Integer)
    # enum PG modulo3.enum_telemetria_origen: String para no recrear el tipo.
    origen: Mapped[Optional[str]] = mapped_column(String)
    # RF-62: NULL hasta que la evaluación asíncrona llena todo el bloque.
    indice_calidad_vision: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 2))
    clasificacion_calidad: Mapped[Optional[str]] = mapped_column(String(20))
    es_apto_para_ia: Mapped[Optional[bool]] = mapped_column(Boolean)
    es_confianza_baja: Mapped[Optional[bool]] = mapped_column(Boolean)
    json_flags_detectados: Mapped[Optional[dict]] = mapped_column(JSONB(none_as_null=True))
    fecha_evaluacion_calidad: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text('now()')
    )
