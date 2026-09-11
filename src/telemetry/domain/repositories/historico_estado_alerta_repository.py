from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.telemetry.domain.entities.alerta import HistoricoEstadoAlerta


class HistoricoEstadoAlertaRepository(ABC):

    @abstractmethod
    def registrar(
        self,
        id_alerta: int,
        estado_anterior: str,
        estado_nuevo: str,
        id_usuario: Optional[int] = None,
        motivo: Optional[str] = None,
    ) -> None: ...

    @abstractmethod
    def obtener_por_alerta(self, id_alerta: int) -> list[HistoricoEstadoAlerta]: ...
