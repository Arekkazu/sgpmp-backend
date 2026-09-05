"""Adaptador stub de :class:`DependenciaMetricaPort`.

Retorna ``False`` siempre: mientras M04 (Registro Productivo) no esté
implementado, ninguna métrica tiene registros productivos activos y la
desactivación no se bloquea por ese motivo (FA-09 — RF-16).
Cuando M04 exista, este stub se reemplaza por la implementación real.
"""
from __future__ import annotations

from src.configuration.domain.repositories.dependencia_metrica_port import DependenciaMetricaPort


class StubDependenciaMetricaAdapter(DependenciaMetricaPort):

    def tiene_dependencias_activas(self, id_metrica_produccion: int) -> bool:
        return False
