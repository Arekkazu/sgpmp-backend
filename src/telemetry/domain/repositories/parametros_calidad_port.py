from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParametrosCalidad:
    k: float = 3.0                        # desviaciones estándar para outlier
    M: int = 5                            # lecturas iguales para sensor congelado
    N: int = 20                           # ventana de serie temporal
    umbral_drift: float = 5.0             # % drift para activar flag
    umbral_drift_significativo: float = 10.0  # % drift para impactar índice
    P: int = 3                            # lecturas consecutivas en misma dirección
    frecuencia_muestreo_min: int = 5      # intervalo esperado entre lecturas (min)


class ParametrosCalidadPort(ABC):

    @abstractmethod
    def obtener_parametros(
        self,
        id_sensor: int,
        tipo_variable: Optional[str] = None,
    ) -> ParametrosCalidad: ...
