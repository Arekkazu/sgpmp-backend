# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-105: filtros de la bandeja, atender y descartar notificaciones |
"""Router de la bandeja de notificaciones internas del usuario (RF-14, RF-105)."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.notificaciones.listar_notificaciones_use_case import (
    ListarNotificacionesUseCase,
)
from src.identity_access.application.use_cases.notificaciones.marcar_notificacion_leida_use_case import (
    AtenderNotificacionUseCase,
    DescartarNotificacionUseCase,
    MarcarNotificacionLeidaUseCase,
)
from src.identity_access.application.use_cases.notificaciones.marcar_todas_leidas_use_case import (
    MarcarTodasLeidasUseCase,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.repositories.notificacion_repository import (
    SqlAlchemyNotificacionRepository,
)
from src.identity_access.infrastructure.schema.notificacion_schema import (
    AtenderNotificacionDTO,
    MarcadasLeidasResponse,
    NotificacionInternaResponse,
    NotificacionesPaginadasResponse,
)
from src.shared.database import get_db
from src.shared.schemas import ErrorResponse


router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])

NivelFiltro = Literal["CRITICA", "ADVERTENCIA", "INFORMATIVA"]
EstadoFiltro = Literal["NUEVA", "LEIDA", "ATENDIDA", "DESCARTADA"]
ModuloFiltro = Literal["cuentas", "activos", "telemetria", "prediccion", "suministros", "finanzas",
                       "integracion", "reportes", "configuracion"]


@router.get(
    "",
    summary="Listar notificaciones propias (RF-14, RF-105)",
    response_model=NotificacionesPaginadasResponse,
    responses={401: {"model": ErrorResponse}},
)
def listar_notificaciones(
    pagina: int = Query(1, ge=1),
    tamano: int = Query(20, ge=1, le=50),
    solo_no_leidas: bool = Query(False),
    nivel: Optional[NivelFiltro] = Query(None),
    estado: Optional[EstadoFiltro] = Query(None, description="Sin estado: nuevas y leídas (panel principal)"),
    modulo: Optional[ModuloFiltro] = Query(None),
    incluir_archivadas: bool = Query(False, description="Incluye las de más de 90 días"),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    """Bandeja interna paginada del usuario: crítica > advertencia > informativa, luego la más reciente.

    **Acceso:** autenticado (solo ve sus propias notificaciones).

    Sin `estado` lista las nuevas y leídas; lo atendido o descartado se consulta con ese estado. Los
    filtros se combinan; un valor fuera de su lista responde 400.
    """
    resultado = ListarNotificacionesUseCase(
        SqlAlchemyNotificacionRepository(db)
    ).execute(
        id_usuario=usuario_actual.id_usuario,
        pagina=pagina,
        tamano=tamano,
        solo_no_leidas=solo_no_leidas,
        nivel=nivel,
        estado=estado,
        modulo=modulo,
        incluir_archivadas=incluir_archivadas,
    )
    return NotificacionesPaginadasResponse(**resultado)


@router.patch(
    "/leidas",
    response_model=MarcadasLeidasResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Marcar como leídas todas las notificaciones propias (T-08)",
)
def marcar_todas_leidas(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> MarcadasLeidasResponse:
    """Marca como leídas todas las notificaciones pendientes del usuario autenticado.

    **Acceso:** autenticado. Devuelve cuántas cambiaron.
    """
    cambiadas = MarcarTodasLeidasUseCase(
        notificaciones_repo=SqlAlchemyNotificacionRepository(db),
        db=db,
    ).execute(usuario_actual.id_usuario)
    return MarcadasLeidasResponse(marcadas=cambiadas)


@router.patch(
    "/{id_notificacion}/leida",
    summary="Marcar una notificación como leída (RF-14)",
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
    """Marca como leída una notificación propia.

    **Acceso:** autenticado. Una notificación ajena responde 404.
    """
    return MarcarNotificacionLeidaUseCase(
        notificaciones_repo=SqlAlchemyNotificacionRepository(db),
        db=db,
    ).execute(id_notificacion, usuario_actual.id_usuario)


@router.patch(
    "/{id_notificacion}/atendida",
    summary="Marcar una notificación como atendida (RF-105)",
    response_model=NotificacionInternaResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse},
               404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def marcar_notificacion_atendida(
    id_notificacion: int,
    dto: AtenderNotificacionDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    """Cierra una notificación propia con lo que se hizo.

    **Acceso:** autenticado. En una alerta crítica `accion_documentada` es obligatoria (20+ caracteres
    con contenido; si no, 400). Ya atendida o descartada → 422. Ajena → 404.
    """
    return AtenderNotificacionUseCase(
        notificaciones_repo=SqlAlchemyNotificacionRepository(db),
        db=db,
    ).execute(id_notificacion, usuario_actual.id_usuario, dto.accion_documentada)


@router.patch(
    "/{id_notificacion}/descartada",
    summary="Descartar una notificación (RF-105)",
    response_model=NotificacionInternaResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def descartar_notificacion(
    id_notificacion: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    """Saca una advertencia o informativa del panel principal; sigue en el historial.

    **Acceso:** autenticado. Una alerta crítica no se descarta (422: se cierra atendiéndola). Ajena → 404.
    """
    return DescartarNotificacionUseCase(
        notificaciones_repo=SqlAlchemyNotificacionRepository(db),
        db=db,
    ).execute(id_notificacion, usuario_actual.id_usuario)
