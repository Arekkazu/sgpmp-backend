"""Puerto de persistencia del agregado ``Evento`` (capa de dominio).

Incluye consulta, registro y archivado histórico del log de auditoría. Sus
operaciones se expresan en términos del dominio y la implementación concreta vive en
``infrastructure/repositories/evento_repository.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.identity_access.domain.entities.evento import Evento
from src.identity_access.domain.value_objects.evento_categoria import EventoCategoria


class EventoRepository(ABC):
    """Contrato de persistencia para eventos y su archivo histórico."""

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
        archivados: bool = False,
    ) -> list[tuple[Evento, str]]:
        """Retorna una página de eventos con su clasificación de integridad.

        Args:
            id_usuario: Filtro por usuario, o ``None``.
            tipo_evento: Filtro por tipo de evento, o ``None``.
            fecha_desde: Límite inferior del rango, o ``None``.
            fecha_hasta: Límite superior del rango, o ``None``.
            offset: Registros a saltar.
            limit: Máximo de registros a retornar.
            categoria: Filtro por categoría funcional, o ``None``.
            archivados: Consultar el archivo histórico en vez del log activo.

        Returns:
            Lista de tuplas ``(Evento, clasificacion)`` donde ``clasificacion`` es
            ``INTEGRO`` si el hash almacenado coincide con el recalculado,
            ``LEGADO`` si el registro ya no era verificable antes de adoptar la
            política y no ha cambiado desde entonces, o ``MANIPULADO`` si el
            contenido fue alterado.
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
        archivados: bool = False,
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
        descripcion: Optional[str] = None,
    ) -> None:
        """Registra un evento de auditoría con su hash de integridad SHA-256.

        La IP, el user-agent y la sesión se toman del contexto del request cuando
        el llamador no los indica, de modo que ningún registro quede sin ellos.

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

    @abstractmethod
    def adquirir_bloqueo_archivado(self) -> bool:
        """Intenta obtener el bloqueo transaccional exclusivo del archivado RF-10."""
        raise NotImplementedError

    @abstractmethod
    def archivar_eventos_anteriores(
        self,
        fecha_corte: datetime,
        limite: int,
    ) -> int:
        """Copia un lote de eventos no archivados anteriores a ``fecha_corte``."""
        raise NotImplementedError
