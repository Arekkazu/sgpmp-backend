from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class HistorialCatalogoRepository(ABC):
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
    ) -> None: ...
