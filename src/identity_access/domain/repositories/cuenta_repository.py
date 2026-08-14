"""Puerto de persistencia del agregado ``Cuenta`` (capa de dominio).

Contrato para leer y escribir cuentas de usuario, expresado en términos del
dominio: recibe y devuelve la entidad :class:`Cuenta`, nunca modelos ORM. La
implementación concreta vive en
``infrastructure/repositories/cuenta_repository.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.identity_access.domain.entities.cuenta import Cuenta


class CuentaRepository(ABC):
    """Contrato de acceso a datos para el agregado :class:`Cuenta`."""

    @abstractmethod
    def crear(self, id_usuario: int, token_hash: str, id_estado_cuenta: Optional[int] = None) -> Cuenta:
        """Crea una cuenta nueva, por defecto en estado PENDIENTE con token de activación.

        Args:
            id_usuario: Usuario propietario de la nueva cuenta.
            token_hash: Hash SHA-256 del token de activación inicial.
            id_estado_cuenta: Estado inicial. Si es ``None`` usa
                :data:`Cuenta.ESTADO_PENDIENTE` (caso normal de autorregistro).
                La provisión mínima SSO lo fija en
                :data:`Cuenta.ESTADO_PENDIENTE_DATOS` directamente por INSERT,
                sin pasar por una transición de estado (evita el trigger de
                validación de transiciones, que no contempla ese origen).

        Returns:
            La entidad :class:`Cuenta` creada, con su identidad asignada.

        Raises:
            ConflictError: Si el usuario ya tiene una cuenta asociada. HTTP 409.
        """
        raise NotImplementedError

    @abstractmethod
    def obtener_por_usuario(self, id_usuario: int) -> Optional[Cuenta]:
        """Obtiene la cuenta de un usuario, o ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def obtener_por_hash_token(self, token_hash: str) -> Optional[Cuenta]:
        """Obtiene la cuenta cuyo hash de token coincide, o ``None``.

        Args:
            token_hash: Hash SHA-256 del token de activación o recuperación.

        Returns:
            La cuenta asociada al hash, o ``None`` si no existe.
        """
        raise NotImplementedError

    @abstractmethod
    def guardar(self, cuenta: Cuenta) -> Cuenta:
        """Persiste los cambios de una cuenta existente (hace ``flush``, sin ``commit``).

        Args:
            cuenta: Entidad con ``id_cuenta_usuario`` asignado y estado ya modificado.

        Returns:
            La entidad re-hidratada desde la base de datos.
        """
        raise NotImplementedError

    @abstractmethod
    def registrar_gestion(
        self,
        id_cuenta_usuario: int,
        accion: str,
        motivo: str,
        id_responsable: int,
    ) -> None:
        """Registra una acción administrativa en ``gestiones_cuenta``.

        Args:
            id_cuenta_usuario: Cuenta afectada.
            accion: Nombre de la acción (valor de ``EnumAccionCuenta``).
            motivo: Justificación para auditoría.
            id_responsable: Administrador que ejecutó la acción.
        """
        raise NotImplementedError

    @abstractmethod
    def contar_admins_activos(self) -> int:
        """Cuenta los administradores con cuenta en estado ACTIVO."""
        raise NotImplementedError
