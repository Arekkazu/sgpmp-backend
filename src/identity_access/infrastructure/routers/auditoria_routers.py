"""Router FastAPI para el módulo de auditoría (`/auditoria`).

Expone la consulta paginada del log de eventos con filtros por usuario,
tipo, categoría y rango de fechas. Solo accesible por administradores.

`GET /auditoria/archivado/` consulta el archivo histórico de RF-10 (eventos con
más de 12 meses copiados a `modulo1.eventos_archivados`) con los mismos filtros,
la misma paginación y el mismo permiso que el log activo.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.auditoria.consultar_auditoria_use_case import ConsultarAuditoriaUseCase
from src.identity_access.domain.value_objects.evento_categoria import EventoCategoria
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.schema.gestion_schema import AuditoriaItemResponse, AuditoriaPaginadaResponse
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/auditoria", tags=["Auditoría"])


def _consultar(
    db: Session,
    usuario_actual: UsuarioActual,
    id_usuario: Optional[int],
    tipo_evento: Optional[int],
    categoria: Optional[EventoCategoria],
    fecha_desde: Optional[datetime],
    fecha_hasta: Optional[datetime],
    pagina: int,
    tamano: int,
    archivados: bool,
) -> AuditoriaPaginadaResponse:
    """Ejecuta la consulta y arma el response, común al log activo y al histórico."""
    use_case = ConsultarAuditoriaUseCase(
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
    )
    resultado = use_case.execute(
        usuario_actual=usuario_actual,
        id_usuario=id_usuario,
        tipo_evento=tipo_evento,
        categoria=categoria,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        pagina=pagina,
        tamano=tamano,
        archivados=archivados,
    )

    items = [
        AuditoriaItemResponse(
            id_evento=evento.id_evento,
            tipo_evento=evento.tipo_evento,
            fecha_evento=evento.fecha_evento,
            modulo=evento.modulo,
            resultado=evento.resultado.value if hasattr(evento.resultado, "value") else evento.resultado,
            detalle=evento.detalle,
            id_usuario=evento.id_usuario,
            categoria=evento.categoria,
            estado=evento.estado,
            id_sesion=evento.id_sesion,
            integridad_ok=integridad_ok,
        )
        for evento, integridad_ok in resultado["items"]
    ]

    return AuditoriaPaginadaResponse(
        total=resultado["total"],
        pagina=resultado["pagina"],
        tamano=resultado["tamano"],
        items=items,
    )


@router.get(
    "/",
    response_model=AuditoriaPaginadaResponse,
    dependencies=[Depends(require_permission(6, 2))],
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
def consultar_auditoria(
    id_usuario: Optional[int] = Query(None),
    tipo_evento: Optional[int] = Query(None),
    categoria: Optional[EventoCategoria] = Query(None),
    fecha_desde: Optional[datetime] = Query(None),
    fecha_hasta: Optional[datetime] = Query(None),
    pagina: int = Query(1, ge=1),
    tamano: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    return _consultar(
        db=db,
        usuario_actual=usuario_actual,
        id_usuario=id_usuario,
        tipo_evento=tipo_evento,
        categoria=categoria,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        pagina=pagina,
        tamano=tamano,
        archivados=False,
    )


@router.get(
    "/archivado/",
    response_model=AuditoriaPaginadaResponse,
    dependencies=[Depends(require_permission(6, 2))],
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Consultar el archivo histórico de auditoría (RF-10)",
)
def consultar_auditoria_archivada(
    id_usuario: Optional[int] = Query(None),
    tipo_evento: Optional[int] = Query(None),
    categoria: Optional[EventoCategoria] = Query(None),
    fecha_desde: Optional[datetime] = Query(None),
    fecha_hasta: Optional[datetime] = Query(None),
    pagina: int = Query(1, ge=1),
    tamano: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    return _consultar(
        db=db,
        usuario_actual=usuario_actual,
        id_usuario=id_usuario,
        tipo_evento=tipo_evento,
        categoria=categoria,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        pagina=pagina,
        tamano=tamano,
        archivados=True,
    )
