"""Modelo ORM del archivo histórico inmutable de eventos de auditoría."""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Enum, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base
from .enums_models import EnumEventoResultado


class EventosArchivados(Base):
    """Copia histórica de eventos que superaron la retención activa de 12 meses."""

    __tablename__ = "eventos_archivados"
    __table_args__ = (
        CheckConstraint(
            "fecha_archivado >= fecha_evento",
            name="chk_eventos_archivados_fecha",
        ),
        Index(
            "ix_eventos_archivados_fecha",
            text("fecha_evento DESC"),
            text("id_evento DESC"),
        ),
        Index(
            "ix_eventos_archivados_usuario_fecha",
            "id_usuario",
            text("fecha_evento DESC"),
        ),
        {
            "schema": "modulo1",
            "comment": (
                "Copia histórica inmutable de eventos de auditoría con antigüedad "
                "superior a la política mínima de retención de 12 meses."
            ),
        },
    )

    id_evento: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=False,
    )
    tipo_evento: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_evento: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    modulo: Mapped[str] = mapped_column(String(50), nullable=False)
    resultado: Mapped[EnumEventoResultado] = mapped_column(
        Enum(
            EnumEventoResultado,
            values_callable=lambda cls: [member.value for member in cls],
            name="enum_evento_resultado",
            schema="modulo1",
        ),
        nullable=False,
    )
    detalle: Mapped[dict] = mapped_column(JSONB, nullable=False)
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    categoria: Mapped[str] = mapped_column(String(30), nullable=False)
    estado: Mapped[str] = mapped_column(String(30), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    id_sesion: Mapped[Optional[int]] = mapped_column(Integer)
    hash_integridad: Mapped[Optional[str]] = mapped_column(Text)
    fecha_archivado: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
