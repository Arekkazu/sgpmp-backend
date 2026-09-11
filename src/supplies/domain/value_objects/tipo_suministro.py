"""Tipos de suministro acumulables por RF-78.

Mapea el ``CHECK`` de ``modulo5.registro_suministro.tipo_suministro``. ALIMENTO
y MEDICAMENTO se originan en RF-75/RF-76 (poblados por trigger, ver
``anotaciones/modulo_5/cu04_gaps_bd_rf77_rf81.md``); SERVICIO_VETERINARIO e
INSEMINACION se registran directamente en este CU (``DIRECTOS``).
"""
from __future__ import annotations

from enum import Enum


class TipoSuministro(str, Enum):
    ALIMENTO = "ALIMENTO"
    MEDICAMENTO = "MEDICAMENTO"
    SERVICIO_VETERINARIO = "SERVICIO_VETERINARIO"
    INSEMINACION = "INSEMINACION"


DIRECTOS = frozenset({TipoSuministro.SERVICIO_VETERINARIO, TipoSuministro.INSEMINACION})
