"""Schemas de respuesta para endpoints de usuarios y autenticación.

`UsuarioResponse` devuelve la entidad completa tras crear o editar.
`LoginResponse` contiene el JWT y los metadatos de la sesión.
`UsuarioCreate` es un schema auxiliar de documentación Swagger (no se usa como DTO de entrada).
"""
import datetime
from pydantic import BaseModel, EmailStr
from src.identity_access.infrastructure.models.enums_models import EnumUsuarioGenero
from src.shared.base_dto import BaseDTO


class UsuarioResponse(BaseModel):
    """Datos completos del usuario retornados tras registro o edición de perfil."""

    id_usuario: int
    nombre: str
    apellidos: str
    correo_electronico: EmailStr
    tipo_identificacion: str
    numero_identificacion: str
    genero: EnumUsuarioGenero
    id_rol: int
    fecha_registro: datetime.datetime
    telefono: str | None
    direccion: str | None
    version: int

    model_config = {"from_attributes": True}


class LoginResponse(BaseDTO):
    """Token JWT y metadatos de la sesión iniciada."""

    token: str
    tipo: str = "Bearer"
    expira_en: int
    message: str
    perfil_incompleto: bool = False


class UsuarioCreate(BaseModel):
    """Schema auxiliar de documentación — representa el body de creación de usuario."""

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
