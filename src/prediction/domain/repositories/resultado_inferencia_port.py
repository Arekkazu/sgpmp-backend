# | Fecha      | Nombre   | Que se hizo                                             |
# |------------|----------|---------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-228-G068 RF-72: activo_en_baja en el resultado    |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de lectura de resultados de inferencia."""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Optional


class ResultadoInferenciaPort(ABC):
    """Puerto para obtener un resultado de inferencia."""
    @abstractmethod
    def obtener_por_id(self, id_resultado: uuid.UUID) -> Optional[dict]:
        """Devuelve dict con fecha_inferencia, id_activo_biologico y activo_en_baja, o None si no existe."""
        ...
