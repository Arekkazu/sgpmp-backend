from __future__ import annotations

from src.prediction.domain.repositories.modelo_activo_port import ModeloActivoPort


class ModeloActivoStubAdapter(ModeloActivoPort):
    """Stub temporal — IoT/IA implementará la tabla de clases objetivo de modelos."""

    def tiene_modelos_activos(self, id_patologia: int) -> bool:
        return False
