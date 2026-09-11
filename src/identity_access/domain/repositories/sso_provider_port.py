"""Puerto de verificación de identidad SSO externa (capa de dominio).

El dominio declara que necesita verificar un token SSO y obtener a cambio una
identidad federada, sin saber que el proveedor es AgroFusion ni que el token
es RS256 — ese detalle vive en la implementación concreta
(``infrastructure/adapters/agrofusion_sso_adapter.py``). Mismo espíritu que el
patrón de "adaptador stub para dependencias cruzadas" documentado en
CLAUDE.md.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.identity_access.domain.value_objects.identidad_federada import IdentidadFederada


class SsoProviderPort(ABC):
    """Contrato para verificar un token de handoff SSO externo."""

    @abstractmethod
    def verificar(self, token: str) -> IdentidadFederada:
        """Verifica un token SSO y devuelve la identidad que certifica.

        Args:
            token: Token de handoff recibido del proveedor SSO externo.

        Returns:
            La :class:`IdentidadFederada` que el token certifica.

        Raises:
            AuthenticationError: Si el token es inválido, expiró, o su firma
                no verifica contra la clave pública del proveedor. HTTP 401.
        """
        raise NotImplementedError
