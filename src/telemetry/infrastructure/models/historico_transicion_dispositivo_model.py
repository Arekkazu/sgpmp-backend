from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class HistoricoTransicionDispositivoModel(Base):
    __tablename__ = 'historico_transiciones_dispositivos'
    __table_args__ = {'schema': 'modulo3'}

    id_transaccion: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    id_dispositivo_iot: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo9.dispositivos_iot.id_dispositivo_iot'), nullable=False
    )
    # enum_estado_dispositivo
    estado_anterior: Mapped[str] = mapped_column(String(30), nullable=False)
    estado_nuevo: Mapped[str] = mapped_column(String(30), nullable=False)
    # enum_causa_primaria
    causa_primaria: Mapped[Optional[str]] = mapped_column(String(50))
    # Typo en DB: causa_secundar
    causa_secundar: Mapped[Optional[Any]] = mapped_column(JSONB)
    # Typo en DB: id_usuairo_responsable
    id_usuairo_responsable: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo1.usuarios.id_usuario')
    )
    notas: Mapped[Optional[str]] = mapped_column(Text)
    fecha_transicion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
