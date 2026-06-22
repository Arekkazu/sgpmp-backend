"""Caso de uso: Obtener identidad visual activa de una finca (GET RF-26)."""
from __future__ import annotations

from typing import Optional

from src.configuration.domain.entities.identidad_visual import IdentidadVisual
from src.configuration.domain.repositories.identidad_visual_repository import IdentidadVisualRepository


class ObtenerIdentidadVisualUseCase:

    def __init__(self, identidad_repo: IdentidadVisualRepository) -> None:
        self.identidad_repo = identidad_repo

    def execute(self, id_finca: int) -> Optional[IdentidadVisual]:
        return self.identidad_repo.obtener_por_finca(id_finca)
