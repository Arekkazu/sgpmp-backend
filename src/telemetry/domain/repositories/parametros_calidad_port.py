# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase, puerto y método |
"""Puerto de dominio de los parámetros de calidad de telemetría.

Define los umbrales que usa el motor de calidad (outliers, sensor congelado,
deriva y frecuencia de muestreo) y la interfaz para obtenerlos por sensor.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParametrosCalidad:
    """Umbrales de calidad aplicables a un sensor.

    Attributes:
        k: Desviaciones estándar para considerar un valor atípico.
        M: Lecturas iguales consecutivas para marcar un sensor congelado.
        N: Tamaño de la ventana de serie temporal.
        umbral_drift: Porcentaje de deriva que activa la señal.
        umbral_drift_significativo: Porcentaje de deriva que afecta el índice.
        P: Lecturas consecutivas en la misma dirección.
        frecuencia_muestreo_min: Intervalo esperado entre lecturas, en minutos.
    """

    k: float = 3.0                        # desviaciones estándar para outlier
    M: int = 5                            # lecturas iguales para sensor congelado
    N: int = 20                           # ventana de serie temporal
    umbral_drift: float = 5.0             # % drift para activar flag
    umbral_drift_significativo: float = 10.0  # % drift para impactar índice
    P: int = 3                            # lecturas consecutivas en misma dirección
    frecuencia_muestreo_min: int = 5      # intervalo esperado entre lecturas (min)


class ParametrosCalidadPort(ABC):
    """Contrato para resolver los umbrales de calidad de un sensor."""

    @abstractmethod
    def obtener_parametros(
        self,
        id_sensor: int,
        tipo_variable: Optional[str] = None,
    ) -> ParametrosCalidad:
        """Devuelve los parámetros de calidad del sensor indicado.

        Args:
            id_sensor: Sensor a evaluar.
            tipo_variable: Variable medida, si el sensor maneja varias.
        """
        ...
