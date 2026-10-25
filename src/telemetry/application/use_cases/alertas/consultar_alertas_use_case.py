# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-24 | Arekkazu | USAB-M03 M3-06/M3-08 RF-57: ubicación con nombres y filtro por fecha de resolución |
from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.shared.errors import NotFoundError
from src.telemetry.domain.entities.alerta import (
    TIPO_ALERTA_TECNICA,
    Alerta,
    AmbitoAlerta,
    HistoricoEstadoAlerta,
)
from src.telemetry.domain.repositories.alerta_repository import AlertaRepository
from src.telemetry.domain.repositories.historico_estado_alerta_repository import HistoricoEstadoAlertaRepository


class ConsultarAlertasUseCase:

    def __init__(
        self,
        alerta_repo: AlertaRepository,
        historico_repo: HistoricoEstadoAlertaRepository,
    ) -> None:
        self.alerta_repo = alerta_repo
        self.historico_repo = historico_repo

    def listar(
        self,
        estado: Optional[str] = None,
        severidad: Optional[str] = None,
        tipo_alerta: Optional[str] = None,
        id_sensor: Optional[int] = None,
        id_activo_biologico: Optional[int] = None,
        origen_evento: Optional[str] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        pagina: int = 1,
        por_pagina: int = 50,
        *,
        ambito: AmbitoAlerta,
        ids_fincas_permitidas: Optional[list[int]] = None,
        fecha_resolucion_desde: Optional[datetime] = None,
    ) -> tuple[list[Alerta], int]:
        # RF-60 D-09: cada endpoint solo lista las alertas de su ámbito. En el
        # operativo, un filtro tipo_alerta=TECNICA devuelve una página vacía.
        if ambito is AmbitoAlerta.TECNICA:
            tipo_alerta = TIPO_ALERTA_TECNICA
        return self.alerta_repo.listar(
            estado=estado,
            severidad=severidad,
            tipo_alerta=tipo_alerta,
            id_sensor=id_sensor,
            id_activo_biologico=id_activo_biologico,
            origen_evento=origen_evento,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            pagina=pagina,
            por_pagina=por_pagina,
            ids_fincas_permitidas=ids_fincas_permitidas,
            excluir_tipo_alerta=TIPO_ALERTA_TECNICA if ambito is AmbitoAlerta.OPERATIVA else None,
            fecha_resolucion_desde=fecha_resolucion_desde,
        )

    def obtener_detalle(
        self,
        id_alerta: int,
        *,
        ambito: AmbitoAlerta,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> tuple[Alerta, list[HistoricoEstadoAlerta]]:
        alerta = self.alerta_repo.obtener_por_id(
            id_alerta, ids_fincas_permitidas=ids_fincas_permitidas
        )
        if alerta is None or not ambito.admite(alerta.tipo_alerta):
            raise NotFoundError(code="ALERTA_NO_ENCONTRADA", message=f"Alerta {id_alerta} no encontrada.")
        historico = self.historico_repo.obtener_por_alerta(id_alerta)
        return alerta, historico
