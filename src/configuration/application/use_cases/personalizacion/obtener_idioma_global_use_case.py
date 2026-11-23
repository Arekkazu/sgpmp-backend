# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso: Obtener el idioma global del sistema (GET RF-29 — Admin)."""
from __future__ import annotations

from typing import Optional

from src.configuration.domain.entities.preferencia_idioma import PreferenciaIdioma
from src.configuration.domain.repositories.preferencia_idioma_repository import PreferenciaIdiomaRepository


class ObtenerIdiomaGlobalUseCase:
    """Idioma por defecto del sistema."""

    def __init__(self, idioma_repo: PreferenciaIdiomaRepository) -> None:
        self.idioma_repo = idioma_repo

    def execute(self) -> Optional[PreferenciaIdioma]:
        """Devuelve el idioma global, o ``None``."""
        return self.idioma_repo.obtener_global()
