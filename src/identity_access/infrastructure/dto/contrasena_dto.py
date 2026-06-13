"""DTOs de entrada para las operaciones de gestión de contraseña.

Incluye validación de política (mínimo 8 chars, mayúscula, número y especial)
y confirmación de coincidencia entre `nueva_contrasena` y su campo de confirmación.
"""
import re

from pydantic import EmailStr, field_validator, model_validator

from src.shared.base_dto import BaseDTO

_POLITICA = re.compile(r'^(?=.*[A-Z])(?=.*\d)(?=.*[@#$%^&+=!*])[A-Za-z\d@#$%^&+=!*]{8,}$')

_MENSAJE_POLITICA = (
    "La contraseña no cumple los requisitos. Debe tener al menos 8 caracteres, "
    "incluir una letra mayúscula, un número y un carácter especial (@, #, $, etc.)."
)


class CambiarContrasenaDTO(BaseDTO):
    """Datos para cambiar la contraseña de un usuario autenticado."""

    contrasena_actual: str
    nueva_contrasena: str
    confirmar_nueva_contrasena: str

    @field_validator("nueva_contrasena")
    @classmethod
    def validar_politica(cls, v: str) -> str:
        if not _POLITICA.match(v):
            raise ValueError(_MENSAJE_POLITICA)
        return v

    @model_validator(mode="after")
    def validar_confirmacion(self) -> "CambiarContrasenaDTO":
        if self.nueva_contrasena != self.confirmar_nueva_contrasena:
            raise ValueError(
                "Error de confirmación. Las contraseñas ingresadas no coinciden. "
                "Por favor, verifique e intente de nuevo."
            )
        return self


class SolicitarRecuperacionDTO(BaseDTO):
    """Correo electrónico para iniciar el flujo de recuperación de contraseña."""

    correo_electronico: EmailStr


class RestablecerContrasenaDTO(BaseDTO):
    """Token de recuperación y nueva contraseña para el restablecimiento."""

    token: str
    nueva_contrasena: str
    confirmar_contrasena: str

    @field_validator("nueva_contrasena")
    @classmethod
    def validar_politica(cls, v: str) -> str:
        if not _POLITICA.match(v):
            raise ValueError(_MENSAJE_POLITICA)
        return v

    @model_validator(mode="after")
    def validar_confirmacion(self) -> "RestablecerContrasenaDTO":
        if self.nueva_contrasena != self.confirmar_contrasena:
            raise ValueError(
                "Error de validación. Las contraseñas ingresadas no coinciden. "
                "Por favor, escríbalas nuevamente."
            )
        return self
