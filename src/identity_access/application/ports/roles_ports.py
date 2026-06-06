from abc import ABC, abstractmethod
from typing import Optional

from src.identity_access.infrastructure.models.roles_model import Roles


class RolesPort(ABC):

    @abstractmethod
    def listar(self) -> list[Roles]:
        pass

    @abstractmethod
    def buscar_por_id(self, id_rol: int) -> Optional[Roles]:
        pass

    @abstractmethod
    def contar_usuarios_por_rol(self, id_rol: int) -> int:
        pass

    @abstractmethod
    def crear_con_sp(self, nombre_rol: str, descripcion: Optional[str], permisos_json: list[dict]) -> int:
        """Llama sp_crear_rol. Retorna el id_rol creado."""
        pass

    @abstractmethod
    def editar(self, rol: Roles, nombre_rol: Optional[str], descripcion: Optional[str]) -> None:
        pass

    @abstractmethod
    def eliminar(self, rol: Roles) -> None:
        pass
