# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | PEND-456 RF-66/RF-68: monitor de predicción con datos reales       |
"""Monitor del motor de inferencia (RF-66): ``GET /prediccion/inferencias``.

Lee ``modulo4.resultados_inferencia``, que escribe el motor de IoT/IA. Mismo recurso
que el historial diagnóstico (42, R): son los mismos resultados, sin fijar un activo.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.application.use_cases.monitor.listar_inferencias_use_case import ListarInferenciasUseCase
from src.prediction.infrastructure.repositories.monitor_prediccion_repository import (
    SqlAlchemyMonitorPrediccionRepository,
)
from src.prediction.infrastructure.schema.monitor_prediccion_schema import InferenciaMonitorResponse
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter
from src.shared.database import get_db
from src.shared.fechas import FechaHoraUtc
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/prediccion/inferencias", tags=["Predicción M04 - Monitor de inferencia"])

_RECURSO = 42  # modulo1.recursos: 'historial_diagnostico'


@router.get(
    "",
    response_model=list[InferenciaMonitorResponse],
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Resultados del motor de inferencia en las fincas del usuario (RF-66)",
)
def listar_inferencias(
    tipo_modelo: Optional[str] = Query(default=None),
    nivel_riesgo: Optional[int] = Query(default=None, description="0 Normal, 1 Bajo, 2 Moderado, 3 Alto"),
    desde: Optional[FechaHoraUtc] = Query(default=None),
    hasta: Optional[FechaHoraUtc] = Query(default=None),
    limite: int = Query(default=50, description="Máximo 200; los más recientes primero."),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> list[InferenciaMonitorResponse]:
    fincas = AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(usuario_actual.id_usuario, usuario_actual.id_rol)
    items = ListarInferenciasUseCase(SqlAlchemyMonitorPrediccionRepository(db)).execute(
        ids_fincas=fincas, tipo_modelo=tipo_modelo, nivel_riesgo=nivel_riesgo, desde=desde, hasta=hasta,
        limite=limite,
    )
    return [InferenciaMonitorResponse.model_validate(i) for i in items]
