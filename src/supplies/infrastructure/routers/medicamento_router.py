"""Router FastAPI para el registro de medicamentos (`/suministros/medicamentos`).

Expone los flujos de RF-76 (CU-01):
  POST   /suministros/medicamentos               — Registrar aplicación de medicamento
  POST   /suministros/medicamentos/{id}/anulacion — Anular aplicación
  GET    /suministros/medicamentos               — Consultar/buscar aplicaciones

Autorización delegada al RBAC centralizado (``src/shared/rbac.py``):
  recurso ``medicamentos`` = id_recurso 48; acciones C=1, R=2, D=4.
  El registro (C) está restringido a Administrador y Veterinario.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.supplies.application.use_cases.suministros.anular_medicamento_use_case import AnularMedicamentoUseCase
from src.supplies.application.use_cases.suministros.consultar_medicamentos_use_case import (
    ConsultarMedicamentosUseCase,
)
from src.supplies.application.use_cases.suministros.registrar_medicamento_use_case import (
    RegistrarMedicamentoUseCase,
)
from src.supplies.infrastructure.adapters.activo_m02_adapter import ActivoM02Adapter
from src.supplies.infrastructure.adapters.ciclo_m02_adapter import CicloM02Adapter
from src.supplies.infrastructure.adapters.estado_activo_m02_adapter import EstadoActivoM02Adapter
from src.supplies.infrastructure.adapters.evento_sanitario_m02_adapter import EventoSanitarioM02Adapter
from src.supplies.infrastructure.adapters.notificacion_medicamento_email_adapter import (
    NotificacionMedicamentoEmailAdapter,
)
from src.supplies.infrastructure.dto.anular_registro_dto import AnularRegistroDTO
from src.supplies.infrastructure.dto.registrar_medicamento_dto import RegistrarMedicamentoDTO
from src.supplies.infrastructure.repositories.medicamento_repository import SqlAlchemyMedicamentoRepository
from src.supplies.infrastructure.schema.medicamento_schema import (
    ConsultaMedicamentosResponse,
    MedicamentoResponse,
    RegistroMedicamentoResponse,
)

router = APIRouter(prefix="/suministros/medicamentos", tags=["Suministros - Medicamentos"])

_RECURSO = 48  # modulo1.recursos: 'medicamentos'


@router.post(
    "",
    response_model=RegistroMedicamentoResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Registrar aplicación de medicamento (RF-76)",
)
def registrar_medicamento(
    dto: RegistrarMedicamentoDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> RegistroMedicamentoResponse:
    use_case = RegistrarMedicamentoUseCase(
        db=db,
        medicamento_repo=SqlAlchemyMedicamentoRepository(db),
        activo_port=ActivoM02Adapter(db),
        ciclo_port=CicloM02Adapter(db),
        evento_port=EventoSanitarioM02Adapter(db),
        estado_port=EstadoActivoM02Adapter(db),
        notificacion_port=NotificacionMedicamentoEmailAdapter(db),
    )
    resultado = use_case.execute(dto, usuario_actual)

    vigente = resultado.fecha_fin_retiro_vigente
    if vigente is not None:
        mensaje = (
            "El medicamento fue registrado correctamente. El período de retiro vigente del activo "
            f"se extiende hasta {vigente.isoformat()}."
        )
    else:
        mensaje = "El medicamento fue registrado correctamente. No aplica período de retiro."

    return RegistroMedicamentoResponse(
        medicamento=MedicamentoResponse.model_validate(resultado.medicamento),
        fecha_fin_retiro_vigente=vigente,
        mensaje=mensaje,
    )


@router.post(
    "/{id_medicamento}/anulacion",
    response_model=MedicamentoResponse,
    dependencies=[Depends(require_permission(_RECURSO, 4))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="Anular una aplicación de medicamento VALIDADA (RF-76)",
)
def anular_medicamento(
    id_medicamento: int,
    dto: AnularRegistroDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> MedicamentoResponse:
    use_case = AnularMedicamentoUseCase(
        db=db,
        medicamento_repo=SqlAlchemyMedicamentoRepository(db),
    )
    medicamento = use_case.execute(id_medicamento, dto, usuario_actual)
    return MedicamentoResponse.model_validate(medicamento)


@router.get(
    "",
    response_model=ConsultaMedicamentosResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Consultar/buscar aplicaciones de medicamento (RF-76)",
)
def consultar_medicamentos(
    id_activo_biologico: Optional[int] = Query(None, description="Filtrar por activo biológico."),
    fecha_desde: Optional[date] = Query(None, description="Fecha de aplicación mínima (inclusive)."),
    fecha_hasta: Optional[date] = Query(None, description="Fecha de aplicación máxima (inclusive)."),
    estado_registro: Optional[str] = Query(None, description="VALIDADO o ANULADO."),
    db: Session = Depends(get_db),
) -> ConsultaMedicamentosResponse:
    use_case = ConsultarMedicamentosUseCase(medicamento_repo=SqlAlchemyMedicamentoRepository(db))
    medicamentos = use_case.execute(
        id_activo_biologico=id_activo_biologico,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        estado_registro=estado_registro,
    )
    items = [MedicamentoResponse.model_validate(m) for m in medicamentos]
    return ConsultaMedicamentosResponse(total=len(items), items=items)
