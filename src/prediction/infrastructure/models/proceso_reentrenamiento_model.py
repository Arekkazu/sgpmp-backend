# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-14 RF-71: modelo ORM de modulo4.procesos_reentrenamiento (migración 21fe51f2aea1) |
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, Integer, Numeric, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.prediction.infrastructure.models.base_model import Base


class ProcesoReentrenamientoModel(Base):
    __tablename__ = "procesos_reentrenamiento"
    __table_args__ = {"schema": "modulo4"}

    id_proceso_reentrenamiento: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    # Columnas ENUM de PostgreSQL mapeadas como String (convención del repo).
    tipo_modelo: Mapped[str] = mapped_column(String(40), nullable=False)
    id_activo_biologico: Mapped[int] = mapped_column(Integer, nullable=False)
    disparador: Mapped[str] = mapped_column(String(20), nullable=False)
    modo_generacion: Mapped[str] = mapped_column(String(30), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    fase_actual: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    porcentaje_progreso: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    json_fases: Mapped[list] = mapped_column(JSONB, nullable=False)
    porcentaje_cpu: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    memoria_ram_mb: Mapped[Optional[int]] = mapped_column(Integer)
    codigo_error: Mapped[Optional[str]] = mapped_column(String(60))
    json_motivos: Mapped[Optional[list]] = mapped_column(JSONB)
    id_version_modelo_referencia: Mapped[Optional[int]] = mapped_column(Integer)
    id_version_modelo_resultante: Mapped[Optional[int]] = mapped_column(Integer)
    id_usuario_solicitante: Mapped[Optional[int]] = mapped_column(Integer)
    fecha_solicitud: Mapped[datetime] = mapped_column(DateTime(True), nullable=False)
    fecha_inicio: Mapped[Optional[datetime]] = mapped_column(DateTime(True))
    fecha_fin: Mapped[Optional[datetime]] = mapped_column(DateTime(True))
    fecha_ultimo_latido: Mapped[Optional[datetime]] = mapped_column(DateTime(True))
