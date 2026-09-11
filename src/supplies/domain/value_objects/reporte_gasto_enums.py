"""Enums de dominio del reporte de gastos acumulados (RF-77 / CU-04)."""
from __future__ import annotations

from enum import Enum


class GranularidadDesglose(str, Enum):
    """Agrupación temporal del reporte (entrada ``tipo_periodo`` del RF-77)."""

    SEMANAL = "SEMANAL"
    MENSUAL = "MENSUAL"
    CICLO_COMPLETO = "CICLO_COMPLETO"  # sin desglose, acumulado total


class EstadoTendencia(str, Enum):
    """Estado de la comparación vs. el período anterior equivalente."""

    CALCULADA = "CALCULADA"
    SIN_BASE_COMPARATIVA = "SIN_BASE_COMPARATIVA"  # período anterior en cero
    SIN_MOVIMIENTO = "SIN_MOVIMIENTO"              # ambos períodos en cero


class CategoriaGasto(str, Enum):
    ALIMENTACION = "ALIMENTACION"
    MEDICACION = "MEDICACION"
