from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.prediction.infrastructure.models.base_model import Base


class EventoAuditoriaM04Model(Base):
    __tablename__ = "eventos_auditoria_m04"
    __table_args__ = {"schema": "modulo4"}

    id_evento: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tipo_evento: Mapped[str] = mapped_column(String(60), nullable=False)
    modulo: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'MODULO4'::character varying"))
    fecha_evento: Mapped[datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    tipo_actor: Mapped[str] = mapped_column(String(20), nullable=False)
    correlacion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, server_default=text("gen_random_uuid()"))
    payload_evento: Mapped[dict] = mapped_column(JSONB, nullable=False)
    es_payload_truncado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    severidad_evento: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'INFO'::modulo4.enum_severidad_evento_auditoria"))
    origen_registro: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'DIRECTO'::character varying"))
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer)
    id_sistema: Mapped[Optional[str]] = mapped_column(String(100))
    id_referencia: Mapped[Optional[str]] = mapped_column(String(100))
    entidad_referencia: Mapped[Optional[str]] = mapped_column(String(50))
    resultado_operacion: Mapped[Optional[str]] = mapped_column(String(10))
    codigo_error: Mapped[Optional[str]] = mapped_column(String(50))
    descripcion_error: Mapped[Optional[str]] = mapped_column(Text)
    origen_dato: Mapped[Optional[str]] = mapped_column(String(20))
    version_modelo: Mapped[Optional[str]] = mapped_column(String(40))
    latencia_ms: Mapped[Optional[int]] = mapped_column(Integer)
    hash_evento: Mapped[Optional[str]] = mapped_column(String(64))
