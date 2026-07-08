from __future__ import annotations

from typing import Optional

from src.telemetry.domain.entities.monitoreo import EstadoSensorActual, ResumenUnidadProductiva, SemaforoCalculator
from src.telemetry.domain.repositories.monitoreo_repository import MonitoreoRepository

# id_rol del Productor — solo para filtrar campos técnicos en la presentación
_ROL_PRODUCTOR = 2


class ObtenerDashboardUseCase:
    """RF-58 — CU04 Flujo principal pasos 1–7.

    Lee el estado actual de sensores desde `estados_actuales_sensores` y
    aplica las reglas de negocio del semáforo antes de devolver los datos.
    No emite commit ni modifica datos (operación de solo lectura).
    """

    def __init__(self, monitoreo_repo: MonitoreoRepository) -> None:
        self.monitoreo_repo = monitoreo_repo

    def execute(
        self,
        id_infraestructura: Optional[int],
        pagina: int,
        por_pagina: int,
        id_rol_usuario: int,
    ) -> tuple[list[EstadoSensorActual], list[ResumenUnidadProductiva], int]:
        sensores, total = self.monitoreo_repo.obtener_estados_sensores(
            id_infraestructura=id_infraestructura,
            pagina=pagina,
            por_pagina=por_pagina,
        )

        for sensor in sensores:
            sensor.estado_semaforo = self._calcular_semaforo_efectivo(sensor)

            # CA-8: Productor no recibe datos técnicos del dispositivo
            if id_rol_usuario == _ROL_PRODUCTOR:
                sensor.nivel_bateria_pct = None
                sensor.calidad_senal_rssi = None
                sensor.calidad_senal_snr = None

        resumen: list[ResumenUnidadProductiva] = []
        if id_infraestructura is None:
            resumen = self.monitoreo_repo.obtener_resumen_unidades()
            # Aplicar mismo recálculo de semáforo al estado general de cada unidad
            estados_por_unidad: dict[int, list[str]] = {}
            for s in sensores:
                if s.id_infraestructura:
                    estados_por_unidad.setdefault(s.id_infraestructura, []).append(s.estado_semaforo)
            for unidad in resumen:
                estados = estados_por_unidad.get(unidad.id_infraestructura, [])
                if estados:
                    unidad.estado_general = SemaforoCalculator.peor_semaforo(estados)

        return sensores, resumen, total

    @staticmethod
    def _calcular_semaforo_efectivo(sensor: EstadoSensorActual) -> str:
        # CA-5: sensor sin datos recientes → GRIS (FA-05)
        if sensor.dato_desactualizado:
            return 'GRIS'

        estado = sensor.estado_semaforo or 'GRIS'

        # CA-4: alerta CRITICA activa → ROJO; alerta activa → al menos AMARILLO
        tiene_critica = sensor.severidad_alerta == 'CRITICO'
        tiene_activa = sensor.id_alerta is not None
        return SemaforoCalculator.aplicar_reglas_alerta(estado, tiene_critica, tiene_activa)
