"""Adaptador stub de :class:`ProcesoCriticoPort`.

Retorna ``False`` siempre: mientras M04 (Predicción) no esté implementado,
ninguna especie tiene procesos críticos activos y la desactivación no se bloquea.
Cuando M04 exista, este stub se reemplaza por la implementación real.
"""
from __future__ import annotations

from src.configuration.domain.repositories.proceso_critico_port import ProcesoCriticoPort


class StubProcesoCriticoAdapter(ProcesoCriticoPort):
    """Implementación temporal que siempre indica que no hay procesos activos."""

    def tiene_proceso_activo(self, id_especie: int) -> bool:
        return False
