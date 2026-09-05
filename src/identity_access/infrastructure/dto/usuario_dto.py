"""DTOs de entrada para registro de usuarios, login y reenvío de token.

Todos heredan de `BaseDTO` (Pydantic) y aplican validaciones de formato
antes de llegar al use case.
"""
import datetime
from typing import Literal, Optional

from pydantic import EmailStr, Field, ValidationInfo, field_validator

from src.identity_access.domain.value_objects.identificacion import (
    identificacion_valida,
    mensaje_identificacion_invalida,
)
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


class SsoLoginDTO(BaseDTO):
    """Token de handoff SSO recibido del frontend (Mecanismo A de AgroFusion)."""

    sso_token: str


class UsuarioCreateDTO(BaseDTO):
    """Datos completos para registrar un nuevo usuario en el sistema."""

    correo_electronico: EmailStr
    # La columna es nullable y la entidad los declara opcionales: el registro
    # no debe exigirlos solo porque el DTO no traía default.
    telefono: Optional[str] = None
    tipo_identificacion: Literal["CC", "CE", "Pasaporte"]
    numero_identificacion: str = Field(min_length=1, max_length=20)
    nombre: str
    apellidos: str
    fecha_nacimiento: datetime.date
    genero: EnumUsuarioGenero
    contrasena: str
    confirmar_contrasena: str
    direccion: Optional[str] = None
    captcha_token: str = Field(min_length=1, max_length=4096)

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
        # `contrasena` se declara antes, así que ya está en `info.data` salvo
        # que haya fallado su propia política — en ese caso ese error basta.
        contrasena = info.data.get("contrasena")
        if contrasena is not None and v != contrasena:
            raise ValueError(
                "Error de confirmación. Las contraseñas ingresadas no coinciden. "
                "Por favor, verifique e intente de nuevo."
            )
        return v

    @field_validator("numero_identificacion")
    @classmethod
    def validar_identificacion(cls, v: str, info: ValidationInfo) -> str:
        # Si `tipo_identificacion` no superó el `Literal`, `info.data` no lo
        # trae y se aplica la regla numérica, que es la más estricta.
        tipo = info.data.get("tipo_identificacion")
        if not identificacion_valida(tipo, v):
            raise ValueError(mensaje_identificacion_invalida(tipo))
        return v
