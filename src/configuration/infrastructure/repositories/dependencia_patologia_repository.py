"""Implementación SQLAlchemy del puerto :class:`DependenciaPatologiaPort`.

Consulta la vista ``vw_rf16_dependencias_patologias``. Solo cuenta como
dependencia activa lo que representa uso real del catálogo M04 (predicciones
de IA, alertas patológicas generadas); ``especies_asociadas`` (vínculo M09) y
``signos_asociados`` (relación de inferencia patología↔signo clínico) son
configuración/catálogo, no uso activo, y no bloquean la desactivación.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.domain.repositories.dependencia_patologia_port import DependenciaPatologiaPort


class SqlAlchemyDependenciaPatologiaRepository(DependenciaPatologiaPort):

    def __init__(self, db: Session) -> None:
        self.db = db

    def tiene_dependencias_activas(self, id_patologia: int) -> bool:
        row = self.db.execute(
            text(
                "SELECT predicciones_asociadas, alertas_asociadas "
                "FROM modulo9.vw_rf16_dependencias_patologias WHERE id_patologias = :id"
            ),
            {"id": id_patologia},
        ).fetchone()
        if row is None:
            return False
        return (row.predicciones_asociadas + row.alertas_asociadas) > 0
