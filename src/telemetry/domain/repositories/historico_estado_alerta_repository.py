# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, puerto y métodos |
"""Puerto de dominio del histórico de estados de una alerta.

Registra cada transición (quién y por qué) y permite consultar la trazabilidad
de una alerta concreta.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.telemetry.domain.entities.alerta import HistoricoEstadoAlerta


class HistoricoEstadoAlertaRepository(ABC):
    """Contrato de registro y consulta de transiciones de estado de alertas."""

    @abstractmethod
    def registrar(
        self,
        id_alerta: int,
        estado_anterior: str,
        estado_nuevo: str,
        id_usuario: Optional[int] = None,
        motivo: Optional[str] = None,
    ) -> None:
        """Registra una transición de estado de la alerta.

        Args:
            id_alerta: Alerta afectada.
            estado_anterior: Estado desde el que se transiciona.
            estado_nuevo: Estado al que se transiciona.
            id_usuario: Usuario responsable, si aplica.
            motivo: Justificación opcional del cambio.
        """
        ...

    @abstractmethod
    def obtener_por_alerta(self, id_alerta: int) -> list[HistoricoEstadoAlerta]:
        """Devuelve las transiciones registradas para una alerta, en orden."""
        ...
