# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | INC-M05-340-G27 RF-78 CA-13: unidad de medida de cada tipo directo |
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

ETIQUETA_TIPO = {
    TipoSuministro.ALIMENTO.value: "alimento",
    TipoSuministro.MEDICAMENTO.value: "medicamento",
    TipoSuministro.SERVICIO_VETERINARIO.value: "servicio veterinario",
    TipoSuministro.INSEMINACION.value: "inseminación",
}

# Restricción 11: unidad única por tipo, sin conversiones. Configuración (M09) no tiene catálogo de
# unidades por tipo de suministro, así que vive aquí junto al CHECK que fija los tipos.
UNIDAD_POR_TIPO = {
    TipoSuministro.SERVICIO_VETERINARIO.value: "servicio",
    TipoSuministro.INSEMINACION.value: "servicio",
}
