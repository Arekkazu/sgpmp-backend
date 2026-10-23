# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-81: cuatro niveles de volumen y tipos  |
"""Enums de dominio del historial/trazabilidad de suministros (RF-81 / CU-04)."""
from __future__ import annotations

from enum import Enum


class TipoTrabajoHistorial(str, Enum):
    """Tipo de trabajo async encolado (motor RF-81)."""

    CONSULTA_PESADA = "CONSULTA_PESADA"  # nivel de volumen 3/4
    EXPORTACION = "EXPORTACION"          # > 10.000 registros


class OrigenPrecio(str, Enum):
    """Origen del precio resuelto de un registro (columna real en BD)."""

    MANUAL = "MANUAL"
    M40_AUTOMATICO = "M40_AUTOMATICO"


class NaturalezaCosto(str, Enum):
    """Naturaleza contable del costo (columna real en BD, ver RF-78)."""

    MANTENIMIENTO = "MANTENIMIENTO"
    INVERSION = "INVERSION"
    VENTA = "VENTA"


class TipoSuministroFiltro(str, Enum):
    """Valores admitidos del filtro ``tipo_suministro_filtro`` (RF-81)."""

    ALIMENTO = "ALIMENTO"
    MEDICAMENTO = "MEDICAMENTO"
    SERVICIO_VETERINARIO = "SERVICIO_VETERINARIO"
    INSEMINACION = "INSEMINACION"
    TODOS = "TODOS"


class OrigenPrecioFiltro(str, Enum):
    MANUAL = "MANUAL"
    M40_AUTOMATICO = "M40_AUTOMATICO"
    TODOS = "TODOS"


class NivelVolumen(int, Enum):
    """Nivel de volumen histórico del activo (Restricción 11 de RF-81).

    - Nivel 1 (≤ 10.000) y Nivel 2 (≤ ``umbral_nivel3``, 50.000): síncronos.
    - Nivel 3 (≤ ``umbral_nivel4``, 200.000): síncrono salvo que lleve más de 3
      filtros o supere 10 s, entonces asíncrono (resultado en ≤ 60 s).
    - Nivel 4: asíncrono siempre (resultado en ≤ 5 min).
    """

    NIVEL_1 = 1
    NIVEL_2 = 2
    NIVEL_3 = 3
    NIVEL_4 = 4


UMBRAL_NIVEL_2 = 10_000
TIEMPO_ESTIMADO_SEGUNDOS = {NivelVolumen.NIVEL_3: 60, NivelVolumen.NIVEL_4: 300}


def nivel_volumen(total: int, umbral_nivel3: int, umbral_nivel4: int) -> NivelVolumen:
    if total <= UMBRAL_NIVEL_2:
        return NivelVolumen.NIVEL_1
    if total <= umbral_nivel3:
        return NivelVolumen.NIVEL_2
    if total <= umbral_nivel4:
        return NivelVolumen.NIVEL_3
    return NivelVolumen.NIVEL_4
