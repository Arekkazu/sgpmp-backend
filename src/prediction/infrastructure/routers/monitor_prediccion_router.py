# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | PEND-456 RF-66/RF-68: monitor de predicción con datos reales       |
# | 2026-10-30 | Arekkazu | RF-66: POST para que el motor IA registre sus resultados           |
"""Resultados del motor de inferencia (RF-66) en ``modulo4.resultados_inferencia``.

  GET  /prediccion/inferencias — Monitor. Mismo recurso que el historial diagnóstico
                                 (42, R): los mismos resultados, sin fijar un activo.
  POST /prediccion/inferencias — Interno: el motor IA (`motor-ia`) entrega un resultado.
                                 Token ``IOT_INFERENCIA_M04_TOKEN``, sin usuario ni RBAC.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.application.use_cases.inferencia.registrar_resultado_inferencia_use_case import (
    RegistrarResultadoInferenciaUseCase,
)
from src.prediction.application.use_cases.monitor.listar_inferencias_use_case import ListarInferenciasUseCase
from src.prediction.infrastructure.adapters.activo_biologico_m02_adapter import ActivoBiologicoM02Adapter
from src.prediction.infrastructure.adapters.version_modelo_adapter import VersionModeloAdapter
from src.prediction.infrastructure.dto.registrar_resultado_inferencia_dto import RegistrarResultadoInferenciaDTO
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)
from src.prediction.infrastructure.repositories.monitor_prediccion_repository import (
    SqlAlchemyMonitorPrediccionRepository,
)
from src.prediction.infrastructure.repositories.resultado_inferencia_repository import (
    SqlAlchemyResultadoInferenciaRepository,
)
from src.prediction.infrastructure.schema.monitor_prediccion_schema import (
    InferenciaMonitorResponse,
    ResultadoInferenciaRegistradoResponse,
)
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter
from src.shared.broker_auth import require_token_servicio_motor_ia
from src.shared.database import get_db, get_db_sistema
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


@router.post(
    "",
    response_model=ResultadoInferenciaRegistradoResponse,
    status_code=201,
    dependencies=[Depends(require_token_servicio_motor_ia)],
    responses={
        200: {"model": ResultadoInferenciaRegistradoResponse, "description": "Ya estaba registrado (duplicado)."},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Registrar un resultado del motor de inferencia (RF-66, interno: motor IA)",
)
def registrar_resultado_inferencia(
    dto: RegistrarResultadoInferenciaDTO,
    response: Response,
    db: Session = Depends(get_db_sistema),
) -> ResultadoInferenciaRegistradoResponse:
    """201 si se guardó; 200 con ``duplicado: true`` si ese ``id_resultado_inferencia`` ya existía."""
    registro = RegistrarResultadoInferenciaUseCase(
        db=db,
        repo=SqlAlchemyResultadoInferenciaRepository(db),
        version_port=VersionModeloAdapter(db),
        activo_port=ActivoBiologicoM02Adapter(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
    ).execute(dto)
    if registro.duplicado:
        response.status_code = 200
    r = registro.resultado
    return ResultadoInferenciaRegistradoResponse(
        id_resultado_inferencia=r.id_resultado_inferencia,
        duplicado=registro.duplicado,
        modo_sombra=r.modo_sombra,
        latencia_excedida=r.latencia_excedida,
        tiene_alerta_generada=r.tiene_alerta_generada,
    )
