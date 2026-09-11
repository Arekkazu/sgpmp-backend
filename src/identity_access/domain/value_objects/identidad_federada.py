"""Value object ``IdentidadFederada`` del dominio de identidad.

Representa la identidad ya verificada que entrega un proveedor SSO externo
(AgroFusion). Es intencionalmente mínima porque eso es todo lo que el
Mecanismo A de AgroFusion garantiza: identificador del usuario en el sistema
externo y su correo, nada más (ver ``domain/repositories/sso_provider_port.py``).
"""
from __future__ import annotations

from dataclasses import dataclass

from src.identity_access.domain.value_objects.email import Email


@dataclass(frozen=True)
class IdentidadFederada:
    """Identidad verificada por un proveedor SSO externo.

    Attributes:
        sub_externo: Identificador del usuario en el sistema externo (claim
            ``sub`` del token verificado).
        email: Correo verificado por el proveedor externo.
        emisor: Emisor del token (claim ``iss``), para trazabilidad/auditoría.
    """

    sub_externo: str
    email: Email
    emisor: str
