from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from src.telemetry.domain.entities.historico_transicion_dispositivo import HistoricoTransicionDispositivo


class HistoricoTransicionDispositivoRepository(ABC):

    @abstractmethod
    def registrar(self, transicion: HistoricoTransicionDispositivo) -> HistoricoTransicionDispositivo: ...

    @abstractmethod
    def listar_por_dispositivo(
        self, id_dispositivo_iot: int, limite: int = 20
    ) -> List[HistoricoTransicionDispositivo]: ...
