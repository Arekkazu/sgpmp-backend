"""Puerto para verificar dependencias activas de una etapa del ciclo productivo.

Consulta si existen activos biológicos actualmente en la etapa. Si los hay,
la desactivación queda bloqueada (FA-03 — RF-16).

La implementación concreta usa la vista ``vw_rf16_dependencias_ciclos`` que
apunta a ``modulo9.ciclos_productivos_biologicos``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class DependenciaCicloPort(ABC):

    @abstractmethod
    def tiene_dependencias_activas(self, id_ciclo_biologico: int) -> bool:
        """Retorna ``True`` si la etapa tiene activos biológicos asociados activos."""
        raise NotImplementedError
