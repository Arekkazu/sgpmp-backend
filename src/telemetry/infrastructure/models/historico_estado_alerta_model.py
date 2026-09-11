from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class HistoricoEstadoAlertaModel(Base):
    __tablename__ = 'historico_estados_alertas'
    __table_args__ = {'schema': 'modulo3'}

    id_historico_estado_alerta: Mapped[int] = mapped_column(
        Integer, Identity(start=1, increment=1), primary_key=True
    )
    id_alerta: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo3.alertas.id_alerta'), nullable=False
    )
    # PG enums — String para no conflictuar con tipos existentes
    estado_anterior: Mapped[str] = mapped_column(String(30), nullable=False)
    estado_nuevo: Mapped[str] = mapped_column(String(30), nullable=False)
    id_usuario: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo1.usuarios.id_usuario')
    )
    motivo: Mapped[Optional[str]] = mapped_column(Text)
    fecha_cambio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
