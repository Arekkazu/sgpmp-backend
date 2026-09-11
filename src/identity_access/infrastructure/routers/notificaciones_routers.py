"""Router de la bandeja de notificaciones internas del usuario."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.notificaciones.listar_notificaciones_use_case import (
    ListarNotificacionesUseCase,
)
from src.identity_access.application.use_cases.notificaciones.marcar_notificacion_leida_use_case import (
    MarcarNotificacionLeidaUseCase,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.repositories.notificacion_repository import (
    SqlAlchemyNotificacionRepository,
)
from src.identity_access.infrastructure.schema.notificacion_schema import (
    NotificacionInternaResponse,
    NotificacionesPaginadasResponse,
)
from src.shared.database import get_db
from src.shared.schemas import ErrorResponse


router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])


@router.get(
    "",
    response_model=NotificacionesPaginadasResponse,
    responses={401: {"model": ErrorResponse}},
)
def listar_notificaciones(
    pagina: int = Query(1, ge=1),
    tamano: int = Query(20, ge=1, le=50),
    solo_no_leidas: bool = Query(False),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    resultado = ListarNotificacionesUseCase(
        SqlAlchemyNotificacionRepository(db)
    ).execute(
        id_usuario=usuario_actual.id_usuario,
        pagina=pagina,
        tamano=tamano,
        solo_no_leidas=solo_no_leidas,
    )
    return NotificacionesPaginadasResponse(**resultado)


@router.patch(
    "/{id_notificacion}/leida",
    response_model=NotificacionInternaResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def marcar_notificacion_leida(
    id_notificacion: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    return MarcarNotificacionLeidaUseCase(
        notificaciones_repo=SqlAlchemyNotificacionRepository(db),
        db=db,
    ).execute(id_notificacion, usuario_actual.id_usuario)
