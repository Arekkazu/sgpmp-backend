# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-36 RF-65: concurrencia optimista (config_version) e historial append-only |
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.prediction.infrastructure.models.base_model import Base


class ConfiguracionIaLogModel(Base):
    """``modulo4.configuracion_ia_log`` (DB-14): snapshot OLD de cada UPDATE/DELETE.

    Append-only: la aplicación solo tiene SELECT; los INSERT los hace el trigger.
    """

    __tablename__ = "configuracion_ia_log"
    __table_args__ = {"schema": "modulo4"}

    id_log: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_configuracion_motor: Mapped[int] = mapped_column(Integer, nullable=False)
    operacion: Mapped[str] = mapped_column(String(10), nullable=False)
    # enum_tipo_modelo / enum_modo_ejecucion en PostgreSQL
    tipo_modelo: Mapped[str] = mapped_column(String(40), nullable=False)
    umbral_riesgo_alto: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3))
    umbral_alerta_critica: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3))
    ventana_temporal_min: Mapped[int] = mapped_column(Integer, nullable=False)
    id_version_modelo_activa: Mapped[Optional[int]] = mapped_column(Integer)
    modo_ejecucion: Mapped[str] = mapped_column(String(20), nullable=False)
    config_version: Mapped[int] = mapped_column(Integer, nullable=False)
    w_factor_sanitario: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    w_factor_ambiental: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    w_factor_densidad: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    temp_min_config: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    temp_max_config: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    hr_min_config: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    hr_max_config: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    densidad_maxima_config: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    es_activa: Mapped[bool] = mapped_column(Boolean, nullable=False)
    id_usuario_responsable: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_creacion_config: Mapped[datetime] = mapped_column(DateTime(True), nullable=False)
    umbral_score_anomalia: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3))
    versiones_activas_por_componente: Mapped[Optional[dict]] = mapped_column(JSONB)
    id_usuario_cambio: Mapped[Optional[int]] = mapped_column(Integer)
    fecha_cambio: Mapped[datetime] = mapped_column(DateTime(True), nullable=False)
