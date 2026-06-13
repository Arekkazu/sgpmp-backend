"""Caso de uso: activación de cuenta mediante token de correo electrónico.

El token fue generado al crear la cuenta o al reenviar el correo de activación.
La validación (token inexistente, expirado o cuenta ya activa) y la transición
de estado se orquestan aquí sobre la entidad :class:`Cuenta`.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.shared.errors import FlowError, GoneError, ValidationError


class ActivarCuentaUseCase:
    """Orquesta la activación de una cuenta a partir de su token de activación."""

    def __init__(self, cuentas_repo: CuentaRepository, db: Session):
        """Inicializa el use case.

        Args:
            cuentas_repo: Repositorio de dominio del agregado Cuenta.
            db: Sesión SQLAlchemy activa del request.
        """
        self.cuentas_repo = cuentas_repo
        self.db = db

    def execute(self, token: str) -> None:
        """Activa la cuenta asociada al token recibido.

        Args:
            token: Token de activación enviado al correo del usuario.

        Raises:
            ValidationError: Si el token no existe o ya fue usado. HTTP 400.
            GoneError: Si el token expiró. HTTP 410.
            FlowError: Si la cuenta ya estaba activa. HTTP 422.
        """
        cuenta = self.cuentas_repo.obtener_por_token(token)
        if cuenta is None:
            raise ValidationError(
                code="TOKEN_INVALIDO",
                message="El token de activación es inválido o inexistente.",
            )

        ahora = datetime.now(timezone.utc)
        if cuenta.token_expirado(ahora):
            expiracion = cuenta.expiracion_token()
            raise GoneError(
                code="TOKEN_EXPIRADO",
                message=f"El token de activación expiró el {expiracion.strftime('%d/%m/%Y')} a las {expiracion.strftime('%H:%M:%S')}. Solicita uno nuevo.",
            )

        if cuenta.esta_activa():
            raise FlowError(
                code="CUENTA_YA_ACTIVA",
                message="La cuenta ya fue activada anteriormente.",
            )

        try:
            cuenta.activar(ahora)
            self.cuentas_repo.guardar(cuenta)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
