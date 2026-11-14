# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-229-G070 RF-72: ventana de retroalimentación desde M09     |
"""Router de la ventana de retroalimentación de RF-72 (`/configuracion/parametros-retroalimentacion`).

  GET   /configuracion/parametros-retroalimentacion — valor efectivo y rango (R sobre recurso 21)
  PATCH /configuracion/parametros-retroalimentacion — cambia la ventana (U sobre recurso 21)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.configuracion_global.parametros_retroalimentacion_use_case import (
    ParametrosRetroalimentacionUseCase,
)
from src.configuration.infrastructure.dto.actualizar_parametros_alertas_dto import ActualizarParametrosAlertasDTO
from src.configuration.infrastructure.schema.parametros_alertas_schema import ParametroAlertaSchema
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(
    prefix="/configuracion/parametros-retroalimentacion",
    tags=["Configuración - Ventana de retroalimentación (RF-72)"],
)

_RECURSO = 21  # modulo1.recursos: 'configuraciones_globales', igual que /configuracion/parametros-alertas


def _use_case(db: Session) -> ParametrosRetroalimentacionUseCase:
    return ParametrosRetroalimentacionUseCase(db, SqlAlchemyParametrosMLOpsRepository(db))


@router.get(
    "",
    response_model=list[ParametroAlertaSchema],
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Consultar la ventana de retroalimentación de RF-72",
)
def consultar_parametros_retroalimentacion(db: Session = Depends(get_db)) -> list[ParametroAlertaSchema]:
    """`fuente`: CONFIGURADO o SIN_CONFIGURAR."""
    return [ParametroAlertaSchema.model_validate(p) for p in _use_case(db).consultar()]


@router.patch(
    "",
    response_model=list[ParametroAlertaSchema],
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Actualizar la ventana de retroalimentación de RF-72 (7 a 365 días)",
)
def actualizar_parametros_retroalimentacion(
    dto: ActualizarParametrosAlertasDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> list[ParametroAlertaSchema]:
    """`{"parametros": {"ventana_retroalimentacion_dias": 120}}`. Fuera de 7..365, no entero o un
    nombre ajeno responde 400; el autor queda registrado."""
    parametros = _use_case(db).actualizar(dto.parametros, usuario_actual.id_usuario)
    return [ParametroAlertaSchema.model_validate(p) for p in parametros]
