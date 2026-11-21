# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #512 RF-16/RF-37: ciclos productivos de la especie con sus fases en orden |
"""Eliminar un ciclo productivo que ningún activo ha usado (RF-16)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.application.use_cases.ciclos_productivos.editar_ciclo_productivo_use_case import obtener_o_404
from src.configuration.domain.repositories.ciclo_productivo_repository import CicloProductivoRepository
from src.shared.errors import ConflictError


class EliminarCicloProductivoUseCase:
    def __init__(self, db: Session, ciclos: CicloProductivoRepository) -> None:
        self.db, self.ciclos = db, ciclos

    def execute(self, id_ciclo_productivo: int) -> None:
        ciclo = obtener_o_404(self.ciclos, id_ciclo_productivo)
        if ciclo.en_uso:
            raise ConflictError(code="CICLO_PRODUCTIVO_EN_USO", message=(
                f"No se puede eliminar el ciclo «{ciclo.nombre}»: hay animales o lotes que ya pasaron por él."))
        try:
            self.ciclos.eliminar(id_ciclo_productivo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
