from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, Numeric, Sequence, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.prediction.infrastructure.models.base_model import Base


class ConfiguracionMotorIAModel(Base):
    __tablename__ = "configuraciones_motor_ia"
    __table_args__ = {"schema": "modulo4"}

    id_configuracion_motor: Mapped[int] = mapped_column(
        Integer,
        Sequence("configuraciones_motor_ia_id_configuracion_motor_seq", schema="modulo4"),
        primary_key=True,
    )
    tipo_modelo: Mapped[str] = mapped_column(String(40), nullable=False)
    umbral_riesgo_alto: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False, server_default=text("0.700"))
    umbral_alerta_critica: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False, server_default=text("0.700"))
    ventana_temporal_min: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("10"))
    id_version_modelo_activa: Mapped[Optional[int]] = mapped_column(Integer)
    modo_ejecucion: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'SERVIDOR'"))
    config_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    w_factor_sanitario: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False, server_default=text("0.500"))
    w_factor_ambiental: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False, server_default=text("0.300"))
    w_factor_densidad: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False, server_default=text("0.200"))
    temp_min_config: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    temp_max_config: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    hr_min_config: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    hr_max_config: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    densidad_maxima_config: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    es_activa: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    id_usuario_responsable: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
