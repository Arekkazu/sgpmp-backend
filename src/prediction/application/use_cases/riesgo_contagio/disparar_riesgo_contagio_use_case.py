# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-68: disparo automático del riesgo de contagio tras cada resultado de RF-66 |
"""RF-68 disparado por cada resultado nuevo de RF-66 (antes solo corría con un POST manual).

El lote es el activo del resultado (#857: M02 no relaciona individuos con su lote). Las entradas
que antes mandaba el cliente salen de la BD (``ContextoContagioPort``). El ambiente solo entra si
está sincronizado con la inferencia (CA-8, 35 s): fuera de eso se calcula sin Fa, con confianza
baja. Un resultado en sombra (modelo no vinculante) calcula y registra el contagio, sin alerta.

RFC-021 (RF-68 v2.0) pasa la unidad de cálculo al área y suma la exposición a las vecinas; el
punto de disparo sigue siendo este.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from src.prediction.application.use_cases.riesgo_contagio.estimar_riesgo_contagio_use_case import (
    EstimarRiesgoContagioUseCase,
)
from src.prediction.domain.entities.resultado_inferencia import ResultadoInferencia
from src.prediction.domain.entities.riesgo_contagio import SINCRONIA_MAXIMA, ResultadoRiesgoContagio
from src.prediction.domain.repositories.contexto_contagio_port import ContextoContagioPort
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

    def __init__(self, *, contexto_port: ContextoContagioPort, estimar: EstimarRiesgoContagioUseCase) -> None:
        self.contexto_port = contexto_port
        self.estimar = estimar

    def execute(self, resultado: ResultadoInferencia) -> Optional[ResultadoRiesgoContagio]:
        """None si RF-68 no corre (sin configuración, datos insuficientes…): el motivo ya queda en RF-73."""
        contexto = self.contexto_port.obtener(resultado.id_activo_biologico, resultado.fecha_inferencia)
        if contexto is None:
            return None
        ambiente = contexto.ambiente
        if ambiente is not None and abs(ambiente.fecha_captura - resultado.fecha_inferencia) > SINCRONIA_MAXIMA:
            ambiente = None
        dto = EstimarRiesgoContagioDTO(
            id_lote=resultado.id_activo_biologico,
            salidas_rf66=[SalidaRf66DTO(
                id_activo_biologico=resultado.id_activo_biologico,
                probabilidad_riesgo_alto=Decimal(str(resultado.probabilidad_riesgo.get(NIVEL_RIESGO_ALTO, 0))),
                fecha_inferencia=resultado.fecha_inferencia,
            )],
            densidad_poblacional=contexto.densidad_poblacional,
            variables_ambientales=VariablesAmbientalesDTO(
                temperatura=ambiente.temperatura, humedad_relativa=ambiente.humedad_relativa,
                fecha_captura=ambiente.fecha_captura,
            ) if ambiente else None,
            porcentaje_sensores_activos=contexto.porcentaje_sensores_activos,
        )
        try:
            return self.estimar.execute_sistema(dto, id_sistema=ID_SISTEMA_DISPARO, alertar=not resultado.modo_sombra)
        except BusinessRuleError as exc:
            logger.info("RF-68: lote %s sin cálculo automático: %s", resultado.id_activo_biologico, exc.code)
            return None
