"""Puerto (ABC) para el registro de auditoría de umbrales ambientales (CU03 RF-17)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class AuditoriaUmbralRepository(ABC):
    @abstractmethod
    def registrar(
        self,
        id_umbral_ambiental: int,
        id_usuario: Optional[int],
        tipo_operacion: str,
        valores_nuevos: dict,
        valores_anteriores: Optional[dict] = None,
    ) -> None: ...
