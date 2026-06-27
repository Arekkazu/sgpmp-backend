"""Puerto para verificar dependencias activas de una métrica de producción.

Consulta si existen registros productivos activos que usan esta métrica. Si
los hay, la desactivación queda bloqueada (FA-09 — RF-16).

M04 no está implementado aún, por lo que la implementación concreta es un
stub que siempre retorna ``False`` (permite desactivar sin restricciones).
Cuando M04 esté disponible, se reemplaza el stub por la implementación real
sin tocar este puerto ni los use cases.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class DependenciaMetricaPort(ABC):

    @abstractmethod
    def tiene_dependencias_activas(self, id_metrica_produccion: int) -> bool:
        """Retorna ``True`` si la métrica tiene registros productivos activos."""
        raise NotImplementedError
