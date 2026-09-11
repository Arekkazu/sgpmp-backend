from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.prediction.infrastructure.models.base_model import Base


class AlertaPatologicaModel(Base):
    __tablename__ = "alertas_patologicas"
    __table_args__ = {"schema": "modulo4"}

    id_alerta_patologica: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_prediccion: Mapped[int] = mapped_column(Integer, nullable=False)
    id_activo_biologico: Mapped[int] = mapped_column(Integer, nullable=False)
    id_finca: Mapped[int] = mapped_column(Integer, nullable=False)
    id_patologia: Mapped[int] = mapped_column(Integer, nullable=False)
    probabilidad_pct: Mapped[float] = mapped_column(Numeric, nullable=False)
    nivel_criticidad: Mapped[str] = mapped_column(String(20), nullable=False)
    estado_alerta: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_generacion: Mapped[datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    fecha_notificacion: Mapped[Optional[datetime]] = mapped_column(DateTime(True))
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer)
    diagnostico_confirmado: Mapped[Optional[str]] = mapped_column(String)
    es_verdadero: Mapped[Optional[bool]] = mapped_column()
    id_notificacion: Mapped[int] = mapped_column(Integer, nullable=False)
