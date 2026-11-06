# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-101 5.2: credenciales del cliente solo en el pedido de token |
"""DTOs de entrada para la integración server-to-server con AgroFusion (canal de identidad, RF-SSO02).

Desde RF-101 v2.0 ``client_id``/``client_secret`` solo llegan en el pedido de token
(``AgroFusionTokenDTO``); el resto de operaciones se autentica con el token de canal en
``Authorization: Bearer``. Si AgroFusion aún manda las credenciales en el cuerpo, se ignoran.

Los campos siguen lo que AgroFusion envía (``agrofusion-backendauth``, ``users_service``): los apellidos
llegan separados, los roles como lista de ids de ``GET_ROLES``, el género con su catálogo (1 masculino,
2 femenino) y el tipo de documento con el id de ``GET_TYPE_DOCUMENT``. El administrador de AgroFusion
traduce sus nombres de campo a los de aquí con la plantilla de cada endpoint (manual, sección 10.1.4).
"""
import datetime
from typing import Literal, Optional

from pydantic import EmailStr, Field, ValidationInfo, field_validator, model_validator

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


# Catálogo de género de AgroFusion (su formulario de usuarios: 1 masculino, 2 femenino).
_GENERO_AGROFUSION = {"1": "M", "2": "F"}
GENERO_A_AGROFUSION = {"M": 1, "F": 2}  # X y T no existen en AgroFusion
TIPOS_DOCUMENTO = {"CC": "Cédula de ciudadanía", "CE": "Cédula de extranjería", "Pasaporte": "Pasaporte"}


def _genero(valor):
    return _GENERO_AGROFUSION.get(str(valor).strip(), valor) if valor is not None else None


class _ApellidosDTO(BaseDTO):
    """AgroFusion envía primer y segundo apellido por separado; SGPMP guarda uno solo."""

    apellidos: Optional[str] = None
    segundo_apellido: Optional[str] = None
    roles: Optional[list[int]] = None
    rol_codigo: Optional[str] = None

    @model_validator(mode="after")
    def _unir_apellidos(self):
        if self.segundo_apellido:
            self.apellidos = f"{self.apellidos or ''} {self.segundo_apellido}".strip()
        return self


class AgroFusionCreateUserDTO(_ApellidosDTO):
    """`CREATE_USER` — alta completa de usuario, activo de inmediato (sin flujo de activación por correo)."""

    correo_electronico: EmailStr
    nombre: str
    apellidos: str
    tipo_identificacion: Literal["CC", "CE", "Pasaporte"]
    numero_identificacion: str = Field(min_length=1, max_length=20)
    fecha_nacimiento: datetime.date
    genero: EnumUsuarioGenero
    contrasena: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None

    @field_validator("genero", mode="before")
    @classmethod
    def _genero_agrofusion(cls, v):
        return _genero(v)

    @field_validator("numero_identificacion")
    @classmethod
    def validar_identificacion(cls, v: str, info: ValidationInfo) -> str:
        tipo = info.data.get("tipo_identificacion")
        if not identificacion_valida(tipo, v):
            raise ValueError(mensaje_identificacion_invalida(tipo))
        return v


class AgroFusionEstadoDTO(BaseDTO):
    """`CHANGE_USER_STATUS` — estado con los códigos de AgroFusion: 1 activo, 2 inactivo, 3 eliminado."""

    nuevo_estado: Literal[1, 2, 3]
    motivo: Optional[str] = None


class AgroFusionUpdateUserDTO(_ApellidosDTO):
    """`UPDATE_USER` — datos de perfil y rol que AgroFusion mantiene; lo que no envía se conserva.

    Documento, fecha de nacimiento y género no se cambian por aquí (en SGPMP solo se completan en una
    cuenta pendiente de datos); si AgroFusion los manda, se ignoran."""
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
