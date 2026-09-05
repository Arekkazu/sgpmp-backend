"""Puerto de persistencia del agregado ``Evento`` (capa de dominio).

Incluye consulta, registro y archivado histórico del log de auditoría. Sus
operaciones se expresan en términos del dominio y la implementación concreta vive en
``infrastructure/repositories/evento_repository.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterator, Optional

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
    def clasificar_conjunto(
        self,
        id_usuario: Optional[int],
        tipo_evento: Optional[int],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
        limite: int,
        categoria: Optional[EventoCategoria] = None,
        archivados: bool = False,
    ) -> dict[int, str]:
        """Clasifica la integridad de todo el conjunto filtrado, sin materializarlo.

        Primera de las dos pasadas de la exportación (RF-10). Recorre el conjunto
        con un cursor de servidor y devuelve solo ``{id_evento: clasificacion}``,
        que pesa órdenes de magnitud menos que las filas completas. Existe para
        que el use case pueda decidir si aborta con 500 por un registro
        ``MANIPULADO`` **antes** de que la respuesta empiece a transmitirse: una
        vez enviadas las cabeceras del 200 ya no se puede convertir en error.

        Args:
            limite: Máximo de registros a considerar, igual que el de la exportación.

        Returns:
            Mapa de ``id_evento`` a ``INTEGRO`` | ``LEGADO`` | ``MANIPULADO``.
        """
        raise NotImplementedError

    @abstractmethod
    def iterar_eventos(
        self,
        id_usuario: Optional[int],
        tipo_evento: Optional[int],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
        limite: int,
        categoria: Optional[EventoCategoria] = None,
        archivados: bool = False,
    ) -> Iterator[Evento]:
        """Itera el conjunto filtrado con cursor de servidor, sin cargarlo entero.

        Segunda pasada de la exportación: emite las entidades de a lotes para que
        el CSV se transmita mientras se lee, en vez de construir el archivo
        completo en memoria. La clasificación de integridad no viene aquí; se
        obtiene antes con :meth:`clasificar_conjunto`.
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
    def obtener_primera_solicitud_recuperacion_por_ip(
        self,
        ip: str,
        desde: datetime,
    ) -> Optional[datetime]:
        """Obtiene en UTC la solicitud tipo 7 más antigua de una IP en la ventana.

        Permite informar cuándo vence realmente el rate limit: una hora después
        de la primera solicitud que todavía se está contabilizando.
        """
        raise NotImplementedError

    @abstractmethod
    def contar_consultas_detalle_usuario(self, id_usuario: int, desde: datetime) -> int:
        """Cuenta las consultas de detalle (tipo 18) exitosas de un actor desde ``desde``.

        Se usa para detectar patrones de extracción masiva de fichas de usuario
        (RF-12) y responder 429. Solo cuenta las consultas que efectivamente
        entregaron datos: si contara también los intentos bloqueados, cada
        reintento alimentaría la ventana y el bloqueo no expiraría nunca.
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
