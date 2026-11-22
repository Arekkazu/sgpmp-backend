# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-129-G27 RF-54/60/63: crear y escalar el aviso de capacidad bajo bloqueo conservando la alerta y sus contratos. |
"""Caso de uso: aviso de buffer del Gateway Edge (RF-54 Fase 4/E1/E6 → RF-60 + RF-63, D10 de AIOT-DEV-03).

El Edge avisa por MQTT (``status`` con ``tipo_mensaje = EVENTO_BUFFER``) que su
buffer alcanzó una ocupación de advertencia (``BUFFER_CAPACITY_WARNING``),
desbordó (``BUFFER_OVERFLOW``) o que aisló datos corruptos
(``BUFFER_DATA_CORRUPTION``). El broker reenvía el aviso y aquí se convierte en
una alerta técnica de RF-60, que solo ven los roles con el recurso de alertas
técnicas (el Ingeniero, no el Productor), y en un evento de auditoría de RF-63.

Mientras la alerta del mismo tipo siga abierta (ACTIVA o EN_ATENCION), cada
aviso nuevo se cuenta en ella en lugar de abrir otra: un buffer lleno avisa
una vez por dato descartado y no debe inundar la bandeja del Ingeniero.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import NotFoundError
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import (
    RegistrarEventoAuditoriaIotUseCase,
)
from src.telemetry.domain.entities.alerta import Alerta, SeveridadAlerta
from src.telemetry.domain.entities.evento_auditoria_iot import (
    ComponenteOrigen,
    EntidadAfectadaTipo,
    SeveridadLog,
    TipoResultado,
)
from src.telemetry.domain.repositories.alerta_repository import AlertaRepository
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository
from src.telemetry.domain.repositories.dispositivo_port import DispositivoPort
from src.telemetry.infrastructure.dto.evento_buffer_dto import EventoBuffer, RecibirEventoBufferDTO

# Un overflow pierde datos nuevos o sobrescribe viejos según la política; una
# corrupción exige intervención técnica (RF-54 E6), por eso pesa más.
_SEVERIDAD = {
    EventoBuffer.BUFFER_CAPACITY_WARNING: 'LEVE',
    EventoBuffer.BUFFER_OVERFLOW: 'MODERADO',
    EventoBuffer.BUFFER_DATA_CORRUPTION: 'CRITICO',
}
_SEVERIDAD_LOG = {
    EventoBuffer.BUFFER_CAPACITY_WARNING: SeveridadLog.WARNING,
    EventoBuffer.BUFFER_OVERFLOW: SeveridadLog.WARNING,
    EventoBuffer.BUFFER_DATA_CORRUPTION: SeveridadLog.ERROR,
}
_ACCION_SUGERIDA = {
    EventoBuffer.BUFFER_CAPACITY_WARNING: 'Revisar la conectividad y sincronizar el buffer antes de agotar su capacidad.',
    EventoBuffer.BUFFER_OVERFLOW: 'Revisar la conectividad del Gateway Edge y su capacidad de buffer.',
    EventoBuffer.BUFFER_DATA_CORRUPTION: 'Revisar el almacenamiento del Gateway Edge: los datos corruptos no se sincronizan.',
}


@dataclass
class ResultadoEventoBuffer:
    id_alerta: int
    es_duplicado: bool
    tipo_alerta_tecnica: str
    severidad: str


def _utc(ts: datetime) -> datetime:
    return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts


class RegistrarEventoBufferUseCase:

    def __init__(
        self,
        db: Session,
        dispositivo_port: DispositivoPort,
        alerta_repo: AlertaRepository,
        auditoria_repo: BitacoraAuditoriaIotRepository,
    ) -> None:
        self.db = db
        self.dispositivo_port = dispositivo_port
        self.alerta_repo = alerta_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, dto: RecibirEventoBufferDTO) -> ResultadoEventoBuffer:
        dispositivo = self.dispositivo_port.obtener_por_serial(dto.serial)
        if dispositivo is None:
            raise NotFoundError(
                code='DISPOSITIVO_NO_ENCONTRADO',
                message=f'No existe un dispositivo con serial {dto.serial}.',
                field='serial',
            )

        ahora = datetime.now(timezone.utc)
        fecha_evento = _utc(dto.timestamp_evento)
        tipo = dto.evento.value
        es_capacidad = dto.evento == EventoBuffer.BUFFER_CAPACITY_WARNING
        severidad = _SEVERIDAD[dto.evento]
        # RF-54 permite configurar el aviso en Edge; no se impone otro mínimo al recibirlo.
        if es_capacidad and dto.porcentaje_ocupacion >= 95:
            severidad = 'CRITICO'
        detalle = {
            'serial': dto.serial,
            'evento': tipo,
            'porcentaje_ocupacion': str(dto.porcentaje_ocupacion),
            'politica_aplicada': dto.politica_aplicada,
            'cantidad_datos_afectados': dto.cantidad_datos_afectados,
            'timestamp_evento': fecha_evento.isoformat(),
        }

        try:
            self.alerta_repo.bloquear_dispositivo(dispositivo.id_dispositivo_iot)
            abierta = self.alerta_repo.buscar_tecnica_abierta(dispositivo.id_dispositivo_iot, tipo)
            if abierta is not None:
                ultima_ocurrencia = fecha_evento
                nueva_severidad = None
                if es_capacidad:
                    if SeveridadAlerta(severidad) > SeveridadAlerta(abierta.severidad):
                        nueva_severidad = severidad
                    if abierta.ultima_ocurrencia is not None:
                        ultima_ocurrencia = max(ultima_ocurrencia, _utc(abierta.ultima_ocurrencia))
                if nueva_severidad is None:
                    self.alerta_repo.actualizar_deduplicacion(abierta.id_alerta, ultima_ocurrencia=ultima_ocurrencia)
                else:
                    self.alerta_repo.actualizar_deduplicacion(abierta.id_alerta,
                        ultima_ocurrencia=ultima_ocurrencia, nueva_severidad=nueva_severidad)
                    abierta.severidad = nueva_severidad
                alerta = abierta
            else:
                alerta = self.alerta_repo.guardar(Alerta(
                    tipo_alerta='TECNICA',
                    severidad=severidad,
                    estado_alerta='ACTIVA',
                    origen_evento='EDGE',
                    tipo_variable=tipo,
                    fecha_evento=fecha_evento,
                    fecha_generacion=ahora,
                    id_dispositivo_ioit=dispositivo.id_dispositivo_iot,
                    id_infraestructura=dispositivo.id_infraestructura,
                    metadato_evento=detalle,
                    diagnostico=self._diagnostico(dto),
                    accion_sugerida=_ACCION_SUGERIDA[dto.evento],
                    ultima_ocurrencia=fecha_evento,
                ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # RF-63 después del commit, best-effort como el resto de M03: la alerta ya quedó.
        RegistrarEventoAuditoriaIotUseCase(db=self.db, auditoria_repo=self.auditoria_repo).execute(
            tipo_evento=tipo,
            resultado=TipoResultado.ADVERTENCIA,
            componente_origen=ComponenteOrigen.RF54,
            severidad_log=(SeveridadLog.ERROR if es_capacidad and severidad == 'CRITICO'
                           else _SEVERIDAD_LOG[dto.evento]),
            descripcion=self._diagnostico(dto),
            entidad_afectada_tipo=EntidadAfectadaTipo.BUFFER,
            entidad_afectada_id=str(dispositivo.id_dispositivo_iot),
            accion_detallada={**detalle, 'id_alerta': alerta.id_alerta, 'es_duplicado': abierta is not None,
                             **({'severidad_alerta': alerta.severidad} if es_capacidad else {})},
        )

        return ResultadoEventoBuffer(
            id_alerta=alerta.id_alerta,
            es_duplicado=abierta is not None,
            tipo_alerta_tecnica=tipo,
            severidad=alerta.severidad,
        )

    @staticmethod
    def _diagnostico(dto: RecibirEventoBufferDTO) -> str:
        politica: Optional[str] = dto.politica_aplicada
        return (
            f'{dto.evento.value} en {dto.serial}: buffer al {dto.porcentaje_ocupacion}%, '
            f'{dto.cantidad_datos_afectados} datos afectados'
            + (f', política {politica}.' if politica else '.')
        )
