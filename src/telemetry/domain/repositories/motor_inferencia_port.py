from abc import ABC, abstractmethod

from src.shared.errors import ServiceUnavailableError
from src.telemetry.domain.entities.telemetria import PaqueteInferencia


class MotorInferenciaNoIntegradoError(ServiceUnavailableError):
    """No existe integración: no se realizó un intento de entrega."""

    def __init__(self) -> None:
        super().__init__(
            code="MOTOR_INFERENCIA_NO_INTEGRADO",
            message="El motor de inferencia aún no está integrado. El envío permanece pendiente.",
        )


class MotorInferenciaPort(ABC):
    @abstractmethod
    def enviar_paquete(self, paquete: PaqueteInferencia) -> bool:
        """True confirma entrega; False indica un intento fallido.

        MotorInferenciaNoIntegradoError indica que no hubo intento por falta
        de integración. No define protocolo, ACK ni reintentos del futuro IA-1.
        """
        ...
