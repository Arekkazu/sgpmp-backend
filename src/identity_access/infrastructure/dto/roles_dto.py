from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO


class PermisoItemDTO(BaseDTO):
    id_recurso: int
    id_accion: int


class CrearRolDTO(BaseDTO):
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
    id_recurso: int
    id_accion: int
