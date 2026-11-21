# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-196-G026 RF-68: modelo de estimación de riesgo de contagio |
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, Numeric, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.prediction.infrastructure.models.base_model import Base


class ResultadoRiesgoContagioModel(Base):
    __tablename__ = "resultados_riesgo_contagio"
    __table_args__ = {"schema": "modulo4"}

    id_resultado_contagio: Mapped[int] = mapped_column(Integer, primary_key=True)
    # El lote (activo biológico) evaluado.
    id_activo_biologico: Mapped[int] = mapped_column(Integer, nullable=False)
    id_configuracion_motor: Mapped[int] = mapped_column(Integer, nullable=False)
    factor_sanitario_fs: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    factor_ambiental_fa: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4))
    factor_densidad_fd: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4))
    w_fs_aplicado: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    w_fa_aplicado: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    w_fd_aplicado: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    probabilidad_contagio: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    nivel_riesgo_contagio: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    confianza_baja: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    data_quality_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3))
    factores_ausentes: Mapped[Optional[list]] = mapped_column(JSONB)
    modo_ejecucion_calculo: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'NORMAL'"))
    n_enfermos_detectados: Mapped[Optional[int]] = mapped_column(Integer)
    total_activos_lote: Mapped[Optional[int]] = mapped_column(Integer)
    porcentaje_sensores_activos: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    variables_ambientales_snap: Mapped[Optional[dict]] = mapped_column(JSONB)
    fecha_calculo: Mapped[datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    # FK a modulo4.alertas_patologicas: la alerta de RF-57 (modulo3.alertas) va en el snapshot.
    id_alerta_generada: Mapped[Optional[int]] = mapped_column(Integer)
