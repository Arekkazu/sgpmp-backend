from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, Sequence, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.prediction.infrastructure.models.base_model import Base


class DespliegueOtaModel(Base):
    __tablename__ = "despliegues_ota"
    __table_args__ = {"schema": "modulo4"}

    id_despliegue_ota: Mapped[int] = mapped_column(
        Integer,
        Sequence("despliegues_ota_id_despliegue_ota_seq", schema="modulo4"),
        primary_key=True,
    )
    id_version_modelo: Mapped[int] = mapped_column(Integer, nullable=False)
    id_dispositivo_iot: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_modelo: Mapped[str] = mapped_column(String(40), nullable=False)
    modo_distribucion: Mapped[str] = mapped_column(String(20), nullable=False)
    estado_despliegue: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'PENDIENTE'"))
    hash_modelo_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    resultado_validacion_hash: Mapped[Optional[bool]] = mapped_column(Boolean)
    id_version_modelo_anterior: Mapped[Optional[int]] = mapped_column(Integer)
    rollback_ejecutado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    intentos_descarga: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_reintentos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("3"))
    tamano_modelo_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    tamano_descargado_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    duracion_proceso_ms: Mapped[Optional[int]] = mapped_column(Integer)
    ventana_inicio: Mapped[Optional[datetime]] = mapped_column(DateTime(True))
    ventana_fin: Mapped[Optional[datetime]] = mapped_column(DateTime(True))
    nivel_bateria_al_inicio: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    fecha_fin: Mapped[Optional[datetime]] = mapped_column(DateTime(True))
    motivo_fallo: Mapped[Optional[str]] = mapped_column(String)
