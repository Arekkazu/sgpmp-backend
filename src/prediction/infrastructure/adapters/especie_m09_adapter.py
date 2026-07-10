from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.repositories.especie_port import EspeciePort


class EspecieM09Adapter(EspeciePort):
    def __init__(self, db: Session) -> None:
        self._db = db

    def especie_activa(self, especie_aplicable: str) -> bool:
        if especie_aplicable == "TODAS":
            return True
        try:
            id_especie = int(especie_aplicable)
        except (ValueError, TypeError):
            return False
        row = self._db.execute(
            text("SELECT 1 FROM modulo9.especies WHERE id_especie = :id AND es_activo = true"),
            {"id": id_especie},
        ).fetchone()
        return row is not None
