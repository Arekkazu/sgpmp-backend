from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.telemetry.domain.entities.monitoreo import SemaforoCalculator
from src.telemetry.domain.repositories.especie_activo_port import EspecieActivoPort
from src.telemetry.domain.repositories.monitoreo_repository import MonitoreoRepository
from src.telemetry.domain.repositories.telemetria_repository import TelemetriaRepository
from src.telemetry.domain.repositories.umbral_historico_port import UmbralHistoricoPort


class ReclasificarSemaforoUseCase:
    """INC-M09-106-G31 (#297): recalcula `estado_semaforo` contra los niveles RF-17
    apenas se conoce el activo biológico (y por tanto la especie) de una lectura.

    Se invoca desde los tres puntos donde una lectura puede quedar VINCULADA a un
    activo biológico: vinculación automática (RF-61-A), resolución de AMBIGUA y
    corrección (RF-61-C). Reutiliza el mismo `UmbralHistoricoPort` y
    `SemaforoCalculator.calcular_por_niveles` que ya usa el historial (RF-59) —
    una sola fuente de verdad para la clasificación semafórica.

    Es un efecto colateral de mejor esfuerzo: si no hay especie, umbral o valor
    resoluble, no hace nada y el semáforo queda como lo dejó el trigger de ingesta
    (`fn_actualizar_estado_sensor`, VERDE) o el estado previo.
    """

    def __init__(
        self,
        db: Session,
        telemetria_repo: TelemetriaRepository,
        especie_port: EspecieActivoPort,
        umbral_port: UmbralHistoricoPort,
        monitoreo_repo: MonitoreoRepository,
    ) -> None:
        self.db = db
        self.telemetria_repo = telemetria_repo
        self.especie_port = especie_port
        self.umbral_port = umbral_port
        self.monitoreo_repo = monitoreo_repo

    def execute(self, id_telemetria: int, id_activo_biologico: Optional[int]) -> Optional[str]:
        if id_activo_biologico is None:
            return None

        telemetria = self.telemetria_repo.obtener_por_id(id_telemetria)
        if telemetria is None:
            return None

        valor = telemetria.valor_ajustado if telemetria.valor_ajustado is not None else telemetria.valor_crudo
        if valor is None:
            return None

        id_especie = self.especie_port.obtener_id_especie(id_activo_biologico)
        if id_especie is None:
            return None

        umbral = self.umbral_port.obtener_umbral_vigente(
            id_variable_ambiental=telemetria.id_variable,
            id_especie=id_especie,
            timestamp=telemetria.timestamp_captura,
        )
        if umbral is None:
            return None

        estado = SemaforoCalculator.calcular_por_niveles(valor=valor, niveles=umbral['niveles'])

        self.monitoreo_repo.actualizar_estado_semaforo_si_vigente(
            id_sensor=telemetria.id_sensor,
            timestamp_captura=telemetria.timestamp_captura,
            estado_semaforo=estado,
        )
        self.db.commit()
        return estado
