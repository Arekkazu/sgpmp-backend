# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Stub de consulta de modelos activos por patología."""
from __future__ import annotations

from src.prediction.domain.repositories.modelo_activo_port import ModeloActivoPort


class ModeloActivoStubAdapter(ModeloActivoPort):
    """Stub temporal — IoT/IA implementará la tabla de clases objetivo de modelos."""

    def tiene_modelos_activos(self, id_patologia: int) -> bool:
        """Retorna True si la patología está en uso como clase objetivo en modelos EN_VALIDACION o ACTIVO."""
        return False
