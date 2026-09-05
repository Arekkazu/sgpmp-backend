"""Puerto del sistema de notificaciones (capa de dominio).

Operaciones de comando y consulta para notificaciones y dispositivos FCM,
expresadas sin tipos de infraestructura: el estado de envío viaja como texto
(``'en_cola'`` / ``'enviado'`` / ``'fallido'``) y las notificaciones se
referencian por su ``id``. La implementación concreta vive en
``infrastructure/repositories/notificacion_repository.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.identity_access.domain.entities.notificacion import Notificacion


class NotificacionRepository(ABC):
    """Contrato de acceso a datos para notificaciones y dispositivos FCM."""

    @abstractmethod
    def registrar(
        self,
        id_evento: int,
        id_usuario: int,
        id_canal: int,
        mensaje: str,
        estado: str,
    ) -> int:
        """Persiste una notificación nueva y devuelve su identidad.

        Args:
            id_evento: Evento de auditoría que origina la notificación.
            id_usuario: Usuario destinatario.
            id_canal: Canal de envío (1=EMAIL, 2=INTERNO).
            mensaje: Cuerpo del mensaje.
            estado: Estado inicial como texto, normalmente ``'en_cola'``.

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
        solo_no_leidas: bool,
        offset: int,
        limit: int,
    ) -> list[Notificacion]:
        """Retorna una página de notificaciones internas del usuario."""
        raise NotImplementedError

    @abstractmethod
    def contar_internas(self, id_usuario: int, solo_no_leidas: bool) -> int:
        """Cuenta las notificaciones internas del usuario."""
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
    def guardar(self, notificacion: Notificacion) -> None:
        """Persiste el estado de lectura de una notificación interna."""
        raise NotImplementedError
