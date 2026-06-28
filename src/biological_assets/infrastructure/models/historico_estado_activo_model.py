from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class HistoricoEstadoActivoModel(Base):
    __tablename__ = 'historicos_estados_activos'
    __table_args__ = {'schema': 'modulo2'}

    id_historico_estado_activo: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_activo_biologico: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo2.activos_biologicos.id_activo_biologico'), nullable=False
    )
    id_estado_nuevo: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo2.estados_activos_biologicos.id_estado_activo_biologico'), nullable=False
    )
    id_estado_anterior: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo2.estados_activos_biologicos.id_estado_activo_biologico'), nullable=False
    )
    fecha_cambio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    motivo_cambio: Mapped[str | None] = mapped_column(Text, nullable=True)
    modulo_origen: Mapped[str] = mapped_column(String(20), nullable=False)
    id_usuario: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo1.usuarios.id_usuario'), nullable=False
    )
