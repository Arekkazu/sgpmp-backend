"""Modelo ORM de la línea base de integridad de auditoría (RF-10).

Registra los eventos que ya no eran verificables al adoptar la verificación
estricta del hash: los escritos por un esquema anterior y los que nunca tuvieron
hash. Sin esta línea base, el 500 exigido por el flujo alterno de hash mismatch
sería permanente sobre registros inmutables e irreparables.
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class IntegridadBaseline(Base):
    """Evento cuya no verificabilidad es anterior a la política, no manipulación."""

    __tablename__ = "integridad_baseline"
    __table_args__ = {
        "schema": "modulo1",
        "comment": (
            "Eventos ya no verificables antes de adoptar la verificación estricta "
            "de RF-10. Permite distinguir el legado irreparable de una "
            "manipulación posterior."
        ),
    }

    id_evento: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=False,
    )
    hash_calculado: Mapped[Optional[str]] = mapped_column(Text)
    motivo: Mapped[str] = mapped_column(String(40), nullable=False)
    fecha_registro: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
