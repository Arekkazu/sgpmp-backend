"""Stub adapter para dependencias de finca.

Retorna False hasta que RF-21 (IoT) y RF-33 (Activos Biológicos) estén implementados.
"""
from src.configuration.domain.repositories.finca_dependency_port import FincaDependencyPort


class FincaStubAdapter(FincaDependencyPort):
    def tiene_dependencias_activas(self, id_finca: int) -> bool:
        return False
