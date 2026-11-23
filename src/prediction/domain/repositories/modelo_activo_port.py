# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de consulta de modelos activos por patología."""
from __future__ import annotations

from abc import ABC, abstractmethod


class ModeloActivoPort(ABC):
    """Puerto para saber si una patología tiene modelos activos."""
    @abstractmethod
    def tiene_modelos_activos(self, id_patologia: int) -> bool:
        """Retorna True si la patología está en uso como clase objetivo en modelos EN_VALIDACION o ACTIVO."""
        ...
