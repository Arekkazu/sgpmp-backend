# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-27 RF-60: aplica politica canonica y señal SNR |
# | 2026-10-22 | Leandro | DEV-42 RF-60: bateria unica, reloj futuro y reconexion |
# | 2026-10-27 | Leandro | INC-M03-126-G27 RF-54: conservar las métricas de buffer en la misma transacción del heartbeat. |
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.shared.errors import AuthenticationError, ServiceUnavailableError
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.domain.entities.heartbeat import Heartbeat
from src.telemetry.domain.repositories.dispositivo_port import DispositivoPort
from src.telemetry.domain.repositories.heartbeat_repository import HeartbeatRepository
from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO
from .transicion_comunicacion import completar_transicion_comunicacion

class RecibirHeartbeatUseCase:

    def __init__(
        self,
        db: Session,
        dispositivo_port: DispositivoPort,
        heartbeat_repo: HeartbeatRepository,
    ) -> None:
        self.db = db
        self.dispositivo_port = dispositivo_port
        self.heartbeat_repo = heartbeat_repo

    def execute(self, dto: HeartbeatDTO) -> Heartbeat:
        device_id = dto.device_id
        ahora = datetime.now(timezone.utc)

        try:
            # Paso 1: Autenticar dispositivo vía M09 (heartbeat no requiere sensor_id)
            dispositivo = self.dispositivo_port.validar_dispositivo_heartbeat(
                device_id=device_id,
                serial=dto.serial,
            )
            if dispositivo is None:
                raise AuthenticationError(
                    code='ERROR_AUTENTICACION_HEARTBEAT',
                    message='El dispositivo no existe o no corresponde al serial.',
                )
            if not dispositivo.es_activo:
                raise AuthenticationError(
                    code='ERROR_AUTENTICACION_HEARTBEAT',
                    message='El dispositivo no está activo.',
                )

            # Paso 2: Persistir heartbeat
            heartbeat = self.heartbeat_repo.guardar(Heartbeat(
                id_heartbeat=None,
                id_dispositivo_iot=device_id,
                tipo_mensaje=dto.tipo_mensaje,
                nivel_bateria_pct=dto.nivel_bateria_pct,
                calidad_senal_rssi=dto.calidad_senal_rssi,
                calidad_senal_snr=dto.calidad_senal_snr,
                estado_local_buffer=dto.estado_local_buffer,
                datos_pendientes_buffer=dto.datos_pendientes_buffer,
                version_firmware=dto.version_firmware,
                coordenadas=dto.coordenadas,
                fecha_registro=dto.fecha_registro,
                fecha_recepcion=ahora,
                reloj_sincronizado=dto.reloj_sincronizado and dto.fecha_registro <= ahora,
                sensores_operativos=[s.model_dump() for s in dto.sensores_operativos] if dto.sensores_operativos is not None else None,
                temperatura_dispositivo=dto.temperatura_dispositivo,
                metricas_buffer=dto.metricas_buffer.model_dump(mode='json') if dto.metricas_buffer is not None else None,
            ))

            # El trigger conserva contacto/reconexión. Las demás responsabilidades
            # se recuperan desde la fila confirmada, igual que en el canal MQTT.
            self.db.commit()
            return heartbeat

        except Exception:
            self.db.rollback()
            raise


class ProcesarHeartbeatPersistidoUseCase:
    """Responsabilidades posteriores al commit, comunes a HTTP y MQTT.

    No vuelve a insertar heartbeats ni interpreta credenciales MQTT como HTTP.
    La transacción externa del procesador confirma efectos y evidencia juntos.
    """
    def __init__(self, estado_repo, alerta_repo, parametros_port, periodo_repo):
        self.estado_repo = estado_repo
        self.alerta_repo = alerta_repo
        self.parametros_port = parametros_port
        self.periodo_repo = periodo_repo

    def procesar_estado(self, heartbeat: Heartbeat, es_ultimo: bool):
        if not es_ultimo:
            return
        estado = self.estado_repo.bloquear_por_dispositivo(heartbeat.id_dispositivo_iot)
        if estado is None:
            raise RuntimeError('Falta el estado creado por el trigger de heartbeat.')
        if estado.fecha_ultimo_contacto is None:
            return
        parametros = self.parametros_port.obtener_comunicacion(heartbeat.id_dispositivo_iot)
        ahora = datetime.now(timezone.utc)
        tiempo = int((ahora-estado.fecha_ultimo_contacto).total_seconds())
        nuevo = estado.evaluar_transicion(
            tiempo,
            heartbeat.estado_local_buffer, parametros.umbral_activo,
            parametros.umbral_sin_senal, parametros.umbral_inactivo,
        )
        if nuevo is not None:
            estado.aplicar_transicion(
                nuevo, causa='FALLO_CONECTIVIDAD' if nuevo in ('BUFFER_ACTIVO','SIN_SEÑAL','INACTIVO') else None,
                ahora=ahora,
            )
            estado.tiempo_sin_contacto = tiempo
            self.estado_repo.actualizar(estado)
            # fn_log_transicion_dispositivo registra transición y período.
        completar_transicion_comunicacion(estado, parametros, tiempo, ahora,
            self.alerta_repo, self.periodo_repo, 'HEARTBEAT')


    def procesar_alertas(self, heartbeat: Heartbeat, id_infraestructura: int):
        self.alerta_repo.bloquear_dispositivo(heartbeat.id_dispositivo_iot)
        if heartbeat.fecha_registro > heartbeat.fecha_recepcion:
            if not self.alerta_repo.buscar_tecnica_activa_dispositivo(heartbeat.id_dispositivo_iot, 'DESINCRONIZACION_RELOJ'):
                self.alerta_repo.guardar(Alerta(
                    tipo_alerta='TECNICA', severidad='LEVE', estado_alerta='ACTIVA',
                    origen_evento='HEARTBEAT', tipo_variable='DESINCRONIZACION_RELOJ',
                    fecha_evento=heartbeat.fecha_recepcion, fecha_generacion=heartbeat.fecha_recepcion,
                    id_dispositivo_ioit=heartbeat.id_dispositivo_iot, id_infraestructura=id_infraestructura,
                    metadato_evento={'id_heartbeat': heartbeat.id_heartbeat, 'reloj_desincronizado': True,
                        'fecha_dispositivo': heartbeat.fecha_registro.isoformat(),
                        'fecha_recepcion': heartbeat.fecha_recepcion.isoformat()},
                ))
        if heartbeat.nivel_bateria_pct is None and heartbeat.calidad_senal_rssi is None and heartbeat.calidad_senal_snr is None:
            return
        params = self.parametros_port.obtener()
        causas = []
        if heartbeat.nivel_bateria_pct is not None:
            if heartbeat.nivel_bateria_pct <= 5:
                causas.append(('APAGADO_INMINENTE', 'CRITICO'))
            elif heartbeat.nivel_bateria_pct <= params.bateria_critica:
                causas.append(('BATERIA_CRITICA', 'CRITICO'))
            elif heartbeat.nivel_bateria_pct <= params.bateria_baja:
                causas.append(('BATERIA_BAJA', 'MODERADO'))
        if heartbeat.calidad_senal_snr is not None and params.snr_degradado is None:
            raise ServiceUnavailableError('PARAMETRO_CONFIGURACION_AUSENTE', 'No está configurado el umbral SNR.')
        if (heartbeat.calidad_senal_rssi is not None and heartbeat.calidad_senal_rssi < params.rssi_degradado) or (
            heartbeat.calidad_senal_snr is not None and heartbeat.calidad_senal_snr < params.snr_degradado
        ):
            causas.append(('SEÑAL_DEGRADADA', 'LEVE'))
        for causa, severidad in causas:
            orden_bateria = {'BATERIA_BAJA': 0, 'BATERIA_CRITICA': 1, 'APAGADO_INMINENTE': 2}
            if causa in orden_bateria:
                existentes = [self.alerta_repo.buscar_tecnica_activa_dispositivo(heartbeat.id_dispositivo_iot, codigo)
                    for codigo in orden_bateria]
                existente = next((a for a in existentes if a is not None), None)
                if existente is not None:
                    condicion = (existente.metadato_evento or {}).get('condicion_bateria', existente.tipo_variable)
                    if orden_bateria[causa] > orden_bateria[condicion]:
                        self.alerta_repo.escalar_bateria(existente.id_alerta, causa, severidad,
                            {'id_heartbeat_escalamiento': heartbeat.id_heartbeat, 'nivel_bateria_pct': str(heartbeat.nivel_bateria_pct)})
                    continue
            if self.alerta_repo.buscar_tecnica_activa_dispositivo(heartbeat.id_dispositivo_iot, causa):
                continue
            self.alerta_repo.guardar(Alerta(
                id_alerta=None, tipo_alerta='TECNICA', severidad=severidad,
                estado_alerta='ACTIVA', origen_evento='HEARTBEAT', tipo_variable=causa,
                fecha_evento=heartbeat.fecha_registro, fecha_generacion=heartbeat.fecha_recepcion,
                id_dispositivo_ioit=heartbeat.id_dispositivo_iot,
                id_infraestructura=id_infraestructura,
                metadato_evento={'id_heartbeat': heartbeat.id_heartbeat},
            ))
            # El trigger de alertas registra el historial inicial; no se duplica.
