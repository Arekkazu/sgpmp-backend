"""Router FastAPI para métricas de producción (`/configuracion/metricas`).

Expone los cuatro flujos de RF-16 CU02 para métricas:
  I) POST   /configuracion/metricas              — Registrar métrica para especie
  J) PATCH  /configuracion/metricas/{id}         — Editar métrica
  K) PATCH  /configuracion/metricas/{id}/desactivar — Desactivar métrica
  L) GET    /configuracion/metricas              — Consultar métricas por especie

Autorización RBAC:
  recurso metricas_produccion = id_recurso 19
  C=1, R=2, U=3, D=4
  Roles autorizados: Administrador (1) y Veterinario (3).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.metricas.consultar_metricas_use_case import ConsultarMetricasUseCase
from src.configuration.application.use_cases.metricas.desactivar_metrica_use_case import DesactivarMetricaUseCase
from src.configuration.application.use_cases.metricas.editar_metrica_use_case import EditarMetricaUseCase
from src.configuration.application.use_cases.metricas.registrar_metrica_use_case import RegistrarMetricaUseCase
from src.configuration.infrastructure.dto.editar_metrica_dto import EditarMetricaDTO
from src.configuration.infrastructure.dto.registrar_metrica_dto import RegistrarMetricaDTO
from src.configuration.infrastructure.repositories.auditoria_metrica_repository import SqlAlchemyAuditoriaMetricaRepository
from src.configuration.infrastructure.repositories.dependencia_metrica_repository import SqlAlchemyDependenciaMetricaRepository
from src.configuration.infrastructure.repositories.especie_repository import SqlAlchemyEspecieRepository
from src.configuration.infrastructure.repositories.metrica_produccion_repository import SqlAlchemyMetricaProduccionRepository
from src.configuration.infrastructure.schema.metrica_schema import MetricaProduccionResponse, MetricasPorEspecieResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/metricas", tags=["Configuración - Métricas de Producción"])

_RECURSO = 19  # modulo1.recursos: 'metricas_produccion'


@router.post(
    "",
    response_model=MetricaProduccionResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Registrar métrica de producción para especie (Flujo I)",
)
def registrar_metrica(
    dto: RegistrarMetricaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> MetricaProduccionResponse:
    use_case = RegistrarMetricaUseCase(
        db=db,
        metricas_repo=SqlAlchemyMetricaProduccionRepository(db),
        especies_repo=SqlAlchemyEspecieRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaMetricaRepository(db),
    )
    metrica = use_case.execute(dto, usuario_actual)
    return MetricaProduccionResponse.model_validate(metrica)


@router.get(
    "",
    response_model=MetricasPorEspecieResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Consultar métricas de producción por especie (Flujo L)",
)
def consultar_metricas(
    id_especie: int = Query(..., description="ID de la especie a consultar."),
    solo_activas: bool = Query(False, description="Si es true, solo devuelve métricas activas."),
    db: Session = Depends(get_db),
) -> MetricasPorEspecieResponse:
    use_case = ConsultarMetricasUseCase(metricas_repo=SqlAlchemyMetricaProduccionRepository(db))
    metricas = use_case.execute(id_especie, solo_activas=solo_activas)
    items = [MetricaProduccionResponse.model_validate(m) for m in metricas]
    return MetricasPorEspecieResponse(total=len(items), items=items)


@router.patch(
    "/{id_metrica_produccion}",
    response_model=MetricaProduccionResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        412: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Editar métrica de producción (Flujo J)",
)
def editar_metrica(
    id_metrica_produccion: int,
    dto: EditarMetricaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> MetricaProduccionResponse:
    use_case = EditarMetricaUseCase(
        db=db,
        metricas_repo=SqlAlchemyMetricaProduccionRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaMetricaRepository(db),
    )
    metrica = use_case.execute(id_metrica_produccion, dto, usuario_actual)
    return MetricaProduccionResponse.model_validate(metrica)


@router.patch(
    "/{id_metrica_produccion}/desactivar",
    response_model=MetricaProduccionResponse,
    dependencies=[Depends(require_permission(_RECURSO, 4))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Desactivar métrica de producción (Flujo K)",
)
def desactivar_metrica(
    id_metrica_produccion: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> MetricaProduccionResponse:
    use_case = DesactivarMetricaUseCase(
        db=db,
        metricas_repo=SqlAlchemyMetricaProduccionRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaMetricaRepository(db),
        dependencia_port=SqlAlchemyDependenciaMetricaRepository(db),
    )
    metrica = use_case.execute(id_metrica_produccion, usuario_actual)
    return MetricaProduccionResponse.model_validate(metrica)
