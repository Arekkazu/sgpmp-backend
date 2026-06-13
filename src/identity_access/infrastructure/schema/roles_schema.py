"""Schemas de respuesta para endpoints de roles y permisos.

`RolConPermisosResponse` agrega la lista de permisos al rol para los endpoints
de listado y detalle. Los demás schemas representan entidades individuales.
"""
import datetime
from typing import Optional

from pydantic import BaseModel


class AccionResponse(BaseModel):
    """Acción del catálogo CRUD (C=1, R=2, U=3, D=4, E=5)."""

    id_accion: int
    codigo: str
    descripcion: Optional[str] = None

    model_config = {"from_attributes": True}


class RecursoResponse(BaseModel):
    """Módulo o recurso del sistema al que se pueden asignar permisos."""

    id_recurso: int
    nombre_recurso: str
    descripcion: Optional[str] = None
    es_proceso_especial: bool

    model_config = {"from_attributes": True}


class PermisoResponse(BaseModel):
    """Permiso concreto (rol + recurso + acción) asignado a un rol."""

    id_permiso: int
    id_recurso: int
    id_accion: int
    nombre: str
    es_activo: bool

    model_config = {"from_attributes": True}


class RolResponse(BaseModel):
    """Datos básicos de un rol sin sus permisos."""

    id_rol: int
    nombre_rol: str
    descripcion: Optional[str] = None
    es_protegido: bool

    model_config = {"from_attributes": True}


class RolConPermisosResponse(BaseModel):
    """Datos del rol incluyendo la lista completa de permisos asignados."""

    id_rol: int
    nombre_rol: str
    descripcion: Optional[str] = None
    es_protegido: bool
    permisos: list[PermisoResponse]
