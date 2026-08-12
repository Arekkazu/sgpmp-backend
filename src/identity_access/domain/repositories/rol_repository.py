"""Puerto de persistencia del agregado ``Rol`` (capa de dominio).

Contrato que la capa de aplicación usa para leer y guardar roles, expresado en
términos del dominio: recibe y devuelve la entidad :class:`Rol`, nunca modelos
ORM. La implementación concreta vive en
``infrastructure/repositories/rol_repository.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.identity_access.domain.entities.rol import Rol


class RolRepository(ABC):
    """Contrato de acceso a datos para el agregado :class:`Rol`."""

    @abstractmethod
    def listar(self) -> list[Rol]:
        """Retorna todos los roles, ordenados por ``id_rol``."""
        raise NotImplementedError

    @abstractmethod
    def obtener_por_id(self, id_rol: int) -> Optional[Rol]:
        """Obtiene un rol por su identidad, o ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def obtener_por_nombre(self, nombre_rol: str) -> Optional[Rol]:
        """Obtiene un rol por su nombre (match exacto case-insensitive), o ``None``.

        Usado por la sincronización server-to-server de AgroFusion para
        resolver el ``rol_codigo`` que envía el Hub contra ``modulo1.roles``.
        """
        raise NotImplementedError

    @abstractmethod
    def contar_usuarios(self, id_rol: int) -> int:
        """Cuenta cuántos usuarios tienen asignado el rol indicado."""
        raise NotImplementedError

    @abstractmethod
    def crear_con_sp(self, nombre_rol: str, descripcion: Optional[str], permisos: list[dict]) -> int:
        """Crea un rol con sus permisos iniciales vía el stored procedure ``sp_crear_rol``.

        Args:
            nombre_rol: Nombre único del nuevo rol.
            descripcion: Descripción opcional.
            permisos: Lista de dicts ``{id_recurso, id_accion}`` con los permisos iniciales.

        Returns:
            ID del rol recién creado.

        Raises:
            ConflictError: Si el nombre de rol ya existe. HTTP 409.
            ValidationError: Si no se envía ningún permiso o un recurso/acción no existe. HTTP 400.
        """
        raise NotImplementedError

    @abstractmethod
    def guardar(self, rol: Rol) -> Rol:
        """Persiste los cambios de un rol existente (nombre/descripción).

        No emite ``commit`` (hace ``flush``). El alta usa :meth:`crear_con_sp`.

        Args:
            rol: Entidad con ``id_rol`` asignado y los campos ya modificados.

        Returns:
            La entidad re-hidratada desde la base de datos.

        Raises:
            BusinessRuleError: Si el rol es protegido y no admite el cambio. HTTP 422.
            ConflictError: Si el nuevo nombre ya está en uso. HTTP 409.
        """
        raise NotImplementedError

    @abstractmethod
    def eliminar(self, rol: Rol) -> None:
        """Elimina un rol del sistema (hace ``flush``, sin ``commit``).

        Args:
            rol: Entidad del rol a eliminar.

        Raises:
            BusinessRuleError: Si el rol es protegido o tiene usuarios asignados. HTTP 422.
        """
        raise NotImplementedError
