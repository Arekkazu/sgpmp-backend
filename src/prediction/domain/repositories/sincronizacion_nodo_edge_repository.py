from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.prediction.domain.entities.sincronizacion_nodo_edge import NodoEdge, SincronizacionNodoEdge


class SincronizacionNodoEdgeRepository(ABC):
    """``modulo4.sincronizacion_nodos_edge``: una fila por (nodo, tipo_modelo)."""

    @abstractmethod
    def registrar_intento(
        self,
        *,
        nodo: NodoEdge,
        tipo_modelo: str,
        config_version_servidor: int,
        config_version_nodo: Optional[int],
        estado_sincronizacion: str,
        motivo_fallo: Optional[str],
        fecha_intento: datetime,
    ) -> SincronizacionNodoEdge:
        """Guarda el veredicto vigente del nodo y suma uno a los intentos.

        ``fecha_aplicacion`` solo avanza cuando el estado es ``APLICADA``.
        """
        ...

    @abstractmethod
    def listar_por_tipo_modelo(self, tipo_modelo: str) -> list[SincronizacionNodoEdge]: ...
