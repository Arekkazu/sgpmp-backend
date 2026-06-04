from __future__ import annotations

from abc import ABC, abstractmethod

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
