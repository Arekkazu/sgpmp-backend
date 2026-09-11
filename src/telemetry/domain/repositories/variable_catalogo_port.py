from abc import ABC, abstractmethod
from typing import Optional

from src.telemetry.domain.entities.telemetria import ReglaVariableI3P1


class VariableCatalogoPort(ABC):

    @abstractmethod
    def obtener_regla(self, tipo_variable: str, unidad: str) -> Optional[ReglaVariableI3P1]:
        """Retorna la regla I3P-1 para tipo_variable con validación de unidad.

        Retorna None si tipo_variable no existe en el catálogo.
        Retorna la regla con unidad normalizada si hay conversión disponible.
        Lanza ValueError si la unidad es inválida y no hay conversión.
        """
