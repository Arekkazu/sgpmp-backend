"""Puerto (ABC): enviar una regla compuesta a los Gateway Edge por el broker (DEV-08).

Contrato BRK-05 (``BROKER-MQTT-SGPMP``): ``POST /v1/commands`` con
``origen: "regla_compuesta"``; el broker publica ``tipo_comando:
"REGLA_COMPUESTA"`` en ``sgpmp/<serial>/command`` y espera el ``ACK_REGLA``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.telemetry.domain.entities.sincronizacion_regla_edge import ResultadoPropagacionEdge


class ReglaCompuestaEdgePort(ABC):

    @abstractmethod
    def propagar_regla(self, seriales_gateway: list[str], payload: dict) -> dict[str, ResultadoPropagacionEdge]:
        """Envía la regla a cada Gateway Edge y devuelve el veredicto de cada uno.

        Nunca lanza. ``estado`` de cada resultado: ``APLICADA`` (llegó el
        ``ACK_REGLA``), ``PENDIENTE`` (el broker sabe que el Gateway está
        desconectado y no publicó), ``NO_CONF`` (broker caído, error HTTP o sin
        ACK) o ``SIN_INTEGRACION`` (el ambiente no tiene broker configurado).
        """
        ...
