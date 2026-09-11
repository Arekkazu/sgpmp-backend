"""Router FastAPI para bitácora de auditoría del módulo de predicción.

RF-73 CU-09 Dev scope:
  GET  /prediccion/auditoria           — Listar bitácora con filtros
  GET  /prediccion/auditoria/exportar  — Exportar CSV/JSON
  GET  /prediccion/auditoria/{id}      — Detalle de evento

Autorización RBAC:
  recurso auditoria_m04 = id_recurso 46
  R=2 (Admin), E=5 (Admin)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.application.use_cases.auditoria.consultar_auditoria_m04_use_case import ConsultarAuditoriaM04UseCase
from src.prediction.application.use_cases.auditoria.exportar_auditoria_m04_use_case import ExportarAuditoriaM04UseCase
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
from src.prediction.infrastructure.schema.evento_auditoria_m04_schema import AuditoriaM04ListResponse, EventoAuditoriaM04Response
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/prediccion/auditoria", tags=["Predicción M04 - Auditoría RF-73"])

_RECURSO = 46  # modulo1.recursos: 'auditoria_m04'


@router.get(
    "",
    response_model=AuditoriaM04ListResponse,
    status_code=200,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Listar bitácora de auditoría M04 con filtros (RF-73)",
)
def listar_auditoria(
    tipo_evento: Optional[str] = Query(default=None, description="Filtrar por tipo de evento"),
    fecha_desde: Optional[datetime] = Query(default=None),
    fecha_hasta: Optional[datetime] = Query(default=None),
    id_usuario: Optional[int] = Query(default=None, description="Filtrar por id de usuario actor"),
    id_sistema: Optional[str] = Query(default=None, description="Filtrar por sistema actor"),
    id_referencia: Optional[str] = Query(default=None, description="Filtrar por id de entidad referenciada"),
    severidad_evento: Optional[str] = Query(default=None, description="INFO | WARNING | ERROR | CRITICAL"),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> AuditoriaM04ListResponse:
    use_case = ConsultarAuditoriaM04UseCase(
        db=db,
        repo=SqlAlchemyEventoAuditoriaM04Repository(db),
    )
    items, total = use_case.listar(
        tipo_evento=tipo_evento,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        id_usuario=id_usuario,
        id_sistema=id_sistema,
        id_referencia=id_referencia,
        severidad_evento=severidad_evento,
        pagina=pagina,
        por_pagina=por_pagina,
        id_usuario_consultor=usuario_actual.id_usuario,
    )
    return AuditoriaM04ListResponse(
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        items=[EventoAuditoriaM04Response.model_validate(e) for e in items],
    )


@router.get(
    "/exportar",
    status_code=200,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Exportar bitácora de auditoría M04 en CSV o JSON (RF-73)",
)
def exportar_auditoria(
    tipo_evento: Optional[str] = Query(default=None),
    fecha_desde: Optional[datetime] = Query(default=None),
    fecha_hasta: Optional[datetime] = Query(default=None),
    id_usuario: Optional[int] = Query(default=None),
    id_sistema: Optional[str] = Query(default=None),
    id_referencia: Optional[str] = Query(default=None),
    severidad_evento: Optional[str] = Query(default=None),
    formato: str = Query(default="json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> StreamingResponse:
    use_case = ExportarAuditoriaM04UseCase(
        db=db,
        repo=SqlAlchemyEventoAuditoriaM04Repository(db),
    )
    contenido, media_type, filename = use_case.exportar(
        tipo_evento=tipo_evento,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        id_usuario=id_usuario,
        id_sistema=id_sistema,
        id_referencia=id_referencia,
        severidad_evento=severidad_evento,
        formato=formato,
        id_usuario_exportador=usuario_actual.id_usuario,
    )
    return StreamingResponse(
        iter([contenido]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{id_evento}",
    response_model=EventoAuditoriaM04Response,
    status_code=200,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Obtener detalle de evento de auditoría M04 (RF-73)",
)
def obtener_evento(
    id_evento: uuid.UUID,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> EventoAuditoriaM04Response:
    use_case = ConsultarAuditoriaM04UseCase(
        db=db,
        repo=SqlAlchemyEventoAuditoriaM04Repository(db),
    )
    entidad = use_case.obtener_por_id(id_evento, id_usuario_consultor=usuario_actual.id_usuario)
    return EventoAuditoriaM04Response.model_validate(entidad)
