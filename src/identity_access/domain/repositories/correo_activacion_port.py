"""Puerto para programar el correo de activación del registro."""
from __future__ import annotations

from abc import ABC, abstractmethod


class CorreoActivacionPort(ABC):
    """Contrato de salida para notificar la activación fuera del request."""

    @abstractmethod
    def programar_envio(
        self,
        correo: str,
        nombre: str,
        token: str,
        id_usuario: int,
    ) -> None:
        """Programa el correo sin esperar su despacho SMTP."""
        raise NotImplementedError
