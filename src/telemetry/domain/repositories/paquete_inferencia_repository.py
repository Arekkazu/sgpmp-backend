from abc import ABC, abstractmethod
from typing import Optional

from src.telemetry.domain.entities.telemetria import PaqueteInferencia


class PaqueteInferenciaRepository(ABC):
    @abstractmethod
    def obtener_por_evento(
        self, id_evento: int, *, bloquear_evento: bool = False,
    ) -> Optional[PaqueteInferencia]:
        """Recupera el paquete existente.

        bloquear_evento serializa la consolidación del mismo evento hasta el
        commit/rollback del caso de uso, incluso si todavía no tiene paquete.
        """
        ...

    @abstractmethod
    def guardar(self, paquete: PaqueteInferencia) -> PaqueteInferencia: ...

    @abstractmethod
    def actualizar_estado(self, id_paquete: int, estado: str, intento: int) -> None: ...
