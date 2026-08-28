"""Schemas de respuesta para gestión de usuarios, auditoría y listados paginados.

`UsuarioEnmascaradoResponse` incluye el número de identificación parcialmente
enmascarado por defecto, con un `computed_field` que expone la versión enmascarada.
`AuditoriaItemResponse` incluye `integridad_ok` para indicar si el hash SHA-256
del evento coincide con el recalculado.
"""
import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, computed_field

from src.identity_access.infrastructure.models.enums_models import EnumUsuarioGenero


class UsuarioEnmascaradoResponse(BaseModel):
    """Datos de un usuario con número de identificación parcialmente enmascarado."""

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
        """Número de identificación con los últimos dígitos reemplazados por asteriscos."""
        num = self.numero_identificacion
        if len(num) <= 4:
            return "*" * len(num)
        return num[:4] + "*" * (len(num) - 4)


class UsuariosPaginadosResponse(BaseModel):
    """Resultado paginado de la consulta de usuarios con enmascarado de identificación."""

    total: int
    pagina: int
    tamano: int
    items: list[UsuarioEnmascaradoResponse]


class UsuarioListadoResponse(BaseModel):
    """Fila simplificada del listado administrativo de usuarios."""

    nombre_usuario: str
    correo_electronico: str
    nombre_rol: str
    estado_cuenta: str
    ultima_modificacion: Optional[datetime.datetime] = None


class UsuarioListadoPaginadoResponse(BaseModel):
    """Resultado paginado del listado administrativo de usuarios."""

    total: int
    pagina: int
    tamano: int
    mensaje: Optional[str] = None
    items: list[UsuarioListadoResponse]


class UsuarioDetalleResponse(BaseModel):
    """Detalle completo de un usuario retornado en consulta de perfil o detalle admin.

    Los 5 campos personales son opcionales porque una cuenta SSO recién
    aprovisionada (``Pendiente Datos``) todavía no los tiene — ver
    ``Usuario.crear_minimo_sso``. ``id_usuario``/``version`` se exponen porque
    el flujo de completar perfil tras SSO necesita ambos para el siguiente
    ``PATCH /usuarios/{id_usuario}``.
    """

    id_usuario: int
    nombre: Optional[str] = None
    apellidos: Optional[str] = None
    correo_electronico: str
    tipo_identificacion: Optional[str] = None
    numero_identificacion: Optional[str] = None
    fecha_nacimiento: Optional[datetime.date] = None
    fecha_registro: datetime.datetime
    nombre_rol: str
    estado_cuenta: str
    version: int


class AuditoriaItemResponse(BaseModel):
    """Evento de auditoría con indicador de integridad del hash SHA-256."""

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
    nombre_usuario: Optional[str] = None
    direccion_ip: Optional[str] = None
    user_agent: Optional[str] = None
    descripcion: Optional[str] = None
    integridad_ok: bool
    # INTEGRO | LEGADO (no verificable desde antes de la política) | MANIPULADO.
    integridad: str

    model_config = {"from_attributes": True}


class AuditoriaPaginadaResponse(BaseModel):
    """Resultado paginado de la consulta del log de auditoría."""

    total: int
    pagina: int
    tamano: int
    items: list[AuditoriaItemResponse]
    # Se llena sólo cuando la consulta supera el umbral de saturación y la
    # respuesta viaja con HTTP 206.
    mensaje: Optional[str] = None
