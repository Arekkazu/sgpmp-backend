"""Política de densidad para activos poblacionales (RF-36)."""
from __future__ import annotations

from decimal import Decimal

from src.shared.errors import BusinessRuleError, ConflictError


def calcular_y_validar_densidad(
    *,
    cantidad_actual: int,
    superficie: Decimal,
    densidad_maxima_por_especie: Decimal | None,
) -> Decimal:
    """Calcula la densidad y exige el límite biológico configurado en M09."""
    if superficie <= 0:
        raise BusinessRuleError(
            code='SUPERFICIE_INFRAESTRUCTURA_INVALIDA',
            message='La infraestructura debe tener una superficie mayor a cero para calcular la densidad.',
            field='id_infraestructura',
        )

    if densidad_maxima_por_especie is None:
        raise BusinessRuleError(
            code='DENSIDAD_MAXIMA_NO_CONFIGURADA',
            message='La especie no tiene configurada una densidad máxima en M09.',
            field='id_especie',
        )

    densidad = Decimal(str(cantidad_actual)) / superficie
    if densidad > densidad_maxima_por_especie:
        raise ConflictError(
            code='DENSIDAD_MAXIMA_SUPERADA',
            message='La densidad del lote supera el máximo permitido para la especie.',
        )
    return densidad
