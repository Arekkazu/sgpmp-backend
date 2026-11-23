# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto del historial de versiones del catálogo de patologías."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class HistorialCatalogoRepository(ABC):
    """Puerto del historial del catálogo de patologías."""
    @abstractmethod
    def registrar(
        self,
        *,
        id_patologia: int,
        version_catalogo: int,
        accion: str,
        datos_nuevos: dict,
        id_usuario: int,
        datos_anteriores: Optional[dict] = None,
    ) -> None:
        """Registra una versión del catálogo."""
        ...
