# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-10 RF-66: monitor de inferencias paginado, con filtros por animal y totales del periodo |
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.prediction.application.use_cases.monitor.filtros_monitor import validar_filtros
from src.prediction.domain.entities.monitor_prediccion import IndicadoresInferencias, InferenciaMonitor
from src.prediction.domain.repositories.monitor_prediccion_repository import MonitorPrediccionRepository
from src.shared.errors import ValidationError

#: Mismo tope que el listado (LIMITE_MAXIMO): una página nunca trae más.
POR_PAGINA_MAXIMO = 200


@dataclass(frozen=True)
class PaginaInferencias:
    items: list[InferenciaMonitor]
    pagina: int
    por_pagina: int
    indicadores: IndicadoresInferencias


class PaginarInferenciasUseCase:
    """AJF-10: el monitor necesitaba saber cuántas hay (no solo las últimas 200) y
    filtrar por animal. ``GET /prediccion/inferencias`` sigue igual para Estado sanitario."""

    def __init__(self, repo: MonitorPrediccionRepository) -> None:
        self._repo = repo

    def execute(
        self, *, ids_fincas: Optional[list[int]], pagina: int = 1, por_pagina: int = 25,
        tipo_modelo: Optional[str] = None, nivel_riesgo: Optional[int] = None,
        desde: Optional[datetime] = None, hasta: Optional[datetime] = None,
        id_activo_biologico: Optional[int] = None, id_infraestructura: Optional[int] = None,
        solo_con_alerta: bool = False, incluir_sombra: bool = True,
    ) -> PaginaInferencias:
        if pagina < 1:
            raise ValidationError(code="PAGINA_INVALIDA", message="pagina debe ser 1 o mayor.", field="pagina")
        if not 1 <= por_pagina <= POR_PAGINA_MAXIMO:
            raise ValidationError(
                code="POR_PAGINA_INVALIDO", message=f"por_pagina debe estar entre 1 y {POR_PAGINA_MAXIMO}.",
                field="por_pagina",
            )
        validar_filtros(tipo_modelo=tipo_modelo, nivel_riesgo=nivel_riesgo, desde=desde, hasta=hasta, limite=por_pagina)
        filtros = dict(
            ids_fincas=ids_fincas, tipo_modelo=tipo_modelo, nivel_riesgo=nivel_riesgo, desde=desde, hasta=hasta,
            id_activo_biologico=id_activo_biologico, id_infraestructura=id_infraestructura,
            solo_con_alerta=solo_con_alerta, incluir_sombra=incluir_sombra,
        )
        items = self._repo.listar_inferencias(**filtros, limite=por_pagina, desplazamiento=(pagina - 1) * por_pagina)
        return PaginaInferencias(items=items, pagina=pagina, por_pagina=por_pagina,
                                 indicadores=self._repo.contar_inferencias(**filtros))
