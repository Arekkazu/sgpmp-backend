"""Implementación SQLAlchemy del puerto :class:`DependenciaCicloPort`.

Consulta la vista ``vw_rf16_dependencias_ciclos`` que cuenta referencias
en ``modulo9.ciclos_productivos_biologicos``.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.domain.repositories.dependencia_ciclo_port import DependenciaCicloPort


class SqlAlchemyDependenciaCicloRepository(DependenciaCicloPort):

    def __init__(self, db: Session) -> None:
        self.db = db

    def tiene_dependencias_activas(self, id_ciclo_biologico: int) -> bool:
        row = self.db.execute(
            text(
                "SELECT referencias_productivas FROM modulo9.vw_rf16_dependencias_ciclos "
                "WHERE id_ciclo_biologico = :id"
            ),
            {"id": id_ciclo_biologico},
        ).fetchone()
        if row is None:
            return False
        return row.referencias_productivas > 0
