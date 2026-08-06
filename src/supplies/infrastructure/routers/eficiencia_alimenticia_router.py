"""Router FastAPI del CU-02 — Eficiencia Alimenticia / ICA (RF-74).

Expone los flujos de cálculo manual (Flujo A) y consulta (Flujo B):
  POST /suministros/eficiencia-alimenticia/calcular                    — Calcular ICA (manual)
  GET  /suministros/eficiencia-alimenticia/activos/{id}/vigente        — Vigente por período
  GET  /suministros/eficiencia-alimenticia/activos/{id}/historial      — Historial

Autorización RBAC (``src/shared/rbac.py``): recurso ``eficiencia_alimenticia`` =
id_recurso 49; acciones E=5 (cálculo), R=2 (consulta).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.supplies.application.use_cases.eficiencia.consultar_historial_ica_use_case import (
    ConsultarHistorialICAUseCase,
)
from src.supplies.application.use_cases.eficiencia.consultar_ica_vigente_use_case import (
    ConsultarICAVigenteUseCase,
)
from src.supplies.domain.value_objects.eficiencia_enums import PeriodoEvaluacion, TipoCalculo
from src.supplies.infrastructure.dto.calcular_ica_dto import CalcularICADTO
from src.supplies.infrastructure.factories.eficiencia_factory import build_calcular_ica_use_case
from src.supplies.infrastructure.repositories.resultado_ica_repository import (
    SqlAlchemyResultadoICARepository,
)
from src.supplies.infrastructure.schema.eficiencia_schema import (
    ConsultaVigenteResponse,
    HistorialICAResponse,
    ResultadoICAResponse,
)

router = APIRouter(
    prefix="/suministros/eficiencia-alimenticia",
    tags=["Suministros - Eficiencia Alimenticia (ICA)"],
)

_RECURSO = 49  # modulo1.recursos: 'eficiencia_alimenticia'


@router.post(
    "/calcular",
    response_model=ResultadoICAResponse,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Calcular el ICA de un activo (RF-74, Flujo A)",
)
def calcular_ica(
    dto: CalcularICADTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ResultadoICAResponse:
    use_case = build_calcular_ica_use_case(db)
    resultado = use_case.execute(
        id_activo_biologico=dto.id_activo_biologico,
        periodo=dto.periodo_evaluacion,
        tipo_calculo=TipoCalculo.MANUAL,
        id_usuario=usuario_actual.id_usuario,
    )
    return ResultadoICAResponse.desde_entidad(resultado)


@router.get(
    "/activos/{id_activo_biologico}/vigente",
    response_model=ConsultaVigenteResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Consultar el ICA vigente de un activo por período (RF-74, Flujo B)",
)
def consultar_vigente(
    id_activo_biologico: int,
    periodo: PeriodoEvaluacion = Query(..., description="Período de evaluación."),
    db: Session = Depends(get_db),
) -> ConsultaVigenteResponse:
    use_case = ConsultarICAVigenteUseCase(SqlAlchemyResultadoICARepository(db))
    resultado = use_case.execute(id_activo_biologico, periodo)
    if resultado is None:
        return ConsultaVigenteResponse(
            id_activo_biologico=id_activo_biologico,
            periodo_evaluacion=periodo.value,
            tiene_resultado=False,
            mensaje="No hay un resultado ICA vigente para el activo y período indicados.",
            resultado=None,
        )
    return ConsultaVigenteResponse(
        id_activo_biologico=id_activo_biologico,
        periodo_evaluacion=periodo.value,
        tiene_resultado=True,
        mensaje=None,
        resultado=ResultadoICAResponse.desde_entidad(resultado),
    )


@router.get(
    "/activos/{id_activo_biologico}/historial",
    response_model=HistorialICAResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Consultar el historial de resultados ICA de un activo (RF-74, Flujo B)",
)
def consultar_historial(
    id_activo_biologico: int,
    periodo: Optional[PeriodoEvaluacion] = Query(None, description="Filtrar por período."),
    db: Session = Depends(get_db),
) -> HistorialICAResponse:
    use_case = ConsultarHistorialICAUseCase(SqlAlchemyResultadoICARepository(db))
    resultados = use_case.execute(id_activo_biologico, periodo)
    items = [ResultadoICAResponse.desde_entidad(r) for r in resultados]
    return HistorialICAResponse(
        id_activo_biologico=id_activo_biologico, total=len(items), items=items
    )
