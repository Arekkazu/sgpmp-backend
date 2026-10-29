# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-43 RF-62: contrato temporal y limites aplicados |
"""Contexto histórico explícito, independiente de SQL y de estados actuales."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class LecturaCalidad:
    id_telemetria: int
    timestamp_captura: datetime
    valor: Decimal
    frecuencia_muestreo_min: int | None = None


@dataclass(frozen=True)
class IntervaloInactividad:
    inicio: datetime
    fin: datetime | None


@dataclass(frozen=True)
class LimitesFisicosCalidad:
    minimo: Decimal
    maximo: Decimal
    # Solo el proveedor oficial puede identificar una versión histórica.
    version: str | None
    fuente: str


@dataclass(frozen=True)
class ContextoCalidad:
    lecturas: tuple[LecturaCalidad, ...]
    periodos: tuple[IntervaloInactividad, ...]
    frecuencia_muestreo_min: int | None
    limites: LimitesFisicosCalidad | None = None
    lecturas_estadisticas: tuple[LecturaCalidad, ...] | None = None


class ContextoCalidadPort(ABC):
    @abstractmethod
    def obtener(self, id_telemetria: int, id_sensor: int, id_variable: int,
                captura: datetime, n: int) -> ContextoCalidad: ...

    @abstractmethod
    def bloquear_evaluacion(self, id_telemetria: int) -> None:
        """Serializa la cadena de evaluaciones de la misma lectura."""

    @abstractmethod
    def omision_registrada(self, id_telemetria: int) -> bool: ...
