# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | RFC-019 D-19.6: CREATE_USER devuelve el token de activación |
"""Response schemas para la integración server-to-server con AgroFusion (Mecanismo B)."""
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


class AgroFusionUsuarioEstadoResponse(BaseDTO):
    """Respuesta de `GET /integraciones/agrofusion/usuarios/{email}` (`GET_USER`)."""

    existe: bool
    id_usuario: Optional[int] = None
    id_estado_cuenta: Optional[int] = None
    id_rol: Optional[int] = None


class AgroFusionUsuarioCreadoResponse(UsuarioResponse):
    """Respuesta de `CREATE_USER`: el usuario y el ``activation_token`` que AgroFusion usa después en
    `ACTIVATE_ACCOUNT` (`GET /usuarios/activar/{activation_token}`, 24 h, RFC-019 D-19.6)."""

    activation_token: str
