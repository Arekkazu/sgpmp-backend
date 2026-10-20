from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class ParametrosHeartbeat:
    bateria_critica: Decimal
    bateria_baja: Decimal
    rssi_degradado: Decimal

    def __post_init__(self):
        if not Decimal(0) <= self.bateria_critica <= self.bateria_baja <= Decimal(100):
            raise ValueError('Los umbrales de batería son inconsistentes.')


class ParametrosHeartbeatPort(Protocol):
    def obtener(self) -> ParametrosHeartbeat: ...
