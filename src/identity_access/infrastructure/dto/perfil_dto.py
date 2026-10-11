"""DTOs de entrada para la edición de perfil de usuario.

`PerfilBaseDTO` reúne los campos de perfil comunes a los dos endpoints.
`EditarPerfilDTO` es el de la edición propia; `EditarPerfilAdminDTO` el de la
edición administrativa, que suma la asignación de rol.

El estado de cuenta se gestiona exclusivamente mediante RF-06.
"""

import datetime
from typing import Any, Literal, Optional

from pydantic import ConfigDict, EmailStr, Field, field_validator

from src.identity_access.infrastructure.models.enums_models import EnumUsuarioGenero
from src.shared.base_dto import BaseDTO
from src.shared.regex import NOMBRE, TELEFONO

# Campos que RF-05 reserva al administrador ("datos críticos"). Se listan con
# los dos nombres que circulan: los del documento de requerimientos
# (``rol_usuario``/``estado_usuario``) y los reales de la API.
CAMPOS_CRITICOS = ("id_rol", "rol_usuario", "estado_usuario", "id_estado_cuenta")


class PerfilBaseDTO(BaseDTO):
    """Campos de perfil comunes a la edición propia y a la administrativa.

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
    tipo_identificacion: Optional[Literal["CC", "CE", "Pasaporte"]] = None
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


class EditarPerfilDTO(PerfilBaseDTO):
    """Campos de perfil editables por el propio usuario.

    Los campos críticos se declaran aquí a propósito, aunque el endpoint no los
    aplique nunca: con ``extra="forbid"`` Pydantic los rechazaba con un 400
    genérico antes de llegar al caso de uso, y RF-05 pide que el intento de
    escalada de privilegios responda 403 **y quede auditado**. Ver
    ``EditarPerfilUseCase``, que es quien los rechaza.
    """

    id_rol: Any = None
    rol_usuario: Any = None
    estado_usuario: Any = None
    id_estado_cuenta: Any = None


class EditarPerfilAdminDTO(PerfilBaseDTO):
    """Campos de perfil editables por un administrador sobre cualquier usuario."""

    id_rol: Optional[int] = None
