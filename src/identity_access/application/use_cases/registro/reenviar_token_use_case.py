"""Caso de uso: reenvío del token de activación de cuenta.

Genera un nuevo token, lo guarda en la cuenta PENDIENTE y envía el correo.
Valida que el correo corresponda a una cuenta que aún puede activarse.
"""
import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.domain.value_objects.token_un_solo_uso import calcular_hash_token
from src.identity_access.infrastructure.dto.usuario_dto import ReenviarTokenDTO
from src.identity_access.infrastructure.email_templates import activation_email
from src.shared.email import send_email
from src.shared.errors import FlowError, ValidationError


class ReenviarTokenUseCase:
    """Orquesta el reenvío del correo de activación con un token nuevo."""

    def __init__(
        self,
        cuentas_repo: CuentaRepository,
        usuarios_repo: UsuarioRepository,
        db: Session,
    ):
        """Inicializa el use case.

        Args:
            cuentas_repo: Repositorio de dominio del agregado Cuenta.
            usuarios_repo: Repositorio de dominio del agregado Usuario (busca por correo).
            db: Sesión SQLAlchemy activa del request.
        """
        self.cuentas_repo = cuentas_repo
        self.usuarios_repo = usuarios_repo
        self.db = db

    def execute(self, dto: ReenviarTokenDTO) -> None:
        """Genera un nuevo token de activación y lo envía por correo.

        Args:
            dto: Correo electrónico del usuario que solicita el reenvío.

        Raises:
            ValidationError: Si no existe una cuenta con ese correo. HTTP 400.
            FlowError: Si la cuenta ya está activa o no admite reenvío. HTTP 422.
        """
        usuario = self.usuarios_repo.obtener_por_correo(Email(dto.correo_electronico))
        if usuario is None:
            raise ValidationError(
                code="CORREO_NO_REGISTRADO",
                message="No existe una cuenta asociada a ese correo electrónico.",
                field="correo_electronico",
            )

        cuenta = self.cuentas_repo.obtener_por_usuario(usuario.id_usuario)
        if cuenta.esta_activa():
            raise FlowError(
                code="CUENTA_YA_ACTIVA",
                message="La cuenta ya está activa. Puedes iniciar sesión directamente.",
            )
        if not cuenta.esta_pendiente():
            raise FlowError(
                code="ESTADO_CUENTA_INVALIDO",
                message="La cuenta no puede recibir un nuevo token en su estado actual.",
            )

        token = secrets.token_urlsafe(32)
        ahora = datetime.now(timezone.utc)
        try:
            cuenta.asignar_token_activacion(calcular_hash_token(token), ahora)
            self.cuentas_repo.guardar(cuenta)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        send_email(
            to=dto.correo_electronico,
            subject="Nuevo token de activación - SGPMP",
            html_body=activation_email(usuario.nombre, token),
        )
