# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-12 | Leandro | INC-M05-350/351-G05 RF-74: permitir lectura exclusiva para las transiciones de estado. |
"""Puerto del repositorio de ejecuciones del batch ICA (RF-74)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.supplies.domain.entities.ejecucion_batch_ica import EjecucionBatchICA


class EjecucionBatchICARepository(ABC):
    @abstractmethod
    def crear(self, ejecucion: EjecucionBatchICA) -> EjecucionBatchICA:
        """Inserta una nueva corrida (EN_EJECUCION) y devuelve la entidad con id."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, ejecucion: EjecucionBatchICA) -> EjecucionBatchICA:
        """Actualiza estado/métricas de una corrida existente."""
        raise NotImplementedError

    @abstractmethod
    def obtener(self, id_ejecucion: int, *, para_actualizar: bool = False) -> Optional[EjecucionBatchICA]:
        """Lee la corrida y la bloquea hasta terminar la transacción si se va a modificar."""
        raise NotImplementedError

    @abstractmethod
    def obtener_en_ejecucion(self) -> Optional[EjecucionBatchICA]:
        """La corrida EN_EJECUCION más reciente, o ``None``."""
        raise NotImplementedError

    @abstractmethod
    def listar_recientes(self, limite: int = 20) -> list[EjecucionBatchICA]:
        raise NotImplementedError
