# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66 POBLACIONAL: resultado por observación de visión y RF-68   |
"""RF-66 POBLACIONAL: cada observación de visión apta (RF-62) se compara con la línea base del
área (RF-24) y deja un resultado por lote, que dispara RF-68 con ``SCORE_POBLACIONAL``.

Lo llama el worker post-commit justo después de ``VISION_CALIDAD`` (la calidad ya está
confirmada). Forma de salida que lee el front (N-05): ``probabilidad_riesgo`` con
``score_anomalia`` y ``umbral_score_anomalia`` (RF-65); sin patología ni probabilidades por clase.
La versión es la del componente ANOMALIAS o, mientras no exista, la del DETECTOR (RF-69).
Es idempotente por (lote, modelo, fin de ventana): un reintento del worker no duplica.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Optional

from sqlalchemy.orm import Session

from src.prediction.domain.entities.anomalia_poblacional import nivel_poblacional, score_anomalia
from src.prediction.domain.entities.resultado_inferencia import ResultadoInferencia
from src.prediction.domain.repositories.configuracion_motor_ia_repository import ConfiguracionMotorIARepository
from src.prediction.domain.repositories.observacion_poblacional_port import (
    LotePoblacional,
    ObservacionPoblacional,
    ObservacionPoblacionalPort,
)
from src.prediction.domain.repositories.resultado_inferencia_repository import ResultadoInferenciaRepository
from src.prediction.domain.repositories.version_modelo_repository import VersionModeloRepository

logger = logging.getLogger(__name__)

COMPONENTES_VERSION = ("ANOMALIAS", "DETECTOR")


class EvaluarAnomaliaPoblacionalUseCase:

    def __init__(self, *, db: Session, observacion_port: ObservacionPoblacionalPort,
                 config_repo: ConfiguracionMotorIARepository, version_repo: VersionModeloRepository,
                 resultado_repo: ResultadoInferenciaRepository,
                 disparar: Optional[Callable[[ResultadoInferencia], None]] = None) -> None:
        self.db = db
        self.observacion_port = observacion_port
        self.config_repo = config_repo
        self.version_repo = version_repo
        self.resultado_repo = resultado_repo
        self.disparar = disparar

    def execute(self, id_observacion: int) -> list[ResultadoInferencia]:
        obs = self.observacion_port.obtener(id_observacion)
        if obs is None or not obs.apto_para_ia:
            return []
        resultados = []
        for lote in self.observacion_port.lotes(obs.id_area):
            resultado = self._resultado(obs, lote)
            if resultado is None:
                continue
            try:
                resultados.append(self.resultado_repo.guardar(resultado))
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
        for resultado in resultados:
            self._contagio(resultado)
        return resultados

    def _resultado(self, obs: ObservacionPoblacional, lote: LotePoblacional) -> Optional[ResultadoInferencia]:
        base = self.observacion_port.linea_base(obs.id_area, lote.id_especie)
        score = score_anomalia(obs.vector, base) if base else None
        if score is None:
            logger.info("RF-66 POBLACIONAL: área %s sin línea base RF-24 para la especie %s", obs.id_area, lote.id_especie)
            return None
        if self.observacion_port.ya_evaluado(lote.id_activo, lote.tipo_modelo, obs.fecha_fin):
            return None
        version = next((v for c in COMPONENTES_VERSION for estado in ("ACTIVO", "SOMBRA")
                        if (v := self.version_repo.obtener_activo_por_tipo(lote.tipo_modelo, c, estado=estado))), None)
        if version is None:
            logger.info("RF-66 POBLACIONAL: %s sin versión ACTIVA ni en SOMBRA en RF-69", lote.tipo_modelo)
            return None
        config = self.config_repo.obtener_por_tipo(lote.tipo_modelo)
        umbral = config.umbral_score_anomalia if config is not None and config.es_activa else None
        return ResultadoInferencia(
            id_resultado_inferencia=uuid.uuid4(),
            id_activo_biologico=lote.id_activo,
            tipo_modelo=lote.tipo_modelo,
            id_version_modelo=version.id_version_modelo,
            nivel_riesgo=nivel_poblacional(score, umbral),
            probabilidad_riesgo={"score_anomalia": float(score),
                                 "umbral_score_anomalia": float(umbral) if umbral is not None else None},
            probabilidad_enfermedad={},
            # Calidad DEGRADADA (RF-62) baja la confianza; no hay probabilidades por clase.
            confianza_global=Decimal("0.5") if obs.confianza_baja else Decimal("1"),
            contexto_incompleto=obs.confianza_baja,
            modo_ejecucion="SERVIDOR",
            modo_sombra=version.estado_version != "ACTIVO",
            fecha_inferencia=datetime.now(timezone.utc),
            id_especie=lote.id_especie,
            fecha_inicio_ventana=obs.fecha_inicio,
            fecha_fin_ventana=obs.fecha_fin,
        )

    def _contagio(self, resultado: ResultadoInferencia) -> None:
        """RF-68 tras el resultado; nunca deshace el resultado ya confirmado."""
        if self.disparar is None:
            return
        try:
            self.disparar(resultado)
        except Exception:
            self.db.rollback()
            logger.exception("RF-68: falló el cálculo automático del lote poblacional %s", resultado.id_activo_biologico)
