"""Response schemas para la integración server-to-server con AgroFusion (Mecanismo B)."""
from typing import Optional

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
