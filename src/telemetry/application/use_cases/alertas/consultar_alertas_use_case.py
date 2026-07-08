from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.shared.errors import NotFoundError
from src.telemetry.domain.entities.alerta import Alerta, HistoricoEstadoAlerta
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
    ) -> tuple[list[Alerta], int]:
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
        )

    def obtener_detalle(self, id_alerta: int) -> tuple[Alerta, list[HistoricoEstadoAlerta]]:
        alerta = self.alerta_repo.obtener_por_id(id_alerta)
        if alerta is None:
            raise NotFoundError(code="ALERTA_NO_ENCONTRADA", message=f"Alerta {id_alerta} no encontrada.")
        historico = self.historico_repo.obtener_por_alerta(id_alerta)
        return alerta, historico
