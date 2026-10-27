# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-26 | destroyerban | INC-M03-112-G55 RF-56: envio de pendientes en lotes de maximo 500 |
"""RF-56 Fase 6, envío batch: drena los paquetes PENDIENTE hacia el motor de inferencia.

Restricción 5 (máximo 500 registros por paquete, se permite fragmentación) y 6 (orden
cronológico). Cada lote se toma, se envía y se confirma en su propia transacción, así el
bloqueo de las filas dura solo lo que tarda ese lote.

Mismos estados que la consolidación (DEV-17): True → ENVIADO, False o error de envío →
FALLIDO, ambos con un intento más. Sin integración (stub) se detiene sin tocar nada: los
paquetes siguen PENDIENTE con sus intentos.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from src.shared.errors import ValidationError
from src.telemetry.domain.entities.telemetria import (
    MAX_REGISTROS_POR_ENVIO_INFERENCIA,
    EstadoPaqueteInferencia,
)
from src.telemetry.domain.repositories.motor_inferencia_port import MotorInferenciaNoIntegradoError, MotorInferenciaPort
from src.telemetry.domain.repositories.paquete_inferencia_repository import PaqueteInferenciaRepository

logger = logging.getLogger(__name__)


@dataclass
class ResultadoDrenado:
    lotes: list[int] = field(default_factory=list)   # tamaño de cada lote intentado
    enviados: int = 0
    fallidos: int = 0
    motor_integrado: bool = True


class DrenarPaquetesPendientesUseCase:

    def __init__(
        self,
        db: Session,
        paquete_repo: PaqueteInferenciaRepository,
        motor_inferencia_port: MotorInferenciaPort,
        tamano_lote: int = MAX_REGISTROS_POR_ENVIO_INFERENCIA,
    ) -> None:
        if not 1 <= tamano_lote <= MAX_REGISTROS_POR_ENVIO_INFERENCIA:
            raise ValidationError(
                code="TAMANO_LOTE_INVALIDO",
                message=f"El tamaño de lote debe estar entre 1 y {MAX_REGISTROS_POR_ENVIO_INFERENCIA}.",
                field="tamano_lote",
            )
        self.db = db
        self.paquete_repo = paquete_repo
        self.motor_inferencia_port = motor_inferencia_port
        self.tamano_lote = tamano_lote

    def execute(self, max_lotes: int = 20) -> ResultadoDrenado:
        resultado = ResultadoDrenado()
        for _ in range(max_lotes):
            try:
                lote = self.paquete_repo.listar_pendientes(self.tamano_lote)
            except Exception:
                self.db.rollback()
                raise
            if not lote:
                self.db.rollback()
                break

            try:
                exito = self.motor_inferencia_port.enviar_lote(lote)
            except MotorInferenciaNoIntegradoError:
                # No hubo intento: se liberan las filas y quedan PENDIENTE.
                self.db.rollback()
                logger.warning('RF-56: %s paquetes pendientes; motor de inferencia no integrado.', len(lote))
                resultado.motor_integrado = False
                break
            except Exception:
                exito = False

            resultado.lotes.append(len(lote))
            estado = EstadoPaqueteInferencia.ENVIADO if exito else EstadoPaqueteInferencia.FALLIDO
            try:
                for paquete in lote:
                    self.paquete_repo.actualizar_estado(
                        paquete.id_paquetes_inferencia, estado, paquete.intento_envios + 1,
                    )
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

            if exito:
                resultado.enviados += len(lote)
            else:
                resultado.fallidos += len(lote)
            if len(lote) < self.tamano_lote:
                break
        return resultado
