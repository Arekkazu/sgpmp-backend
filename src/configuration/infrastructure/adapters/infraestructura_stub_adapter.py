"""Stub adapter para dependencias de infraestructura.

Retorna False hasta que RF-21 (IoT) y módulo de activos biológicos estén implementados.
"""
from src.configuration.domain.repositories.infraestructura_dependency_port import InfraestructuraDependencyPort


class InfraestructuraStubAdapter(InfraestructuraDependencyPort):
    def tiene_dependencias_activas(self, id_infraestructura: int) -> bool:
        return False
