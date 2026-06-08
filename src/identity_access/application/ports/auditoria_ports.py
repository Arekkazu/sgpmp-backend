"""Contrato de persistencia para consultas de auditoría.

Define las operaciones de lectura sobre la tabla ``eventos`` que el use case
de consulta de auditoría necesita. La implementación concreta vive en
``infrastructure/repositories/auditoria_repository.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.identity_access.infrastructure.models.eventos_model import Eventos


class AuditoriaPort(ABC):
    """Interfaz de acceso a datos para consultas de auditoría de eventos."""

    @abstractmethod
    def listar_eventos(
        self,
        id_usuario: Optional[int],
        tipo_evento: Optional[int],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
        offset: int,
        limit: int,
    ) -> list[tuple[Eventos, bool]]:
        """Retorna una página de eventos de auditoría con filtros opcionales.

        Args:
            id_usuario: Filtro por ID de usuario. ``None`` para todos.
            tipo_evento: Filtro por tipo de evento. ``None`` para todos.
            fecha_desde: Límite inferior del rango de fechas. ``None`` sin límite inferior.
            fecha_hasta: Límite superior del rango de fechas. ``None`` sin límite superior.
            offset: Número de registros a saltar.
            limit: Número máximo de registros a retornar.

        Returns:
            Lista de tuplas ``(Eventos, es_sospechoso)`` donde ``es_sospechoso``
            indica si el evento fue marcado como actividad anómala.
        """
        pass

    @abstractmethod
    def contar_eventos(
        self,
        id_usuario: Optional[int],
        tipo_evento: Optional[int],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
    ) -> int:
        """Cuenta el total de eventos que cumplen los filtros dados.

        Se usa junto con ``listar_eventos`` para calcular el total de páginas.

        Args:
            id_usuario: Filtro por ID de usuario. ``None`` para todos.
            tipo_evento: Filtro por tipo de evento. ``None`` para todos.
            fecha_desde: Límite inferior del rango de fechas. ``None`` sin límite.
            fecha_hasta: Límite superior del rango de fechas. ``None`` sin límite.

        Returns:
            Número total de eventos que coinciden con los filtros.
        """
        pass
