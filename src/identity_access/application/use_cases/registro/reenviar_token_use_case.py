"""Caso de uso: reenvío del token de activación de cuenta.

Genera un nuevo token, lo guarda en la cuenta PENDIENTE y envía el correo.
Si el correo no corresponde a una cuenta pendiente, el port eleva el error.
"""
import secrets

from src.identity_access.application.ports.cuentas_ports import CuentasPort
from src.identity_access.infrastructure.dto.usuario_dto import ReenviarTokenDTO
from src.identity_access.infrastructure.email_templates import activation_email
from src.shared.email import send_email


class ReenviarTokenUseCase:
    """Orquesta el reenvío del correo de activación con un token nuevo."""

    def __init__(self, cuentas_port: CuentasPort):
        """Inicializa el use case.

        Args:
            cuentas_port: Actualización del token y consulta del nombre del usuario.
        """
        self.cuentas_port = cuentas_port

    def execute(self, dto: ReenviarTokenDTO) -> None:
        """Genera un nuevo token de activación y lo envía por correo.

        Args:
            dto: Correo electrónico del usuario que solicita el reenvío.

        Raises:
            NotFoundError: Si no existe una cuenta pendiente con ese correo. HTTP 404.
        """
        token = secrets.token_urlsafe(32)
        nombre = self.cuentas_port.reenviar_token(dto.correo_electronico, token)
        send_email(
            to=dto.correo_electronico,
            subject="Nuevo token de activación - SGPMP",
            html_body=activation_email(nombre, token),
        )
