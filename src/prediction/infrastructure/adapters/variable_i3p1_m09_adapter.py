# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-31 | Arekkazu | USAB-M03-M04 M4-02 RF-64: solo las 11 variables del RF-64 |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Adaptador de las variables admitidas en las patologías."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.repositories.variable_i3p1_port import CODIGOS_VARIABLES_PATOLOGIA, VariableI3P1Port


class VariableI3P1M09Adapter(VariableI3P1Port):
    """Valida las variables de una patología contra el catálogo."""
    def __init__(self, db: Session) -> None:
        self._db = db

    def obtener_ids_activos(self, ids: list[int]) -> list[int]:
        """Devuelve los ids que existen y están activos en el catálogo I3P-1."""
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

    def obtener_ids_para_patologia(self, ids: list[int]) -> list[int]:
        """Los ids activos que además están entre las variables del RF-64.

        Por defecto no restringe (adaptadores de prueba); el adaptador de M09 filtra
        por ``CODIGOS_VARIABLES_PATOLOGIA``.
        """
        if not ids:
            return []
        rows = self._db.execute(
            text(
                "SELECT id_variable_ambiental FROM modulo9.variables_ambientales "
                "WHERE id_variable_ambiental = ANY(:ids) AND es_activo = true "
                "AND codigo_telemetria = ANY(:codigos)"
            ),
            {"ids": ids, "codigos": sorted(CODIGOS_VARIABLES_PATOLOGIA)},
        ).fetchall()
        return [row[0] for row in rows]
