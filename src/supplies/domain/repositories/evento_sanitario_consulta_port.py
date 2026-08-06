"""Puerto de consulta de eventos sanitarios (RF-41).

RF-76 permite vincular una aplicación de medicamento a un evento sanitario
previo. El sistema debe validar que el evento exista y pertenezca al mismo
activo biológico. La implementación consulta ``modulo2.eventos_sanitarios``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class EventoSanitarioConsultaPort(ABC):
    """Contrato para validar la pertenencia de un evento sanitario a un activo."""

    @abstractmethod
    def obtener_activo_de_evento(self, id_evento: int) -> Optional[int]:
        """Devuelve el ``id_activo_biologico`` dueño del evento, o ``None`` si no existe."""
        raise NotImplementedError
