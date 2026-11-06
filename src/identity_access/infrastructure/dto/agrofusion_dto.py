# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-101 5.2: credenciales del cliente solo en el pedido de token |
"""DTOs de entrada para la integración server-to-server con AgroFusion (canal de identidad, RF-SSO02).

Desde RF-101 v2.0 ``client_id``/``client_secret`` solo llegan en el pedido de token
(``AgroFusionTokenDTO``); el resto de operaciones se autentica con el token de canal en
``Authorization: Bearer``. Si AgroFusion aún manda las credenciales en el cuerpo, se ignoran.
"""
import datetime
from typing import Literal, Optional

from pydantic import EmailStr, Field, ValidationInfo, field_validator

from src.identity_access.domain.value_objects.identificacion import (
    identificacion_valida,
    mensaje_identificacion_invalida,
)
from src.identity_access.infrastructure.models.enums_models import EnumUsuarioGenero
from src.shared.base_dto import BaseDTO


class AgroFusionCredencialesDTO(BaseDTO):
    """Credenciales del cliente externo; solo las lleva el pedido de token."""

    client_id: str
    client_secret: str


class AgroFusionTokenDTO(AgroFusionCredencialesDTO):
    """`GET_AUTHORIZATION` — solicita un JWT sgpmp para un correo ya existente."""

    email: EmailStr


class AgroFusionCreateUserDTO(BaseDTO):
    """`CREATE_USER` — alta completa de usuario, activo de inmediato (sin flujo de activación por correo)."""

    correo_electronico: EmailStr
    nombre: str
    apellidos: str
    tipo_identificacion: Literal["CC", "CE", "Pasaporte"]
    numero_identificacion: str = Field(min_length=1, max_length=20)
    fecha_nacimiento: datetime.date
    genero: EnumUsuarioGenero
    rol_codigo: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None

    @field_validator("numero_identificacion")
    @classmethod
    def validar_identificacion(cls, v: str, info: ValidationInfo) -> str:
        tipo = info.data.get("tipo_identificacion")
        if not identificacion_valida(tipo, v):
            raise ValueError(mensaje_identificacion_invalida(tipo))
        return v


class AgroFusionEstadoDTO(BaseDTO):
    """`CHANGE_USER_STATUS` — cambia el estado de cuenta de un usuario existente."""

    id_estado_cuenta: int
    motivo: Optional[str] = None
