"""Puerto para verificar dependencias activas de una patología.

Consulta si la patología está referenciada en eventos sanitarios del sistema.
Si existen, la desactivación queda bloqueada (FA-04 — RF-16).

La implementación concreta usa ``vw_rf16_dependencias_patologias``, que incluye
joins a tablas de M04 (predicciones, alertas). Mientras M04 no esté implementado,
el stub siempre retorna ``False``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class DependenciaPatologiaPort(ABC):

    @abstractmethod
    def tiene_dependencias_activas(self, id_patologia: int) -> bool:
        """Retorna ``True`` si la patología tiene eventos sanitarios o predicciones asociadas."""
        raise NotImplementedError
