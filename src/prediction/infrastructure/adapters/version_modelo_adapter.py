# | Fecha      | Nombre       | Que se hizo                                           |
# |------------|--------------|-------------------------------------------------------|
# | 2026-10-31 | Arekkazu     | RFC-010 RF-69: versión por animal, estado SOMBRA y fuente de datos |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Adaptador de consulta del estado de versiones de modelo."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.repositories.version_modelo_port import VersionModeloPort


class VersionModeloAdapter(VersionModeloPort):
    """Consulta el estado de una versión de modelo."""
    def __init__(self, db: Session) -> None:
        self._db = db

    def obtener_estado(self, id_version: int) -> Optional[str]:
        """Devuelve el estado_version del modelo o None si no existe."""
        row = self._db.execute(
            text(
                "SELECT estado_version::text FROM modulo4.versiones_modelos "
                "WHERE id_version_modelo = :id"
            ),
            {"id": id_version},
        ).fetchone()
        return row[0] if row else None

    def obtener_llave(
        self, id_version: int
    ) -> Optional[tuple[str, Optional[str], Optional[str], Optional[int]]]:
        """(estado_version, tipo_modelo, componente, id_activo_biologico) o None si no existe
        (RF-65 4.e, RFC-009, RFC-010).
        """
        row = self._db.execute(
            text(
                "SELECT estado_version::text, tipo_modelo::text, componente, id_activo_biologico "
                "FROM modulo4.versiones_modelos WHERE id_version_modelo = :id"
            ),
            {"id": id_version},
        ).fetchone()
        return (row[0], row[1], row[2], row[3]) if row else None
