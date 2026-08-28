"""Puerto de persistencia del agregado ``Usuario`` (capa de dominio).

Define el contrato que la capa de aplicación usa para leer y guardar usuarios,
expresado **en términos del dominio**: recibe y devuelve la entidad
:class:`Usuario` y el value object :class:`Email`, nunca modelos ORM ni filas.
La implementación concreta vive en infraestructura
(``infrastructure/repositories/usuario_repository.py``) y es la única
que conoce SQLAlchemy.

Este puerto vive en ``domain/`` —y no en ``application/ports/``— para respetar
la regla de dependencias: el dominio declara lo que necesita y la
infraestructura lo implementa, de modo que las flechas siempre apuntan hacia
adentro (infraestructura → aplicación → dominio).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.identity_access.domain.entities.usuario import Usuario
from src.identity_access.domain.entities.usuario_detalle import UsuarioDetalle
from src.identity_access.domain.value_objects.email import Email


class UsuarioRepository(ABC):
    """Contrato de acceso a datos para el agregado :class:`Usuario`."""

    @abstractmethod
    def obtener_por_id(self, id_usuario: int) -> Optional[Usuario]:
        """Obtiene un usuario por su identidad.

        Args:
            id_usuario: Identidad del usuario a buscar.

        Returns:
            La entidad :class:`Usuario` o ``None`` si no existe.
        """
        raise NotImplementedError

    @abstractmethod
    def obtener_por_correo(self, correo: Email) -> Optional[Usuario]:
        """Obtiene un usuario por su correo electrónico.

        Args:
            correo: Correo a buscar (value object ya validado).

        Returns:
            La entidad :class:`Usuario` o ``None`` si no existe.
        """
        raise NotImplementedError

    @abstractmethod
    def guardar(self, usuario: Usuario) -> Usuario:
        """Persiste un usuario y devuelve la entidad con su identidad asignada.

        No emite ``commit``: la operación queda dentro de la transacción que el
        caso de uso controla (hace ``flush`` interno). Tras guardar, la entidad
        devuelta trae ``id_usuario`` y ``version`` poblados por la base de datos.

        Args:
            usuario: Entidad a persistir. Si ``id_usuario`` es ``None`` se inserta.

        Returns:
            La entidad persistida, re-hidratada desde la base de datos.

        Raises:
            ConflictError: Si el correo o el número de identificación ya existen.
                HTTP 409.
        """
        raise NotImplementedError

    @abstractmethod
    def cambiar_contrasena(self, usuario: Usuario) -> None:
        """Persiste la nueva contraseña del usuario (hace ``flush``, sin ``commit``).

        Espera la entidad con la contraseña ya reemplazada por la nueva. No emite
        ``commit``: la transacción la controla el caso de uso.

        Args:
            usuario: Entidad cuya contraseña ya fue reemplazada por la nueva.

        Raises:
            ConflictError: Si la nueva contraseña fue usada recientemente (un
                trigger de base de datos rechaza la reutilización). HTTP 409.
        """
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, usuario: Usuario, version_cliente: int) -> Usuario:
        """Actualiza los datos del usuario con control de concurrencia optimista.

        Verifica que ``version_cliente`` coincida con la versión actual del
        registro antes de escribir. Hace ``flush``, sin ``commit``.

        Args:
            usuario: Entidad con los campos ya modificados (nombre, apellidos,
                correo, teléfono, dirección, rol).
            version_cliente: Versión del registro que el cliente leyó previamente.

        Returns:
            La entidad re-hidratada desde la base de datos (versión incrementada).

        Raises:
            PreconditionFailedError: Si ``version_cliente`` no coincide con la
                versión actual en DB. HTTP 412.
            ConflictError: Si el nuevo correo ya pertenece a otra cuenta. HTTP 409.
        """
        raise NotImplementedError

    @abstractmethod
    def obtener_detalle(self, id_usuario: int) -> Optional[UsuarioDetalle]:
        """Obtiene la proyección de lectura de un usuario (con rol y estado resueltos).

        Args:
            id_usuario: Identidad del usuario a consultar.

        Returns:
            El :class:`UsuarioDetalle` o ``None`` si no existe.
        """
        raise NotImplementedError

    @abstractmethod
    def listar_detalle(
        self,
        nombre: Optional[str],
        correo: Optional[str],
        id_estado: Optional[int],
        id_rol: Optional[int],
        offset: int,
        limit: int,
        estado_cuenta: Optional[str] = None,
        actualizado_desde: Optional[datetime] = None,
    ) -> list[UsuarioDetalle]:
        """Retorna una página de proyecciones de lectura aplicando filtros opcionales.

        Ordenada por ``fecha_registro`` descendente (más reciente primero).

        Args:
            nombre: Filtro parcial por nombre o apellidos (ILIKE).
            correo: Filtro parcial por correo electrónico (ILIKE).
            id_estado: Filtro exacto por id de estado de cuenta.
            id_rol: Filtro exacto por rol.
            offset: Registros a saltar.
            limit: Máximo de registros a retornar.
            estado_cuenta: Filtro exacto por nombre de estado de cuenta
                (case-insensitive), resuelto contra el catálogo
                ``modulo1.estados_cuentas``. Puede combinarse con ``id_estado``.
            actualizado_desde: Si se indica, solo retorna usuarios cuya
                ``fecha_actualizacion`` o ``fecha_cambio_estado`` de cuenta sea
                posterior a este instante — soporta el polling incremental del
                mecanismo de refresco de ``GET /usuarios/admin``.

        Returns:
            Lista de :class:`UsuarioDetalle` que cumplen los filtros.
        """
        raise NotImplementedError

    @abstractmethod
    def contar(
        self,
        nombre: Optional[str],
        correo: Optional[str],
        id_estado: Optional[int],
        id_rol: Optional[int],
        estado_cuenta: Optional[str] = None,
        actualizado_desde: Optional[datetime] = None,
    ) -> int:
        """Cuenta el total de usuarios que cumplen los filtros (para paginar)."""
        raise NotImplementedError

    @abstractmethod
    def listar_ids_con_permiso(self, id_recurso: int, id_accion: int) -> list[int]:
        """Retorna los IDs de usuarios activos cuyo rol tiene ese permiso activo.

        Permite dirigir una notificación al conjunto de destinatarios correcto sin
        codificar un ``id_rol`` concreto: quién recibe la alerta se decide en
        ``modulo1.permisos``, igual que el acceso a los endpoints.

        Args:
            id_recurso: ID del recurso (tabla ``modulo1.recursos``).
            id_accion: ID de la acción (tabla ``modulo1.acciones``).

        Returns:
            Lista de ``id_usuario`` ordenada ascendentemente; vacía si nadie califica.
        """
        raise NotImplementedError
