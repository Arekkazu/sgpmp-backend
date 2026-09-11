from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class GestionFaseModel(Base):
    __tablename__ = 'gestiones_fases'
    __table_args__ = {'schema': 'modulo2'}

    id_gestion_fases: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_activo_biologico: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo2.activos_biologicos.id_activo_biologico'), nullable=False
    )
    id_ciclo_productiva: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo9.ciclos_productivos.id_ciclo_productivo'), nullable=False
    )
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_finalizacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    es_activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    id_usuario: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo1.usuarios.id_usuario'), nullable=False
    )
    motivo_cambio: Mapped[str | None] = mapped_column(Text, nullable=True)
