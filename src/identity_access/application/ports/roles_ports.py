"""Contrato de persistencia para el agregado de roles.

Define las operaciones sobre la tabla ``roles`` que los use cases de gestión
de roles necesitan. La implementación concreta vive en
``infrastructure/repositories/roles_repository.py``.
"""
from abc import ABC, abstractmethod
from typing import Optional

from src.identity_access.infrastructure.models.roles_model import Roles


class RolesPort(ABC):
    """Interfaz de acceso a datos para el agregado ``Roles``."""

    @abstractmethod
    def listar(self) -> list[Roles]:
        """Retorna todos los roles registrados en el sistema.

        Returns:
            Lista de instancias ORM de roles, incluyendo roles protegidos.
        """
        pass

    @abstractmethod
    def buscar_por_id(self, id_rol: int) -> Optional[Roles]:
        """Busca un rol por su clave primaria.

        Args:
            id_rol: ID del rol a buscar.

        Returns:
            Instancia ORM del rol o ``None`` si no existe.
        """
        pass

    @abstractmethod
    def contar_usuarios_por_rol(self, id_rol: int) -> int:
        """Cuenta cuántos usuarios tienen asignado un rol específico.

        Se usa para validar que un rol no esté en uso antes de eliminarlo.

        Args:
            id_rol: ID del rol a consultar.

        Returns:
            Número de usuarios que tienen ese rol asignado.
        """
        pass

    @abstractmethod
    def crear_con_sp(self, nombre_rol: str, descripcion: Optional[str], permisos_json: list[dict]) -> int:
        """Crea un rol con sus permisos iniciales usando el stored procedure ``sp_crear_rol``.

        El stored procedure crea el rol y asigna los permisos en una sola
        transacción atómica en la DB.

        Args:
            nombre_rol: Nombre único del nuevo rol.
            descripcion: Descripción opcional del rol.
            permisos_json: Lista de dicts con los permisos iniciales, cada uno
                con las claves ``id_recurso`` e ``id_accion``.

        Returns:
            ID del rol recién creado.
        """
        pass

    @abstractmethod
    def editar(self, rol: Roles, nombre_rol: Optional[str], descripcion: Optional[str]) -> None:
        """Actualiza el nombre y/o descripción de un rol existente.

        Args:
            rol: Instancia ORM del rol a modificar.
            nombre_rol: Nuevo nombre del rol. ``None`` para no modificarlo.
            descripcion: Nueva descripción. ``None`` para no modificarla.
        """
        pass

    @abstractmethod
    def eliminar(self, rol: Roles) -> None:
        """Elimina un rol del sistema.

        Solo debe llamarse tras verificar que el rol no está en uso
        (ver ``contar_usuarios_por_rol``) y que no es un rol protegido.

        Args:
            rol: Instancia ORM del rol a eliminar.
        """
        pass
