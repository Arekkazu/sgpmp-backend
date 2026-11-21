# | Fecha      | Nombre   | Que se hizo                                       |
# |------------|----------|---------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-107: puerto del catálogo de mensajes de error |
"""Puerto del catálogo de mensajes de error (RF-107 RNF-03)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.mensaje_error import MensajeError


class CatalogoMensajesErrorRepository(ABC):

    @abstractmethod
    def listar(self, idioma: Optional[str]) -> list[MensajeError]: ...

    @abstractmethod
    def guardar(self, mensaje: MensajeError) -> MensajeError:
        """Crea o reemplaza la entrada de ``(clave, idioma)``."""

    @abstractmethod
    def eliminar(self, clave: str, idioma: str) -> bool: ...
