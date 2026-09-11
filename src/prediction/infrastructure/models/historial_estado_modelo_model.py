from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, Sequence, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.prediction.infrastructure.models.base_model import Base


class HistorialEstadoModeloModel(Base):
    __tablename__ = "historial_estados_modelos"
    __table_args__ = {"schema": "modulo4"}

    id_historial_estado_modelo: Mapped[int] = mapped_column(
        Integer,
        Sequence("historial_estados_modelos_id_historial_estado_modelo_seq", schema="modulo4"),
        primary_key=True,
    )
    id_version_modelo: Mapped[int] = mapped_column(Integer, nullable=False)
    estado_anterior: Mapped[Optional[str]] = mapped_column(String(20))
    estado_nuevo: Mapped[str] = mapped_column(String(20), nullable=False)
    tipo_actor: Mapped[str] = mapped_column(String(20), nullable=False)
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer)
    id_sistema: Mapped[Optional[str]] = mapped_column(String(100))
    id_proceso_rf71: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    correlacion_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    motivo: Mapped[Optional[str]] = mapped_column(Text)
    fecha_transicion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
