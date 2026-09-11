from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.shared.errors import NotFoundError
from src.telemetry.domain.entities.telemetria_calidad import TelemetriaCalidad
from src.telemetry.domain.repositories.telemetria_calidad_repository import TelemetriaCalidadRepository


class ConsultarCalidadUseCase:

    def __init__(self, calidad_repo: TelemetriaCalidadRepository) -> None:
        self.calidad_repo = calidad_repo

    def get(self, id_telemetria: int) -> TelemetriaCalidad:
        evaluacion = self.calidad_repo.obtener_por_lectura(id_telemetria)
        if evaluacion is None:
            raise NotFoundError(
                code='EVALUACION_CALIDAD_NO_ENCONTRADA',
                message='No existe evaluación de calidad para esta lectura.',
            )
        return evaluacion

    def listar(
        self,
        id_sensor: Optional[int] = None,
        clasificacion: Optional[str] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        estado_evaluacion: Optional[str] = None,
        pagina: int = 1,
        por_pagina: int = 50,
    ) -> tuple[list[TelemetriaCalidad], int]:
        return self.calidad_repo.listar(
            id_sensor=id_sensor,
            clasificacion=clasificacion,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            estado_evaluacion=estado_evaluacion,
            pagina=pagina,
            por_pagina=por_pagina,
        )
