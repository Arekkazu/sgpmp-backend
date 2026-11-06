# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-97/RF-109: datos del sistema origen y límites de la exportación |
"""Configuración de M07 por variables de entorno (RF-109 sin ficha: ver el plan de M07).

- ``SGPMP_ENTORNO``: ``DEV``, ``TEST`` o ``PROD``; va a ``SourceSystem.Environment`` y, en ``PROD``,
  exige el anexo APROBADO para activar un contrato (fuera de producción basta EN_REVISION).
- ``M07_LIMITE_BYTES`` (20 MB, el límite de SIGCON por lote) y ``M07_TIMEOUT_SEGUNDOS`` (5 s, RF-95 Fase 5).
"""
from __future__ import annotations

import os

from src.accounting_integration.domain.services.aaef import SistemaOrigen

ENTORNO = os.getenv("SGPMP_ENTORNO", "DEV").strip().upper()
SISTEMA_ORIGEN = SistemaOrigen(system_id="SGPMP", system_name="SIGAB", environment=ENTORNO)
LIMITE_BYTES = int(os.getenv("M07_LIMITE_BYTES", str(20 * 1024 * 1024)))
TIMEOUT_SEGUNDOS = int(os.getenv("M07_TIMEOUT_SEGUNDOS", "5"))


def es_produccion() -> bool:
    return ENTORNO == "PROD"
