from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, Numeric, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.prediction.infrastructure.models.base_model import Base


class ResultadoInferenciaModel(Base):
    __tablename__ = "resultados_inferencia"
    __table_args__ = {"schema": "modulo4"}

    id_resultado_inferencia: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    id_paquete_inferencia: Mapped[Optional[int]] = mapped_column(Integer)
    id_activo_biologico: Mapped[int] = mapped_column(Integer, nullable=False)
    id_especie: Mapped[int] = mapped_column(Integer, nullable=False)
    fase_productiva: Mapped[Optional[str]] = mapped_column(String(50))
    tipo_modelo: Mapped[str] = mapped_column(String(40), nullable=False)
    id_version_modelo: Mapped[int] = mapped_column(Integer, nullable=False)
    nivel_riesgo: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    probabilidad_riesgo: Mapped[dict] = mapped_column(JSONB, nullable=False)
    id_patologia: Mapped[Optional[int]] = mapped_column(Integer)
    probabilidad_enfermedad: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confianza_global: Mapped[float] = mapped_column(Numeric, nullable=False)
    contexto_incompleto: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    latencia_excedida: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    modo_ejecucion: Mapped[str] = mapped_column(String(20), nullable=False)
    latencia_ms: Mapped[Optional[int]] = mapped_column(Integer)
    fecha_inicio_ventana: Mapped[Optional[datetime]] = mapped_column(DateTime(True))
    fecha_fin_ventana: Mapped[Optional[datetime]] = mapped_column(DateTime(True))
    fecha_inferencia: Mapped[datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    tiene_alerta_generada: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    id_alerta_generada: Mapped[Optional[int]] = mapped_column(Integer)
