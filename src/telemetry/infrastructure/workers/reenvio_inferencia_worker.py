# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-27 | destroyerban | INC-M03-113-G56 RF-56: 5 intentos con backoff 0/5/15/30/60 s y reenvio automatico |
"""RF-56 CA-6: cola de reenvío. Cada IOT_INFERENCIA_REENVIO_SEG drena los paquetes PENDIENTE
cuyo reintento venció, en orden cronológico y en lotes de máximo 500.

El motor es el adaptador de MotorInferenciaPort que se conecte aquí. Con el stub no hay
intento: los paquetes siguen PENDIENTE y se reenvían solos cuando se conecte el real.
"""
from __future__ import annotations

import asyncio
import logging
import os

from src.shared.database import sesion_sistema
from src.telemetry.application.use_cases.inferencia.drenar_paquetes_pendientes_use_case import (
    DrenarPaquetesPendientesUseCase,
)
from src.telemetry.infrastructure.adapters.motor_inferencia_stub_adapter import MotorInferenciaStubAdapter
from src.telemetry.infrastructure.repositories.paquete_inferencia_repository import SqlAlchemyPaqueteInferenciaRepository

logger = logging.getLogger(__name__)


def drenar_una_vez() -> None:
    db = sesion_sistema()
    try:
        DrenarPaquetesPendientesUseCase(
            db=db,
            paquete_repo=SqlAlchemyPaqueteInferenciaRepository(db),
            motor_inferencia_port=MotorInferenciaStubAdapter(),
        ).execute()
    finally:
        db.close()


async def reenviar_paquetes_inferencia_periodicamente() -> None:
    # 5 s por defecto: es la espera más corta de la política (intento 2).
    intervalo = max(1, int(os.getenv('IOT_INFERENCIA_REENVIO_SEG', '5')))
    while True:
        await asyncio.sleep(intervalo)
        try:
            await asyncio.to_thread(drenar_una_vez)
        except Exception:
            logger.exception('No se pudieron reenviar los paquetes de inferencia pendientes; se reintentará.')
