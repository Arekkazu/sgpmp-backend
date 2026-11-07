# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-07 RF-53: consulta del monitor de ingesta con rango acotado y paginación |
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from src.shared.errors import ValidationError
from src.shared.fechas import fin_dia_usuario, hoy_usuario, inicio_dia_usuario
from src.telemetry.domain.entities.lectura_ingesta import FiltrosIngesta, IndicadoresIngesta, LecturaIngesta
from src.telemetry.domain.repositories.ingesta_repository import IngestaRepository

#: Con decenas de miles de eventos por día, un rango mayor no se puede paginar con total exacto.
RANGO_MAXIMO = timedelta(days=31)
POR_PAGINA_MAXIMO = 200
ESTADOS = frozenset({
    'LECTURA_VALIDA', 'FUERA_DE_RANGO', 'ERROR_CALIBRACION', 'ERROR_ESTRUCTURA', 'ERROR_AUTENTICACION',
    'ERROR_DUPLICADO', 'ERROR_TIEMPO', 'ERROR_UNIDAD', 'ERROR_SENSOR',
})
ORIGENES = frozenset({'TIEMPO_REAL', 'BUFFER_LOCAL', 'EDGE_AGREGADO'})


class ConsultarIngestaUseCase:
    """AJF-07: el monitor de ingesta pintaba ingestaMock.ts. Solo lectura."""

    def __init__(self, repo: IngestaRepository) -> None:
        self._repo = repo

    def listar(
        self, *, ids_fincas: Optional[list[int]], desde: Optional[datetime] = None, hasta: Optional[datetime] = None,
        estado_calidad: Optional[str] = None, origen: Optional[str] = None, id_dispositivo_iot: Optional[int] = None,
        id_sensor: Optional[int] = None, pagina: int = 1, por_pagina: int = 50, ahora: Optional[datetime] = None,
    ) -> tuple[list[LecturaIngesta], int, FiltrosIngesta]:
        ahora = ahora or datetime.now(timezone.utc)
        hasta = hasta or ahora
        desde = desde or hasta - timedelta(hours=24)
        if desde > hasta:
            raise ValidationError(code='RANGO_FECHAS_INVALIDO', message='La fecha de inicio no puede ser posterior a la de fin.', field='desde')
        if hasta - desde > RANGO_MAXIMO:
            raise ValidationError(code='RANGO_MAXIMO_EXCEDIDO', message='El rango de fechas no puede superar 31 días.', field='desde')
        if pagina < 1:
            raise ValidationError(code='PAGINA_INVALIDA', message='pagina debe ser 1 o mayor.', field='pagina')
        if not 1 <= por_pagina <= POR_PAGINA_MAXIMO:
            raise ValidationError(code='POR_PAGINA_INVALIDO', message=f'por_pagina debe estar entre 1 y {POR_PAGINA_MAXIMO}.', field='por_pagina')
        if estado_calidad is not None and estado_calidad not in ESTADOS:
            raise ValidationError(code='ESTADO_INVALIDO', message=f'estado_calidad debe ser uno de: {sorted(ESTADOS)}.', field='estado_calidad')
        if origen is not None and origen not in ORIGENES:
            raise ValidationError(code='ORIGEN_INVALIDO', message=f'origen debe ser uno de: {sorted(ORIGENES)}.', field='origen')
        filtros = FiltrosIngesta(desde=desde, hasta=hasta, ids_fincas=ids_fincas, estado_calidad=estado_calidad,
                                 origen=origen, id_dispositivo_iot=id_dispositivo_iot, id_sensor=id_sensor,
                                 pagina=pagina, por_pagina=por_pagina)
        items, total = self._repo.listar(filtros)
        return items, total, filtros

    def indicadores_de_hoy(self, ids_fincas: Optional[list[int]]) -> IndicadoresIngesta:
        """El día del usuario (cabecera X-Zona-Horaria), no el día UTC."""
        hoy = hoy_usuario()
        return self._repo.indicadores(inicio_dia_usuario(hoy), fin_dia_usuario(hoy), ids_fincas)

