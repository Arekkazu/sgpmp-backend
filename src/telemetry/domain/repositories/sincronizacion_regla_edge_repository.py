"""Puerto (ABC): destinos y estado por nodo de las reglas compuestas (DEV-08)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.telemetry.domain.entities.sincronizacion_regla_edge import GatewayEdge, SincronizacionReglaEdge


class SincronizacionReglaEdgeRepository(ABC):

    @abstractmethod
    def listar_gateways_destino(self, id_regla_alertas: int) -> list[GatewayEdge]:
        """Gateway Edge activos de las áreas de la finca y especie de la regla.

        No depende de la identidad de quien llama: la propagación de una regla
        no puede cambiar según el rol que la dispara.
        """
        ...

    @abstractmethod
    def registrar_intento(
        self,
        *,
        id_regla_alertas: int,
        gateway: GatewayEdge,
        version_regla: int,
        estado_sincronizacion: str,
        mensaje: Optional[str],
        fecha_intento: datetime,
        id_usuario: Optional[int],
    ) -> SincronizacionReglaEdge:
        """Guarda el veredicto vigente de la regla en ese Gateway (una fila por par).

        Un intento nuevo reemplaza el estado anterior y suma uno a los intentos.
        ``fecha_aplicacion`` solo avanza cuando el estado es ``APLICADA``.
        """
        ...

    @abstractmethod
    def listar_por_regla(self, id_regla_alertas: int) -> list[SincronizacionReglaEdge]: ...
