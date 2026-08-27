"""DTOs de entrada para la edición de perfil de usuario.

`EditarPerfilDTO` contiene los campos editables por el propio usuario.
`EditarPerfilAdminDTO` extiende el anterior con la asignación de rol,
editable únicamente mediante el endpoint administrativo.

El estado de cuenta se gestiona exclusivamente mediante RF-06.
"""

import datetime
from typing import Optional

from pydantic import ConfigDict, EmailStr, Field, field_validator

from src.identity_access.infrastructure.models.enums_models import EnumUsuarioGenero
from src.shared.base_dto import BaseDTO
from src.shared.regex import NOMBRE, NUMERO_IDENTIFICACION, TELEFONO


class EditarPerfilDTO(BaseDTO):
    """Campos de perfil editables por el propio usuario.

    ``tipo_identificacion``/``numero_identificacion``/``fecha_nacimiento``/
    ``genero`` solo aplican para completar una cuenta ``PENDIENTE_DATOS``
    (provista vía SSO de AgroFusion sin sincronización previa) — ver
    :class:`EditarPerfilUseCase`. Una cuenta ya completa no puede reescribirlos
    por esta vía.
    """

    model_config = ConfigDict(extra="forbid")

    nombre: str
    apellidos: str
    correo_electronico: Optional[EmailStr] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    tipo_identificacion: Optional[str] = None
    numero_identificacion: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=20,
    )
    fecha_nacimiento: Optional[datetime.date] = None
    genero: Optional[EnumUsuarioGenero] = None
    version: int

    @field_validator("nombre", "apellidos")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        if not NOMBRE.match(v):
            raise ValueError(
                "Solo se permiten letras, espacios y caracteres del idioma español "
                "(á, ñ, etc.)"
            )
        return v

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not TELEFONO.match(v):
            raise ValueError(
                "Número telefónico inválido. Asegúrese de ingresar solo dígitos "
                "numéricos (mínimo 7, máximo 15)"
            )
        return v

    @field_validator("numero_identificacion")
    @classmethod
    def validar_numero_identificacion(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not NUMERO_IDENTIFICACION.fullmatch(v):
            raise ValueError(
                "El número de identificación debe contener únicamente "
                "dígitos del 0 al 9"
            )
        return v


class EditarPerfilAdminDTO(EditarPerfilDTO):
    """Extiende `EditarPerfilDTO` con la asignación administrativa de rol."""

    id_rol: Optional[int] = None
