# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-209-G092 RF-73: filtro por correlacion_id |
# | 2026-10-27 | Leandro | INC-M04-158-G086 RF-73: identificar consultas globales sin inventar entidades de negocio. |
# | 2026-10-29 | Arekkazu | TC-DIS-195 RF-73: filtro de la bitácora M04 por tipo_modelo del evento |
# | 2026-10-29 | Arekkazu | QA-M04-27-10 CU09 H-04 RF-73: consultar la bitácora no emite HISTORIAL_CONSULTADO |
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from src.prediction.domain.entities.evento_auditoria_m04 import EventoAuditoriaM04
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository


class ConsultarAuditoriaM04UseCase:
    """CU09 H-04: consultar la bitácora no deja evento. HISTORIAL_CONSULTADO es del
    historial diagnóstico (RF-67); cada carga de la pestaña llenaba la bitácora."""

    def __init__(self, repo: EventoAuditoriaM04Repository) -> None:
        self._repo = repo

    def listar(
        self,
        *,
        tipo_evento: Optional[str],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
        id_usuario: Optional[int],
        id_sistema: Optional[str],
        id_referencia: Optional[str],
        severidad_evento: Optional[str],
        pagina: int,
        por_pagina: int,
        correlacion_id: Optional[uuid.UUID] = None,
        tipo_modelo: Optional[str] = None,
    ) -> tuple[list[EventoAuditoriaM04], int]:
        items, total = self._repo.consultar(
            tipo_evento=tipo_evento,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            id_usuario=id_usuario,
            id_sistema=id_sistema,
            id_referencia=id_referencia,
            severidad_evento=severidad_evento,
            correlacion_id=correlacion_id,
            tipo_modelo=tipo_modelo,
            pagina=pagina,
            por_pagina=por_pagina,
        )
        return items, total

    def obtener_por_id(self, id_evento: uuid.UUID) -> EventoAuditoriaM04:
        return self._repo.obtener_por_id(id_evento)
