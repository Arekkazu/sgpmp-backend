from abc import ABC, abstractmethod

from src.telemetry.domain.entities.telemetria import PaqueteInferencia


class MotorInferenciaPort(ABC):
    @abstractmethod
    def enviar_paquete(self, paquete: PaqueteInferencia) -> bool: ...
