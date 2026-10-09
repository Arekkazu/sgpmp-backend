"""Entidad de valor: nivel de alerta dentro de un umbral ambiental."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.configuration.domain.value_objects.nivel_alerta import NivelAlerta


@dataclass
class NivelAlertaAmbiental:
    """Tramo [límite inferior, límite superior] de un nivel semafórico dentro de un
    umbral ambiental.
    """
    nivel: NivelAlerta
    limite_inferior: Decimal
    limite_superior: Decimal
