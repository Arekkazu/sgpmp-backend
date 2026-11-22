# | Fecha      | Nombre   | Que se hizo                                                      |
# |------------|----------|------------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M03-135-G01 RF-49: especies compatibles de un sensor desde M09 |
from __future__ import annotations

from abc import ABC, abstractmethod


class CompatibilidadSensorEspecieRepository(ABC):
    """Lista blanca de especies con las que un sensor se puede vincular a un activo (RF-49 R3)."""

    @abstractmethod
    def listar_especies(self, id_sensor: int) -> list[int]: ...

    @abstractmethod
    def reemplazar(self, id_sensor: int, ids_especies: list[int]) -> None: ...
