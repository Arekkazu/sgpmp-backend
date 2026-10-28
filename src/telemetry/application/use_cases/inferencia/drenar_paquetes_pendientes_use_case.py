# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-26 | destroyerban | INC-M03-112-G55 RF-56: envio de pendientes en lotes de maximo 500 |
# | 2026-10-27 | destroyerban | INC-M03-113-G56 RF-56: 5 intentos con backoff 0/5/15/30/60 s y reenvio automatico |
"""RF-56 Fase 6, envío batch y cola de reenvío: drena los paquetes PENDIENTE hacia el motor.

Restricción 5 (máximo 500 registros por paquete, se permite fragmentación), 6 (orden
cronológico) y 14 (5 intentos: inmediato, 5, 15, 30 y 60 s). Solo se toman los pendientes
cuyo reintento ya venció; cada lote se toma, se envía y se confirma en su propia transacción.

Por paquete, tras el envío del lote:
- confirmado → ENVIADO;
- rechazo del motor (E5) → FALLIDO, sin reintentos;
- no confirmado o error de transporte (E4) → PENDIENTE con un intento más y el siguiente
  programado, o FALLIDO si ese era el quinto.
Sin integración (stub) se detiene sin tocar nada: los paquetes siguen PENDIENTE con sus
intentos y se reenvían en orden cuando el motor esté disponible (CA-6).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.shared.errors import ValidationError
from src.telemetry.domain.entities.telemetria import (
    MAX_REGISTROS_POR_ENVIO_INFERENCIA,
    EstadoPaqueteInferencia,
    estado_tras_envio_fallido,
)
from src.telemetry.domain.repositories.motor_inferencia_port import (
    MotorInferenciaNoIntegradoError,
    MotorInferenciaPort,
    MotorInferenciaRechazoError,
)
from src.telemetry.domain.repositories.paquete_inferencia_repository import PaqueteInferenciaRepository

logger = logging.getLogger(__name__)


@dataclass
class ResultadoDrenado:
    lotes: list[int] = field(default_factory=list)   # tamaño de cada lote intentado
    enviados: int = 0
    fallidos: int = 0
    reprogramados: int = 0                           # quedan PENDIENTE con otro intento programado
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

            rechazado = False
            try:
                exito = self.motor_inferencia_port.enviar_lote(lote)
            except MotorInferenciaNoIntegradoError:
                # No hubo intento: se liberan las filas y quedan PENDIENTE.
                self.db.rollback()
                # INFO: la cola corre cada pocos segundos; el WARNING por paquete ya lo deja la consolidación.
                logger.info('RF-56: %s paquetes pendientes; motor de inferencia no integrado.', len(lote))
                resultado.motor_integrado = False
                break
            except MotorInferenciaRechazoError:
                exito, rechazado = False, True
            except Exception:
                exito = False

            resultado.lotes.append(len(lote))
            ahora = datetime.now(timezone.utc)
            try:
                for paquete in lote:
                    intento = paquete.intento_envios + 1
                    if exito:
                        estado = EstadoPaqueteInferencia.ENVIADO
                    elif rechazado:
                        estado = EstadoPaqueteInferencia.FALLIDO
                    else:
                        estado = estado_tras_envio_fallido(intento)
                    self.paquete_repo.actualizar_estado(paquete.id_paquetes_inferencia, estado, intento, ahora)
                    if estado == EstadoPaqueteInferencia.ENVIADO:
                        resultado.enviados += 1
                    elif estado == EstadoPaqueteInferencia.FALLIDO:
                        resultado.fallidos += 1
                    else:
                        resultado.reprogramados += 1
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

            if len(lote) < self.tamano_lote:
                break
        return resultado
