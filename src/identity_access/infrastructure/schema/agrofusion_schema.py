# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | RFC-019 D-19.6: CREATE_USER devuelve el token de activación |
# | 2026-11-06 | Arekkazu | RF-SSO02: respuestas con los nombres que lee AgroFusion |
"""Response schemas para la integración server-to-server con AgroFusion (Mecanismo B)."""
import datetime
from typing import Optional

from src.identity_access.infrastructure.schema.user_schema import UsuarioResponse
from src.shared.base_dto import BaseDTO


class AgroFusionRolResumen(BaseDTO):
    """Fila de respuesta de `GET /integraciones/agrofusion/roles` (`GET_ROLES`). AgroFusion pasa la lista
    sin plantilla a su frontend, que lee ``role_id``/``role_name``."""

    id_rol: int
    nombre_rol: str
    role_id: int
    role_name: str


class AgroFusionTokenResponse(BaseDTO):
    """Respuesta de `POST /integraciones/agrofusion/token` (`GET_AUTHORIZATION`).

    Nombres de campo intencionales (``access_token``/``expires_in``) para
    calzar con la plantilla de respuesta que el Hub de AgroFusion espera.
    """

    access_token: str
    expires_in: int


class AgroFusionUsuarioResponse(BaseDTO):
    """Respuesta de `GET_USER`. AgroFusion conserva las claves que se registren en su plantilla y lee
    ``user_id`` (para `{user_id}`) y ``type_document_id``; por eso van también con sus nombres. Los roles
    van como lista (SGPMP asigna uno) y el género con su código (1 M, 2 F). Se responde sin nulos: su
    plantilla convertiría un nulo en el texto «None»."""

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
    user_id: int
    name: str
    first_last_name: str
    email: str
    birthday: Optional[datetime.date] = None
    document_number: Optional[str] = None
    type_document_id: Optional[int] = None


class AgroFusionTipoDocumento(BaseDTO):
    """Fila de `GET_TYPE_DOCUMENT`; AgroFusion la pasa sin plantilla y lee ``id``/``name``."""

    id: int
    name: str


class AgroFusionUsuarioCreadoResponse(UsuarioResponse):
    """Respuesta de `CREATE_USER`: el usuario y el ``activation_token`` que AgroFusion usa después en
    `ACTIVATE_ACCOUNT` (`GET /usuarios/activar/{activation_token}`, 24 h, RFC-019 D-19.6)."""

    activation_token: str
