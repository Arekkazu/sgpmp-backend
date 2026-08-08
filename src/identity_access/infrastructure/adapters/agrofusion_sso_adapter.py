"""Adaptador SSO de AgroFusion (Mecanismo A — handoff de login interactivo).

Implementación concreta de :class:`SsoProviderPort`. Verifica el token RS256
de un solo uso (TTL 2 min) que ``backendauth`` de AgroFusion emite tras un
login interactivo exitoso. A diferencia del antipatrón observado en el código
de referencia de AgroFusion (``backendint`` declara ``jwt_issuer`` mas nunca lo
valida al decodificar), aquí ``audience``/``issuer`` se pasan explícitos a
``jwt.decode`` para que ``python-jose`` los verifique.

Sigue el mismo patrón de lectura de configuración que ``src/shared/jwt.py``:
variables de entorno leídas a nivel de módulo/instancia con ``os.getenv``, sin
un objeto ``Settings`` centralizado (no existe uno en este proyecto).
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from jose import JWTError, jwt

from src.identity_access.domain.repositories.sso_provider_port import SsoProviderPort
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.domain.value_objects.identidad_federada import IdentidadFederada
from src.shared.errors import AuthenticationError, InfrastructureError

load_dotenv()

_ALGORITHM = "RS256"


class AgroFusionSsoAdapter(SsoProviderPort):
    """Verifica tokens de handoff SSO emitidos por ``backendauth`` de AgroFusion."""

    def __init__(self) -> None:
        self._public_key_path = os.getenv("AGROFUSION_SSO_PUBLIC_KEY_PATH")
        self._project_code = os.getenv("AGROFUSION_PROJECT_CODE")
        self._issuer = os.getenv("AGROFUSION_ISSUER", "agrofusion-auth")

    def verificar(self, token: str) -> IdentidadFederada:
        """Verifica la firma RS256, `audience`, `issuer` y expiración del token.

        Raises:
            InfrastructureError: La clave pública configurada no se pudo leer. HTTP 500.
            AuthenticationError: Firma inválida, `aud`/`iss` incorrectos, token
                expirado (recordar TTL de 2 minutos), o payload sin los claims
                mínimos (`sub`, `email`). HTTP 401.
        """
        try:
            with open(self._public_key_path, "r", encoding="utf-8") as f:
                public_key = f.read()
        except OSError as exc:
            raise InfrastructureError(
                code="AGROFUSION_CLAVE_PUBLICA_NO_DISPONIBLE",
                message="No se pudo leer la clave pública configurada para verificar tokens SSO de AgroFusion.",
                original_error=exc,
            )

        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=[_ALGORITHM],
                audience=self._project_code,
                issuer=self._issuer,
            )
        except JWTError:
            raise AuthenticationError(
                code="SSO_TOKEN_INVALIDO",
                message="El token SSO de AgroFusion es inválido, expiró o su firma no pudo verificarse.",
            )

        sub_externo = payload.get("sub")
        email = payload.get("email")
        if not sub_externo or not email:
            raise AuthenticationError(
                code="SSO_TOKEN_INVALIDO",
                message="El token SSO de AgroFusion no contiene los datos mínimos esperados (sub, email).",
            )

        return IdentidadFederada(
            sub_externo=str(sub_externo),
            email=Email(email),
            emisor=self._issuer,
        )
