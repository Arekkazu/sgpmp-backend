# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-43 RF-62: contrato temporal y limites aplicados |
# | 2026-10-31 | Claude | INC-M03-243-G169 RF-62: serie sin calibración y huella de límites físicos aplicados |
# | 2026-10-31 | Claude | INC-M03-236-G16 RF-62: deriva contra el valor de referencia de la calibración vigente |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Contexto histórico explícito, independiente de SQL y de estados actuales."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class LecturaCalidad:
    """Lectura usada como serie de referencia en la evaluación de calidad."""
    id_telemetria: int
    timestamp_captura: datetime
    valor: Decimal
    frecuencia_muestreo_min: int | None = None


@dataclass(frozen=True)
class IntervaloInactividad:
    """Periodo en que el dispositivo estuvo inactivo."""
    inicio: datetime
    fin: datetime | None


@dataclass(frozen=True)
class LimitesFisicosCalidad:
    """Rango físico del sensor con su versión."""
    minimo: Decimal
    maximo: Decimal
    # Solo el proveedor oficial puede identificar una versión histórica.
    version: str | None
    fuente: str


@dataclass(frozen=True)
class ContextoCalidad:
    """Serie de lecturas, periodos inactivos y límites para evaluar calidad."""
    lecturas: tuple[LecturaCalidad, ...]
    periodos: tuple[IntervaloInactividad, ...]
    frecuencia_muestreo_min: int | None
    limites: LimitesFisicosCalidad | None = None
    lecturas_estadisticas: tuple[LecturaCalidad, ...] | None = None


class ContextoCalidadPort(ABC):
    """Puerto para obtener el contexto de evaluación de calidad de una lectura."""
    @abstractmethod
    def obtener(self, id_telemetria: int, id_sensor: int, id_variable: int,
                captura: datetime, n: int, *, incluir_sin_calibracion: bool = False) -> ContextoCalidad:
        """``incluir_sin_calibracion`` (G169, R7): la serie también toma lecturas
        ERROR_CALIBRACION (valor crudo). Un sensor sin calibración solo tiene esas."""

    def referencia_calibracion(self, id_sensor: int, captura: datetime) -> Decimal | None:
        """G16 (#876): valor de referencia (RF-24) de la calibración vigente en la captura."""
        return None

    def limites_fisicos(self, id_variable: int) -> LimitesFisicosCalidad | None:
        """G169 (R7/R9): límites físicos vigentes de la variable, con su versión."""
        return None

    @abstractmethod
    def bloquear_evaluacion(self, id_telemetria: int) -> None:
        """Serializa la cadena de evaluaciones de la misma lectura."""

    @abstractmethod
    def omision_registrada(self, id_telemetria: int) -> bool:
        """Indica si ya se registró la omisión de la evaluación de la lectura."""
        ...
