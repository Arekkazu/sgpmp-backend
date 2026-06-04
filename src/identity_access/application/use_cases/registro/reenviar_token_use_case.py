import secrets

from src.identity_access.application.ports.cuentas_ports import CuentasPort
from src.identity_access.infrastructure.dto.usuario_dto import ReenviarTokenDTO
from src.identity_access.infrastructure.email_templates import activation_email
from src.shared.email import send_email


class ReenviarTokenUseCase:

    def __init__(self, cuentas_port: CuentasPort):
        self.cuentas_port = cuentas_port

    def execute(self, dto: ReenviarTokenDTO) -> None:
        token = secrets.token_urlsafe(32)
        nombre = self.cuentas_port.reenviar_token(dto.correo_electronico, token)
        send_email(
            to=dto.correo_electronico,
            subject="Nuevo token de activación - SGPMP",
            html_body=activation_email(nombre, token),
        )
