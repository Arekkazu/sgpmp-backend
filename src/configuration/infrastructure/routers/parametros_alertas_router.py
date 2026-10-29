# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-168-G76 RF-57: GET/PATCH /configuracion/parametros-alertas |
"""Router de los parámetros de RF-57 que configura el administrador (`/configuracion/parametros-alertas`).

  GET   /configuracion/parametros-alertas — valor efectivo, configurado, base y rango (R sobre recurso 21)
  PATCH /configuracion/parametros-alertas — cambia uno o varios (U sobre recurso 21)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.configuracion_global.parametros_alertas_use_case import ParametrosAlertasUseCase
from src.configuration.infrastructure.dto.actualizar_parametros_alertas_dto import ActualizarParametrosAlertasDTO
from src.configuration.infrastructure.schema.parametros_alertas_schema import ParametroAlertaSchema
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/parametros-alertas", tags=["Configuración - Parámetros de alertas (RF-57)"])

_RECURSO = 21  # modulo1.recursos: 'configuraciones_globales' (el mismo de los parámetros operativos)


def _use_case(db: Session) -> ParametrosAlertasUseCase:
    return ParametrosAlertasUseCase(db, SqlAlchemyParametrosMLOpsRepository(db))


@router.get(
    "",
    response_model=list[ParametroAlertaSchema],
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Consultar los parámetros de RF-57 (umbral E12/E13, confianza mínima, ventana E16, tormenta)",
)
def consultar_parametros_alertas(db: Session = Depends(get_db)) -> list[ParametroAlertaSchema]:
    """`fuente`: CONFIGURADO, VALOR_BASE (el del RF, sin configurar) o SIN_CONFIGURAR (sin valor base)."""
    return [ParametroAlertaSchema.model_validate(p) for p in _use_case(db).consultar()]


@router.patch(
    "",
    response_model=list[ParametroAlertaSchema],
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Actualizar parámetros de RF-57 (validación y lock de DEV-14)",
)
def actualizar_parametros_alertas(
    dto: ActualizarParametrosAlertasDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> list[ParametroAlertaSchema]:
    """Un nombre ajeno a RF-57 o un valor fuera de rango responde 400; el autor queda registrado."""
    parametros = _use_case(db).actualizar(dto.parametros, usuario_actual.id_usuario)
    return [ParametroAlertaSchema.model_validate(p) for p in parametros]
