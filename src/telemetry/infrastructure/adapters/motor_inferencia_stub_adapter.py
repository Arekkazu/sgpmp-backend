from src.telemetry.domain.entities.telemetria import PaqueteInferencia
from src.telemetry.domain.repositories.motor_inferencia_port import MotorInferenciaPort


class MotorInferenciaStubAdapter(MotorInferenciaPort):
    """Stub de M04 hasta que el motor de inferencia real esté disponible."""

    def enviar_paquete(self, paquete: PaqueteInferencia) -> bool:
        return True
