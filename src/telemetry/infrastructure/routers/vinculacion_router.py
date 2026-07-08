"""Router FastAPI para vinculación de lecturas teleméricas a activos biológicos.

RF-61 — CU05 Dev scope:
  GET   /iot/vinculaciones                    — Listar vinculaciones con filtros
  GET   /iot/vinculaciones/{id}               — Detalle de vinculación
  PATCH /iot/vinculaciones/{id}/resolver      — Resolver vinculación AMBIGUA (manual, RF-61-C)
  POST  /iot/vinculaciones/{id}/corregir      — Corrección inmutable (RF-61-C)

Auth: JWT Bearer + RBAC recurso 37 (vinculaciones_lecturas).
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
from src.telemetry.application.use_cases.infraestructura.corregir_vinculacion_use_case import CorregirVinculacionUseCase
from src.telemetry.application.use_cases.infraestructura.listar_vinculaciones_use_case import ListarVinculacionesUseCase
from src.telemetry.application.use_cases.infraestructura.resolver_vinculacion_use_case import ResolverVinculacionUseCase
from src.telemetry.infrastructure.adapters.activo_biologico_stub_adapter import ActivoBiologicoStubAdapter
from src.telemetry.infrastructure.dto.corregir_vinculacion_dto import CorregirVinculacionDTO
from src.telemetry.infrastructure.dto.resolver_vinculacion_dto import ResolverVinculacionDTO
from src.telemetry.infrastructure.repositories.vinculacion_lectura_repository import SqlAlchemyVinculacionLecturaRepository
from src.telemetry.infrastructure.schema.vinculacion_lectura_schema import ListaVinculacionesSchema, VinculacionLecturaSchema

router = APIRouter(prefix="/iot/vinculaciones", tags=["Telemetría IoT - Vinculaciones RF-61"])


@router.get(
    "",
    response_model=ListaVinculacionesSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(37, 2))],
    summary="Listar vinculaciones de lecturas a activos biológicos (RF-61)",
)
def listar_vinculaciones(
    id_telemetria: Optional[int] = Query(default=None),
    estado_vinculacion: Optional[str] = Query(default=None),
    mecanismo_vinculacion: Optional[str] = Query(default=None),
    id_infraestructura: Optional[int] = Query(default=None),
    fecha_desde: Optional[datetime] = Query(default=None),
    fecha_hasta: Optional[datetime] = Query(default=None),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaVinculacionesSchema:
    use_case = ListarVinculacionesUseCase(
        db=db,
        vinculacion_repo=SqlAlchemyVinculacionLecturaRepository(db),
    )
    items, total = use_case.execute(
        id_telemetria=id_telemetria,
        estado_vinculacion=estado_vinculacion,
        mecanismo_vinculacion=mecanismo_vinculacion,
        id_infraestructura=id_infraestructura,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        pagina=pagina,
        por_pagina=por_pagina,
    )
    return ListaVinculacionesSchema(
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        items=[VinculacionLecturaSchema.model_validate(v) for v in items],
    )


@router.get(
    "/{id_vinculacion_lectura}",
    response_model=VinculacionLecturaSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(37, 2))],
    summary="Obtener detalle de vinculación (RF-61)",
)
def obtener_vinculacion(
    id_vinculacion_lectura: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> VinculacionLecturaSchema:
    repo = SqlAlchemyVinculacionLecturaRepository(db)
    vinculacion = repo.obtener_por_id(id_vinculacion_lectura)
    if vinculacion is None:
        raise NotFoundError(
            code='VINCULACION_NO_ENCONTRADA',
            message='Vinculación no encontrada.',
        )
    return VinculacionLecturaSchema.model_validate(vinculacion)


@router.patch(
    "/{id_vinculacion_lectura}/resolver",
    response_model=VinculacionLecturaSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(37, 3))],
    summary="Resolver vinculación AMBIGUA manualmente (RF-61-C)",
)
def resolver_vinculacion(
    id_vinculacion_lectura: int,
    dto: ResolverVinculacionDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> VinculacionLecturaSchema:
    use_case = ResolverVinculacionUseCase(
        db=db,
        vinculacion_repo=SqlAlchemyVinculacionLecturaRepository(db),
    )
    vinculacion = use_case.execute(
        id_vinculacion_lectura=id_vinculacion_lectura,
        dto=dto,
        id_usuario=usuario_actual.id_usuario,
    )
    return VinculacionLecturaSchema.model_validate(vinculacion)


@router.post(
    "/{id_vinculacion_lectura}/corregir",
    response_model=VinculacionLecturaSchema,
    status_code=201,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(37, 3))],
    summary="Corrección inmutable de vinculación (RF-61-C)",
)
def corregir_vinculacion(
    id_vinculacion_lectura: int,
    dto: CorregirVinculacionDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> VinculacionLecturaSchema:
    use_case = CorregirVinculacionUseCase(
        db=db,
        vinculacion_repo=SqlAlchemyVinculacionLecturaRepository(db),
    )
    nueva = use_case.execute(
        id_vinculacion_lectura=id_vinculacion_lectura,
        dto=dto,
        id_usuario=usuario_actual.id_usuario,
    )
    return VinculacionLecturaSchema.model_validate(nueva)
