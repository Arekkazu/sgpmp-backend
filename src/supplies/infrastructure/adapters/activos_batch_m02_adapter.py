"""Adaptador que lista los activos ACTIVO para el batch ICA (RF-74) contra ``modulo2``."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.supplies.domain.repositories.activo_consulta_port import ESTADO_ACTIVO
from src.supplies.domain.repositories.activos_batch_port import ActivoBatchRef, ActivosBatchPort


class ActivosBatchM02Adapter(ActivosBatchPort):
    """Selecciona activos en estado ACTIVO de ``modulo2.activos_biologicos``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def listar_activos_para_batch(self) -> list[ActivoBatchRef]:
        filas = self.db.execute(
            text(
                "SELECT id_activo_biologico, fecha_inicio_ciclo "
                "FROM modulo2.activos_biologicos "
                "WHERE id_estado = :estado "
                "ORDER BY fecha_inicio_ciclo ASC NULLS LAST, id_activo_biologico ASC"
            ),
            {"estado": ESTADO_ACTIVO},
        ).fetchall()
        return [
            ActivoBatchRef(
                id_activo_biologico=f.id_activo_biologico,
                fecha_inicio_ciclo=f.fecha_inicio_ciclo,
            )
            for f in filas
        ]
