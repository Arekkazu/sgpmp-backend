from src.telemetry.domain.entities.telemetria import PaqueteInferencia
from src.telemetry.domain.repositories.motor_inferencia_port import MotorInferenciaNoIntegradoError, MotorInferenciaPort


class MotorInferenciaStubAdapter(MotorInferenciaPort):
    """P7: señala falta de integración; nunca confirma una entrega ficticia."""

    def enviar_paquete(self, paquete: PaqueteInferencia) -> bool:
        raise MotorInferenciaNoIntegradoError()
