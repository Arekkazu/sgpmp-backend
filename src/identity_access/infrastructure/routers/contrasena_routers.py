"""Router FastAPI para el módulo de contraseña (`/contrasena`).

Expone los endpoints de cambio de contraseña (usuario autenticado),
solicitud de recuperación por correo y restablecimiento por token.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.contrasena.cambiar_contrasena_use_case import CambiarContrasenaUseCase
from src.identity_access.application.use_cases.contrasena.restablecer_contrasena_use_case import RestablecerContrasenaUseCase
from src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case import SolicitarRecuperacionUseCase
from src.identity_access.infrastructure.adapters.correo_recuperacion_background_adapter import (
    CorreoRecuperacionBackgroundAdapter,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.dto.contrasena_dto import (
    CambiarContrasenaDTO,
    RestablecerContrasenaDTO,
    SolicitarRecuperacionDTO,
)
from src.identity_access.infrastructure.repositories.cuenta_repository import SqlAlchemyCuentaRepository
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.repositories.intento_anonimo_repository import SqlAlchemyIntentoAnonimoRepository
from src.identity_access.infrastructure.repositories.notificacion_repository import SqlAlchemyNotificacionRepository
from src.identity_access.infrastructure.repositories.sesion_repository import SqlAlchemySesionRepository
from src.identity_access.infrastructure.repositories.usuario_repository import SqlAlchemyUsuarioRepository
from src.shared.database import get_db
from src.shared.notificacion_service import NotificacionService
from src.shared.schemas import ErrorResponse, MessageResponse

router = APIRouter(prefix="/contrasena", tags=["Contraseña"])


@router.put(
    "/usuarios/{id_usuario}",
    summary="Cambiar la contraseña propia (RF-07)",
    response_model=MessageResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        423: {"model": ErrorResponse},
        500: {"model": ErrorResponse, "description": "La contraseña puede quedar actualizada aunque falle el cierre de sesiones (RF-07)."},
    },
)
def cambiar_contrasena(
    id_usuario: int,
    dto: CambiarContrasenaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    """Cambia la contraseña del usuario autenticado verificando la actual.

    **Acceso:** autenticado; `id_usuario` debe ser el propio (403 en otro caso).

    Errores: contraseña actual incorrecta (401), contraseña reutilizada (409),
    cuenta no activa (422), 5 intentos fallidos bloquean el cambio 30 minutos
    (423). Al terminar se cierran todas las sesiones activas del usuario.
    """
    use_case = CambiarContrasenaUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        cuentas_repo=SqlAlchemyCuentaRepository(db),
        sesiones_repo=SqlAlchemySesionRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
        notificacion_service=NotificacionService(port=SqlAlchemyNotificacionRepository(db), db=db),
    )
    use_case.execute(id_usuario, dto, usuario_actual)
    return {"message": "Contraseña actualizada exitosamente. Por seguridad, se han cerrado todas las sesiones activas."}


@router.post(
    "/recuperar",
    summary="Solicitar recuperación de contraseña (RF-08)",
    response_model=MessageResponse,
    status_code=202,
    responses={
        400: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
def solicitar_recuperacion(
    dto: SolicitarRecuperacionDTO,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Envía al correo un enlace para restablecer la contraseña (válido 15 minutos).

    **Acceso:** público.

    Responde siempre el mismo mensaje genérico (202) exista o no el correo, para
    evitar enumeración de usuarios. Limitado a 3 solicitudes por hora por IP (429).
    """
    ip = request.client.host if request.client else "unknown"
    use_case = SolicitarRecuperacionUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        cuentas_repo=SqlAlchemyCuentaRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        intentos_anonimos_repo=SqlAlchemyIntentoAnonimoRepository(db),
        db=db,
        correo_recuperacion_port=CorreoRecuperacionBackgroundAdapter(background_tasks),
    )
    message = use_case.execute(dto, ip)
    return {"message": message}


@router.post(
    "/restablecer",
    summary="Restablecer la contraseña con el token de recuperación (RF-09)",
    response_model=MessageResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        410: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        423: {"model": ErrorResponse},
    },
)
def restablecer_contrasena(dto: RestablecerContrasenaDTO, request: Request, db: Session = Depends(get_db)):
    """Fija una contraseña nueva usando el token recibido por correo.

    **Acceso:** público.

    Errores: token inválido (401), ya usado o contraseña reutilizada (409), token
    expirado (410), demasiados intentos desde la IP (423). El token se destruye
    tras el uso y se cierran todas las sesiones activas.
    """
    ip = request.client.host if request.client else "unknown"
    use_case = RestablecerContrasenaUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        cuentas_repo=SqlAlchemyCuentaRepository(db),
        sesiones_repo=SqlAlchemySesionRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        intentos_anonimos_repo=SqlAlchemyIntentoAnonimoRepository(db),
        db=db,
        notificacion_service=NotificacionService(port=SqlAlchemyNotificacionRepository(db), db=db),
    )
    use_case.execute(dto, ip)
    return {"message": "Contraseña restablecida exitosamente. Ya puedes iniciar sesión con tu nueva contraseña."}
