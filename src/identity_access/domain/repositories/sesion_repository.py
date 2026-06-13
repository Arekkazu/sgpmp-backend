"""Puerto de persistencia del agregado ``Sesion`` (capa de dominio).

Contrato para gestionar sesiones de acceso y sus tokens, expresado en términos
del dominio: recibe y devuelve las entidades :class:`Sesion` y :class:`Token`,
nunca modelos ORM. La implementación concreta vive en
``infrastructure/repositories/sesion_repository.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.identity_access.domain.entities.sesion import Sesion
from src.identity_access.domain.entities.token import Token


class SesionRepository(ABC):
    """Contrato de acceso a datos para sesiones y tokens de acceso."""

    @abstractmethod
    def buscar_sesion_activa(self, id_cuenta_usuario: int) -> Optional[Sesion]:
        """Retorna la sesión activa de una cuenta, o ``None``."""
        raise NotImplementedError

    @abstractmethod
    def buscar_sesion_por_token(self, id_token: int) -> Optional[Sesion]:
        """Retorna la sesión asociada a un token, o ``None``."""
        raise NotImplementedError

    @abstractmethod
    def invalidar_sesion(self, sesion: Sesion) -> None:
        """Cierra una sesión y marca su token como usado (hace ``flush``)."""
        raise NotImplementedError

    @abstractmethod
    def invalidar_todas_sesiones(self, id_cuenta_usuario: int) -> None:
        """Cierra todas las sesiones activas de una cuenta (hace ``flush``)."""
        raise NotImplementedError

    @abstractmethod
    def crear_token_acceso(self, fecha_expiracion: datetime) -> Token:
        """Crea un token de acceso con la expiración dada y lo devuelve."""
        raise NotImplementedError

    @abstractmethod
    def crear_sesion(
        self,
        id_cuenta_usuario: int,
        id_token: int,
        direccion_ip: str,
        agente_usuario: str,
        fecha_expiracion: datetime,
    ) -> Sesion:
        """Crea una sesión activa para la cuenta y la devuelve."""
        raise NotImplementedError
