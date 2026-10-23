# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-40 RF-53: define lectura oficial del catalogo |
from abc import ABC, abstractmethod
from typing import Optional

from src.telemetry.domain.entities.telemetria import ReglaVariableI3P1


class VariableCatalogoPort(ABC):

    @abstractmethod
    def obtener_regla(self, tipo_variable: str) -> Optional[ReglaVariableI3P1]:
        """Consulta metadatos vigentes; None si la variable no existe o está inactiva.

        No valida mediciones: PostgreSQL conserva unidad, rango y calibración.
        Los fallos del catálogo se propagan como errores de infraestructura.
        """
