"""Contrato de persistencia para el agregado de permisos RBAC.

Define las operaciones sobre la tabla ``permisos`` que los use cases de
gestión de permisos necesitan. Los permisos relacionan un rol con un recurso
y una acción. La implementación concreta vive en
``infrastructure/repositories/permisos_repository.py``.
"""
from abc import ABC, abstractmethod
from typing import Optional

from src.identity_access.infrastructure.models.permisos_model import Permisos


class PermisosPort(ABC):
    """Interfaz de acceso a datos para el agregado ``Permisos``."""

    @abstractmethod
    def listar_por_rol(self, id_rol: int) -> list[Permisos]:
        """Retorna todos los permisos asignados a un rol.

        Args:
            id_rol: ID del rol cuyos permisos se listan.

        Returns:
            Lista de instancias ORM de permisos del rol.
        """
        pass

    @abstractmethod
    def buscar(self, id_rol: int, id_recurso: int, id_accion: int) -> Optional[Permisos]:
        """Busca un permiso específico por la combinación rol + recurso + acción.

        Args:
            id_rol: ID del rol.
            id_recurso: ID del recurso protegido.
            id_accion: ID de la acción sobre el recurso.

        Returns:
            Instancia ORM del permiso o ``None`` si no existe.
        """
        pass

    @abstractmethod
    def asignar(self, id_rol: int, id_recurso: int, id_accion: int, nombre_rol: str) -> Permisos:
        """Asigna un permiso a un rol para un recurso y acción dados.

        Args:
            id_rol: ID del rol al que se asigna el permiso.
            id_recurso: ID del recurso protegido.
            id_accion: ID de la acción permitida.
            nombre_rol: Nombre del rol, usado para el registro de auditoría.

        Returns:
            Instancia ORM del permiso recién creado.
        """
        pass

    @abstractmethod
    def retirar(self, permiso: Permisos) -> None:
        """Elimina un permiso del sistema.

        Args:
            permiso: Instancia ORM del permiso a eliminar.
        """
        pass

    @abstractmethod
    def existe_recurso(self, id_recurso: int) -> bool:
        """Verifica si un recurso existe en la tabla ``recursos``.

        Args:
            id_recurso: ID del recurso a verificar.

        Returns:
            ``True`` si el recurso existe, ``False`` en caso contrario.
        """
        pass

    @abstractmethod
    def existe_accion(self, id_accion: int) -> bool:
        """Verifica si una acción existe en la tabla ``acciones``.

        Args:
            id_accion: ID de la acción a verificar.

        Returns:
            ``True`` si la acción existe, ``False`` en caso contrario.
        """
        pass

    @abstractmethod
    def buscar_por_id(self, id_permiso: int) -> Optional[Permisos]:
        """Busca un permiso por su clave primaria.

        Args:
            id_permiso: ID del permiso a buscar.

        Returns:
            Instancia ORM del permiso o ``None`` si no existe.
        """
        pass
