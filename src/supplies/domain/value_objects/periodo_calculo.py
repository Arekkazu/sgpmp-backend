"""Value object que resuelve la ventana de fechas de un período ICA (RF-74).

Traduce un ``PeriodoEvaluacion`` a un par ``(fecha_inicio, fecha_fin)`` concreto:

- ``SEMANAL``   → últimos 7 días (``hoy-6`` … ``hoy``).
- ``MENSUAL``   → mes en curso (día 1 del mes … ``hoy``).
- ``POR_CICLO`` → ``fecha_inicio_ciclo`` … (``fecha_cierre_ciclo`` o ``hoy``).

Es una función pura del dominio: no toca BD. La ``fecha_inicio_ciclo`` y la
``fecha_cierre`` se obtienen fuera (puertos ``ActivoConsultaPort`` /
``CicloAbiertoPort``) y se pasan como argumentos.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from src.shared.errors import BusinessRuleError
from src.supplies.domain.value_objects.eficiencia_enums import PeriodoEvaluacion


@dataclass(frozen=True)
class PeriodoCalculo:
    """Ventana temporal resuelta para el cálculo del ICA."""

    periodo: PeriodoEvaluacion
    fecha_inicio: date
    fecha_fin: date

    @classmethod
    def resolver(
        cls,
        periodo: PeriodoEvaluacion,
        *,
        hoy: date,
        fecha_inicio_ciclo: Optional[date] = None,
        fecha_cierre_ciclo: Optional[date] = None,
    ) -> "PeriodoCalculo":
        if periodo == PeriodoEvaluacion.SEMANAL:
            return cls(periodo, hoy - timedelta(days=6), hoy)

        if periodo == PeriodoEvaluacion.MENSUAL:
            return cls(periodo, hoy.replace(day=1), hoy)

        if periodo == PeriodoEvaluacion.POR_CICLO:
            if fecha_inicio_ciclo is None:
                raise BusinessRuleError(
                    code="CICLO_SIN_FECHA_INICIO",
                    message=(
                        "No es posible calcular el ICA POR_CICLO: el activo no tiene una "
                        "fecha de inicio de ciclo productivo."
                    ),
                    field="periodo_evaluacion",
                )
            return cls(periodo, fecha_inicio_ciclo, fecha_cierre_ciclo or hoy)

        raise BusinessRuleError(
            code="PERIODO_INVALIDO",
            message=f"Período de evaluación no soportado: {periodo}.",
            field="periodo_evaluacion",
        )
