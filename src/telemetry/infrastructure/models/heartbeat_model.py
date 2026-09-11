from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Identity, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class HeartbeatModel(Base):
    __tablename__ = 'heartbeats'
    __table_args__ = {'schema': 'modulo3'}

    id_heartbeat: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    id_dispositivo_iot: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo9.dispositivos_iot.id_dispositivo_iot'), nullable=False
    )
    tipo_mensaje: Mapped[str] = mapped_column(String(30), nullable=False)
    nivel_bateria_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    calidad_senal_rssi: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 2))
    calidad_senal_snr: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 2))
    # Char(1): 'I'=INACTIVO, 'A'=ACTIVO, 'L'=LLENO (enum_estado_buffer_local)
    estado_local_buffer: Mapped[Optional[str]] = mapped_column(String(1))
    datos_pendientes_buffer: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version_firmware: Mapped[Optional[str]] = mapped_column(String(50))
    coordenadas: Mapped[Optional[Any]] = mapped_column(JSONB)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_recepcion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reloj_sincronizado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
