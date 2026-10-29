# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M03-136/137 RF-63: filtros id_usuario, rf_origen y registro_incompleto |
# | 2026-10-25 | Arekkazu | USAB-M03 M3-14 RF-63: bitácora limitada a las fincas del usuario salvo para el auditor |
# | 2026-10-27 | destroyerban | INC-M03-116-G59 RF-56 CA-8: filtro entidad_afectada_tipo y alcance por finca de PAQUETE_IA |
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

    def get(self, id_evento: UUID, *, ids_fincas_permitidas: Optional[list[int]] = None) -> EventoAuditoriaIot:
        # Fuera de las fincas del usuario el evento "no existe" (404), igual que en Alertas.
        evento = self.auditoria_repo.obtener(id_evento, ids_fincas_permitidas=ids_fincas_permitidas)
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
        id_usuario: Optional[int] = None,
        rf_origen: Optional[str] = None,
        registro_incompleto: Optional[bool] = None,
        entidad_afectada_tipo: Optional[str] = None,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> tuple[list[EventoAuditoriaIot], int]:
        return self.auditoria_repo.listar(
            ids_fincas_permitidas=ids_fincas_permitidas,
            id_usuario=id_usuario,
            rf_origen=rf_origen,
            registro_incompleto=registro_incompleto,
            entidad_afectada_tipo=entidad_afectada_tipo,
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
