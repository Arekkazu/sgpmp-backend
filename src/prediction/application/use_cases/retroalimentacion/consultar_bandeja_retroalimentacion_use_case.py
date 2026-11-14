# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | RF-72: bandeja de inferencias por evaluar (la pantalla mostraba datos de ejemplo) |
# | 2026-11-03 | Claude   | RF-72: página e indicadores en una sola consulta |
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.configuration.domain.entities.parametro_mlops import RF72_VENTANA, numero_configurado
from src.configuration.domain.repositories.parametros_mlops_port import ParametrosMLOpsPort
from src.prediction.domain.entities.bandeja_retroalimentacion import (
    ESTADOS_EVALUACION,
    FiltrosBandejaRetroalimentacion,
    IndicadoresBandejaRetroalimentacion,
    InferenciaPorEvaluar,
)
from src.prediction.domain.repositories.bandeja_retroalimentacion_repository import (
    BandejaRetroalimentacionRepository,
)
from src.shared.errors import ValidationError

POR_PAGINA_MAXIMO = 100
#: Sin fechas se mira la ventana más un mes: así aparecen también las recién vencidas.
MARGEN_VENCIDAS = timedelta(days=30)
RANGO_MAXIMO = timedelta(days=366)


@dataclass(frozen=True)
class PaginaBandejaRetroalimentacion:
    items: list[InferenciaPorEvaluar]
    total: int
    pagina: int
    por_pagina: int
    ventana_dias: int
    indicadores: IndicadoresBandejaRetroalimentacion


class ConsultarBandejaRetroalimentacionUseCase:
    """RF-72: qué puede evaluar el veterinario. La ventana es la misma que valida el registro
    (``ventana_retroalimentacion_dias`` de M09), así la bandeja no ofrece lo que el POST rechazaría."""

    def __init__(self, repo: BandejaRetroalimentacionRepository, parametros_port: ParametrosMLOpsPort) -> None:
        self._repo = repo
        self._parametros = parametros_port

    def execute(
        self, *, ids_fincas: Optional[list[int]], id_usuario: int, estado_evaluacion: Optional[str] = None,
        nivel_riesgo: Optional[int] = None, id_activo_biologico: Optional[int] = None,
        desde: Optional[datetime] = None, hasta: Optional[datetime] = None, pagina: int = 1,
        por_pagina: int = 25, ahora: Optional[datetime] = None,
    ) -> PaginaBandejaRetroalimentacion:
        if estado_evaluacion is not None and estado_evaluacion not in ESTADOS_EVALUACION:
            raise ValidationError(
                code="ESTADO_EVALUACION_INVALIDO",
                message=f"estado_evaluacion debe ser uno de {list(ESTADOS_EVALUACION)}.",
                field="estado_evaluacion",
            )
        if nivel_riesgo is not None and not 0 <= nivel_riesgo <= 3:
            raise ValidationError(code="NIVEL_RIESGO_INVALIDO", message="nivel_riesgo debe estar entre 0 y 3.",
                                  field="nivel_riesgo")
        if pagina < 1:
            raise ValidationError(code="PAGINA_INVALIDA", message="pagina debe ser 1 o mayor.", field="pagina")
        if not 1 <= por_pagina <= POR_PAGINA_MAXIMO:
            raise ValidationError(code="POR_PAGINA_INVALIDO",
                                  message=f"por_pagina debe estar entre 1 y {POR_PAGINA_MAXIMO}.", field="por_pagina")

        ahora = ahora or datetime.now(timezone.utc)
        ventana = numero_configurado(self._parametros.obtener([RF72_VENTANA]), RF72_VENTANA,
                                     minimo=7, maximo=365, entero=True)
        hasta = hasta or ahora
        desde = desde or hasta - timedelta(days=ventana) - MARGEN_VENCIDAS
        if desde > hasta:
            raise ValidationError(code="RANGO_FECHAS_INVALIDO", message="desde no puede ser posterior a hasta.",
                                  field="desde")
        if hasta - desde > RANGO_MAXIMO:
            raise ValidationError(code="RANGO_FECHAS_EXCESIVO", message="El rango no puede superar 366 días.",
                                  field="desde")

        filtros = FiltrosBandejaRetroalimentacion(
            ids_fincas=ids_fincas, desde=desde, hasta=hasta, ahora=ahora, ventana_dias=int(ventana),
            id_usuario=id_usuario, estado_evaluacion=estado_evaluacion, nivel_riesgo=nivel_riesgo,
            id_activo_biologico=id_activo_biologico, pagina=pagina, por_pagina=por_pagina,
        )
        items, total, indicadores = self._repo.consultar(filtros)
        return PaginaBandejaRetroalimentacion(
            items=items, total=total, pagina=pagina, por_pagina=por_pagina, ventana_dias=int(ventana),
            indicadores=indicadores,
        )
