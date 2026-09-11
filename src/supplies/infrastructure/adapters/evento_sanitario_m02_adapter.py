"""Adaptador de consulta de eventos sanitarios (RF-41) contra ``modulo2``.

``eventos_sanitarios`` comparte PK con ``eventos_activos`` (``id_evento`` =
``eventos_activos.id_eventos``), que es donde vive ``id_activo_biologico``. Se
usa SQL directo porque no hay modelo ORM de eventos_sanitarios en este módulo.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.supplies.domain.repositories.evento_sanitario_consulta_port import EventoSanitarioConsultaPort


class EventoSanitarioM02Adapter(EventoSanitarioConsultaPort):
    """Consulta la pertenencia de un evento sanitario a un activo en ``modulo2``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_activo_de_evento(self, id_evento: int) -> Optional[int]:
        row = self.db.execute(
            text(
                "SELECT ea.id_activo_biologico "
                "FROM modulo2.eventos_sanitarios es "
                "JOIN modulo2.eventos_activos ea ON ea.id_eventos = es.id_evento "
                "WHERE es.id_evento = :id"
            ),
            {"id": id_evento},
        ).fetchone()
        return row.id_activo_biologico if row else None
