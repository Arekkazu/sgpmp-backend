# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79: M06 provisional (recepción)        |
"""Modelo ORM de ``modulo6.recepciones_provisiones_m05`` (migración bf404c6f1018)."""
import datetime
import uuid
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.base_model import Base


class RecepcionProvisionM05Model(Base):
    __tablename__ = "recepciones_provisiones_m05"
    __table_args__ = {"schema": "modulo6"}

    id_recepcion_provision_m05: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_evento_provision: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, unique=True)
    modalidad: Mapped[str] = mapped_column(String(15), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(10), nullable=False)
    id_activo_biologico: Mapped[int] = mapped_column(Integer, nullable=False)
    id_gestion_fases: Mapped[Optional[int]] = mapped_column(Integer)
    json_contenido: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fecha_recepcion: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text("now()")
    )
