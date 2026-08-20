"""Puerto de persistencia (lectura) del agregado ``Evento`` (capa de dominio).

Contrato de consulta del log de auditoría, expresado en términos del dominio:
devuelve la entidad :class:`Evento` acompañada de su flag de integridad. La
implementación concreta vive en
``infrastructure/repositories/evento_repository.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.identity_access.domain.entities.evento import Evento
from src.identity_access.domain.value_objects.evento_categoria import EventoCategoria


class EventoRepository(ABC):
    """Contrato de acceso a datos para la consulta de eventos de auditoría."""

    @abstractmethod
    def listar_eventos(
        self,
        id_usuario: Optional[int],
        tipo_evento: Optional[int],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
        offset: int,
        limit: int,
        categoria: Optional[EventoCategoria] = None,
    ) -> list[tuple[Evento, bool]]:
        """Retorna una página de eventos con su flag de integridad.

        Args:
            id_usuario: Filtro por usuario, o ``None``.
            tipo_evento: Filtro por tipo de evento, o ``None``.
            fecha_desde: Límite inferior del rango, o ``None``.
            fecha_hasta: Límite superior del rango, o ``None``.
            offset: Registros a saltar.
            limit: Máximo de registros a retornar.
            categoria: Filtro por categoría funcional, o ``None``.

        Returns:
            Lista de tuplas ``(Evento, integridad_ok)`` donde ``integridad_ok``
            indica si el hash almacenado coincide con el recalculado.
        """
        raise NotImplementedError

    @abstractmethod
    def contar_eventos(
        self,
        id_usuario: Optional[int],
        tipo_evento: Optional[int],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
        categoria: Optional[EventoCategoria] = None,
    ) -> int:
        """Cuenta el total de eventos que cumplen los filtros (para paginar)."""
        raise NotImplementedError

    @abstractmethod
    def registrar(
        self,
        tipo_evento: int,
        exitoso: bool,
        id_usuario: int,
        detalle: dict,
        id_sesion: Optional[int] = None,
    ) -> None:
        """Registra un evento de auditoría con su hash de integridad SHA-256.

        Args:
            tipo_evento: ID del tipo de evento.
            exitoso: Resultado (``True`` = EXITOSO, ``False`` = FALLIDO).
            id_usuario: Usuario relacionado con el evento.
            detalle: Contexto del evento (se serializa como JSONB).
            id_sesion: Sesión asociada, si aplica.
        """
        raise NotImplementedError

    @abstractmethod
    def contar_solicitudes_recuperacion_por_ip(self, ip: str, desde: datetime) -> int:
        """Cuenta las solicitudes de recuperación (tipo 7) desde una IP a partir de ``desde``.

        Se usa para aplicar rate limiting al endpoint de recuperación de contraseña.
        """
        raise NotImplementedError
