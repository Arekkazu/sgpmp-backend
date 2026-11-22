# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | RF-19 v1.1: asignar o quitar el titular tributario de una finca |
"""Caso de uso RF-19 v1.1: los cuatro campos del titular se informan juntos o ninguno, y todas las
fincas con el mismo número deben tener la misma razón social y el mismo DV (forman un titular)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.repositories.titular_finca_repository import TitularFincaRepository
from src.configuration.domain.value_objects.titular_tributario import TitularTributario
from src.shared.errors import ConflictError, NotFoundError


class AsignarTitularFincaUseCase:
    def __init__(self, db: Session, repo: TitularFincaRepository) -> None:
        self.db = db
        self.repo = repo

    def execute(self, id_finca: int, titular: Optional[TitularTributario]) -> dict:
        if self.repo.obtener(id_finca) is None:
            raise NotFoundError(code="FINCA_NO_ENCONTRADA", message="La finca no existe.")
        if titular is not None:
            otra = self.repo.otro_con_mismo_numero(titular.numero_id_tributaria, id_finca)
            if otra and ((otra["razon_social"] or "").strip().lower() != titular.razon_social.strip().lower()
                         or (otra["dv"] or None) != (titular.dv or None)):
                raise ConflictError(code="TITULAR_INCONSISTENTE", message=(
                    f"La finca {otra['nombre']} tiene el mismo número con otra razón social o dígito de verificación. "
                    "Las fincas de un titular deben coincidir."))
        try:
            self.repo.guardar(id_finca, titular)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.repo.obtener(id_finca)
