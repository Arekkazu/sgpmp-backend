# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-105: filtros de la bandeja, atender y descartar notificaciones |
# | 2026-11-18 | Arekkazu | M08 RF-105 R6: preferencias de canal del usuario |
# | 2026-11-21 | destroyerban | INC-M08-382-G013 RF-105: sin tamano la bandeja trae 50 por página |
# | 2026-11-21 | destroyerban | INC-M08-383-G014 RF-105: notificación ajena → 403 con el mensaje del RF |
"""Router de la bandeja de notificaciones internas del usuario (RF-14, RF-105)."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.notificaciones.listar_notificaciones_use_case import (
    TAMANO_PAGINA_BANDEJA,
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
from src.identity_access.application.use_cases.notificaciones.preferencias_notificacion_use_case import (
    ConsultarPreferenciasNotificacionUseCase,
    GuardarPreferenciasNotificacionUseCase,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.repositories.notificacion_repository import (
    SqlAlchemyNotificacionRepository,
)
from src.identity_access.infrastructure.schema.notificacion_schema import (
    AtenderNotificacionDTO,
    GuardarPreferenciasDTO,
    MarcadasLeidasResponse,
    NotificacionInternaResponse,
    NotificacionesPaginadasResponse,
    PreferenciaNotificacionResponse,
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
    tamano: int = Query(TAMANO_PAGINA_BANDEJA, ge=1, le=TAMANO_PAGINA_BANDEJA,
                        description="Notificaciones por página: 50 por defecto y como máximo"),
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
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def marcar_notificacion_leida(
    id_notificacion: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    """Marca como leída una notificación propia.

    **Acceso:** autenticado. Una notificación de otro usuario responde 403 y una inexistente 404.
    """
    return MarcarNotificacionLeidaUseCase(
        notificaciones_repo=SqlAlchemyNotificacionRepository(db),
        db=db,
    ).execute(id_notificacion, usuario_actual.id_usuario)


@router.patch(
    "/{id_notificacion}/atendida",
    summary="Marcar una notificación como atendida (RF-105)",
    response_model=NotificacionInternaResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse},
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
    con contenido; si no, 400). Ya atendida o descartada → 422. De otro usuario → 403; inexistente → 404.
    """
    return AtenderNotificacionUseCase(
        notificaciones_repo=SqlAlchemyNotificacionRepository(db),
        db=db,
    ).execute(id_notificacion, usuario_actual.id_usuario, dto.accion_documentada)


@router.patch(
    "/{id_notificacion}/descartada",
    summary="Descartar una notificación (RF-105)",
    response_model=NotificacionInternaResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
               422: {"model": ErrorResponse}},
)
def descartar_notificacion(
    id_notificacion: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    """Saca una advertencia o informativa del panel principal; sigue en el historial.

    **Acceso:** autenticado. Una alerta crítica no se descarta (422: se cierra atendiéndola). De otro
    usuario → 403; inexistente → 404.
    """
    return DescartarNotificacionUseCase(
        notificaciones_repo=SqlAlchemyNotificacionRepository(db),
        db=db,
    ).execute(id_notificacion, usuario_actual.id_usuario)


@router.get(
    "/preferencias",
    summary="Preferencias de canal por nivel (RF-105)",
    response_model=list[PreferenciaNotificacionResponse],
    responses={401: {"model": ErrorResponse}},
)
def consultar_preferencias(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    """Canales por nivel del usuario autenticado. Sin configurar rigen los valores por defecto: push en crítica y
    advertencia, correo solo en crítica. La bandeja interna siempre está activa.

    **Acceso:** autenticado (solo las propias)."""
    return ConsultarPreferenciasNotificacionUseCase(SqlAlchemyNotificacionRepository(db)).execute(
        usuario_actual.id_usuario)


@router.put(
    "/preferencias",
    summary="Guardar preferencias de canal (RF-105)",
    response_model=list[PreferenciaNotificacionResponse],
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
def guardar_preferencias(
    dto: GuardarPreferenciasDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    """`{"preferencias": [{"nivel": "ADVERTENCIA", "canal": "PUSH", "habilitado": false}]}`. Solo push y correo:
    la bandeja interna no se apaga. Nivel o canal fuera de su lista → 400.

    **Acceso:** autenticado (solo las propias)."""
    return GuardarPreferenciasNotificacionUseCase(SqlAlchemyNotificacionRepository(db), db).execute(
        usuario_actual.id_usuario, [(p.nivel, p.canal, p.habilitado) for p in dto.preferencias])

