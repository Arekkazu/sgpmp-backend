"""Puerto de persistencia del agregado ``Permiso`` (capa de dominio).

Contrato para leer y escribir permisos RBAC, expresado en términos del dominio:
recibe y devuelve la entidad :class:`Permiso`, nunca modelos ORM. La
implementación concreta vive en
``infrastructure/repositories/permiso_repository.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.identity_access.domain.entities.permiso import Permiso


class PermisoRepository(ABC):
    """Contrato de acceso a datos para el agregado :class:`Permiso`."""

    @abstractmethod
    def listar_por_rol(self, id_rol: int) -> list[Permiso]:
        """Retorna los permisos de un rol, ordenados por recurso y acción."""
        raise NotImplementedError

    @abstractmethod
    def buscar(self, id_rol: int, id_recurso: int, id_accion: int) -> Optional[Permiso]:
        """Busca un permiso por la combinación rol + recurso + acción."""
        raise NotImplementedError

    @abstractmethod
    def buscar_por_id(self, id_permiso: int) -> Optional[Permiso]:
        """Obtiene un permiso por su identidad, o ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def existe_recurso(self, id_recurso: int) -> bool:
        """Indica si el recurso existe en el catálogo."""
        raise NotImplementedError

    @abstractmethod
    def existe_accion(self, id_accion: int) -> bool:
        """Indica si la acción existe en el catálogo."""
        raise NotImplementedError

    @abstractmethod
    def asignar(self, id_rol: int, id_recurso: int, id_accion: int, nombre_rol: str) -> Permiso:
        """Crea y persiste un permiso para el rol indicado (hace ``flush``, sin ``commit``).

        Args:
            id_rol: Rol al que se asigna el permiso.
            id_recurso: Recurso protegido.
            id_accion: Acción permitida.
            nombre_rol: Nombre del rol, usado para componer el nombre del permiso.

        Returns:
            La entidad :class:`Permiso` recién creada.

        Raises:
            ConflictError: Si el rol ya tiene ese permiso. HTTP 409.
            BusinessRuleError: Si se intenta asignar un permiso administrativo a otro rol. HTTP 422.
        """
        raise NotImplementedError

    @abstractmethod
    def retirar(self, permiso: Permiso) -> None:
        """Elimina un permiso (hace ``flush``, sin ``commit``).

        Args:
            permiso: Entidad del permiso a eliminar.

        Raises:
            BusinessRuleError: Si dejaría al rol sin permisos o es un permiso
                administrativo inmutable. HTTP 422.
        """
        raise NotImplementedError
