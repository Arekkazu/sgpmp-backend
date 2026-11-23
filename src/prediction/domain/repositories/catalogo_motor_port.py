# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66/RF-69: catálogo del motor IA armado desde la BD            |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Lo que el motor IA necesita para armar su catálogo solo, sin ``catalogo.json`` manual."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.prediction.domain.entities.animal_motor import AnimalMotor


class CatalogoMotorPort(ABC):
    """Puerto del catálogo de animales y modelos del motor."""
    @abstractmethod
    def animales(self, id_activo: Optional[int] = None) -> list[AnimalMotor]:
        """Animales INDIVIDUAL vivos, con sensor directo, en un área de modelo individual."""

    @abstractmethod
    def version_referencia(self, tipo_modelo: str) -> Optional[int]:
        """Versión ACTIVO o SOMBRA de algún animal de ese tipo de modelo, para copiarla."""

    @abstractmethod
    def lecturas(self, id_activo: int, desde: datetime, hasta: datetime) -> list[dict]:
        """Lecturas de ET-02 del animal en el formato largo del contrato IA-1."""
