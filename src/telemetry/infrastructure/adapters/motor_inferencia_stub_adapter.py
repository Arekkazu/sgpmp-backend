# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-26 | destroyerban | INC-M03-112-G55 RF-56: envio de pendientes en lotes de maximo 500 |
from src.telemetry.domain.entities.telemetria import PaqueteInferencia
from src.telemetry.domain.repositories.motor_inferencia_port import MotorInferenciaNoIntegradoError, MotorInferenciaPort


class MotorInferenciaStubAdapter(MotorInferenciaPort):
    """P7: señala falta de integración; nunca confirma una entrega ficticia."""

    def enviar_paquete(self, paquete: PaqueteInferencia) -> bool:
        raise MotorInferenciaNoIntegradoError()

    def enviar_lote(self, paquetes: list[PaqueteInferencia]) -> bool:
        raise MotorInferenciaNoIntegradoError()
