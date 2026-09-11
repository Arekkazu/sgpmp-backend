"""Router FastAPI de la bitácora de auditoría de M05 (RF-80, CU-06).

  GET  /suministros/auditoria             — Listar bitácora con filtros
  GET  /suministros/auditoria/exportar    — Exportar CSV/Excel/PDF
  GET  /suministros/auditoria/{id}        — Detalle de un evento

RBAC: recurso 57 (`bitacora_auditoria_suministros`). R=2 (Administrador,
Contador, Revisor Fiscal), E=5 (mismos roles, exportar).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.supplies.domain.repositories.auditoria_suministro_read_port import FiltrosAuditoriaSuministro
from src.supplies.infrastructure.factories.auditoria_suministros_factory import (
    build_consultar_auditoria_use_case,
    build_exportar_auditoria_use_case,
)
from src.supplies.infrastructure.schema.auditoria_suministro_schema import (
    AuditoriaSuministrosListResponse,
    EventoAuditoriaSuministroResponse,
)

router = APIRouter(prefix="/suministros/auditoria", tags=["Suministros - Auditoría del Módulo (RF-80)"])

_RECURSO = 57


@router.get(
    "",
    response_model=AuditoriaSuministrosListResponse,
    status_code=200,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Listar la bitácora de auditoría de M05 con filtros (RF-80)",
)
def listar_auditoria(
    tipo_operacion: Optional[str] = Query(default=None, description="Ej: SUMINISTRO_REGISTRADO, CICLO_CONSOLIDADO..."),
    id_usuario: Optional[int] = Query(default=None, description="Filtrar por id de usuario actor"),
    fecha_desde: Optional[datetime] = Query(default=None),
    fecha_hasta: Optional[datetime] = Query(default=None),
    entidad_afectada: Optional[str] = Query(default=None),
    id_activo_biologico: Optional[int] = Query(default=None, gt=0),
    id_ciclo_productivo: Optional[int] = Query(default=None, gt=0),
    resultado: Optional[str] = Query(default=None, description="EXITOSO | FALLIDO | RECHAZADO"),
    clasificacion_registro: Optional[str] = Query(default=None, description="NIC41 | TECNICO"),
    pagina: int = Query(default=1, ge=1),
    registros_por_pagina: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> AuditoriaSuministrosListResponse:
    filtros = FiltrosAuditoriaSuministro(
        tipo_operacion=tipo_operacion,
        id_usuario=id_usuario,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        entidad_afectada=entidad_afectada,
        id_activo_biologico=id_activo_biologico,
        id_ciclo_productivo=id_ciclo_productivo,
        resultado=resultado,
        clasificacion_registro=clasificacion_registro,
        pagina=pagina,
        registros_por_pagina=registros_por_pagina,
    )
    use_case = build_consultar_auditoria_use_case(db)
    items, total = use_case.listar(filtros)
    return AuditoriaSuministrosListResponse(
        total=total,
        pagina=pagina,
        registros_por_pagina=registros_por_pagina,
        items=[EventoAuditoriaSuministroResponse.model_validate(e) for e in items],
    )


@router.get(
    "/exportar",
    status_code=200,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Exportar la bitácora de auditoría de M05 en CSV, Excel o PDF (RF-80)",
)
def exportar_auditoria(
    tipo_operacion: Optional[str] = Query(default=None),
    id_usuario: Optional[int] = Query(default=None),
    fecha_desde: Optional[datetime] = Query(default=None),
    fecha_hasta: Optional[datetime] = Query(default=None),
    entidad_afectada: Optional[str] = Query(default=None),
    id_activo_biologico: Optional[int] = Query(default=None, gt=0),
    id_ciclo_productivo: Optional[int] = Query(default=None, gt=0),
    resultado: Optional[str] = Query(default=None),
    clasificacion_registro: Optional[str] = Query(default=None),
    formato: str = Query(default="csv", pattern="^(csv|xlsx|pdf)$"),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> StreamingResponse:
    filtros = FiltrosAuditoriaSuministro(
        tipo_operacion=tipo_operacion,
        id_usuario=id_usuario,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        entidad_afectada=entidad_afectada,
        id_activo_biologico=id_activo_biologico,
        id_ciclo_productivo=id_ciclo_productivo,
        resultado=resultado,
        clasificacion_registro=clasificacion_registro,
    )
    use_case = build_exportar_auditoria_use_case(db)
    contenido, media_type, nombre_archivo = use_case.exportar(filtros, formato=formato)
    return StreamingResponse(
        iter([contenido]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@router.get(
    "/{id_auditoria_suministro}",
    response_model=EventoAuditoriaSuministroResponse,
    status_code=200,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Obtener el detalle de un evento de auditoría de M05 (RF-80)",
)
def obtener_evento(
    id_auditoria_suministro: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> EventoAuditoriaSuministroResponse:
    use_case = build_consultar_auditoria_use_case(db)
    entidad = use_case.obtener_por_id(id_auditoria_suministro)
    return EventoAuditoriaSuministroResponse.model_validate(entidad)
