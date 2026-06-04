from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.identity_access.infrastructure.dto.usuario_dto import UsuarioCreateDTO
from src.identity_access.infrastructure.models.usuarios_model import Usuarios


class UsuariosPort(ABC):

    @abstractmethod
    def create_usuario(self, dto: UsuarioCreateDTO) -> Usuarios:
        pass

    @abstractmethod
    def buscar_por_correo(self, correo_electronico: str) -> Optional[Usuarios]:
        pass
