from __future__ import annotations

from src.prediction.domain.repositories.nodo_edge_port import NodoEdgePort


class NodoEdgeStubAdapter(NodoEdgePort):
    """Stub temporal — IoT/IA gestiona el registro y disponibilidad de nodos Edge."""

    def hay_nodos_activos(self, tipo_modelo: str) -> bool:
        return True
