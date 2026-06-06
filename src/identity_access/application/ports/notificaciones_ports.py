from abc import ABC, abstractmethod
from typing import Optional

from src.identity_access.infrastructure.models.enums_models import EnumEstadoEnvio
from src.identity_access.infrastructure.models.notificaciones_model import Notificaciones


class NotificacionesPort(ABC):

    @abstractmethod
    def registrar(
        self,
        id_evento: int,
        id_usuario: int,
        id_canal: int,
        mensaje: str,
        estado_envio: EnumEstadoEnvio,
    ) -> Notificaciones:
        pass

    @abstractmethod
    def actualizar_estado(self, notificacion: Notificaciones, estado: EnumEstadoEnvio) -> None:
        pass

    @abstractmethod
    def verificar_anti_spam(
        self, id_usuario: int, tipo_evento: int, id_canal: int, ventana_minutos: int
    ) -> bool:
        """Retorna True si ya existe una notificación reciente (dentro de la ventana)."""
        pass

    @abstractmethod
    def buscar_ultimo_evento_id(self, id_usuario: int, tipo_evento: int) -> Optional[int]:
        """Retorna el id_evento más reciente para ese usuario y tipo."""
        pass

    @abstractmethod
    def buscar_estado_cuenta(self, id_usuario: int) -> Optional[int]:
        """Retorna id_estado_cuenta del usuario."""
        pass

    @abstractmethod
    def buscar_fcm_tokens(self, id_usuario: int) -> list[str]:
        """Retorna todos los FCM tokens registrados del usuario."""
        pass

    @abstractmethod
    def guardar_fcm_token(self, id_usuario: int, token: str, user_agent: Optional[str] = None) -> None:
        pass
