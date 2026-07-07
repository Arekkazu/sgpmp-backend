from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class UmbralHistoricoPort(ABC):

    @abstractmethod
    def obtener_umbral_vigente(
        self,
        tipo_variable: str,
        id_especie: Optional[int],
        timestamp: datetime,
    ) -> Optional[dict]:
        """Retorna el umbral de M09 vigente en `timestamp` para la variable y especie dadas.

        Formato del dict: {"umbral_min": Decimal, "umbral_max": Decimal, "tolerancia_pct": float}
        Retorna None si no existe umbral configurado (semáforo queda GRIS).
        """
