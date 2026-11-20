# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-19 | Arekkazu | INC-M07-373-G37 RF-98: período de gracia del contrato contable configurable desde M09 |
"""Router del período de gracia del contrato contable (`/configuracion/parametros-integracion-contable`).

  GET   /configuracion/parametros-integracion-contable — mínimo y por defecto efectivos (R sobre recurso 21)
  PATCH /configuracion/parametros-integracion-contable — los cambia (U sobre recurso 21)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.configuracion_global.parametros_integracion_contable_use_case import (
    ParametrosIntegracionContableUseCase,
)
from src.configuration.infrastructure.dto.actualizar_parametros_alertas_dto import ActualizarParametrosAlertasDTO
from src.configuration.infrastructure.schema.parametros_alertas_schema import ParametroAlertaSchema
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(
    prefix="/configuracion/parametros-integracion-contable",
    tags=["Configuración - Período de gracia del contrato contable (RF-98)"],
)

_RECURSO = 21  # modulo1.recursos: 'configuraciones_globales', igual que /configuracion/parametros-alertas


def _use_case(db: Session) -> ParametrosIntegracionContableUseCase:
    return ParametrosIntegracionContableUseCase(db, SqlAlchemyParametrosMLOpsRepository(db))


@router.get(
    "",
    response_model=list[ParametroAlertaSchema],
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Consultar el período de gracia del contrato contable (RF-98)",
)
def consultar_parametros_integracion_contable(db: Session = Depends(get_db)) -> list[ParametroAlertaSchema]:
    """`aaef_gracia_minima_dias` y `aaef_gracia_defecto_dias`; `fuente`: CONFIGURADO o VALOR_BASE (30 y 90)."""
    return [ParametroAlertaSchema.model_validate(p) for p in _use_case(db).consultar()]


@router.patch(
    "",
    response_model=list[ParametroAlertaSchema],
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Actualizar el período de gracia del contrato contable (1 a 3650 días)",
)
def actualizar_parametros_integracion_contable(
    dto: ActualizarParametrosAlertasDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> list[ParametroAlertaSchema]:
    """`{"parametros": {"aaef_gracia_minima_dias": 30, "aaef_gracia_defecto_dias": 90}}`. Fuera de 1..3650,
    no entero, un por defecto menor que el mínimo o un nombre ajeno responde 400; el autor queda registrado."""
    parametros = _use_case(db).actualizar(dto.parametros, usuario_actual.id_usuario)
    return [ParametroAlertaSchema.model_validate(p) for p in parametros]
