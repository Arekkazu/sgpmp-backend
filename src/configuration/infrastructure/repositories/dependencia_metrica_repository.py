"""Implementación SQLAlchemy del puerto :class:`DependenciaMetricaPort`.

Verifica si existen registros productivos (``modulo2.eventos_productivos``) que
usan la métrica. Esa tabla es inmutable (triggers bloquean UPDATE/DELETE) y no
tiene columna de estado: la existencia de una fila ya es evidencia de uso activo.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.domain.repositories.dependencia_metrica_port import DependenciaMetricaPort


class SqlAlchemyDependenciaMetricaRepository(DependenciaMetricaPort):

    def __init__(self, db: Session) -> None:
        self.db = db

    def tiene_dependencias_activas(self, id_metrica_produccion: int) -> bool:
        return bool(
            self.db.execute(
                text(
                    "SELECT EXISTS(SELECT 1 FROM modulo2.eventos_productivos "
                    "WHERE id_metrica_produccion = :id)"
                ),
                {"id": id_metrica_produccion},
            ).scalar()
        )
