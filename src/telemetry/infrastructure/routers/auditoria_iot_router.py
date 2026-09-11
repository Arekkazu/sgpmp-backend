"""Router FastAPI para bitácora de auditoría IoT.

RF-63 — CU06 Dev scope:
  GET  /iot/auditoria                       — Listar bitácora con filtros
  GET  /iot/auditoria/{id_evento}           — Detalle de evento
  GET  /iot/auditoria/exportar              — Exportar JSON/CSV
  POST /iot/auditoria/verificar-integridad  — Verificar hashes SHA-256

Auth: JWT Bearer + RBAC recurso 39 (bitacora_auditoria_iot).
componente_origen no se expone en respuestas (campo interno).
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.telemetry.application.use_cases.auditoria.consultar_bitacora_iot_use_case import ConsultarBitacoraIotUseCase
from src.telemetry.application.use_cases.auditoria.verificar_integridad_bitacora_use_case import VerificarIntegridadBitacoraUseCase
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.schema.bitacora_auditoria_iot_schema import (
    EventoAuditoriaIotSchema,
    ListaAuditoriaIotSchema,
    VerificacionIntegridadSchema,
)

router = APIRouter(prefix="/iot/auditoria", tags=["Telemetría IoT - Auditoría RF-63"])


@router.get(
    "",
    response_model=ListaAuditoriaIotSchema,
    status_code=200,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    dependencies=[Depends(require_permission(39, 2))],
    summary="Listar bitácora de auditoría IoT (RF-63)",
)
def listar_auditoria(
    fecha_desde: Optional[datetime] = Query(default=None),
    fecha_hasta: Optional[datetime] = Query(default=None),
    tipo_evento: Optional[str] = Query(default=None),
    severidad_log: Optional[str] = Query(default=None),
    clasificacion_registro: Optional[str] = Query(default=None),
    entidad_afectada_id: Optional[str] = Query(default=None),
    resultado: Optional[str] = Query(default=None),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaAuditoriaIotSchema:
    use_case = ConsultarBitacoraIotUseCase(
        auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(db),
    )
    items, total = use_case.listar(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        tipo_evento=tipo_evento,
        severidad_log=severidad_log,
        clasificacion_registro=clasificacion_registro,
        entidad_afectada_id=entidad_afectada_id,
        resultado=resultado,
        pagina=pagina,
        por_pagina=por_pagina,
    )
    return ListaAuditoriaIotSchema(
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        items=[EventoAuditoriaIotSchema.model_validate(e) for e in items],
    )


@router.get(
    "/exportar",
    status_code=200,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    dependencies=[Depends(require_permission(39, 5))],
    summary="Exportar bitácora de auditoría IoT (RF-63)",
)
def exportar_auditoria(
    fecha_desde: Optional[datetime] = Query(default=None),
    fecha_hasta: Optional[datetime] = Query(default=None),
    tipo_evento: Optional[str] = Query(default=None),
    clasificacion_registro: Optional[str] = Query(default=None),
    formato: str = Query(default='json', pattern='^(json|csv)$'),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> StreamingResponse:
    use_case = ConsultarBitacoraIotUseCase(
        auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(db),
    )
    items, _ = use_case.listar(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        tipo_evento=tipo_evento,
        clasificacion_registro=clasificacion_registro,
        pagina=1,
        por_pagina=10000,
    )
    schemas = [EventoAuditoriaIotSchema.model_validate(e) for e in items]

    if formato == 'csv':
        output = io.StringIO()
        if schemas:
            writer = csv.DictWriter(output, fieldnames=schemas[0].model_fields.keys())
            writer.writeheader()
            for s in schemas:
                writer.writerow(s.model_dump())
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="auditoria_iot.csv"'},
        )

    data = json.dumps([s.model_dump(mode='json') for s in schemas], default=str)
    return StreamingResponse(
        iter([data]),
        media_type='application/json',
        headers={'Content-Disposition': 'attachment; filename="auditoria_iot.json"'},
    )


@router.get(
    "/{id_evento}",
    response_model=EventoAuditoriaIotSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(39, 2))],
    summary="Obtener detalle de evento de auditoría (RF-63)",
)
def obtener_evento(
    id_evento: UUID,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> EventoAuditoriaIotSchema:
    use_case = ConsultarBitacoraIotUseCase(
        auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(db),
    )
    return EventoAuditoriaIotSchema.model_validate(use_case.get(id_evento))


@router.post(
    "/verificar-integridad",
    response_model=VerificacionIntegridadSchema,
    status_code=200,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    dependencies=[Depends(require_permission(39, 5))],
    summary="Verificar integridad SHA-256 de la bitácora (RF-63 FA-11)",
)
def verificar_integridad(
    fecha_desde: Optional[datetime] = Query(default=None),
    fecha_hasta: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> VerificacionIntegridadSchema:
    use_case = VerificarIntegridadBitacoraUseCase(
        db=db,
        auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(db),
    )
    resultado = use_case.execute(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
    return VerificacionIntegridadSchema(
        total_verificados=resultado.total_verificados,
        comprometidos=resultado.comprometidos,
        ids_comprometidos=resultado.ids_comprometidos,
    )
