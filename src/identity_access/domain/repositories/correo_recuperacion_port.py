"""Puerto para programar correos del flujo de recuperación de contraseña."""
from __future__ import annotations

from abc import ABC, abstractmethod


class CorreoRecuperacionPort(ABC):
    """Contrato de salida para despachar correos fuera del request HTTP."""

    @abstractmethod
    def programar_recuperacion(
        self,
        correo: str,
        nombre: str,
        token: str,
        id_usuario: int,
    ) -> None:
        """Programa el correo que permite restablecer la contraseña."""
        raise NotImplementedError

    @abstractmethod
    def programar_activacion(
        self,
        correo: str,
        nombre: str,
        token: str,
        id_usuario: int,
    ) -> None:
        """Programa la activación cuando la cuenta aún está pendiente."""
        raise NotImplementedError
