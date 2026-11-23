# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Adaptador de consulta de especies."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.repositories.especie_port import EspeciePort


class EspecieM09Adapter(EspeciePort):
    """Verifica si una especie está activa."""
    def __init__(self, db: Session) -> None:
        self._db = db

    def especie_activa(self, especie_aplicable: str) -> bool:
        """Retorna True si especie_aplicable es 'TODAS' o un id_especie activo en M09."""
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
