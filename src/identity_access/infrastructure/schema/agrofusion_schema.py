# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | RFC-019 D-19.6: CREATE_USER devuelve el token de activación |
"""Response schemas para la integración server-to-server con AgroFusion (Mecanismo B)."""
import datetime
from typing import Optional

from src.identity_access.infrastructure.schema.user_schema import UsuarioResponse
from src.shared.base_dto import BaseDTO


class AgroFusionRolResumen(BaseDTO):
    """Fila de respuesta de `GET /integraciones/agrofusion/roles` (`GET_ROLES`)."""

    id_rol: int
    nombre_rol: str


class AgroFusionTokenResponse(BaseDTO):
    """Respuesta de `POST /integraciones/agrofusion/token` (`GET_AUTHORIZATION`).

    Nombres de campo intencionales (``access_token``/``expires_in``) para
    calzar con la plantilla de respuesta que el Hub de AgroFusion espera.
    """

    access_token: str
    expires_in: int


class AgroFusionUsuarioResponse(BaseDTO):
    """Respuesta de `GET_USER`. AgroFusion toma el id para `{user_id}` y mapea el resto con su plantilla;
    los roles van como lista (SGPMP asigna uno) y el género también con su código (1 M, 2 F)."""

    id_usuario: int
    nombre: str
    apellidos: str
    correo_electronico: str
    roles: list[int]
    tipo_identificacion: Optional[str] = None
    numero_identificacion: Optional[str] = None
    fecha_nacimiento: Optional[datetime.date] = None
    genero: Optional[str] = None
    genero_id: Optional[int] = None
    id_estado_cuenta: Optional[int] = None


class AgroFusionTipoDocumento(BaseDTO):
    """Fila de `GET_TYPE_DOCUMENT`."""

    id: str
    nombre: str


class AgroFusionUsuarioCreadoResponse(UsuarioResponse):
    """Respuesta de `CREATE_USER`: el usuario y el ``activation_token`` que AgroFusion usa después en
    `ACTIVATE_ACCOUNT` (`GET /usuarios/activar/{activation_token}`, 24 h, RFC-019 D-19.6)."""

    activation_token: str
