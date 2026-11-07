# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-76: E11 200, edición 405 y alcance     |
"""Router FastAPI para el registro de medicamentos (`/suministros/medicamentos`).

Expone los flujos de RF-76 (CU-01):
  POST   /suministros/medicamentos               — Registrar aplicación de medicamento
  POST   /suministros/medicamentos/{id}/anulacion — Anular aplicación
  GET    /suministros/medicamentos               — Consultar/buscar aplicaciones
  PUT/PATCH/DELETE /suministros/medicamentos/{id} — 405: registro inmutable (R5)

Autorización delegada al RBAC centralizado (``src/shared/rbac.py``):
  recurso ``medicamentos`` = id_recurso 48; acciones C=1, R=2, D=4.
  El registro (C) está restringido a Administrador y Veterinario.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.supplies.infrastructure.dto.anular_registro_dto import AnularRegistroDTO
from src.supplies.infrastructure.dto.registrar_medicamento_dto import RegistrarMedicamentoDTO
from src.supplies.infrastructure.factories.suministros_factory import (
    build_anular_medicamento_use_case,
    build_consultar_medicamentos_use_case,
    build_rechazar_modificacion_use_case,
    build_registrar_medicamento_use_case,
)
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
    response: Response,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> RegistroMedicamentoResponse:
    """201 al registrar; 200 con los tratamientos activos si el activo ya estaba EN_TRATAMIENTO (E11)."""
    resultado = build_registrar_medicamento_use_case(db).execute(dto, usuario_actual)

    vigente = resultado.fecha_fin_retiro_vigente
    mensaje = resultado.mensaje
    if mensaje is not None:
        response.status_code = 200
    elif vigente is not None:
        mensaje = (
            "El medicamento fue registrado correctamente. El período de retiro vigente del activo "
            f"se extiende hasta {vigente.isoformat()}."
        )
    else:
        mensaje = "El medicamento fue registrado correctamente. No aplica período de retiro."

    return RegistroMedicamentoResponse(
        medicamento=MedicamentoResponse.model_validate(resultado.medicamento),
        fecha_fin_retiro_vigente=vigente,
        tratamientos_activos=resultado.tratamientos_activos,
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
    medicamento = build_anular_medicamento_use_case(db).execute(id_medicamento, dto, usuario_actual)
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
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ConsultaMedicamentosResponse:
    medicamentos = build_consultar_medicamentos_use_case(db).execute(
        usuario_actual,
        id_activo_biologico=id_activo_biologico,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        estado_registro=estado_registro,
    )
    items = [MedicamentoResponse.model_validate(m) for m in medicamentos]
    return ConsultaMedicamentosResponse(total=len(items), items=items)


_RESPUESTAS_405 = {404: {"model": ErrorResponse}, 405: {"model": ErrorResponse}}


# Un registro por método: con `methods=[...]` FastAPI repite el operationId y el OpenAPI queda inválido.
@router.put("/{id_medicamento}", responses=_RESPUESTAS_405, dependencies=[Depends(require_permission(_RECURSO, 2))],
            summary="Bloqueado: una aplicación VALIDADA es inmutable (RF-76 R5)")
@router.patch("/{id_medicamento}", responses=_RESPUESTAS_405, dependencies=[Depends(require_permission(_RECURSO, 2))],
              summary="Bloqueado: una aplicación VALIDADA es inmutable (RF-76 R5)")
@router.delete("/{id_medicamento}", responses=_RESPUESTAS_405, dependencies=[Depends(require_permission(_RECURSO, 2))],
               summary="Bloqueado: una aplicación VALIDADA es inmutable (RF-76 R5)")
def rechazar_modificacion_medicamento(id_medicamento: int, db: Session = Depends(get_db)) -> None:
    """RF-76 R5: la aplicación no se edita ni se borra; se anula y se registra de nuevo (405)."""
    build_rechazar_modificacion_use_case(db).medicamento(id_medicamento)
