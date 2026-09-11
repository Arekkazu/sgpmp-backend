from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.prediction.infrastructure.models.base_model import Base


class HistorialDiagnosticoEventoModel(Base):
    __tablename__ = "historial_diagnostico_eventos"
    __table_args__ = {"schema": "modulo4"}

    id_evento: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4)
    tipo_evento: Mapped[str] = mapped_column(String(30), nullable=False)
    id_activo_biologico: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_evento: Mapped[datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    id_resultado_inferencia: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
