import datetime
from pydantic import BaseModel, EmailStr
from src.identity_access.infrastructure.models.enums_models import EnumUsuarioGenero


class UsuarioResponse(BaseModel):
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


    model_config = {"from_attributes": True}


class UsuarioCreate(BaseModel):
    tipo_identificacion: str
    numero_identificacion: str
    nombre: str
    apellidos: str
    fecha_nacimiento: datetime.date
    genero: EnumUsuarioGenero
    correo_electronico: EmailStr
    contrasena: str
    id_rol: int
    telefono: str | None = None
    direccion: str | None = None
