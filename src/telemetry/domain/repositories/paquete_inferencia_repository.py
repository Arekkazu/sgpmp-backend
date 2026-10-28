# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-26 | destroyerban | INC-M03-112-G55 RF-56: envio de pendientes en lotes de maximo 500 |
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

    @abstractmethod
    def listar_pendientes(self, limite: int) -> list[PaqueteInferencia]:
        """Hasta `limite` paquetes PENDIENTE en orden cronológico de captura.

        Los bloquea hasta el commit/rollback del caso de uso; otro drenado
        concurrente los salta en vez de enviarlos dos veces.
        """
        ...
