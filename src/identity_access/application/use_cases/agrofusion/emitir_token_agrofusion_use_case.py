"""Caso de uso: emisión de JWT sgpmp para el Hub de AgroFusion (`GET_AUTHORIZATION`).

Sin contraseña ni handoff RS256: la confianza la da el secreto compartido
``client_id``/``client_secret``, ya verificado por el router
(``verify_agrofusion_client``) antes de instanciar este use case. Reutiliza
``sesion_comun`` para no duplicar la emisión de sesión/JWT.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.sesiones.sesion_comun import (
    emitir_sesion,
    verificar_estado_cuenta,
)
from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.sesion_repository import SesionRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.email import Email
from src.shared.errors import NotFoundError

TIPO_LOGIN_EXITOSO = 3


class EmitirTokenAgroFusionUseCase:
    """Emite un JWT sgpmp normal para un usuario ya existente, sin contraseña."""

    def __init__(
        self,
        usuarios_repo: UsuarioRepository,
        cuentas_repo: CuentaRepository,
        sesiones_repo: SesionRepository,
        eventos_repo: EventoRepository,
        db: Session,
    ):
        self.usuarios_repo = usuarios_repo
        self.cuentas_repo = cuentas_repo
        self.sesiones_repo = sesiones_repo
        self.eventos_repo = eventos_repo
        self.db = db

    def execute(self, email: str, ip: str, user_agent: str) -> tuple[str, int]:
        """Emite un JWT sgpmp válido para el correo indicado.

        Args:
            email: Correo del usuario sgpmp para el que el Hub solicita un token.
            ip: Dirección IP de origen de la llamada M2M.
            user_agent: Cadena User-Agent de la llamada M2M.

        Returns:
            Tupla ``(jwt_str, expires_in_segundos)``.

        Raises:
            NotFoundError: No existe una cuenta sgpmp con ese correo. HTTP 404.
            LockedError: La cuenta está bloqueada temporalmente. HTTP 423.
            AuthorizationError: La cuenta está pendiente, inactiva o eliminada. HTTP 403.
        """
        usuario = self.usuarios_repo.obtener_por_correo(Email(email))
        if usuario is None:
            raise NotFoundError(
                code="USUARIO_NO_ENCONTRADO",
                message="No existe una cuenta sgpmp asociada a ese correo.",
            )

        cuenta = self.cuentas_repo.obtener_por_usuario(usuario.id_usuario)
        ahora = datetime.now(timezone.utc)
        verificar_estado_cuenta(cuenta, usuario, self.cuentas_repo, self.db, ahora)

        jwt_str, fecha_expiracion, _ = emitir_sesion(
            usuario=usuario,
            cuenta=cuenta,
            ip=ip,
            user_agent=user_agent,
            tipo_evento_exitoso=TIPO_LOGIN_EXITOSO,
            sesiones_repo=self.sesiones_repo,
            cuentas_repo=self.cuentas_repo,
            eventos_repo=self.eventos_repo,
            db=self.db,
            ahora=ahora,
            detalle_extra={"mecanismo": "agrofusion_m2m"},
        )

        expira_en = int((fecha_expiracion - ahora).total_seconds())
        return jwt_str, expira_en
