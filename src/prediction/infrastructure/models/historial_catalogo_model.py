from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.prediction.infrastructure.models.base_model import Base


class HistorialCatalogoModel(Base):
    __tablename__ = "historial_catalogo_patologias"
    __table_args__ = {"schema": "modulo4"}

    id_historial_catalogo: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_patologia: Mapped[int] = mapped_column(Integer, nullable=False)
    version_catalogo: Mapped[int] = mapped_column(Integer, nullable=False)
    accion: Mapped[str] = mapped_column(String(30), nullable=False)
    datos_nuevos: Mapped[dict] = mapped_column(JSONB, nullable=False)
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_cambio: Mapped[datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    datos_anteriores: Mapped[Optional[dict]] = mapped_column(JSONB)
