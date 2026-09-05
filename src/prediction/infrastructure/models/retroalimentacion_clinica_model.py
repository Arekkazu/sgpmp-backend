from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.prediction.infrastructure.models.base_model import Base


class RetroalimentacionClinicaModel(Base):
    __tablename__ = "retroalimentaciones_clinicas"
    __table_args__ = {"schema": "modulo4"}

    id_retroalimentacion: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    id_resultado_inferencia: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    id_activo_biologico: Mapped[int] = mapped_column(Integer, nullable=False)
    estado_retroalimentacion: Mapped[str] = mapped_column(String(20), nullable=False)
    diagnosticos_reales: Mapped[Optional[list]] = mapped_column(ARRAY(Integer))
    fuente_diagnostico: Mapped[Optional[str]] = mapped_column(String(30))
    es_fuente_desconocida: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    es_conflicto_retroalimentacion: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    observaciones_clinicas: Mapped[Optional[str]] = mapped_column(Text)
    id_usuario_veterinario: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_retroalimentacion: Mapped[datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    estado_registro: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ACTIVO'::character varying"))
