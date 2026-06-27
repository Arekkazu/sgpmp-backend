"""Puerto (ABC) para auditoría de dispositivos IoT."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class AuditoriaDispositivoIotRepository(ABC):

    @abstractmethod
    def registrar(
        self,
        *,
        id_dispositivo_iot: int,
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict,
        valores_anteriores: Optional[dict] = None,
    ) -> None:
        ...
