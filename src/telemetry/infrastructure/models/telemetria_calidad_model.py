from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class TelemetriaCalidadModel(Base):
    __tablename__ = 'telemetria_calidad'
    __table_args__ = ({'schema': 'modulo3'},)

    id_evaluacion: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default='gen_random_uuid()',
    )
    id_telemetria: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo3.telemetrias.id_telemetria', name='fk_calidad_telemetria'),
        nullable=False,
    )
    id_sensor: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_evaluacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default='now()'
    )
    indice_calidad: Mapped[Optional[int]] = mapped_column(SmallInteger)
    clasificacion_calidad: Mapped[str] = mapped_column(String(20), nullable=False)
    apto_para_ia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    apto_para_nic41: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    flags_detectados: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    version_limites_fisicos_aplicada: Mapped[Optional[str]] = mapped_column(String(50))
    parametros_aplicados: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    parametros_calibracion_aplicados: Mapped[Optional[dict]] = mapped_column(JSONB)
    estado_evaluacion: Mapped[str] = mapped_column(String(10), nullable=False, default='VIGENTE')
    motivo_reevaluacion: Mapped[Optional[str]] = mapped_column(Text)
    id_evaluacion_superada: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey('modulo3.telemetria_calidad.id_evaluacion', name='fk_calidad_superada'),
    )
    version_evaluacion: Mapped[Optional[str]] = mapped_column(String(100))
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default='now()'
    )
