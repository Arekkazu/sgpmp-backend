from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from src.shared.errors import NotFoundError
from src.telemetry.domain.entities.evento_auditoria_iot import EventoAuditoriaIot
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository


class ConsultarBitacoraIotUseCase:

    def __init__(self, auditoria_repo: BitacoraAuditoriaIotRepository) -> None:
        self.auditoria_repo = auditoria_repo

    def get(self, id_evento: UUID) -> EventoAuditoriaIot:
        evento = self.auditoria_repo.obtener(id_evento)
        if evento is None:
            raise NotFoundError(code='EVENTO_NO_ENCONTRADO', message='Evento de auditoría no encontrado.')
        return evento

    def listar(
        self,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        tipo_evento: Optional[str] = None,
        severidad_log: Optional[str] = None,
        clasificacion_registro: Optional[str] = None,
        entidad_afectada_id: Optional[str] = None,
        resultado: Optional[str] = None,
        pagina: int = 1,
        por_pagina: int = 50,
    ) -> tuple[list[EventoAuditoriaIot], int]:
        return self.auditoria_repo.listar(
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            tipo_evento=tipo_evento,
            severidad_log=severidad_log,
            clasificacion_registro=clasificacion_registro,
            entidad_afectada_id=entidad_afectada_id,
            resultado=resultado,
            pagina=pagina,
            por_pagina=por_pagina,
        )
