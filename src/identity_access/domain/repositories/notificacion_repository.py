# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-105: nivel, agrupación, filtros de bandeja, entrega y purga  |
# | 2026-11-18 | Arekkazu | M08 RF-105: preferencias de canal y ventana de agrupación configurable |
# | 2026-11-21 | destroyerban | INC-M08-383-G014 RF-105: notificación ajena → 403 con el mensaje del RF |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto del sistema de notificaciones (capa de dominio).

Operaciones de comando y consulta para notificaciones y dispositivos FCM,
expresadas sin tipos de infraestructura: el estado de envío viaja como texto
(``'en_cola'`` / ``'enviado'`` / ``'fallido'``) y las notificaciones se
referencian por su ``id``. La implementación concreta vive en
``infrastructure/repositories/notificacion_repository.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from src.identity_access.domain.entities.notificacion import Notificacion
from src.identity_access.domain.value_objects.nivel_notificacion import (
    VENTANA_AGRUPACION_POR_DEFECTO,
    canal_por_defecto,
)


@dataclass(frozen=True)
class FiltroBandeja:
    """Filtros de la bandeja (RF-105). Sin ``estado``: el panel principal (NUEVA y LEÍDA).
    ``desde``: lo anterior está archivado y solo sale si se pide (``None`` = sin corte)."""
    solo_no_leidas: bool = False
    nivel: Optional[str] = None
    estado: Optional[str] = None
    modulo: Optional[str] = None
    desde: Optional[datetime] = None


@dataclass(frozen=True)
class EntregaPendiente:
    """Notificación interna CRÍTICA o ADVERTENCIA cuyo push falta entregar (o reintentar)."""
    id_notificacion: int
    id_evento: int
    id_usuario: int
    mensaje: str
    nivel: str
    intentos_push: int
    modulo: Optional[str]
    contexto: dict[str, Any] = field(default_factory=dict)


class NotificacionRepository(ABC):
    """Contrato de acceso a datos para notificaciones y dispositivos FCM."""

    def canal_habilitado(self, id_usuario: int, nivel: str, canal: str) -> bool:
        """RF-105 R6: si el usuario recibe ``nivel`` por ``canal`` (PUSH o EMAIL). Sin preferencia, el valor
        por defecto del RF."""
        return canal_por_defecto(nivel, canal)

    def ventana_agrupacion_minutos(self) -> int:
        """Minutos en que avisos iguales sobre el mismo animal se agrupan (configurable en M09)."""
        return VENTANA_AGRUPACION_POR_DEFECTO

    def preferencias(self, id_usuario: int) -> dict[tuple[str, str], bool]:
        """Preferencias guardadas del usuario: ``(nivel, canal) → habilitado``."""
        return {}

    def guardar_preferencias(self, id_usuario: int, preferencias: dict[tuple[str, str], bool]) -> None:
        """Guarda las preferencias de canal por nivel del usuario."""
        raise NotImplementedError

    @abstractmethod
    def registrar(
        self,
        id_evento: int,
        id_usuario: int,
        id_canal: int,
        mensaje: str,
        estado: str,
        *,
        nivel: Optional[str] = None,
        id_activo_biologico: Optional[int] = None,
        contexto: Optional[dict[str, Any]] = None,
        entrega_inmediata: bool = False,
    ) -> int:
        """Persiste una notificación nueva y devuelve su identidad.

        Args:
            id_evento: Evento de auditoría que origina la notificación.
            id_usuario: Usuario destinatario.
            id_canal: Canal de envío (1=EMAIL, 2=INTERNO).
            mensaje: Cuerpo del mensaje.
            estado: Estado inicial como texto, normalmente ``'en_cola'``.
            nivel: Nivel sugerido; el definitivo sale del tipo de evento y nunca es más bajo (RF-105).
            id_activo_biologico: Animal o lote al que se refiere, para agrupar (RF-105 Fase 2.1).
            contexto: Datos del origen (``url`` de destino, finca, área); sin ``url`` se usa la del módulo.
            entrega_inmediata: Quien registra envía el push ya; el entregador en segundo plano solo
                lo reintentará si falla.

        Returns:
            El ``id_notificacion`` recién creado.
        """
        raise NotImplementedError

    @abstractmethod
    def actualizar_estado(self, id_notificacion: int, estado: str) -> None:
        """Actualiza el estado de envío de una notificación.

        Args:
            id_notificacion: Identidad de la notificación.
            estado: Nuevo estado como texto (``'enviado'`` o ``'fallido'``).
        """
        raise NotImplementedError

    @abstractmethod
    def verificar_anti_spam(
        self, id_usuario: int, tipo_evento: int, id_canal: int, ventana_minutos: int
    ) -> bool:
        """Indica si ya hubo una notificación reciente del mismo tipo y canal."""
        raise NotImplementedError

    @abstractmethod
    def sumar_ocurrencia(
        self, id_usuario: int, tipo_evento: int, id_activo_biologico: int, ventana_minutos: int
    ) -> bool:
        """Si el usuario tiene una notificación interna abierta del mismo tipo y animal dentro de la
        ventana, le suma una ocurrencia en vez de crear otra (RF-105 CA-9). Devuelve si la sumó."""
        raise NotImplementedError

    @abstractmethod
    def pendientes_de_entrega(self, limite: int) -> list[EntregaPendiente]:
        """Internas CRÍTICA/ADVERTENCIA aún NUEVAS cuyo push está pendiente o toca reintentar.
        Las bloquea hasta el commit para que dos procesos no las entreguen dos veces."""
        raise NotImplementedError

    @abstractmethod
    def registrar_intento_push(
        self, id_notificacion: int, entregada: bool, proximo_intento: Optional[datetime]
    ) -> None:
        """Suma un intento de push: entregado, a reintentar en ``proximo_intento`` o fallido final."""
        raise NotImplementedError

    @abstractmethod
    def purgar_informativas(self, antes_de: datetime) -> int:
        """Borra las internas INFORMATIVAS leídas o descartadas anteriores a la fecha (RF-105 R3)."""
        raise NotImplementedError

    @abstractmethod
    def buscar_ultimo_evento_id(self, id_usuario: int, tipo_evento: int) -> Optional[int]:
        """Retorna el ID del evento más reciente del usuario y tipo dados, o ``None``."""
        raise NotImplementedError

    @abstractmethod
    def buscar_estado_cuenta(self, id_usuario: int) -> Optional[int]:
        """Retorna el ID del estado de cuenta del usuario, o ``None`` si no tiene cuenta."""
        raise NotImplementedError

    @abstractmethod
    def buscar_correo_usuario(self, id_usuario: int) -> Optional[str]:
        """Retorna el correo del usuario, o ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def buscar_fcm_tokens(self, id_usuario: int) -> list[str]:
        """Retorna los FCM tokens registrados del usuario (lista vacía si no hay)."""
        raise NotImplementedError

    @abstractmethod
    def guardar_fcm_token(self, id_usuario: int, token: str, user_agent: Optional[str] = None) -> None:
        """Registra un dispositivo FCM para el usuario."""
        raise NotImplementedError

    @abstractmethod
    def listar_internas(
        self,
        id_usuario: int,
        filtro: FiltroBandeja,
        offset: int,
        limit: int,
    ) -> list[Notificacion]:
        """Página de internas del usuario: CRÍTICA > ADVERTENCIA > INFORMATIVA, luego la más reciente."""
        raise NotImplementedError

    @abstractmethod
    def contar_internas(self, id_usuario: int, filtro: FiltroBandeja) -> int:
        """Cuenta las notificaciones internas del usuario con el filtro."""
        raise NotImplementedError

    @abstractmethod
    def obtener_interna(
        self,
        id_notificacion: int,
        id_usuario: int,
    ) -> Optional[Notificacion]:
        """Obtiene una notificación interna si pertenece al usuario."""
        raise NotImplementedError

    @abstractmethod
    def existe_interna(self, id_notificacion: int) -> bool:
        """Si existe una notificación interna con ese id, sea de quien sea.

        Solo responde sí o no: sirve para distinguir una notificación ajena (403) de una inexistente (404)
        sin leer nada de su contenido (RF-105 restricción 4)."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, notificacion: Notificacion) -> None:
        """Persiste el estado de una notificación interna (lectura, atención, descarte)."""
        raise NotImplementedError

    @abstractmethod
    def marcar_todas_leidas(self, id_usuario: int) -> int:
        """Marca como leídas las notificaciones internas del usuario; devuelve cuántas cambió."""
        raise NotImplementedError
