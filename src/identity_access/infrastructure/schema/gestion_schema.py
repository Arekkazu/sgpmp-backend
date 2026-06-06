import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, computed_field

from src.identity_access.infrastructure.models.enums_models import EnumUsuarioGenero


class UsuarioEnmascaradoResponse(BaseModel):
    id_usuario: int
    nombre: str
    apellidos: str
    correo_electronico: EmailStr
    tipo_identificacion: str
    numero_identificacion: str
    genero: EnumUsuarioGenero
    id_rol: int
    fecha_registro: datetime.datetime
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    version: int
    id_estado_cuenta: Optional[int] = None

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def numero_identificacion_enmascarado(self) -> str:
        num = self.numero_identificacion
        if len(num) <= 4:
            return "*" * len(num)
        return num[:4] + "*" * (len(num) - 4)


class UsuariosPaginadosResponse(BaseModel):
    total: int
    pagina: int
    tamano: int
    items: list[UsuarioEnmascaradoResponse]


class UsuarioListadoResponse(BaseModel):
    nombre_usuario: str
    correo_electronico: str
    nombre_rol: str
    estado_cuenta: str


class UsuarioListadoPaginadoResponse(BaseModel):
    total: int
    pagina: int
    tamano: int
    items: list[UsuarioListadoResponse]


class UsuarioDetalleResponse(BaseModel):
    nombre: str
    apellidos: str
    correo_electronico: str
    tipo_identificacion: str
    numero_identificacion: str
    fecha_nacimiento: datetime.date
    fecha_registro: datetime.datetime
    nombre_rol: str
    estado_cuenta: str


class AuditoriaItemResponse(BaseModel):
    id_evento: int
    tipo_evento: int
    fecha_evento: datetime.datetime
    modulo: str
    resultado: str
    detalle: Any
    id_usuario: int
    categoria: str
    estado: str
    id_sesion: Optional[int] = None
    integridad_ok: bool

    model_config = {"from_attributes": True}


class AuditoriaPaginadaResponse(BaseModel):
    total: int
    pagina: int
    tamano: int
    items: list[AuditoriaItemResponse]
