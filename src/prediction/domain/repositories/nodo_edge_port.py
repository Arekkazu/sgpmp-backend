from __future__ import annotations

from abc import ABC, abstractmethod

from src.prediction.domain.entities.sincronizacion_nodo_edge import NodoEdge


class NodoEdgePort(ABC):
    @abstractmethod
    def listar_nodos_activos(self, tipo_modelo: str) -> list[NodoEdge]:
        """Gateway Edge activos que atienden un área activa con ese ``tipo_modelo`` asignado.

        Vacío decide ``MODO_EDGE_SIN_NODOS`` (FA-08). No depende de quién llama.
        """
        ...
