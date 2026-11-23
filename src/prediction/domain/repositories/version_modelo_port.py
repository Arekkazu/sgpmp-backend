# | Fecha      | Nombre       | Que se hizo                                           |
# |------------|--------------|-------------------------------------------------------|
# | 2026-10-31 | Arekkazu     | RFC-010 RF-69: versión por animal, estado SOMBRA y fuente de datos |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de consulta del estado de versiones de modelo."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class VersionModeloPort(ABC):
    """Puerto para consultar el estado de una versión."""
    @abstractmethod
    def obtener_estado(self, id_version: int) -> Optional[str]:
        """Devuelve el estado_version del modelo o None si no existe."""
        ...

    @abstractmethod
    def obtener_llave(
        self, id_version: int
    ) -> Optional[tuple[str, Optional[str], Optional[str], Optional[int]]]:
        """(estado_version, tipo_modelo, componente, id_activo_biologico) o None si no existe
        (RF-65 4.e, RFC-009, RFC-010)."""
        ...
