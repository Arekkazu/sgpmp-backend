"""Puerto de persistencia de intentos anónimos por IP (capa de dominio).

Rate limiting / bloqueo por IP para flujos donde el actor no está
identificado (correo inexistente, token inválido) y por lo tanto no existe
un ``id_usuario`` al que atar el conteo en ``modulo1.eventos`` (columna
``NOT NULL``, con FK a ``usuarios``). Tabla de solo inserción, sin relación
con la auditoría de seguridad de eventos reales de un usuario.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class IntentoAnonimoRepository(ABC):
    """Contrato de persistencia para el conteo de intentos anónimos por IP."""

    @abstractmethod
    def registrar(self, tipo: str, ip: str) -> None:
        """Inserta un intento con la fecha actual del servidor."""
        raise NotImplementedError

    @abstractmethod
    def contar_por_ip(self, tipo: str, ip: str, desde: datetime) -> int:
        """Cuenta los intentos de ``tipo`` registrados por ``ip`` desde ``desde``."""
        raise NotImplementedError

    @abstractmethod
    def obtener_fecha_mas_antigua_por_ip(
        self, tipo: str, ip: str, desde: datetime
    ) -> Optional[datetime]:
        """Fecha del intento más antiguo dentro de la ventana, o ``None``.

        Es el intento que, al salir de la ventana, libera cupo — se usa para
        informar la hora real de desbloqueo en vez de una fija.
        """
        raise NotImplementedError
