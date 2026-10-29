# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-37 RF-73: reintentos, respaldo local y sincronización de la bitácora M04 |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-10-25 | Arekkazu | USAB-M04 T-18 RF-73: nombre del usuario actor además del id |
# | 2026-10-26 | Arekkazu | INC-M04 G089/G092 RF-73: 422 en parámetros inválidos y filtro correlacion_id |
# | 2026-10-29 | Arekkazu | TC-DIS-195 RF-73: filtro de la bitácora M04 por tipo_modelo del evento |
# | 2026-10-29 | Arekkazu | QA-M04-27-10 CU09 H-04 RF-73: consultar la bitácora no deja evento |
"""Router FastAPI para bitácora de auditoría del módulo de predicción.

RF-73 CU-09 Dev scope:
  GET  /prediccion/auditoria           — Listar bitácora con filtros
  GET  /prediccion/auditoria/exportar  — Exportar CSV/JSON
  GET  /prediccion/auditoria/{id}      — Detalle de evento

Autorización RBAC:
  recurso auditoria_m04 = id_recurso 46
  R=2 (Administrador; Veterinario desde DB-08, DEV-37: RF-73 actores), E=5 (Administrador)
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.application.use_cases.auditoria.consultar_auditoria_m04_use_case import ConsultarAuditoriaM04UseCase
from src.prediction.application.use_cases.auditoria.exportar_auditoria_m04_use_case import ExportarAuditoriaM04UseCase
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
from src.prediction.infrastructure.schema.evento_auditoria_m04_schema import AuditoriaM04ListResponse, EventoAuditoriaM04Response
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.shared.fechas import FechaHoraUtc

router = APIRouter(prefix="/prediccion/auditoria", tags=["Predicción M04 - Auditoría RF-73"])

_RECURSO = 46  # modulo1.recursos: 'auditoria_m04'


def _con_nombre_usuario(db: Session, eventos: list[EventoAuditoriaM04Response]) -> list[EventoAuditoriaM04Response]:
    """T-18: nombre de quien hizo cada evento, una consulta por página."""
    ids = list({e.id_usuario for e in eventos if e.id_usuario is not None})
    if ids:
        nombres = dict(db.execute(text(
            "SELECT id_usuario, trim(nombre || ' ' || coalesce(apellidos, '')) FROM modulo1.usuarios "
            "WHERE id_usuario = ANY(:ids)"
        ), {"ids": ids}).all())
        for evento in eventos:
            evento.nombre_usuario = nombres.get(evento.id_usuario)
    return eventos


@router.get(
    "",
    response_model=AuditoriaM04ListResponse,
    status_code=200,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse, "description": "Parámetros inválidos (p. ej. por_pagina fuera de 1–200)"},
    },
    # INC-M04-208-G089: el contrato publica 422 para parámetros inválidos; el runtime lo cumple.
    openapi_extra={"x-codigo-validacion": 422},
    summary="Listar bitácora de auditoría M04 con filtros (RF-73)",
)
def listar_auditoria(
    tipo_evento: Optional[str] = Query(default=None, description="Filtrar por tipo de evento"),
    fecha_desde: Optional[FechaHoraUtc] = Query(default=None),
    fecha_hasta: Optional[FechaHoraUtc] = Query(default=None),
    id_usuario: Optional[int] = Query(default=None, description="Filtrar por id de usuario actor"),
    id_sistema: Optional[str] = Query(default=None, description="Filtrar por sistema actor"),
    id_referencia: Optional[str] = Query(default=None, description="Filtrar por id de entidad referenciada"),
    severidad_evento: Optional[str] = Query(default=None, description="INFO | WARNING | ERROR | CRITICAL"),
    correlacion_id: Optional[uuid.UUID] = Query(
        default=None, description="Cadena completa de un flujo (paquete → inferencia → alerta → retroalimentación)"
    ),
    tipo_modelo: Optional[str] = Query(default=None, description="Filtrar por tipo de modelo del evento (RFC-009)"),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> AuditoriaM04ListResponse:
    use_case = ConsultarAuditoriaM04UseCase(repo=SqlAlchemyEventoAuditoriaM04Repository(db))
    items, total = use_case.listar(
        tipo_evento=tipo_evento,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        id_usuario=id_usuario,
        id_sistema=id_sistema,
        id_referencia=id_referencia,
        severidad_evento=severidad_evento,
        correlacion_id=correlacion_id,
        tipo_modelo=tipo_modelo,
        pagina=pagina,
        por_pagina=por_pagina,
    )
    return AuditoriaM04ListResponse(
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        items=_con_nombre_usuario(db, [EventoAuditoriaM04Response.model_validate(e) for e in items]),
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
    fecha_desde: Optional[FechaHoraUtc] = Query(default=None),
    fecha_hasta: Optional[FechaHoraUtc] = Query(default=None),
    id_usuario: Optional[int] = Query(default=None),
    id_sistema: Optional[str] = Query(default=None),
    id_referencia: Optional[str] = Query(default=None),
    severidad_evento: Optional[str] = Query(default=None),
    tipo_modelo: Optional[str] = Query(default=None),
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
        tipo_modelo=tipo_modelo,
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
) -> EventoAuditoriaM04Response:
    use_case = ConsultarAuditoriaM04UseCase(repo=SqlAlchemyEventoAuditoriaM04Repository(db))
    entidad = use_case.obtener_por_id(id_evento)
    return _con_nombre_usuario(db, [EventoAuditoriaM04Response.model_validate(entidad)])[0]
