from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.repositories.variable_i3p1_port import VariableI3P1Port


class VariableI3P1M09Adapter(VariableI3P1Port):
    def __init__(self, db: Session) -> None:
        self._db = db

    def obtener_ids_activos(self, ids: list[int]) -> list[int]:
        if not ids:
            return []
        rows = self._db.execute(
            text(
                "SELECT id_variable_ambiental FROM modulo9.variables_ambientales "
                "WHERE id_variable_ambiental = ANY(:ids) AND es_activo = true"
            ),
            {"ids": ids},
        ).fetchall()
        return [row[0] for row in rows]
