# | Fecha      | Nombre   | Que se hizo                                       |
# |------------|----------|---------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-107: listar el catálogo de mensajes de error |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso: el catálogo de mensajes de error, para que el front lo guarde y traduzca los errores (RF-107)."""
from __future__ import annotations

from typing import Optional

from src.configuration.domain.entities.mensaje_error import MensajeError
from src.configuration.domain.repositories.catalogo_mensajes_error_repository import CatalogoMensajesErrorRepository


class ListarMensajesErrorUseCase:
    """Lista el catálogo de mensajes de error."""

    def __init__(self, repo: CatalogoMensajesErrorRepository) -> None:
        self.repo = repo

    def execute(self, idioma: Optional[str] = None) -> list[MensajeError]:
        """Lista los mensajes, opcionalmente de un idioma."""
        return self.repo.listar(idioma)
