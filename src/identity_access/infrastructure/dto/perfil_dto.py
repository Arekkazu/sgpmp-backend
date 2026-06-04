from typing import Optional

from pydantic import EmailStr, field_validator

from src.shared.base_dto import BaseDTO
from src.shared.regex import NOMBRE, TELEFONO


class EditarPerfilDTO(BaseDTO):
    nombre: str
    apellidos: str
    correo_electronico: Optional[EmailStr] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    version: int

    @field_validator("nombre", "apellidos")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        if not NOMBRE.match(v):
            raise ValueError(
                "Solo se permiten letras, espacios y caracteres del idioma español (á, ñ, etc.)"
            )
        return v

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not TELEFONO.match(v):
            raise ValueError(
                "Número telefónico inválido. Asegúrese de ingresar solo dígitos numéricos (mínimo 7, máximo 15)"
            )
        return v


class EditarPerfilAdminDTO(EditarPerfilDTO):
    id_estado_cuenta: Optional[int] = None
    id_rol: Optional[int] = None
