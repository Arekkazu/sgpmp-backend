# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | INC-M03-82-G192 RF-62: GET/PATCH /configuracion/politica-vision    |
"""Router de la política de visión de RF-62 (`/configuracion/politica-vision`).

  GET   /configuracion/politica-vision — w1, w2, w3, tracks_perdidos_tolerables, umbral_optima,
                                         umbral_degradada y factor_en_calibracion (R sobre recurso 21)
  PATCH /configuracion/politica-vision — cambia uno o varios (U sobre recurso 21)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.configuracion_global.politica_vision_use_case import PoliticaVisionUseCase
from src.configuration.infrastructure.dto.actualizar_parametros_alertas_dto import ActualizarParametrosAlertasDTO
from src.configuration.infrastructure.schema.parametros_alertas_schema import ParametroAlertaSchema
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/politica-vision", tags=["Configuración - Política de visión (RF-62)"])

_RECURSO = 21  # modulo1.recursos: 'configuraciones_globales', igual que /configuracion/parametros-alertas


def _use_case(db: Session) -> PoliticaVisionUseCase:
    return PoliticaVisionUseCase(db, SqlAlchemyParametrosMLOpsRepository(db))


@router.get(
    "",
    response_model=list[ParametroAlertaSchema],
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Consultar la política de visión de RF-62 (pesos, tracks tolerables, umbrales y factor)",
)
def consultar_politica_vision(db: Session = Depends(get_db)) -> list[ParametroAlertaSchema]:
    """`fuente`: CONFIGURADO o VALOR_BASE (el de RFC-011, todavía sin configurar)."""
    return [ParametroAlertaSchema.model_validate(p) for p in _use_case(db).consultar()]


@router.patch(
    "",
    response_model=list[ParametroAlertaSchema],
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Actualizar la política de visión de RF-62 sin redespliegue",
)
def actualizar_politica_vision(
    dto: ActualizarParametrosAlertasDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> list[ParametroAlertaSchema]:
    """400 si w1 + w2 + w3 ≠ 1, si umbral_optima ≤ umbral_degradada o un valor sale de su rango."""
    parametros = _use_case(db).actualizar(dto.parametros, usuario_actual.id_usuario)
    return [ParametroAlertaSchema.model_validate(p) for p in parametros]
