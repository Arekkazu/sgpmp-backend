"""Puerto de validación CAPTCHA para el registro de usuarios."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class CaptchaVerifierPort(ABC):
    """Contrato que aísla al caso de uso del proveedor CAPTCHA concreto."""

    @abstractmethod
    def verificar(self, token: str, ip: Optional[str] = None) -> bool:
        """Valida un token CAPTCHA emitido para el formulario de registro.

        Args:
            token: Respuesta generada por el widget CAPTCHA del frontend.
            ip: Dirección IP del cliente, cuando está disponible.

        Returns:
            ``True`` únicamente si el proveedor confirma el desafío.

        Raises:
            ServiceUnavailableError: Si el proveedor no está configurado o no
                puede responder de forma confiable. El flujo debe fallar cerrado.
        """
        raise NotImplementedError
