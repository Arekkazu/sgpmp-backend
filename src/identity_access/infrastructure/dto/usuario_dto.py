"""DTOs de entrada para registro de usuarios, login y reenvío de token.

Todos heredan de `BaseDTO` (Pydantic) y aplican validaciones de formato
antes de llegar al use case.
"""
import datetime

from pydantic import EmailStr, Field, ValidationInfo, field_validator

from src.identity_access.infrastructure.models.enums_models import EnumUsuarioGenero
from src.shared.base_dto import BaseDTO
from src.shared.regex import NUMERO_IDENTIFICACION, PASSWORD


class ReenviarTokenDTO(BaseDTO):
    """Datos para solicitar el reenvío del correo de activación."""

    correo_electronico: EmailStr


class LoginDTO(BaseDTO):
    """Credenciales de inicio de sesión."""

    correo_electronico: EmailStr
    contrasena: str


class SsoLoginDTO(BaseDTO):
    """Token de handoff SSO recibido del frontend (Mecanismo A de AgroFusion)."""

    sso_token: str


class UsuarioCreateDTO(BaseDTO):
    """Datos completos para registrar un nuevo usuario en el sistema."""

    correo_electronico: EmailStr
    telefono: str
    tipo_identificacion: str
    numero_identificacion: str = Field(min_length=1, max_length=20)
    nombre: str
    apellidos: str
    fecha_nacimiento: datetime.date
    genero: EnumUsuarioGenero
    contrasena: str
    confirmar_contrasena: str
    direccion: str

    @field_validator("numero_identificacion")
    @classmethod
    def validar_numero_identificacion(cls, v: str) -> str:
        if not NUMERO_IDENTIFICACION.fullmatch(v):
            raise ValueError(
                "El número de identificación debe contener únicamente "
                "dígitos del 0 al 9"
            )
        return v

    @field_validator("contrasena")
    @classmethod
    def validar_contrasena(cls, v: str) -> str:
        if not PASSWORD.match(v):
            raise ValueError(
                "La contraseña debe tener mínimo 8 caracteres, "
                "una mayúscula, un número y un carácter especial"
            )
        return v

    @field_validator("confirmar_contrasena")
    @classmethod
    def validar_confirmacion_contrasena(
        cls,
        v: str,
        info: ValidationInfo,
    ) -> str:
        contrasena = info.data.get("contrasena")
        if contrasena is not None and v != contrasena:
            raise ValueError("Las contraseñas ingresadas no coinciden")
        return v
