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
    ) -> list[tuple[Evento, bool]]:
        """Retorna una página de eventos con su flag de integridad.

        Args:
            id_usuario: Filtro por usuario, o ``None``.
            tipo_evento: Filtro por tipo de evento, o ``None``.
            fecha_desde: Límite inferior del rango, o ``None``.
            fecha_hasta: Límite superior del rango, o ``None``.
            offset: Registros a saltar.
            limit: Máximo de registros a retornar.

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
    ) -> int:
        """Cuenta el total de eventos que cumplen los filtros (para paginar)."""
        raise NotImplementedError
