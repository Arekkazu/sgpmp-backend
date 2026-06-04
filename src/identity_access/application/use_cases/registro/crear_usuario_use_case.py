import secrets
from datetime import date

from sqlalchemy.orm import Session

from src.identity_access.application.ports.cuentas_ports import CuentasPort
from src.identity_access.application.ports.usuarios_ports import UsuariosPort
from src.identity_access.infrastructure.dto.usuario_dto import UsuarioCreateDTO
from src.identity_access.infrastructure.email_templates import activation_email
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.shared.email import send_email
from src.shared.errors import AuthorizationError


class CrearUsuarioUseCase:

    def __init__(self, usuarios_port: UsuariosPort, cuentas_port: CuentasPort, db: Session):
        self.usuarios_port = usuarios_port
        self.cuentas_port = cuentas_port
        self.db = db

    def _verificar_edad_minima(self, fecha_nacimiento: date) -> None:
        hoy = date.today()
        edad = hoy.year - fecha_nacimiento.year - (
            (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day)
        )
        if edad < 18:
            raise AuthorizationError(
                code="EDAD_MINIMA_REQUERIDA",
                message="Registro denegado: debe ser mayor de 18 años para registrarse como responsable de una unidad productiva en el sistema.",
                field="fecha_nacimiento",
            )

    def execute(self, dto: UsuarioCreateDTO) -> Usuarios:
        self._verificar_edad_minima(dto.fecha_nacimiento)
        try:
            usuario = self.usuarios_port.create_usuario(dto)
            token = secrets.token_urlsafe(32)
            self.cuentas_port.create_cuenta(usuario.id_usuario, token)
            self.db.commit()
            self.db.refresh(usuario)
        except Exception:
            self.db.rollback()
            raise

        send_email(
            to=usuario.correo_electronico,
            subject="Activa tu cuenta en SGPMP",
            html_body=activation_email(usuario.nombre, token),
        )

        return usuario
