"""Router FastAPI para evaluación de calidad de telemetría.

RF-62 — CU06 Dev scope:
  GET  /iot/calidad                         — Listar evaluaciones con filtros
  GET  /iot/calidad/{id_telemetria}         — Calidad de una lectura específica
  POST /iot/calidad/{id_telemetria}/evaluar — Disparar evaluación puntual
  POST /iot/calidad/reevaluar               — Re-evaluación explícita admin (FA-08)

Auth: JWT Bearer + RBAC recurso 38 (calidad_telemetria).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.shared.database import get_db
from src.shared.errors import NotFoundError
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.repositories.usuario_repository import SqlAlchemyUsuarioRepository
from src.telemetry.application.use_cases.calidad.consultar_calidad_use_case import ConsultarCalidadUseCase
from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
from src.telemetry.application.use_cases.calidad.solicitar_reevaluacion_use_case import SolicitarReevaluacionUseCase
from src.telemetry.infrastructure.adapters.parametros_calidad_stub_adapter import ParametrosCalidadStubAdapter
from src.telemetry.infrastructure.dto.solicitar_reevaluacion_dto import SolicitarReevaluacionDTO
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.repositories.telemetria_calidad_repository import SqlAlchemyTelemetriaCalidadRepository
from src.telemetry.infrastructure.repositories.telemetria_repository import SqlAlchemyTelemetriaRepository
from src.telemetry.infrastructure.schema.telemetria_calidad_schema import (
    ListaCalidadSchema,
    ReevaluacionResponseSchema,
    TelemetriaCalidadSchema,
)

router = APIRouter(prefix="/iot/calidad", tags=["Telemetría IoT - Calidad RF-62"])


@router.get(
    "",
    response_model=ListaCalidadSchema,
    status_code=200,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    dependencies=[Depends(require_permission(38, 2))],
    summary="Listar evaluaciones de calidad (RF-62)",
)
def listar_calidad(
    id_sensor: Optional[int] = Query(default=None),
    clasificacion: Optional[str] = Query(default=None),
    fecha_desde: Optional[datetime] = Query(default=None),
    fecha_hasta: Optional[datetime] = Query(default=None),
    estado_evaluacion: Optional[str] = Query(default=None),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaCalidadSchema:
    use_case = ConsultarCalidadUseCase(
        calidad_repo=SqlAlchemyTelemetriaCalidadRepository(db),
    )
    items, total = use_case.listar(
        id_sensor=id_sensor,
        clasificacion=clasificacion,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        estado_evaluacion=estado_evaluacion,
        pagina=pagina,
        por_pagina=por_pagina,
    )
    return ListaCalidadSchema(
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        items=[TelemetriaCalidadSchema.model_validate(e) for e in items],
    )


@router.get(
    "/{id_telemetria}",
    response_model=TelemetriaCalidadSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(38, 2))],
    summary="Obtener calidad de una lectura (RF-62)",
)
def obtener_calidad(
    id_telemetria: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> TelemetriaCalidadSchema:
    use_case = ConsultarCalidadUseCase(
        calidad_repo=SqlAlchemyTelemetriaCalidadRepository(db),
    )
    return TelemetriaCalidadSchema.model_validate(use_case.get(id_telemetria))


@router.post(
    "/{id_telemetria}/evaluar",
    response_model=TelemetriaCalidadSchema,
    status_code=201,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(38, 5))],
    summary="Disparar evaluación de calidad puntual (RF-62)",
)
def evaluar_calidad(
    id_telemetria: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> TelemetriaCalidadSchema:
    from sqlalchemy import text
    row = db.execute(
        text(
            'SELECT id_sensor, id_variable, valor_crudo, valor_ajustado, '
            'timestamp_captura, estado_calidad, parametros_calibracion '
            'FROM modulo3.telemetrias WHERE id_telemetria = :id'
        ),
        {'id': id_telemetria},
    ).fetchone()
    if row is None:
        raise NotFoundError(code='TELEMETRIA_NO_ENCONTRADA', message='Lectura telemétrica no encontrada.')

    from decimal import Decimal
    use_case = EvaluarCalidadTelemetriaUseCase(
        db=db,
        telemetria_repo=SqlAlchemyTelemetriaRepository(db),
        calidad_repo=SqlAlchemyTelemetriaCalidadRepository(db),
        parametros_port=ParametrosCalidadStubAdapter(),
        auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(db),
    )
    evaluacion = use_case.execute(
        id_telemetria=id_telemetria,
        id_sensor=row[0],
        id_variable=row[1],
        valor=Decimal(str(row[2])),
        valor_ajustado=Decimal(str(row[3])) if row[3] else None,
        timestamp_captura=row[4],
        estado_calidad_rf53=row[5],
        parametros_calibracion=row[6],
    )
    return TelemetriaCalidadSchema.model_validate(evaluacion)


@router.post(
    "/reevaluar",
    response_model=ReevaluacionResponseSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(38, 5))],
    summary="Re-evaluación explícita ante error de configuración (FA-08)",
)
def solicitar_reevaluacion(
    dto: SolicitarReevaluacionDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ReevaluacionResponseSchema:
    use_case = SolicitarReevaluacionUseCase(
        db=db,
        calidad_repo=SqlAlchemyTelemetriaCalidadRepository(db),
        telemetria_repo=SqlAlchemyTelemetriaRepository(db),
        parametros_port=ParametrosCalidadStubAdapter(),
        auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(db),
    )
    detalle = SqlAlchemyUsuarioRepository(db).obtener_detalle(usuario_actual.id_usuario)
    nombre_usuario = f"{detalle.nombre} {detalle.apellidos}" if detalle else str(usuario_actual.id_usuario)
    resultado = use_case.execute(dto=dto, id_usuario=usuario_actual.id_usuario, nombre_usuario=nombre_usuario)
    return ReevaluacionResponseSchema(
        evaluaciones_superadas=resultado.evaluaciones_superadas,
        evaluaciones_creadas=resultado.evaluaciones_creadas,
    )
