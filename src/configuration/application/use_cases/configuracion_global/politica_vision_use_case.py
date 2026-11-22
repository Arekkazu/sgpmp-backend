# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | INC-M03-82-G192 RF-62: política de visión configurable desde M09   |
"""Los 7 parámetros de la política de visión de RF-62 (RFC-011), configurables por el administrador.

Antes solo se sembraban con ``scripts/configurar_parametros_dev14.py --sembrar-vision``.
"""
from __future__ import annotations

from typing import Any

from src.configuration.application.use_cases.configuracion_global.parametros_alertas_use_case import (
    ParametroAlerta,
    ParametrosAlertasUseCase,
)
from src.configuration.domain.entities.parametros_vision import (
    DEGRADADA, FACTOR, OPTIMA, PREDETERMINADOS_VISION, TOLERABLES, W1, W2, W3,
)

_DESCRIPCIONES = {
    W1: "Peso de la confianza de detección en el índice de calidad (w1 + w2 + w3 = 1)",
    W2: "Peso de la continuidad de tracks en el índice de calidad",
    W3: "Peso de la estabilidad de la observación en el índice de calidad",
    TOLERABLES: "Tracks perdidos tolerables por ventana antes de penalizar",
    OPTIMA: "Índice mínimo (0-100) para clasificar la observación como ÓPTIMA",
    DEGRADADA: "Índice mínimo (0-100) para DEGRADADA; debajo es NO_APTO (menor que el óptimo)",
    FACTOR: "Factor que multiplica el índice mientras la cámara está EN_CALIBRACION",
}
PARAMETROS_VISION = {nombre: (PREDETERMINADOS_VISION[nombre], d) for nombre, d in _DESCRIPCIONES.items()}


class PoliticaVisionUseCase(ParametrosAlertasUseCase):
    catalogo = PARAMETROS_VISION
    codigo_invalido, rf = "PARAMETRO_VISION_INVALIDO", "la política de visión (RF-62)"

    def actualizar(self, cambios: dict[str, Any], id_usuario: int) -> list[ParametroAlerta]:
        # DEV-14 valida los 7 juntos (pesos que suman 1, óptimo > degradado): en una BD sin
        # sembrar, los que no se envían toman el valor base de RFC-011.
        faltantes = set(self.catalogo) - set(self.parametros_repo.obtener(list(self.catalogo)))
        base = {nombre: self.catalogo[nombre][0] for nombre in faltantes}
        return super().actualizar({**base, **cambios}, id_usuario)
