# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-26 | destroyerban | INC-M03-112-G55 RF-56: envio de pendientes en lotes de maximo 500 |
# | 2026-10-27 | destroyerban | INC-M03-113-G56 RF-56: 5 intentos con backoff 0/5/15/30/60 s y reenvio automatico |
from abc import ABC, abstractmethod

from src.shared.errors import BusinessRuleError, ServiceUnavailableError
from src.telemetry.domain.entities.telemetria import PaqueteInferencia


class MotorInferenciaNoIntegradoError(ServiceUnavailableError):
    """No existe integración: no se realizó un intento de entrega."""

    def __init__(self) -> None:
        super().__init__(
            code="MOTOR_INFERENCIA_NO_INTEGRADO",
            message="El motor de inferencia aún no está integrado. El envío permanece pendiente.",
        )


class MotorInferenciaRechazoError(BusinessRuleError):
    """RF-56 E5: el motor rechaza el paquete (esquema o datos). Es definitivo: no se reintenta."""

    def __init__(self, detalle: str = "") -> None:
        super().__init__(
            code="MOTOR_INFERENCIA_RECHAZO",
            message=f"El motor de inferencia rechazó el paquete. {detalle}".strip(),
        )


class MotorInferenciaPort(ABC):
    @abstractmethod
    def enviar_paquete(self, paquete: PaqueteInferencia) -> bool:
        """True confirma entrega; False indica un intento fallido que se reintenta
        (RF-56 restricción 14), igual que un error de transporte.

        MotorInferenciaRechazoError (E5) es un rechazo definitivo: FALLIDO sin
        reintentos. MotorInferenciaNoIntegradoError indica que no hubo intento por
        falta de integración. No define protocolo ni ACK del futuro IA-1.
        """
        ...

    @abstractmethod
    def enviar_lote(self, paquetes: list[PaqueteInferencia]) -> bool:
        """Envío batch (RF-56 Fase 6). Recibe como máximo
        MAX_REGISTROS_POR_ENVIO_INFERENCIA paquetes, en orden cronológico.

        Misma semántica que enviar_paquete, para el lote completo.
        """
        ...
