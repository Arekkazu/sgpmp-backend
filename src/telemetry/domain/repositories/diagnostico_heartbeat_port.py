"""Frontera pendiente M09/FW-06, sin asumir valores ni convención de versiones.

La implementación persistente se debe incorporar al disponer del contrato de
configuración autorizado. El worker deja pendiente una etapa que la necesite
si no hay implementación inyectada; no hay adaptador que simule éxito.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class UmbralesTemperaturaDispositivo:
    maximo_operativo: Decimal
    critico: Decimal | None = None

    def __post_init__(self):
        if not self.maximo_operativo.is_finite() or (
            self.critico is not None and (
                not self.critico.is_finite() or self.critico < self.maximo_operativo
            )
        ):
            raise ValueError('Los umbrales de temperatura son inconsistentes.')


@dataclass(frozen=True)
class ComparacionFirmware:
    version_minima: str
    es_anterior: bool

    def __post_init__(self):
        if not isinstance(self.version_minima, str) or not self.version_minima.strip() or type(self.es_anterior) is not bool:
            raise ValueError('La comparación de firmware requiere mínimo y resultado explícitos.')


class DiagnosticoHeartbeatPort(Protocol):
    def obtener_umbrales_temperatura(self, id_dispositivo: int) -> UmbralesTemperaturaDispositivo: ...

    def comparar_firmware(self, id_dispositivo: int, version_instalada: str) -> ComparacionFirmware:
        """Aplica la convención aprobada de FW-06; nunca orden lexicográfico."""
        ...
