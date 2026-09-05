from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Optional


class ResultadoInferenciaPort(ABC):
    @abstractmethod
    def obtener_por_id(self, id_resultado: uuid.UUID) -> Optional[dict]:
        """Devuelve dict con fecha_inferencia e id_activo_biologico, o None si no existe."""
        ...
