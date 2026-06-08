"""Router FastAPI para el módulo de contraseña (`/contrasena`).

Expone los endpoints de cambio de contraseña (usuario autenticado),
solicitud de recuperación por correo y restablecimiento por token.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.contrasena.cambiar_contrasena_use_case import CambiarContrasenaUseCase
from src.identity_access.application.use_cases.contrasena.restablecer_contrasena_use_case import RestablecerContrasenaUseCase
from src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case import SolicitarRecuperacionUseCase
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.dto.contrasena_dto import (
    CambiarContrasenaDTO,
    RestablecerContrasenaDTO,
    SolicitarRecuperacionDTO,
)
from src.identity_access.infrastructure.repositories.cuenta_repository import SqlAlchemyCuentaRepository
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.repositories.notificacion_repository import SqlAlchemyNotificacionRepository
from src.identity_access.infrastructure.repositories.sesion_repository import SqlAlchemySesionRepository
from src.identity_access.infrastructure.repositories.sqlalchemy_usuario_repository import SqlAlchemyUsuarioRepository
from src.shared.database import get_db
from src.shared.notificacion_service import NotificacionService
from src.shared.schemas import ErrorResponse, MessageResponse

router = APIRouter(prefix="/contrasena", tags=["Contraseña"])


@router.put(
    "/usuarios/{id_usuario}",
    response_model=MessageResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        423: {"model": ErrorResponse},
    },
)
def cambiar_contrasena(
    id_usuario: int,
    dto: CambiarContrasenaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
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
    response_model=MessageResponse,
    status_code=202,
    responses={
        400: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
def solicitar_recuperacion(dto: SolicitarRecuperacionDTO, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    use_case = SolicitarRecuperacionUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        cuentas_repo=SqlAlchemyCuentaRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
        notificacion_service=NotificacionService(port=SqlAlchemyNotificacionRepository(db), db=db),
    )
    message = use_case.execute(dto, ip)
    return {"message": message}


@router.post(
    "/restablecer",
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
    ip = request.client.host if request.client else "unknown"
    use_case = RestablecerContrasenaUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        cuentas_repo=SqlAlchemyCuentaRepository(db),
        sesiones_repo=SqlAlchemySesionRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
        notificacion_service=NotificacionService(port=SqlAlchemyNotificacionRepository(db), db=db),
    )
    use_case.execute(dto, ip)
    return {"message": "Contraseña restablecida exitosamente. Ya puedes iniciar sesión con tu nueva contraseña."}
