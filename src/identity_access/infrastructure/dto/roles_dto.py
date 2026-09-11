"""DTOs de entrada para la gestión de roles y permisos.

`CrearRolDTO` exige al menos un permiso; `EditarRolDTO` acepta modificación
parcial; `AsignarPermisoDTO` y `PermisoItemDTO` representan un par recurso-acción.
"""
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO


class PermisoItemDTO(BaseDTO):
    """Par recurso-acción que define un permiso individual."""

    id_recurso: int
    id_accion: int


class CrearRolDTO(BaseDTO):
    """Datos para crear un nuevo rol con sus permisos iniciales."""

    nombre_rol: str
    descripcion: Optional[str] = None
    permisos: list[PermisoItemDTO]

    @field_validator("nombre_rol")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre del rol no puede estar vacío.")
        return v

    @field_validator("permisos")
    @classmethod
    def validar_permisos(cls, v: list) -> list:
        if not v:
            raise ValueError(
                "Operación rechazada: Todo rol debe poseer al menos un permiso asociado."
            )
        return v


class EditarRolDTO(BaseDTO):
    """Campos editables de un rol existente (ambos opcionales, al menos uno requerido)."""

    nombre_rol: Optional[str] = None
    descripcion: Optional[str] = None

    @field_validator("nombre_rol")
    @classmethod
    def validar_nombre(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("El nombre del rol no puede estar vacío.")
        return v


class AsignarPermisoDTO(BaseDTO):
    """Par recurso-acción para asignar un permiso a un rol existente."""

    id_recurso: int
    id_accion: int
