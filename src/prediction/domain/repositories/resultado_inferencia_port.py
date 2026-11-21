# | Fecha      | Nombre   | Que se hizo                                             |
# |------------|----------|---------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-228-G068 RF-72: activo_en_baja en el resultado    |
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Optional


class ResultadoInferenciaPort(ABC):
    @abstractmethod
    def obtener_por_id(self, id_resultado: uuid.UUID) -> Optional[dict]:
        """Devuelve dict con fecha_inferencia, id_activo_biologico y activo_en_baja, o None si no existe."""
        ...
