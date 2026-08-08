"""DTOs de entrada para la integración server-to-server con AgroFusion (Mecanismo B).

Todos incluyen ``client_id``/``client_secret`` en el body porque el contrato
de referencia de AgroFusion (``backendint``) los envía así en cada operación
de tipo `POST`/`PATCH` — ver ``verify_agrofusion_client`` en
``src/shared/agrofusion_auth.py``. Los endpoints `GET` reciben las mismas
credenciales por query params (sin body), declarados directamente en el
router.
"""
import datetime
from typing import Optional

from pydantic import EmailStr

from src.identity_access.infrastructure.models.enums_models import EnumUsuarioGenero
from src.shared.base_dto import BaseDTO


class AgroFusionCredencialesDTO(BaseDTO):
    """Credenciales M2M compartidas por las operaciones con body."""

    client_id: str
    client_secret: str


class AgroFusionTokenDTO(AgroFusionCredencialesDTO):
    """`GET_AUTHORIZATION` — solicita un JWT sgpmp para un correo ya existente."""

    email: EmailStr


class AgroFusionCreateUserDTO(AgroFusionCredencialesDTO):
    """`CREATE_USER` — alta completa de usuario, activo de inmediato (sin flujo de activación por correo)."""

    correo_electronico: EmailStr
    nombre: str
    apellidos: str
    tipo_identificacion: str
    numero_identificacion: str
    fecha_nacimiento: datetime.date
    genero: EnumUsuarioGenero
    rol_codigo: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None


class AgroFusionEstadoDTO(AgroFusionCredencialesDTO):
    """`CHANGE_USER_STATUS` — cambia el estado de cuenta de un usuario existente."""

    id_estado_cuenta: int
    motivo: Optional[str] = None
