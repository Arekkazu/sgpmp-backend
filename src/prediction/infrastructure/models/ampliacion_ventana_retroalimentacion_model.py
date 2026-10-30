# | Fecha      | Nombre   | Que se hizo                                                  |
# |------------|----------|--------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-229-G070 RF-72: ampliación de ventana por resultado  |
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Identity, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.prediction.infrastructure.models.base_model import Base


class AmpliacionVentanaRetroalimentacionModel(Base):
    __tablename__ = "ampliaciones_ventana_retroalimentacion"
    __table_args__ = {"schema": "modulo4"}

    id_ampliacion_ventana_retroalimentacion: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    id_resultado_inferencia: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    fecha_limite: Mapped[datetime] = mapped_column(DateTime(True), nullable=False)
    justificacion: Mapped[str] = mapped_column(Text, nullable=False)
    id_usuario_autorizador: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
