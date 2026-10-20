from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, Integer, Numeric, Sequence, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.prediction.infrastructure.models.base_model import Base


class DistribucionOtaModel(Base):
    """``modulo4.distribuciones_ota`` (DB-04, DEV-15): una distribución OTA y su rollout."""

    __tablename__ = "distribuciones_ota"
    __table_args__ = {"schema": "modulo4"}

    id_distribucion_ota: Mapped[int] = mapped_column(
        Integer,
        Sequence("distribuciones_ota_id_distribucion_ota_seq", schema="modulo4"),
        primary_key=True,
    )
    id_version_modelo: Mapped[int] = mapped_column(Integer, nullable=False)
    # enum_tipo_modelo / enum_modo_distribucion_ota — String para no conflictuar con el tipo existente.
    tipo_modelo: Mapped[str] = mapped_column(String(40), nullable=False)
    componente: Mapped[Optional[str]] = mapped_column(String(20))
    modo_distribucion: Mapped[str] = mapped_column(String(20), nullable=False)
    ventana_inicio: Mapped[Optional[datetime]] = mapped_column(DateTime(True))
    ventana_fin: Mapped[Optional[datetime]] = mapped_column(DateTime(True))
    nivel_bateria_minimo: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    tamano_fragmento_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    max_reintentos_descarga: Mapped[int] = mapped_column(Integer, nullable=False)
    fase_rollout: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'CANARY'"))
    porcentaje_parcial: Mapped[Optional[int]] = mapped_column(SmallInteger)
    estado_distribucion: Mapped[str] = mapped_column(String(15), nullable=False, server_default=text("'EN_CURSO'"))
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    fecha_actualizacion: Mapped[Optional[datetime]] = mapped_column(DateTime(True))
