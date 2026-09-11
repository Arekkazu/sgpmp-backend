"""Puerto del repositorio de la cola de cálculo ICA (RF-74)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.supplies.domain.entities.item_cola_ica import ItemColaICA
from src.supplies.domain.value_objects.eficiencia_enums import EstadoItemCola


class ColaCalculoICARepository(ABC):
    @abstractmethod
    def encolar(self, item: ItemColaICA) -> Optional[ItemColaICA]:
        """Encola un activo. Devuelve ``None`` si ya estaba pendiente (idempotente
        por el índice único parcial)."""
        raise NotImplementedError

    @abstractmethod
    def listar_pendientes(self, limite: Optional[int] = None) -> list[ItemColaICA]:
        """Activos EN_COLA por prioridad y antigüedad."""
        raise NotImplementedError

    @abstractmethod
    def contar_pendientes(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def marcar(
        self,
        id_cola: int,
        estado: EstadoItemCola,
        *,
        fecha_procesado: Optional[datetime] = None,
    ) -> None:
        raise NotImplementedError
