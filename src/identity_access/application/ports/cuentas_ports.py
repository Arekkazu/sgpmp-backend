"""Contrato de persistencia para el agregado de cuentas de usuario.

Define las operaciones sobre ``cuentas_usuarios`` y ``gestiones_cuenta``
que los use cases necesitan. Separa la lógica de estado de cuenta (bloqueos,
intentos fallidos, tokens) de los datos de identidad del usuario.
La implementación concreta vive en
``infrastructure/repositories/cuentas_repository.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.identity_access.infrastructure.models.cuenta_usuarios_model import CuentasUsuarios


class CuentasPort(ABC):
    """Interfaz de acceso a datos para el agregado ``CuentasUsuarios``."""

    @abstractmethod
    def create_cuenta(self, id_usuario: int, token: str) -> CuentasUsuarios:
        """Crea una nueva cuenta en estado PENDIENTE con token de activación.

        Args:
            id_usuario: ID del usuario al que pertenece la cuenta.
            token: Token de activación generado por el use case.

        Returns:
            Instancia ORM de la cuenta recién creada.
        """
        pass

    @abstractmethod
    def activar_cuenta(self, token: str) -> CuentasUsuarios:
        """Activa una cuenta verificando el token de activación.

        Args:
            token: Token de activación recibido del usuario.

        Returns:
            Instancia ORM de la cuenta activada.

        Raises:
            NotFoundError: Si el token no corresponde a ninguna cuenta.
            GoneError: Si el token ya fue usado o expiró.
        """
        pass

    @abstractmethod
    def reenviar_token(self, correo_electronico: str, nuevo_token: str) -> str:
        """Reemplaza el token de activación de la cuenta asociada al correo.

        Args:
            correo_electronico: Correo del usuario que solicita el reenvío.
            nuevo_token: Nuevo token generado por el use case.

        Returns:
            El nombre del usuario para usar en el email de reenvío.
        """
        pass

    @abstractmethod
    def buscar_cuenta_por_usuario(self, id_usuario: int) -> Optional[CuentasUsuarios]:
        """Busca la cuenta asociada a un usuario por su ID.

        Args:
            id_usuario: ID del usuario propietario de la cuenta.

        Returns:
            Instancia ORM de la cuenta o ``None`` si no existe.
        """
        pass

    @abstractmethod
    def incrementar_intentos_fallidos(self, cuenta: CuentasUsuarios) -> None:
        """Incrementa en uno el contador de intentos de login fallidos.

        Args:
            cuenta: Instancia ORM de la cuenta a actualizar.
        """
        pass

    @abstractmethod
    def bloquear_cuenta(self, cuenta: CuentasUsuarios) -> None:
        """Bloquea la cuenta por exceso de intentos fallidos de login.

        Args:
            cuenta: Instancia ORM de la cuenta a bloquear.
        """
        pass

    @abstractmethod
    def resetear_intentos(self, cuenta: CuentasUsuarios) -> None:
        """Reinicia a cero el contador de intentos fallidos de login.

        Se llama tras un login exitoso.

        Args:
            cuenta: Instancia ORM de la cuenta a actualizar.
        """
        pass

    @abstractmethod
    def actualizar_ultimo_acceso(self, cuenta: CuentasUsuarios) -> None:
        """Registra la marca temporal del último login exitoso.

        Args:
            cuenta: Instancia ORM de la cuenta a actualizar.
        """
        pass

    @abstractmethod
    def poner_cuenta_pendiente(self, cuenta: CuentasUsuarios, nuevo_token: str) -> None:
        """Cambia el estado de la cuenta a PENDIENTE y asigna un nuevo token de verificación.

        Se usa cuando el correo del usuario es modificado y requiere reverificación.

        Args:
            cuenta: Instancia ORM de la cuenta a actualizar.
            nuevo_token: Token de verificación del nuevo correo.
        """
        pass

    @abstractmethod
    def guardar_token_recuperacion(self, cuenta: CuentasUsuarios, token: str) -> None:
        """Persiste el token de recuperación de contraseña en la cuenta.

        Args:
            cuenta: Instancia ORM de la cuenta a actualizar.
            token: Token de recuperación generado por el use case.
        """
        pass

    @abstractmethod
    def buscar_cuenta_por_token_recuperacion(self, token: str) -> Optional[CuentasUsuarios]:
        """Busca una cuenta por su token de recuperación de contraseña activo.

        Args:
            token: Token de recuperación a buscar.

        Returns:
            Instancia ORM de la cuenta o ``None`` si el token no existe o ya fue usado.
        """
        pass

    @abstractmethod
    def incrementar_intentos_cambio_contrasena(self, cuenta: CuentasUsuarios) -> None:
        """Incrementa el contador de intentos fallidos de cambio de contraseña.

        Args:
            cuenta: Instancia ORM de la cuenta a actualizar.
        """
        pass

    @abstractmethod
    def bloquear_cambio_contrasena(self, cuenta: CuentasUsuarios) -> None:
        """Bloquea temporalmente la posibilidad de cambiar contraseña por exceso de intentos.

        Args:
            cuenta: Instancia ORM de la cuenta a bloquear.
        """
        pass

    @abstractmethod
    def resetear_intentos_cambio_contrasena(self, cuenta: CuentasUsuarios) -> None:
        """Reinicia el contador de intentos fallidos de cambio de contraseña.

        Args:
            cuenta: Instancia ORM de la cuenta a actualizar.
        """
        pass

    @abstractmethod
    def registrar_gestion(
        self,
        id_cuenta_usuario: int,
        accion: str,
        motivo: str,
        id_responsable: int,
    ) -> None:
        """Registra una acción administrativa sobre la cuenta en ``gestiones_cuenta``.

        Args:
            id_cuenta_usuario: ID de la cuenta afectada.
            accion: Nombre de la acción realizada (ej: ``"BLOQUEAR"``).
            motivo: Justificación de la acción para auditoría.
            id_responsable: ID del administrador que ejecutó la acción.
        """
        pass

    @abstractmethod
    def contar_admins_activos(self) -> int:
        """Cuenta el número de administradores con cuenta en estado ACTIVO.

        Se usa para proteger al último administrador activo de ser desactivado.

        Returns:
            Número de administradores activos en el sistema.
        """
        pass
