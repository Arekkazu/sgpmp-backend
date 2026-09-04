"""Puerto de lectura de los datos que alimentan cada widget del dashboard (RF-28)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class WidgetDatosRepository(ABC):

    @abstractmethod
    def obtener(self, fuente_datos: str) -> list[dict[str, Any]]:
        """Filas de la fuente indicada, o lista vacía si la fuente no está soportada."""
        raise NotImplementedError
