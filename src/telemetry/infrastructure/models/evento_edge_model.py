from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Identity, Integer, Numeric, PrimaryKeyConstraint, String
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class EventoEdgeComputingModel(Base):
    __tablename__ = 'eventos_edge_computing'
    __table_args__ = (
        PrimaryKeyConstraint('id_evento_edge_computing', name='eventos_edge_computing_pkey'),
        {'schema': 'modulo3'},
    )

    id_evento_edge_computing: Mapped[int] = mapped_column(
        Integer,
        Identity(start=1, increment=1),
        primary_key=True,
    )
    id_dispositivo_iot: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo9.dispositivos_iot.id_dispositivo_iot'),
        nullable=False,
    )
    id_sensor: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo9.sensores.id_sensores'),
        nullable=False,
    )
    # PG enum — String para no conflictuar con tipo existente en PostgreSQL
    tipo_evento: Mapped[str] = mapped_column(String(30), nullable=False)
    severidad: Mapped[Optional[str]] = mapped_column(String(20))
    variables_involucradas: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    # FK a modulo3.reglas_alertas — no mapeada, solo Integer
    id_regla_alerta: Mapped[Optional[int]] = mapped_column(Integer)
    valor_evaluado: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    umbral_min_aplicado: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    umbral_max_aplicado: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    desviacion_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    fecha_captura: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_procesamiento: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    origen_dato: Mapped[str] = mapped_column(String(20), nullable=False)
    estado_conectividad: Mapped[bool] = mapped_column(Boolean, nullable=False)
    metadatos: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    enviado_backend: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Nota: typo en BD — nombre exacto de columna es almacendado_buffer
    almacendado_buffer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
