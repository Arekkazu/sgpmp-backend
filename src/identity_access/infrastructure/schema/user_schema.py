import datetime
from pydantic import BaseModel, EmailStr
from src.identity_access.infrastructure.models.enums_models import EnumUsuarioGenero
from src.shared.base_dto import BaseDTO


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


class LoginResponse(BaseDTO):
    token: str
    tipo: str = "Bearer"
    expira_en: int
    message: str


class UsuarioCreate(BaseModel):
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
