from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.identity_access.infrastructure.models.sesiones_model import Sesiones
from src.identity_access.infrastructure.models.tokens_model import Tokens


class SesionesPort(ABC):

    @abstractmethod
    def buscar_sesion_activa(self, id_cuenta_usuario: int) -> Optional[Sesiones]:
        pass

    @abstractmethod
    def buscar_sesion_por_token(self, id_token: int) -> Optional[Sesiones]:
        pass

    @abstractmethod
    def invalidar_sesion(self, sesion: Sesiones) -> None:
        pass

    @abstractmethod
    def crear_token_acceso(self, fecha_expiracion: datetime) -> Tokens:
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
        pass

    @abstractmethod
    def invalidar_todas_sesiones(self, id_cuenta_usuario: int) -> None:
        pass

    @abstractmethod
    def contar_solicitudes_recuperacion_por_ip(self, ip: str, desde: datetime) -> int:
        pass
