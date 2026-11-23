# | Fecha      | Nombre   | Que se hizo                                       |
# |------------|----------|---------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-107: borrar un mensaje del catálogo        |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso: quitar una entrada del catálogo; el front vuelve al texto que trae la respuesta del backend."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.repositories.catalogo_mensajes_error_repository import CatalogoMensajesErrorRepository
from src.shared.errors import NotFoundError


class EliminarMensajeErrorUseCase:
    """Elimina un mensaje del catálogo de errores."""

    def __init__(self, db: Session, repo: CatalogoMensajesErrorRepository) -> None:
        self.db = db
        self.repo = repo

    def execute(self, clave: str, idioma: str) -> None:
        """Elimina el mensaje de la clave e idioma.

        Raises:
            NotFoundError: Si el mensaje no existe.
        """
        try:
            if not self.repo.eliminar(clave, idioma):
                raise NotFoundError(code="MENSAJE_INEXISTENTE", field="clave",
                                    message="Ese mensaje no está en el catálogo.")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
