from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.telemetry.domain.repositories.especie_activo_port import EspecieActivoPort


class EspecieActivoM02Adapter(EspecieActivoPort):
    """Lee `modulo2.activos_biologicos.id_especie` para un activo ya vinculado a una lectura.

    No resuelve *qué* activo corresponde a un sensor/dispositivo (eso sigue siendo
    ActivoBiologicoDependencyPort, hoy stub) — solo consulta la especie de un
    `id_activo_biologico` que la vinculación (automática o manual) ya identificó.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_id_especie(self, id_activo_biologico: int) -> Optional[int]:
        row = self.db.execute(
            text('SELECT id_especie FROM modulo2.activos_biologicos WHERE id_activo_biologico = :id'),
            {'id': id_activo_biologico},
        ).fetchone()
        return row[0] if row else None
