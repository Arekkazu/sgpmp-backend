from abc import ABC, abstractmethod
from typing import Optional

from src.identity_access.infrastructure.models.permisos_model import Permisos


class PermisosPort(ABC):

    @abstractmethod
    def listar_por_rol(self, id_rol: int) -> list[Permisos]:
        pass

    @abstractmethod
    def buscar(self, id_rol: int, id_recurso: int, id_accion: int) -> Optional[Permisos]:
        pass

    @abstractmethod
    def asignar(self, id_rol: int, id_recurso: int, id_accion: int, nombre_rol: str) -> Permisos:
        pass

    @abstractmethod
    def retirar(self, permiso: Permisos) -> None:
        pass

    @abstractmethod
    def existe_recurso(self, id_recurso: int) -> bool:
        pass

    @abstractmethod
    def existe_accion(self, id_accion: int) -> bool:
        pass

    @abstractmethod
    def buscar_por_id(self, id_permiso: int) -> Optional[Permisos]:
        pass
