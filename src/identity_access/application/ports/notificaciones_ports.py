"""Contrato de persistencia para el sistema de notificaciones.

Define las operaciones sobre ``notificaciones`` y ``dispositivos_fcm``
que ``NotificacionService`` necesita. La implementación concreta vive en
``infrastructure/repositories/notificaciones_repository.py``.
"""
from abc import ABC, abstractmethod
from typing import Optional

from src.identity_access.infrastructure.models.enums_models import EnumEstadoEnvio
from src.identity_access.infrastructure.models.notificaciones_model import Notificaciones


class NotificacionesPort(ABC):
    """Interfaz de acceso a datos para notificaciones y dispositivos FCM."""

    @abstractmethod
    def registrar(
        self,
        id_evento: int,
        id_usuario: int,
        id_canal: int,
        mensaje: str,
        estado_envio: EnumEstadoEnvio,
    ) -> Notificaciones:
        """Persiste una nueva notificación en estado inicial.

        Args:
            id_evento: ID del evento de auditoría que origina la notificación.
            id_usuario: ID del usuario destinatario.
            id_canal: ID del canal de envío (1=EMAIL, 2=INTERNO).
            mensaje: Cuerpo del mensaje de la notificación.
            estado_envio: Estado inicial, normalmente ``EN_COLA``.

        Returns:
            Instancia ORM de la notificación con su ID asignado.
        """
        pass

    @abstractmethod
    def actualizar_estado(self, notificacion: Notificaciones, estado: EnumEstadoEnvio) -> None:
        """Actualiza el estado de envío de una notificación existente.

        Args:
            notificacion: Instancia ORM de la notificación a actualizar.
            estado: Nuevo estado (``ENVIADO`` o ``FALLIDO``).
        """
        pass

    @abstractmethod
    def verificar_anti_spam(
        self, id_usuario: int, tipo_evento: int, id_canal: int, ventana_minutos: int
    ) -> bool:
        """Verifica si ya se envió una notificación reciente del mismo tipo y canal.

        Consulta si existe una notificación para el usuario, tipo de evento y canal
        dentro de la ventana de tiempo indicada.

        Args:
            id_usuario: ID del usuario destinatario.
            tipo_evento: ID del tipo de evento a verificar.
            id_canal: ID del canal a verificar (1=EMAIL, 2=INTERNO).
            ventana_minutos: Tamaño de la ventana de tiempo en minutos.

        Returns:
            ``True`` si ya existe una notificación reciente (bloquear el envío),
            ``False`` si se puede enviar.
        """
        pass

    @abstractmethod
    def buscar_ultimo_evento_id(self, id_usuario: int, tipo_evento: int) -> Optional[int]:
        """Retorna el ID del evento más reciente para un usuario y tipo de evento.

        Args:
            id_usuario: ID del usuario.
            tipo_evento: ID del tipo de evento a buscar.

        Returns:
            ID del evento más reciente o ``None`` si no existe ninguno.
        """
        pass

    @abstractmethod
    def buscar_estado_cuenta(self, id_usuario: int) -> Optional[int]:
        """Retorna el estado actual de la cuenta del usuario.

        Args:
            id_usuario: ID del usuario a consultar.

        Returns:
            ID del estado de cuenta o ``None`` si el usuario no tiene cuenta.
        """
        pass

    @abstractmethod
    def buscar_fcm_tokens(self, id_usuario: int) -> list[str]:
        """Retorna todos los FCM tokens registrados del usuario.

        Args:
            id_usuario: ID del usuario a consultar.

        Returns:
            Lista de FCM tokens activos. Lista vacía si el usuario no tiene
            dispositivos registrados.
        """
        pass

    @abstractmethod
    def guardar_fcm_token(self, id_usuario: int, token: str, user_agent: Optional[str] = None) -> None:
        """Registra un nuevo dispositivo FCM para el usuario.

        El trigger de la tabla maneja el upsert: si el token ya existe,
        actualiza ``ultimo_uso``; si es nuevo, lo inserta.

        Args:
            id_usuario: ID del usuario propietario del dispositivo.
            token: FCM token del dispositivo.
            user_agent: Header User-Agent del request, identifica el dispositivo.
        """
        pass
