# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | PEND-456 RF-66/RF-68: monitor de predicción con datos reales       |
# | 2026-11-02 | Arekkazu | RF-66/RF-68: por_activo, las N más recientes de cada animal o lote |
"""Validación común de los filtros del monitor (inferencias y contagio)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.shared.errors import ValidationError
from src.shared.tipo_modelo import TIPOS_MODELO

LIMITE_MAXIMO = 200
#: Estado sanitario pide las últimas de cada animal o lote: con cámaras que emiten cada 20 s, las
#: 200 más recientes de todo el alcance dejan fuera a los animales sin eventos recientes.
POR_ACTIVO_MAXIMO = 50


def validar_filtros(
    *, nivel_riesgo: Optional[int], desde: Optional[datetime], hasta: Optional[datetime],
    limite: int, tipo_modelo: Optional[str] = None,
) -> int:
    """Devuelve el límite acotado a [1, LIMITE_MAXIMO]."""
    if tipo_modelo is not None and tipo_modelo not in TIPOS_MODELO:
        raise ValidationError(
            code="TIPO_MODELO_INVALIDO",
            message=f"tipo_modelo debe ser uno de: {sorted(TIPOS_MODELO)}.",
            field="tipo_modelo",
        )
    if nivel_riesgo is not None and not 0 <= nivel_riesgo <= 3:
        raise ValidationError(
            code="NIVEL_RIESGO_INVALIDO", message="nivel_riesgo debe estar entre 0 y 3.", field="nivel_riesgo",
        )
    if desde is not None and hasta is not None and desde > hasta:
        raise ValidationError(
            code="RANGO_FECHAS_INVALIDO",
            message="La fecha de inicio no puede ser posterior a la fecha de fin.",
            field="desde",
        )
    return max(1, min(limite, LIMITE_MAXIMO))


def validar_por_activo(por_activo: Optional[int]) -> Optional[int]:
    if por_activo is not None and not 1 <= por_activo <= POR_ACTIVO_MAXIMO:
        raise ValidationError(
            code="POR_ACTIVO_INVALIDO",
            message=f"por_activo debe estar entre 1 y {POR_ACTIVO_MAXIMO}.",
            field="por_activo",
        )
    return por_activo
