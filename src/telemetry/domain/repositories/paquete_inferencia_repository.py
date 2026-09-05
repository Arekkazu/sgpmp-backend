from abc import ABC, abstractmethod

from src.telemetry.domain.entities.telemetria import PaqueteInferencia


class PaqueteInferenciaRepository(ABC):
    @abstractmethod
    def guardar(self, paquete: PaqueteInferencia) -> PaqueteInferencia: ...

    @abstractmethod
    def actualizar_estado(self, id_paquete: int, estado: str, intento: int) -> None: ...
