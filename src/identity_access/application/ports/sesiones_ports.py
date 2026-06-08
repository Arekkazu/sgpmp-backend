"""Contrato de persistencia para sesiones, tokens y eventos de auditoría.

Define las operaciones sobre ``sesiones``, ``tokens`` y ``eventos`` que los
use cases de autenticación y auditoría necesitan. La implementación concreta
vive en ``infrastructure/repositories/sesiones_repository.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.identity_access.infrastructure.models.sesiones_model import Sesiones
from src.identity_access.infrastructure.models.tokens_model import Tokens


class SesionesPort(ABC):
    """Interfaz de acceso a datos para sesiones, tokens y eventos de auditoría."""

    @abstractmethod
    def buscar_sesion_activa(self, id_cuenta_usuario: int) -> Optional[Sesiones]:
        """Busca la sesión activa de una cuenta.

        Args:
            id_cuenta_usuario: ID de la cuenta cuya sesión se busca.

        Returns:
            Instancia ORM de la sesión activa o ``None`` si no existe.
        """
        pass

    @abstractmethod
    def buscar_sesion_por_token(self, id_token: int) -> Optional[Sesiones]:
        """Busca una sesión por el ID de su token de acceso.

        Args:
            id_token: ID del token asociado a la sesión.

        Returns:
            Instancia ORM de la sesión o ``None`` si no existe.
        """
        pass

    @abstractmethod
    def invalidar_sesion(self, sesion: Sesiones) -> None:
        """Marca una sesión como inactiva.

        Args:
            sesion: Instancia ORM de la sesión a invalidar.
        """
        pass

    @abstractmethod
    def crear_token_acceso(self, fecha_expiracion: datetime) -> Tokens:
        """Crea un nuevo registro de token de acceso en la tabla ``tokens``.

        Args:
            fecha_expiracion: Marca temporal UTC en que el token expira.

        Returns:
            Instancia ORM del token creado con su ``id_token`` asignado.
        """
        pass

    @abstractmethod
    def crear_sesion(
        self,
        id_cuenta_usuario: int,
        id_token: int,
        direccion_ip: str,
        agente_usuario: str,
        fecha_expiracion: datetime,
    ) -> Sesiones:
        """Registra una nueva sesión activa para la cuenta del usuario.

        Args:
            id_cuenta_usuario: ID de la cuenta que inicia sesión.
            id_token: ID del token de acceso asociado a esta sesión.
            direccion_ip: Dirección IP desde la que se inició la sesión.
            agente_usuario: User-Agent del cliente (browser/dispositivo).
            fecha_expiracion: Marca temporal UTC de expiración de la sesión.

        Returns:
            Instancia ORM de la sesión creada.
        """
        pass

    @abstractmethod
    def registrar_evento(
        self,
        tipo_evento: int,
        resultado: EnumEventoResultado,
        id_usuario: int,
        detalle: dict,
        id_sesion: Optional[int] = None,
    ) -> None:
        """Registra un evento de auditoría en la tabla ``eventos``.

        Args:
            tipo_evento: ID del tipo de evento (tabla ``tipo_eventos``).
            resultado: Resultado de la operación (EXITOSO o FALLIDO).
            id_usuario: ID del usuario que ejecutó la acción.
            detalle: Diccionario con información contextual del evento,
                serializado como JSONB en la DB.
            id_sesion: ID de la sesión activa al momento del evento. ``None``
                para eventos que ocurren fuera de una sesión (ej: login fallido).
        """
        pass

    @abstractmethod
    def invalidar_todas_sesiones(self, id_cuenta_usuario: int) -> None:
        """Invalida todas las sesiones activas de una cuenta.

        Se usa al cambiar contraseña, bloquear cuenta o iniciar sesión en
        otro dispositivo (política de sesión única).

        Args:
            id_cuenta_usuario: ID de la cuenta cuyas sesiones se invalidan.
        """
        pass

    @abstractmethod
    def contar_solicitudes_recuperacion_por_ip(self, ip: str, desde: datetime) -> int:
        """Cuenta las solicitudes de recuperación de contraseña desde una IP en un período.

        Se usa para aplicar rate limiting y prevenir abuso del endpoint
        de recuperación de contraseña.

        Args:
            ip: Dirección IP a consultar.
            desde: Marca temporal desde la cual contar las solicitudes.

        Returns:
            Número de solicitudes de recuperación registradas desde esa IP
            en el período indicado.
        """
        pass
