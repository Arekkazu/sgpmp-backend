# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-37 RF-73: reintentos, respaldo local y sincronización de la bitácora M04 |
"""Aviso al Administrador de la contingencia de la bitácora de M04 (RF-73 E8, DEV-37).

Best-effort, después del commit: una implementación nunca propaga un fallo de entrega.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class AvisoAuditoriaM04Port(ABC):
    @abstractmethod
    def avisar_fallback_activado(self, resumen: dict) -> None:
        """RF-73 E8: alerta AUDITORIA_FALLBACK_ACTIVADO con el inicio de la contingencia."""
