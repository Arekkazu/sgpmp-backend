"""DTOs de entrada para registro de usuarios, login y reenvío de token.

Todos heredan de `BaseDTO` (Pydantic) y aplican validaciones de formato
antes de llegar al use case.
"""
import datetime
from pydantic import EmailStr, field_validator
from src.identity_access.infrastructure.models.enums_models import EnumUsuarioGenero
from src.shared.base_dto import BaseDTO
from src.shared.regex import PASSWORD


class ReenviarTokenDTO(BaseDTO):
    """Datos para solicitar el reenvío del correo de activación."""

    correo_electronico: EmailStr


class LoginDTO(BaseDTO):
    """Credenciales de inicio de sesión."""

    correo_electronico: EmailStr
    contrasena: str


class UsuarioCreateDTO(BaseDTO):
    """Datos completos para registrar un nuevo usuario en el sistema."""

    correo_electronico: EmailStr
    telefono: str
    tipo_identificacion: str
    numero_identificacion: str
    nombre: str
    apellidos: str
    fecha_nacimiento: datetime.date
    genero: EnumUsuarioGenero
    contrasena: str
    direccion: str

    @field_validator("contrasena")
    @classmethod
    def validar_contrasena(cls, v: str) -> str:
        if not PASSWORD.match(v):
            raise ValueError(
                "La contraseña debe tener mínimo 8 caracteres, "
                "una mayúscula, un número y un carácter especial"
            )
        return v
