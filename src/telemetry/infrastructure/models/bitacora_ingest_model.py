from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, PrimaryKeyConstraint, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class BitacoraIngestModel(Base):
    __tablename__ = 'bitacora_ingest'
    __table_args__ = (
        PrimaryKeyConstraint('id_bitacora_ingest', name='bitacora_ingest_pkey'),
        {'schema': 'modulo3'},
    )

    id_bitacora_ingest: Mapped[int] = mapped_column(
        Integer,
        Identity(start=1, increment=1),
        primary_key=True,
    )
    id_telemetria: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey('modulo3.telemetrias.id_telemetria', name='bitacora_ingest_id_telemetria_fkey'),
    )
    id_sensor: Mapped[Optional[int]] = mapped_column(Integer)
    id_dispositivo_iot: Mapped[Optional[int]] = mapped_column(Integer)
    # PG enum enum_eventos_edge_computing_tipo_evento — usar String
    tipo_evento: Mapped[Optional[str]] = mapped_column(String(30))
    # PG enum enum_bitacora_ingest_estado_calidad — usar String
    estado_calidad: Mapped[Optional[str]] = mapped_column(String(30))
    descripcion_text: Mapped[Optional[str]] = mapped_column(Text)
    payload_recibido: Mapped[Optional[dict]] = mapped_column(JSONB)
    # PG enum enum_bitacora_ingest_severidad — usar String
    severidad: Mapped[Optional[str]] = mapped_column(String(20))
    fecha_evento: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_captura_dato: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # Nota: typo en la DB — nombre exacto de la columna es gatway_id
    gatway_id: Mapped[Optional[str]] = mapped_column(String(100))
