"""Router FastAPI para retroalimentación clínica M04 (`/prediccion/retroalimentacion`).

RF-72 CU-08: registro de retroalimentación clínica sobre resultados de inferencia.
  POST /prediccion/retroalimentacion

Autorización RBAC:
  recurso retroalimentacion_clinica = id_recurso 45
  C=1 (Veterinario)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.application.use_cases.retroalimentacion.registrar_retroalimentacion_use_case import RegistrarRetroalimentacionUseCase
from src.prediction.infrastructure.adapters.resultado_inferencia_adapter import SqlAlchemyResultadoInferenciaAdapter
from src.prediction.infrastructure.dto.registrar_retroalimentacion_dto import RegistrarRetroalimentacionDTO
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
from src.prediction.infrastructure.repositories.patologia_m04_repository import SqlAlchemyPatologiaM04Repository
from src.prediction.infrastructure.repositories.retroalimentacion_clinica_repository import SqlAlchemyRetroalimentacionClinicaRepository
from src.prediction.infrastructure.schema.retroalimentacion_clinica_schema import RetroalimentacionClinicaResponse
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(
    prefix="/prediccion/retroalimentacion",
    tags=["Predicción M04 - Retroalimentación Clínica"],
)

_RECURSO = 45


@router.post(
    "",
    status_code=201,
    response_model=RetroalimentacionClinicaResponse,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Registrar retroalimentación clínica sobre un resultado de inferencia (RF-72)",
)
def registrar_retroalimentacion(
    dto: RegistrarRetroalimentacionDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> RetroalimentacionClinicaResponse:
    use_case = RegistrarRetroalimentacionUseCase(
        db=db,
        repo=SqlAlchemyRetroalimentacionClinicaRepository(db),
        resultado_port=SqlAlchemyResultadoInferenciaAdapter(db),
        patologia_repo=SqlAlchemyPatologiaM04Repository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
    )
    entidad = use_case.execute(dto, usuario_actual.id_usuario)
    return RetroalimentacionClinicaResponse.from_entity(entidad)
