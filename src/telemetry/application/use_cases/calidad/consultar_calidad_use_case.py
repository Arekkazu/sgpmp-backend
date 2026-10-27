# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-24 | Arekkazu | USAB-M03 M3-14 RF-62: calidad limitada a las fincas del usuario |
# | 2026-10-26 | Leandro | INC-M03-103-G164 RF-62: rechazar rangos invertidos antes de consultar y comparar fechas en UTC. |
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.shared.errors import BusinessRuleError, NotFoundError
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
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> tuple[list[TelemetriaCalidad], int]:
        # Conservar las fechas sin zona admitidas por el contrato, haciendo
        # explícita su interpretación UTC al comparar y consultar TIMESTAMPTZ.
        if fecha_desde is not None:
            fecha_desde = fecha_desde.replace(tzinfo=timezone.utc) if fecha_desde.tzinfo is None else fecha_desde.astimezone(timezone.utc)
        if fecha_hasta is not None:
            fecha_hasta = fecha_hasta.replace(tzinfo=timezone.utc) if fecha_hasta.tzinfo is None else fecha_hasta.astimezone(timezone.utc)
        if fecha_desde is not None and fecha_hasta is not None and fecha_desde > fecha_hasta:
            raise BusinessRuleError(
                code='VAL_ENTRADA',
                message='La fecha desde no puede ser posterior a la fecha hasta.',
                field='fecha_desde',
            )
        return self.calidad_repo.listar(
            id_sensor=id_sensor,
            clasificacion=clasificacion,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            estado_evaluacion=estado_evaluacion,
            pagina=pagina,
            por_pagina=por_pagina,
            ids_fincas_permitidas=ids_fincas_permitidas,
        )
