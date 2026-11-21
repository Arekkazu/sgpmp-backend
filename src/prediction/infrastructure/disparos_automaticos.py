# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66/RF-68: disparos automáticos de M04 (fuera de un request)   |
"""Ensamblado de los disparos automáticos de M04, compartido por el router y el worker.

- ``disparar_riesgo_contagio``: RF-68 tras cada resultado nuevo de RF-66 (lo llama el POST
  del motor IA y el poblacional).
- ``evaluar_anomalia_poblacional``: RF-66 POBLACIONAL tras ``VISION_CALIDAD`` (worker).

Ninguno tumba a quien lo llama: lo anterior ya está confirmado; el fallo queda en el log.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from src.prediction.application.use_cases.poblacional.evaluar_anomalia_poblacional_use_case import (
    EvaluarAnomaliaPoblacionalUseCase,
)
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
from src.prediction.infrastructure.adapters.observacion_poblacional_m03_m09_adapter import (
    ObservacionPoblacionalM03M09Adapter,
)
from src.prediction.infrastructure.adapters.ocupacion_lote_m02_adapter import OcupacionLoteM02Adapter
from src.prediction.infrastructure.repositories.configuracion_motor_ia_repository import (
    SqlAlchemyConfiguracionMotorIARepository,
)
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)
from src.prediction.infrastructure.repositories.resultado_inferencia_repository import (
    SqlAlchemyResultadoInferenciaRepository,
)
from src.prediction.infrastructure.repositories.resultado_riesgo_contagio_repository import (
    SqlAlchemyResultadoRiesgoContagioRepository,
)
from src.prediction.infrastructure.repositories.version_modelo_repository import SqlAlchemyVersionModeloRepository

logger = logging.getLogger(__name__)


def disparar_riesgo_contagio(db: Session, resultado: ResultadoInferencia) -> None:
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


def evaluar_anomalia_poblacional(db: Session, id_observacion_vision: int) -> None:
    """RF-66 POBLACIONAL de una observación ya evaluada por RF-62.

    ponytail: sin reintento propio; si falla, esa ventana queda sin resultado (la calidad sí
    quedó). Pasar a una etapa post-commit propia si se necesita reintentar.
    """
    try:
        EvaluarAnomaliaPoblacionalUseCase(
            db=db,
            observacion_port=ObservacionPoblacionalM03M09Adapter(db),
            config_repo=SqlAlchemyConfiguracionMotorIARepository(db),
            version_repo=SqlAlchemyVersionModeloRepository(db),
            resultado_repo=SqlAlchemyResultadoInferenciaRepository(db),
            disparar=lambda resultado: disparar_riesgo_contagio(db, resultado),
        ).execute(id_observacion_vision)
    except Exception:
        db.rollback()
        logger.exception("RF-66 POBLACIONAL: falló la observación de visión %s", id_observacion_vision)
