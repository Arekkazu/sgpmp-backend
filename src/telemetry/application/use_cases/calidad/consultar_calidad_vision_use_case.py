# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | RF-62: listado de observaciones de visión evaluadas (el panel mostraba datos de ejemplo) |
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.shared.errors import ValidationError
from src.telemetry.domain.entities.calidad_vision_listado import (
    CLASES_VISION, SIN_EVALUAR, FiltrosCalidadVision, ObservacionVisionEvaluada, PoliticaVisionVigente,
)
from src.telemetry.domain.repositories.calidad_vision_repository import CalidadVisionRepository, PoliticaVisionPort

POR_PAGINA_MAXIMO = 200
#: Una cámara envía una observación por ventana (minutos): 24 h por defecto, como la ingesta.
RANGO_POR_DEFECTO = timedelta(hours=24)
RANGO_MAXIMO = timedelta(days=31)


@dataclass(frozen=True)
class PaginaCalidadVision:
    items: list[ObservacionVisionEvaluada]
    total: int
    pagina: int
    por_pagina: int
    desde: datetime
    hasta: datetime
    politica: Optional[PoliticaVisionVigente]
    politica_motivo: Optional[str]


class ConsultarCalidadVisionUseCase:

    def __init__(self, repo: CalidadVisionRepository, politica: PoliticaVisionPort) -> None:
        self._repo = repo
        self._politica = politica

    def execute(self, *, ids_fincas: Optional[list[int]], id_dispositivo_iot: Optional[int] = None,
                clasificacion: Optional[str] = None, desde: Optional[datetime] = None,
                hasta: Optional[datetime] = None, pagina: int = 1, por_pagina: int = 50,
                ahora: Optional[datetime] = None) -> PaginaCalidadVision:
        if clasificacion is not None and clasificacion not in (*CLASES_VISION, SIN_EVALUAR):
            raise ValidationError(code="CLASIFICACION_INVALIDA",
                                  message=f"clasificacion debe ser una de {[*CLASES_VISION, SIN_EVALUAR]}.",
                                  field="clasificacion")
        if pagina < 1:
            raise ValidationError(code="PAGINA_INVALIDA", message="pagina debe ser 1 o mayor.", field="pagina")
        if not 1 <= por_pagina <= POR_PAGINA_MAXIMO:
            raise ValidationError(code="POR_PAGINA_INVALIDO",
                                  message=f"por_pagina debe estar entre 1 y {POR_PAGINA_MAXIMO}.", field="por_pagina")
        hasta = hasta or ahora or datetime.now(timezone.utc)
        desde = desde or hasta - RANGO_POR_DEFECTO
        if desde > hasta:
            raise ValidationError(code="RANGO_FECHAS_INVALIDO", message="desde no puede ser posterior a hasta.",
                                  field="desde")
        if hasta - desde > RANGO_MAXIMO:
            raise ValidationError(code="RANGO_FECHAS_EXCESIVO", message="El rango no puede superar 31 días.",
                                  field="desde")
        items, total = self._repo.listar(FiltrosCalidadVision(
            desde=desde, hasta=hasta, ids_fincas=ids_fincas, id_dispositivo_iot=id_dispositivo_iot,
            clasificacion=clasificacion, pagina=pagina, por_pagina=por_pagina,
        ))
        politica, motivo = self._politica.vigente()
        return PaginaCalidadVision(items=items, total=total, pagina=pagina, por_pagina=por_pagina, desde=desde,
                                   hasta=hasta, politica=politica, politica_motivo=motivo)
