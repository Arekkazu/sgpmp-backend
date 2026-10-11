"""Taxonomía de modelos de IA por tipo de manejo (RFC-009, M04 + RF-20 de M09).

`tipo_modelo` dejó de clasificarse por tamaño del animal: ahora son seis modelos
en tres paradigmas. El paradigma no se envía, se deriva del tipo, y decide qué
validaciones, métricas y campos aplican (RF-65/69/70/73). Vive en `shared`
porque lo consumen M04 (prediction) y M09 (área y especie).
"""
from __future__ import annotations

from typing import Literal, Optional, get_args

POBLACIONAL = "POBLACIONAL"
INDIVIDUAL = "INDIVIDUAL"
META = "META"

# RF-20: el meta-modelo de contagio no se asigna a un área ni es familia de una especie.
TipoModeloAsignable = Literal[
    "MODELO_AVES",
    "MODELO_PORCINOS",
    "MODELO_ACUICULTURA",
    "MODELO_ESPECIES_MEDIANAS",
    "MODELO_ESPECIES_GRANDES",
]
TipoModelo = Literal[TipoModeloAsignable, "MODELO_RIESGO_CONTAGIO"]
# RF-69/RF-70: los modelos POBLACIONAL se versionan y despliegan por componente.
Componente = Literal["DETECTOR", "SEGUIMIENTO", "METRICAS", "ANOMALIAS"]

PARADIGMA_POR_TIPO_MODELO: dict[str, str] = {
    "MODELO_AVES": POBLACIONAL,
    "MODELO_PORCINOS": POBLACIONAL,
    "MODELO_ACUICULTURA": POBLACIONAL,
    "MODELO_ESPECIES_MEDIANAS": INDIVIDUAL,
    "MODELO_ESPECIES_GRANDES": INDIVIDUAL,
    "MODELO_RIESGO_CONTAGIO": META,
}
TIPOS_MODELO = frozenset(PARADIGMA_POR_TIPO_MODELO)
TIPOS_MODELO_ASIGNABLES = frozenset(get_args(TipoModeloAsignable))
COMPONENTES_POBLACIONAL = frozenset(get_args(Componente))


def paradigma_de(tipo_modelo: Optional[str]) -> Optional[str]:
    return PARADIGMA_POR_TIPO_MODELO.get(tipo_modelo) if tipo_modelo else None


def es_poblacional(tipo_modelo: Optional[str]) -> bool:
    return paradigma_de(tipo_modelo) == POBLACIONAL
