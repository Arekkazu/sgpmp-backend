# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | PEND-456 RF-66/RF-68: monitor de predicción con datos reales       |
# | 2026-10-30 | Arekkazu | RF-66: POST para que el motor IA registre sus resultados           |
# | 2026-10-30 | Arekkazu | RF-66: patología base por código RF-64                             |
# | 2026-11-02 | Arekkazu | RF-68: cada resultado nuevo dispara el riesgo de contagio de su lote |
# | 2026-11-02 | Arekkazu | RFC-021 C21.4: el disparo recalcula también las áreas expuestas    |
"""Resultados del motor de inferencia (RF-66) en ``modulo4.resultados_inferencia``.

  GET  /prediccion/inferencias — Monitor. Mismo recurso que el historial diagnóstico
                                 (42, R): los mismos resultados, sin fijar un activo.
  POST /prediccion/inferencias — Interno: el motor IA (`motor-ia`) entrega un resultado.
                                 Token ``IOT_INFERENCIA_M04_TOKEN``, sin usuario ni RBAC.
                                 Un resultado nuevo dispara RF-68 para su lote; si RF-68
                                 falla, el resultado ya quedó guardado y la respuesta no cambia.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.application.use_cases.inferencia.registrar_resultado_inferencia_use_case import (
    RegistrarResultadoInferenciaUseCase,
)
from src.prediction.application.use_cases.monitor.listar_inferencias_use_case import ListarInferenciasUseCase
from src.prediction.application.use_cases.riesgo_contagio.disparar_riesgo_contagio_use_case import (
    DispararRiesgoContagioUseCase,
)
from src.prediction.application.use_cases.riesgo_contagio.estimar_riesgo_contagio_use_case import (
    EstimarRiesgoContagioUseCase,
)
from src.prediction.domain.entities.resultado_inferencia import ResultadoInferencia
from src.prediction.infrastructure.adapters.activo_biologico_m02_adapter import ActivoBiologicoM02Adapter
from src.prediction.infrastructure.adapters.alerta_contagio_rf57_adapter import AlertaContagioRf57Adapter
from src.prediction.infrastructure.adapters.contexto_contagio_m02_m09_adapter import ContextoContagioM02M09Adapter
from src.prediction.infrastructure.adapters.exposicion_topologia_m09_adapter import ExposicionTopologiaM09Adapter
from src.prediction.infrastructure.adapters.ocupacion_lote_m02_adapter import OcupacionLoteM02Adapter
from src.prediction.infrastructure.adapters.version_modelo_adapter import VersionModeloAdapter
from src.prediction.infrastructure.dto.registrar_resultado_inferencia_dto import RegistrarResultadoInferenciaDTO
from src.prediction.infrastructure.repositories.configuracion_motor_ia_repository import (
    SqlAlchemyConfiguracionMotorIARepository,
)
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)
from src.prediction.infrastructure.repositories.patologia_m04_repository import SqlAlchemyPatologiaM04Repository
from src.prediction.infrastructure.repositories.monitor_prediccion_repository import (
    SqlAlchemyMonitorPrediccionRepository,
)
from src.prediction.infrastructure.repositories.resultado_inferencia_repository import (
    SqlAlchemyResultadoInferenciaRepository,
)
from src.prediction.infrastructure.repositories.resultado_riesgo_contagio_repository import (
    SqlAlchemyResultadoRiesgoContagioRepository,
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

logger = logging.getLogger(__name__)

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
        patologia_repo=SqlAlchemyPatologiaM04Repository(db),
    ).execute(dto)
    if registro.duplicado:
        response.status_code = 200
    else:
        _disparar_riesgo_contagio(db, registro.resultado)
    r = registro.resultado
    return ResultadoInferenciaRegistradoResponse(
        id_resultado_inferencia=r.id_resultado_inferencia,
        duplicado=registro.duplicado,
        modo_sombra=r.modo_sombra,
        latencia_excedida=r.latencia_excedida,
        tiene_alerta_generada=r.tiene_alerta_generada,
    )


def _disparar_riesgo_contagio(db: Session, resultado: ResultadoInferencia) -> None:
    """RF-68 tras RF-66. Nunca tumba el registro: el resultado ya está confirmado."""
    try:
        exposicion = ExposicionTopologiaM09Adapter(db)
        DispararRiesgoContagioUseCase(
            contexto_port=ContextoContagioM02M09Adapter(db),
            exposicion_port=exposicion,
            estimar=EstimarRiesgoContagioUseCase(
                db=db,
                config_repo=SqlAlchemyConfiguracionMotorIARepository(db),
                resultado_repo=SqlAlchemyResultadoRiesgoContagioRepository(db),
                activo_port=ActivoBiologicoM02Adapter(db),
                ocupacion_port=OcupacionLoteM02Adapter(db),
                alerta_port=AlertaContagioRf57Adapter(db),
                auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
                exposicion_port=exposicion,
            ),
        ).execute(resultado)
    except Exception:
        db.rollback()
        logger.exception("RF-68: falló el cálculo automático del lote %s", resultado.id_activo_biologico)
