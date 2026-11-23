# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M04-138-G001 RF-64: búsqueda por nombre |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso de consulta del catálogo de patologías."""
from __future__ import annotations

from typing import Optional

from src.prediction.domain.entities.patologia_m04 import PatologiaM04
from src.prediction.domain.repositories.patologia_m04_repository import PatologiaM04Repository


class ConsultarPatologiasUseCase:
    """Consulta el catálogo de patologías."""
    def __init__(self, *, repo: PatologiaM04Repository) -> None:
        self._repo = repo

    def execute(
        self,
        especie_aplicable: Optional[str] = None,
        solo_activas: Optional[bool] = None,
        solo_base: Optional[bool] = None,
        nombre: Optional[str] = None,
    ) -> list[PatologiaM04]:
        """Lista las patologías con los filtros dados."""
        return self._repo.listar(
            especie_aplicable=especie_aplicable,
            solo_activas=solo_activas,
            solo_base=solo_base,
            nombre=nombre,
        )
