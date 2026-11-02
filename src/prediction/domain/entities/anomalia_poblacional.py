# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66 POBLACIONAL: puntaje de anomalía del área contra RF-24     |
"""RF-66 POBLACIONAL (RFC-009/RFC-011): el riesgo del área sale de comparar su vector de
comportamiento (sobre D4 de la cámara) con la línea base del área y especie (RF-24).

Puntaje = media de las desviaciones relativas |x − mediana| / max(|mediana|, ε) de los
componentes calibrados, acotada a [0, 1]: 0 es el comportamiento de siempre y 1 un cambio del
100 % o más. Es la regla provisional mientras AIoT/Análisis definen la del componente
ANOMALIAS (DEV, sombra). Dominio puro.
"""
from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal
from typing import Optional

EPSILON = Decimal("0.01")
_CUATRO = Decimal("0.0001")


def score_anomalia(vector: dict, linea_base: dict) -> Optional[Decimal]:
    """None si el vector no comparte ningún componente con la línea base."""
    desviaciones = [
        abs(Decimal(str(vector[c])) - Decimal(str(m))) / max(abs(Decimal(str(m))), EPSILON)
        for c, m in linea_base.items()
        if vector.get(c) is not None and m is not None
    ]
    if not desviaciones:
        return None
    return min(Decimal(1), sum(desviaciones) / len(desviaciones)).quantize(_CUATRO, ROUND_HALF_EVEN)


def nivel_poblacional(score: Decimal, umbral: Optional[Decimal]) -> int:
    """Bajo el umbral, 0; desde el umbral, 2 (alto) y desde la mitad del camino a 1, 3 (crítico).
    Sin umbral en RF-65 el área no se clasifica (0, y el front lo muestra «sin umbral»)."""
    if not umbral or score < umbral:
        return 0
    return 3 if score >= (1 + umbral) / 2 else 2
