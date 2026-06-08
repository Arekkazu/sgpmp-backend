"""Router FastAPI para el módulo de sesiones (`/sesiones`).

Expone los endpoints de inicio y cierre de sesión con JWT.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.sesiones.login_use_case import LoginUseCase
from src.identity_access.application.use_cases.sesiones.logout_use_case import LogoutUseCase
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.dto.usuario_dto import LoginDTO
from src.identity_access.infrastructure.repositories.cuenta_repository import SqlAlchemyCuentaRepository
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.repositories.notificacion_repository import SqlAlchemyNotificacionRepository
from src.identity_access.infrastructure.repositories.sesion_repository import SqlAlchemySesionRepository
from src.identity_access.infrastructure.repositories.sqlalchemy_usuario_repository import SqlAlchemyUsuarioRepository
from src.identity_access.infrastructure.schema.user_schema import LoginResponse
from src.shared.database import get_db
from src.shared.notificacion_service import NotificacionService
from src.shared.schemas import ErrorResponse, MessageResponse

router = APIRouter(prefix="/sesiones", tags=["Sesiones"])


@router.post(
    "/",
    response_model=LoginResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        423: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def iniciar_sesion(dto: LoginDTO, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    use_case = LoginUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        cuentas_repo=SqlAlchemyCuentaRepository(db),
        sesiones_repo=SqlAlchemySesionRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
        notificacion_service=NotificacionService(port=SqlAlchemyNotificacionRepository(db), db=db),
    )
    jwt_str, fecha_expiracion, sesion_previa_cerrada, _ = use_case.execute(dto, ip, user_agent)

    ahora = datetime.now(timezone.utc)
    expira_en = int((fecha_expiracion - ahora).total_seconds())

    if sesion_previa_cerrada:
        message = "Sesión iniciada exitosamente. Se ha cerrado automáticamente la sesión activa en otros dispositivos por políticas de seguridad de sesión única."
    else:
        message = "Sesión iniciada exitosamente."

    return LoginResponse(token=jwt_str, expira_en=expira_en, message=message)


@router.delete(
    "/",
    response_model=MessageResponse,
    responses={
        401: {"model": ErrorResponse},
    },
)
def cerrar_sesion(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    use_case = LogoutUseCase(
        sesiones_repo=SqlAlchemySesionRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
    )
    use_case.execute(id_token=usuario_actual.id_token, id_usuario=usuario_actual.id_usuario)
    return {"message": "Sesión cerrada exitosamente."}
