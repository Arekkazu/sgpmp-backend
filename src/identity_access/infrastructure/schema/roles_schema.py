import datetime
from typing import Optional

from pydantic import BaseModel


class AccionResponse(BaseModel):
    id_accion: int
    codigo: str
    descripcion: Optional[str] = None

    model_config = {"from_attributes": True}


class RecursoResponse(BaseModel):
    id_recurso: int
    nombre_recurso: str
    descripcion: Optional[str] = None
    es_proceso_especial: bool

    model_config = {"from_attributes": True}


class PermisoResponse(BaseModel):
    id_permiso: int
    id_recurso: int
    id_accion: int
    nombre: str
    es_activo: bool

    model_config = {"from_attributes": True}


class RolResponse(BaseModel):
    id_rol: int
    nombre_rol: str
    descripcion: Optional[str] = None
    es_protegido: bool

    model_config = {"from_attributes": True}


class RolConPermisosResponse(BaseModel):
    id_rol: int
    nombre_rol: str
    descripcion: Optional[str] = None
    es_protegido: bool
    permisos: list[PermisoResponse]
