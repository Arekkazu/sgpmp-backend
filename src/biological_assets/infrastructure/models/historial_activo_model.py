from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Identity, Integer, PrimaryKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class HistorialActivoModel(Base):
    __tablename__ = 'historial_activos'
    __table_args__ = (
        PrimaryKeyConstraint('id_historial_activo', name='historial_activos_pkey'),
        UniqueConstraint('id_activo_biologico', 'version', name='uq_historial_activo_version'),
        CheckConstraint('version > 0', name='ck_historial_activo_version_positiva'),
        {'schema': 'modulo2'},
    )

    id_historial_activo: Mapped[int] = mapped_column(
        Integer,
        Identity(start=1, increment=1),
        primary_key=True,
    )
    id_activo_biologico: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo2.activos_biologicos.id_activo_biologico', name='historial_activos_id_activo_biologico_fkey'),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_evento: Mapped[str] = mapped_column(String(30), nullable=False)
    json_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fecha_evento: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    id_usuario: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo1.usuarios.id_usuario', name='historial_activos_id_usuario_fkey'),
        nullable=False,
    )
