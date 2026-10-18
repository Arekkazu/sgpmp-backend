from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.shared.errors import AuthenticationError
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.domain.entities.heartbeat import Heartbeat
from src.telemetry.domain.repositories.dispositivo_port import DispositivoPort
from src.telemetry.domain.repositories.heartbeat_repository import HeartbeatRepository
from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO

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

    def execute(self, dto: HeartbeatDTO, device_id: int, access_key: str) -> Heartbeat:
        ahora = datetime.now(timezone.utc)

        try:
            # Paso 1: Autenticar dispositivo vía M09 (heartbeat no requiere sensor_id)
            dispositivo = self.dispositivo_port.validar_dispositivo_heartbeat(
                device_id=device_id,
                access_key=access_key,
            )
            if dispositivo is None:
                raise AuthenticationError(
                    code='ERROR_AUTENTICACION_HEARTBEAT',
                    message='Dispositivo no encontrado o credenciales inválidas.',
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
                reloj_sincronizado=dto.reloj_sincronizado,
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
    def __init__(self, estado_repo, alerta_repo, parametros_port):
        self.estado_repo = estado_repo
        self.alerta_repo = alerta_repo
        self.parametros_port = parametros_port

    def procesar_estado(self, heartbeat: Heartbeat, es_ultimo: bool):
        if not es_ultimo:
            return
        estado = self.estado_repo.obtener_por_dispositivo(heartbeat.id_dispositivo_iot)
        if estado is None:
            raise RuntimeError('Falta el estado creado por el trigger de heartbeat.')
        # El trigger ya registra el contacto y la reconexión. Un reproceso no puede
        # despertar un dispositivo que RF-60 ya marcó sin señal, ni el mantenimiento.
        if estado.estado_actual not in ('ACTIVO', 'BUFFER_ACTIVO'):
            return
        nuevo = 'BUFFER_ACTIVO' if heartbeat.estado_local_buffer in ('A', 'L') else 'ACTIVO'
        if nuevo != estado.estado_actual:
            estado.aplicar_transicion(
                nuevo, causa='FALLO_CONECTIVIDAD' if nuevo == 'BUFFER_ACTIVO' else None,
                ahora=heartbeat.fecha_recepcion,
            )
            self.estado_repo.actualizar(estado)
            # fn_log_transicion_dispositivo registra transición y período.


    def procesar_alertas(self, heartbeat: Heartbeat, id_infraestructura: int):
        if heartbeat.nivel_bateria_pct is None and heartbeat.calidad_senal_rssi is None:
            return
        params = self.parametros_port.obtener()
        causas = []
        if heartbeat.nivel_bateria_pct is not None:
            if heartbeat.nivel_bateria_pct <= params.bateria_critica:
                causas.append(('BATERIA_CRITICA', 'CRITICO'))
            elif heartbeat.nivel_bateria_pct <= params.bateria_baja:
                causas.append(('BATERIA_BAJA', 'MODERADO'))
        if heartbeat.calidad_senal_rssi is not None and heartbeat.calidad_senal_rssi < params.rssi_degradado:
            causas.append(('SEÑAL_DEGRADADA', 'LEVE'))
        for causa, severidad in causas:
            if self.alerta_repo.buscar_tecnica_activa_dispositivo(heartbeat.id_dispositivo_iot, causa):
                continue
            self.alerta_repo.guardar(Alerta(
                id_alerta=None, tipo_alerta='TECNICA', severidad=severidad,
                estado_alerta='ACTIVA', origen_evento='HEARTBEAT', tipo_variable=causa,
                fecha_evento=heartbeat.fecha_registro, fecha_generacion=heartbeat.fecha_recepcion,
                id_dispositivo_ioit=heartbeat.id_dispositivo_iot,
                id_infraestructura=id_infraestructura,
            ))
            # El trigger de alertas registra el historial inicial; no se duplica.
