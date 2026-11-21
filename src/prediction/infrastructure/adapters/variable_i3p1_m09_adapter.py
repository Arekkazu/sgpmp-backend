# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-31 | Arekkazu | USAB-M03-M04 M4-02 RF-64: solo las 11 variables del RF-64 |
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.repositories.variable_i3p1_port import CODIGOS_VARIABLES_PATOLOGIA, VariableI3P1Port


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

    def obtener_ids_para_patologia(self, ids: list[int]) -> list[int]:
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
