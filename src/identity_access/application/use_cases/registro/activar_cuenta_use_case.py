"""Caso de uso: activación de cuenta mediante token de correo electrónico.

El token fue generado al crear la cuenta o al reenviar el correo de activación.
La lógica de validación y actualización de estado reside en el port/repository.
"""
from src.identity_access.application.ports.cuentas_ports import CuentasPort


class ActivarCuentaUseCase:
    """Orquesta la activación de una cuenta a partir de su token de activación."""

    def __init__(self, cuentas_port: CuentasPort):
        """Inicializa el use case.

        Args:
            cuentas_port: Activación del estado de la cuenta por token.
        """
        self.cuentas_port = cuentas_port

    def execute(self, token: str) -> None:
        """Activa la cuenta asociada al token recibido.

        Args:
            token: Token de activación enviado al correo del usuario.

        Raises:
            AuthenticationError: Si el token no existe o ya fue usado. HTTP 401.
            GoneError: Si el token expiró. HTTP 410.
        """
        self.cuentas_port.activar_cuenta(token)
