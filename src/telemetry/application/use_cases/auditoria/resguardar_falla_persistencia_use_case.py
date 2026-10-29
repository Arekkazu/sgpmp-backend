# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-125-G12 RF-53/63: construir evidencia FALLA_PERSISTENCIA sin depender de la BD caída. |
from datetime import datetime, timezone
from uuid import uuid4
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import _calcular_hash
from src.telemetry.domain.entities.evento_auditoria_iot import (
    EventoAuditoriaIot, ComponenteOrigen, EntidadAfectadaTipo, TipoResultado, SeveridadLog, clasificar_componente,
)
from src.telemetry.domain.repositories.respaldo_auditoria_iot_port import RespaldoAuditoriaIotPort


class ResguardarFallaPersistenciaUseCase:
    def __init__(self, respaldo: RespaldoAuditoriaIotPort):
        self.respaldo = respaldo

    def execute(self, endpoint: str, detalle: dict) -> EventoAuditoriaIot:
        clasificacion, retencion = clasificar_componente(ComponenteOrigen.RF53)
        dispositivo = detalle.get('device_id')
        evento = EventoAuditoriaIot(
            id_evento=uuid4(), tipo_evento='FALLA_PERSISTENCIA', fecha_hora=datetime.now(timezone.utc),
            resultado=TipoResultado.FALLIDO, componente_origen=ComponenteOrigen.RF53,
            entidad_afectada_tipo=EntidadAfectadaTipo.DISPOSITIVO if dispositivo else None,
            entidad_afectada_id=str(dispositivo) if dispositivo else None,
            accion_detallada={'endpoint':endpoint, 'operacion':'POST', 'resguardo_lectura':'EDGE_RF54', **detalle},
            descripcion='No se confirmó la persistencia de la ingesta; el emisor debe conservar y reintentar.',
            severidad_log=SeveridadLog.ERROR, clasificacion_registro=clasificacion, retencion_aplicable=retencion,
        )
        evento.hash_integridad = _calcular_hash(evento)
        self.respaldo.guardar(evento)
        return evento
