# | Fecha      | Nombre   | Que se hizo                                                      |
# |------------|----------|------------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M03-135-G01 RF-49: especies compatibles de un sensor desde M09 |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de especies compatibles con un sensor."""
from __future__ import annotations

from abc import ABC, abstractmethod


class CompatibilidadSensorEspecieRepository(ABC):
    """Lista blanca de especies con las que un sensor se puede vincular a un activo (RF-49 R3)."""

    @abstractmethod
    def listar_especies(self, id_sensor: int) -> list[int]:
        """Lista los ids de especies compatibles con el sensor."""
        ...

    @abstractmethod
    def reemplazar(self, id_sensor: int, ids_especies: list[int]) -> None:
        """Reemplaza las especies compatibles con el sensor."""
        ...
