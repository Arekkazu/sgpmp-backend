from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.identity_access.infrastructure.models.cuenta_usuarios_model import CuentasUsuarios


class CuentasPort(ABC):

    @abstractmethod
    def create_cuenta(self, id_usuario: int, token: str) -> CuentasUsuarios:
        pass

    @abstractmethod
    def activar_cuenta(self, token: str) -> CuentasUsuarios:
        pass

    @abstractmethod
    def reenviar_token(self, correo_electronico: str, nuevo_token: str) -> str:
        pass

    @abstractmethod
    def buscar_cuenta_por_usuario(self, id_usuario: int) -> Optional[CuentasUsuarios]:
        pass

    @abstractmethod
    def incrementar_intentos_fallidos(self, cuenta: CuentasUsuarios) -> None:
        pass

    @abstractmethod
    def bloquear_cuenta(self, cuenta: CuentasUsuarios) -> None:
        pass

    @abstractmethod
    def resetear_intentos(self, cuenta: CuentasUsuarios) -> None:
        pass

    @abstractmethod
    def actualizar_ultimo_acceso(self, cuenta: CuentasUsuarios) -> None:
        pass
