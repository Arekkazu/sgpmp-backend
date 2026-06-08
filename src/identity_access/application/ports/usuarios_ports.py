"""Contrato de persistencia para el agregado de usuarios.

Define las operaciones de lectura y escritura sobre la tabla ``usuarios``
que los use cases necesitan. La implementación concreta vive en
``infrastructure/repositories/usuarios_repository.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.identity_access.infrastructure.dto.usuario_dto import UsuarioCreateDTO
from src.identity_access.infrastructure.models.usuarios_model import Usuarios


class UsuariosPort(ABC):
    """Interfaz de acceso a datos para el agregado ``Usuarios``."""

    @abstractmethod
    def create_usuario(self, dto: UsuarioCreateDTO) -> Usuarios:
        """Persiste un nuevo usuario en la base de datos.

        Args:
            dto: DTO con los datos validados del nuevo usuario.

        Returns:
            Instancia ORM del usuario recién creado con su ``id_usuario`` asignado.
        """
        pass

    @abstractmethod
    def buscar_por_correo(self, correo_electronico: str) -> Optional[Usuarios]:
        """Busca un usuario por su dirección de correo electrónico.

        Args:
            correo_electronico: Correo a buscar (case-insensitive según la DB).

        Returns:
            Instancia ORM del usuario o ``None`` si no existe.
        """
        pass

    @abstractmethod
    def buscar_por_id(self, id_usuario: int) -> Optional[Usuarios]:
        """Busca un usuario por su clave primaria.

        Args:
            id_usuario: ID del usuario a buscar.

        Returns:
            Instancia ORM del usuario o ``None`` si no existe.
        """
        pass

    @abstractmethod
    def actualizar_usuario(self, usuario: Usuarios, cambios: dict, version_cliente: int) -> Usuarios:
        """Aplica cambios a un usuario con control de concurrencia optimista.

        Verifica que ``version_cliente`` coincida con la versión actual del
        registro antes de escribir. Si hay discrepancia, lanza
        ``PreconditionFailedError``.

        Args:
            usuario: Instancia ORM del usuario a modificar.
            cambios: Diccionario ``{campo: nuevo_valor}`` con los campos a actualizar.
            version_cliente: Versión del registro que el cliente leyó previamente.

        Returns:
            Instancia ORM actualizada del usuario.

        Raises:
            PreconditionFailedError: Si ``version_cliente`` no coincide con la
                versión actual en DB. HTTP 412.
        """
        pass

    @abstractmethod
    def verificar_rol_existe(self, id_rol: int) -> bool:
        """Verifica si un rol existe en la tabla ``roles``.

        Args:
            id_rol: ID del rol a verificar.

        Returns:
            ``True`` si el rol existe, ``False`` en caso contrario.
        """
        pass

    @abstractmethod
    def cambiar_contrasena(self, usuario: Usuarios, nuevo_hash: str) -> None:
        """Actualiza el hash de contraseña del usuario.

        Args:
            usuario: Instancia ORM del usuario al que se le cambia la contraseña.
            nuevo_hash: Hash bcrypt de la nueva contraseña.
        """
        pass

    @abstractmethod
    def listar_paginado(
        self,
        nombre: Optional[str],
        correo: Optional[str],
        id_estado: Optional[int],
        id_rol: Optional[int],
        offset: int,
        limit: int,
    ) -> list[Usuarios]:
        """Retorna una página de usuarios aplicando filtros opcionales.

        Args:
            nombre: Filtro parcial por nombre o apellidos (ILIKE).
            correo: Filtro parcial por correo electrónico (ILIKE).
            id_estado: Filtro exacto por estado de cuenta.
            id_rol: Filtro exacto por rol.
            offset: Número de registros a saltar.
            limit: Número máximo de registros a retornar.

        Returns:
            Lista de instancias ORM de usuarios que cumplen los filtros.
        """
        pass

    @abstractmethod
    def contar(
        self,
        nombre: Optional[str],
        correo: Optional[str],
        id_estado: Optional[int],
        id_rol: Optional[int],
    ) -> int:
        """Cuenta el total de usuarios que cumplen los filtros dados.

        Se usa junto con ``listar_paginado`` para calcular el total de páginas.

        Args:
            nombre: Filtro parcial por nombre o apellidos.
            correo: Filtro parcial por correo electrónico.
            id_estado: Filtro exacto por estado de cuenta.
            id_rol: Filtro exacto por rol.

        Returns:
            Número total de usuarios que coinciden con los filtros.
        """
        pass
