# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-26 | destroyerban | INC-M03-112-G55 RF-56: envio de pendientes en lotes de maximo 500 |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Adaptador que señala que el motor de inferencia no está integrado."""
from src.telemetry.domain.entities.telemetria import PaqueteInferencia
from src.telemetry.domain.repositories.motor_inferencia_port import MotorInferenciaNoIntegradoError, MotorInferenciaPort


class MotorInferenciaStubAdapter(MotorInferenciaPort):
    """P7: señala falta de integración; nunca confirma una entrega ficticia."""

    def enviar_paquete(self, paquete: PaqueteInferencia) -> bool:
        """Siempre falla: no hay motor integrado.

        Raises:
            MotorInferenciaNoIntegradoError: Siempre.
        """
        raise MotorInferenciaNoIntegradoError()

    def enviar_lote(self, paquetes: list[PaqueteInferencia]) -> bool:
        """Siempre falla: no hay motor integrado.

        Raises:
            MotorInferenciaNoIntegradoError: Siempre.
        """
        raise MotorInferenciaNoIntegradoError()
