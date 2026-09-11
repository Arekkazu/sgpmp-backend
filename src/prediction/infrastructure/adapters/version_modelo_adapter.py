from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.repositories.version_modelo_port import VersionModeloPort


class VersionModeloAdapter(VersionModeloPort):
    def __init__(self, db: Session) -> None:
        self._db = db

    def obtener_estado(self, id_version: int) -> Optional[str]:
        row = self._db.execute(
            text(
                "SELECT estado_version::text FROM modulo4.versiones_modelos "
                "WHERE id_version_modelo = :id"
            ),
            {"id": id_version},
        ).fetchone()
        return row[0] if row else None
