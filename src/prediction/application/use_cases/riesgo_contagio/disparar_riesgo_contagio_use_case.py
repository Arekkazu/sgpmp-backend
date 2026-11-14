# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-68: disparo automático del riesgo de contagio tras cada resultado de RF-66 |
# | 2026-11-02 | Arekkazu | RFC-021 C21.4: recalcula las áreas expuestas cuando cambia un foco vecino |
# | 2026-11-02 | Arekkazu | RF-68: una salida POBLACIONAL entra como score_anomalia (SCORE_POBLACIONAL) |
"""RF-68 disparado por cada resultado nuevo de RF-66 (antes solo corría con un POST manual).

El lote es el activo del resultado (#857: M02 no relaciona individuos con su lote). Las entradas
que antes mandaba el cliente salen de la BD (``ContextoContagioPort``). El ambiente solo entra si
está sincronizado con la inferencia (CA-8, 35 s): fuera de eso se calcula sin Fa, con confianza
baja. Un resultado en sombra (modelo no vinculante) calcula y registra el contagio, sin alerta.

RFC-021 (C21.4, disparador «cambio de Fs en un vecino»): después del lote del resultado se
recalculan los lotes de las áreas a las que llega una arista activa desde la suya, para que su
exposición refleje el foco nuevo. Un solo salto: esos recálculos no disparan otros. Usan su propia
salida de RF-66 si es reciente; si no, se calculan con Fs ausente (ambiente, densidad y exposición).
La alerta de exposición de RFC-021 (umbral 0,40) todavía no se emite: esos recálculos no alertan.

Una salida POBLACIONAL (``score_anomalia`` en ``probabilidad_riesgo``) entra como el puntaje de
anomalía del área (Fs = ``SCORE_POBLACIONAL``) en vez de la probabilidad de riesgo alto.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from src.prediction.application.use_cases.riesgo_contagio.estimar_riesgo_contagio_use_case import (
    EstimarRiesgoContagioUseCase,
)
from src.prediction.domain.entities.resultado_inferencia import ResultadoInferencia
from src.prediction.domain.entities.riesgo_contagio import (
    SINCRONIA_MAXIMA,
    VIGENCIA_INFERENCIA,
    ResultadoRiesgoContagio,
)
from src.prediction.domain.repositories.contexto_contagio_port import ContextoContagioPort, SalidaReciente
from src.prediction.domain.repositories.exposicion_port import ExposicionPort
from src.prediction.infrastructure.dto.estimar_riesgo_contagio_dto import (
    EstimarRiesgoContagioDTO,
    SalidaRf66DTO,
    VariablesAmbientalesDTO,
)
from src.shared.errors import BusinessRuleError

logger = logging.getLogger(__name__)

ID_SISTEMA_DISPARO = "RF66_DISPARO_RF68"
#: probabilidad_riesgo de RF-66 viene por nivel (0 Normal … 3 Alto).
NIVEL_RIESGO_ALTO = "3"


class DispararRiesgoContagioUseCase:

    def __init__(self, *, contexto_port: ContextoContagioPort, estimar: EstimarRiesgoContagioUseCase,
                 exposicion_port: Optional[ExposicionPort] = None) -> None:
        self.contexto_port = contexto_port
        self.estimar = estimar
        self.exposicion_port = exposicion_port

    def execute(self, resultado: ResultadoInferencia) -> Optional[ResultadoRiesgoContagio]:
        """Contagio del lote del resultado; None si RF-68 no corre (el motivo ya queda en RF-73)."""
        salida = SalidaReciente(resultado.probabilidad_riesgo, resultado.fecha_inferencia, resultado.modo_sombra)
        foco = self._calcular(resultado.id_activo_biologico, salida, alertar=not resultado.modo_sombra,
                              exigir_cobertura_rf66=True)
        if self.exposicion_port is not None:
            ahora = datetime.now(timezone.utc)
            for lote in self.exposicion_port.lotes_expuestos(resultado.id_activo_biologico):
                if lote != resultado.id_activo_biologico:
                    propia = self.contexto_port.ultima_salida_rf66(lote, ahora - VIGENCIA_INFERENCIA)
                    self._calcular(lote, propia, alertar=False, exigir_cobertura_rf66=False)
        return foco

    def _calcular(self, id_lote: int, salida: Optional[SalidaReciente], *, alertar: bool,
                  exigir_cobertura_rf66: bool) -> Optional[ResultadoRiesgoContagio]:
        instante = salida.fecha_inferencia if salida else datetime.now(timezone.utc)
        contexto = self.contexto_port.obtener(id_lote, instante)
        if contexto is None:
            return None
        ambiente = contexto.ambiente
        if ambiente is not None and salida and abs(ambiente.fecha_captura - salida.fecha_inferencia) > SINCRONIA_MAXIMA:
            ambiente = None
        score = salida.probabilidad_riesgo.get("score_anomalia") if salida else None
        dto = EstimarRiesgoContagioDTO(
            id_lote=id_lote,
            score_anomalia=Decimal(str(score)) if score is not None else None,
            salidas_rf66=[SalidaRf66DTO(
                id_activo_biologico=id_lote,
                probabilidad_riesgo_alto=Decimal(str(salida.probabilidad_riesgo.get(NIVEL_RIESGO_ALTO, 0))),
                fecha_inferencia=salida.fecha_inferencia,
            )] if salida and score is None else [],
            densidad_poblacional=contexto.densidad_poblacional,
            variables_ambientales=VariablesAmbientalesDTO(
                temperatura=ambiente.temperatura, humedad_relativa=ambiente.humedad_relativa,
                fecha_captura=ambiente.fecha_captura,
            ) if ambiente else None,
            porcentaje_sensores_activos=contexto.porcentaje_sensores_activos,
        )
        try:
            return self.estimar.execute_sistema(dto, id_sistema=ID_SISTEMA_DISPARO, alertar=alertar,
                                                exigir_cobertura_rf66=exigir_cobertura_rf66)
        except BusinessRuleError as exc:
            logger.info("RF-68: lote %s sin cálculo automático: %s", id_lote, exc.code)
            return None
