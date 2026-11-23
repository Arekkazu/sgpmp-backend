# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, puerto y métodos |
"""Puerto de dominio del histórico de transiciones de estado de dispositivos IoT.

Permite registrar cada cambio de estado y consultar los últimos de un
dispositivo concreto.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from src.telemetry.domain.entities.historico_transicion_dispositivo import HistoricoTransicionDispositivo


class HistoricoTransicionDispositivoRepository(ABC):
    """Contrato de registro y consulta de transiciones de estado de dispositivos."""

    @abstractmethod
    def registrar(self, transicion: HistoricoTransicionDispositivo) -> HistoricoTransicionDispositivo:
        """Registra una transición y devuelve la entidad persistida."""
        ...

    @abstractmethod
    def listar_por_dispositivo(
        self, id_dispositivo_iot: int, limite: int = 20
    ) -> List[HistoricoTransicionDispositivo]:
        """Devuelve las últimas transiciones del dispositivo, de más reciente a más antigua."""
        ...
