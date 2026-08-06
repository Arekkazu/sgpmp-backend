"""Router FastAPI para el costeo directo de suministros (`/suministros/costeo-directo`).

Expone los flujos de RF-78 (CU-05) para SERVICIO_VETERINARIO/INSEMINACION:
  POST   /suministros/costeo-directo                           — Registrar suministro directo
  POST   /suministros/costeo-directo/{id}/correccion            — Corregir un registro existente
  GET    /suministros/costeo-directo/acumulado/activo/{id}      — Acumulado del ciclo abierto de un activo
  GET    /suministros/costeo-directo/acumulado/ciclo/{id}       — Acumulado por instancia de ciclo (M06)

Autorización delegada al RBAC centralizado (``src/shared/rbac.py``):
  recurso ``costeo_directo_suministros`` = id_recurso 55; acciones C=1, R=2, U=3.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.supplies.infrastructure.dto.registrar_correccion_suministro_dto import (
    RegistrarCorreccionSuministroDTO,
)
from src.supplies.infrastructure.dto.registrar_suministro_directo_dto import RegistrarSuministroDirectoDTO
from src.supplies.infrastructure.factories.costeo_suministros_factory import (
    build_consultar_acumulado_ciclo_use_case,
    build_registrar_correccion_suministro_use_case,
    build_registrar_suministro_directo_use_case,
)
from src.supplies.infrastructure.schema.acumulado_ciclo_schema import AcumuladoCicloResponse
from src.supplies.infrastructure.schema.registro_suministro_directo_schema import (
    RegistroSuministroDirectoResponse,
)

router = APIRouter(prefix="/suministros/costeo-directo", tags=["Suministros - Costeo Directo (RF-78)"])

_RECURSO = 55  # modulo1.recursos: 'costeo_directo_suministros'


@router.post(
    "",
    response_model=RegistroSuministroDirectoResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Registrar un suministro directo SERVICIO_VETERINARIO/INSEMINACION (RF-78)",
)
def registrar_suministro_directo(
    dto: RegistrarSuministroDirectoDTO,
    response: Response,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> RegistroSuministroDirectoResponse:
    use_case = build_registrar_suministro_directo_use_case(db)
    resultado = use_case.execute(dto, usuario_actual)
    if resultado.ya_procesado:
        response.status_code = 200  # E8 — reintento con id_idempotencia ya procesado
    return RegistroSuministroDirectoResponse.model_validate(resultado.registro)


@router.post(
    "/{id_registro_original}/correccion",
    response_model=RegistroSuministroDirectoResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Corregir un registro de suministro existente (RF-78 E7)",
)
def registrar_correccion_suministro(
    id_registro_original: UUID,
    dto: RegistrarCorreccionSuministroDTO,
    response: Response,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> RegistroSuministroDirectoResponse:
    use_case = build_registrar_correccion_suministro_use_case(db)
    resultado = use_case.execute(id_registro_original, dto, usuario_actual)
    if resultado.ya_procesado:
        response.status_code = 200  # E8 — reintento con id_idempotencia ya procesado
    return RegistroSuministroDirectoResponse.model_validate(resultado.registro)


@router.get(
    "/acumulado/activo/{id_activo_biologico}",
    response_model=AcumuladoCicloResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Consultar el acumulado del ciclo productivo activo de un activo (RF-78)",
)
def consultar_acumulado_por_activo(
    id_activo_biologico: int,
    db: Session = Depends(get_db),
) -> AcumuladoCicloResponse:
    use_case = build_consultar_acumulado_ciclo_use_case(db)
    resultado = use_case.por_activo(id_activo_biologico)
    return AcumuladoCicloResponse.model_validate(resultado)


@router.get(
    "/acumulado/ciclo/{id_gestion_fases}",
    response_model=AcumuladoCicloResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Consultar el acumulado por instancia de ciclo (RF-78) — uso de M06/Contador",
)
def consultar_acumulado_por_gestion_fase(
    id_gestion_fases: int,
    db: Session = Depends(get_db),
) -> AcumuladoCicloResponse:
    use_case = build_consultar_acumulado_ciclo_use_case(db)
    resultado = use_case.por_gestion_fase(id_gestion_fases)
    return AcumuladoCicloResponse.model_validate(resultado)
