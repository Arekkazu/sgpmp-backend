from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import AuthenticationError
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.domain.entities.heartbeat import Heartbeat
from src.telemetry.domain.entities.historico_transicion_dispositivo import HistoricoTransicionDispositivo
from src.telemetry.domain.entities.periodo_inactividad import PeriodoInactividad
from src.telemetry.domain.repositories.alerta_repository import AlertaRepository
from src.telemetry.domain.repositories.dispositivo_port import DispositivoPort
from src.telemetry.domain.repositories.estado_dispositivo_iot_repository import EstadoDispositivoIoTRepository
from src.telemetry.domain.repositories.heartbeat_repository import HeartbeatRepository
from src.telemetry.domain.repositories.historico_transicion_dispositivo_repository import HistoricoTransicionDispositivoRepository
from src.telemetry.domain.repositories.historico_estado_alerta_repository import HistoricoEstadoAlertaRepository
from src.telemetry.domain.repositories.periodo_inactividad_repository import PeriodoInactividadRepository
from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO

# Umbrales de batería para alertas técnicas
_UMBRAL_BATERIA_BAJA = Decimal('30')
_UMBRAL_BATERIA_CRITICA = Decimal('10')
_UMBRAL_RSSI_DEGRADADO = Decimal('-100')


class RecibirHeartbeatUseCase:

    def __init__(
        self,
        db: Session,
        dispositivo_port: DispositivoPort,
        heartbeat_repo: HeartbeatRepository,
        estado_repo: EstadoDispositivoIoTRepository,
        transicion_repo: HistoricoTransicionDispositivoRepository,
        periodo_repo: PeriodoInactividadRepository,
        alerta_repo: AlertaRepository,
        historico_alerta_repo: HistoricoEstadoAlertaRepository,
    ) -> None:
        self.db = db
        self.dispositivo_port = dispositivo_port
        self.heartbeat_repo = heartbeat_repo
        self.estado_repo = estado_repo
        self.transicion_repo = transicion_repo
        self.periodo_repo = periodo_repo
        self.alerta_repo = alerta_repo
        self.historico_alerta_repo = historico_alerta_repo

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

            # Paso 3: Obtener o inicializar estado del dispositivo
            estado = self.estado_repo.obtener_por_dispositivo(device_id)
            if estado is None:
                estado = self.estado_repo.guardar(EstadoDispositivoIoT(
                    id_estado_dispositivo_iot=None,
                    id_dispositivo_iot=device_id,
                    estado_actual='ACTIVO',
                    fecha_ultimo_contacto=ahora,
                    id_ultimo_heartbeat=heartbeat.id_heartbeat,
                    tiempo_sin_contacto=0,
                    causa_primaria=None,
                    causas_secundarias=None,
                    fecha_ultima_actualizacion=ahora,
                    id_usuario=None,
                ))
            else:
                # Paso 4: Evaluar transición de estado
                tiempo_seg = int((ahora - estado.fecha_ultimo_contacto).total_seconds()) \
                    if estado.fecha_ultimo_contacto else 0
                nuevo_estado = estado.evaluar_transicion(
                    tiempo_sin_contacto_seg=0,  # heartbeat recibido → tiempo=0 → ACTIVO
                    estado_local_buffer=dto.estado_local_buffer,
                )
                estado_anterior = estado.estado_actual

                # Actualizar contacto
                estado.fecha_ultimo_contacto = ahora
                estado.id_ultimo_heartbeat = heartbeat.id_heartbeat
                estado.tiempo_sin_contacto = 0
                estado.fecha_ultima_actualizacion = ahora

                # Paso 5: Si buffer_local activo → verificar BUFFER_ACTIVO
                if dto.estado_local_buffer == 'A':
                    nuevo_estado = 'BUFFER_ACTIVO'
                else:
                    nuevo_estado = 'ACTIVO'

                if nuevo_estado != estado_anterior:
                    estado.aplicar_transicion(nuevo_estado, causa=None, ahora=ahora)
                    self.transicion_repo.registrar(HistoricoTransicionDispositivo(
                        id_transaccion=None,
                        id_dispositivo_iot=device_id,
                        estado_anterior=estado_anterior,
                        estado_nuevo=nuevo_estado,
                        causa_primaria=None,
                        causa_secundaria=None,
                        id_usuario_responsable=None,
                        notas='Transición por recepción de heartbeat.',
                        fecha_transicion=ahora,
                    ))

                    # Cerrar periodo de inactividad si vuelve a ACTIVO/BUFFER_ACTIVO
                    if nuevo_estado in ('ACTIVO', 'BUFFER_ACTIVO'):
                        periodo = self.periodo_repo.obtener_abierto_por_dispositivo(device_id)
                        if periodo is not None:
                            periodo.cerrar(ahora)
                            self.periodo_repo.cerrar(periodo)

                self.estado_repo.actualizar(estado)

            # Paso 6: Detectar condiciones anómalas y generar alertas técnicas
            self._generar_alertas_tecnicas(device_id, dispositivo.id_infraestructura, heartbeat, ahora)  # type: ignore[arg-type]

            self.db.commit()
            return heartbeat

        except Exception:
            self.db.rollback()
            raise

    def _generar_alertas_tecnicas(
        self,
        id_dispositivo: int,
        id_infraestructura: int,
        heartbeat: Heartbeat,
        ahora: datetime,
    ) -> None:
        causas = []

        if heartbeat.nivel_bateria_pct is not None:
            if heartbeat.nivel_bateria_pct <= _UMBRAL_BATERIA_CRITICA:
                causas.append(('BATERIA_CRITICA', 'CRITICA'))
            elif heartbeat.nivel_bateria_pct <= _UMBRAL_BATERIA_BAJA:
                causas.append(('BATERIA_BAJA', 'ALTA'))

        if heartbeat.calidad_senal_rssi is not None:
            if heartbeat.calidad_senal_rssi < _UMBRAL_RSSI_DEGRADADO:
                causas.append(('SEÑAL_DEGRADADA', 'MEDIA'))

        for causa, severidad in causas:
            alerta = Alerta(
                tipo_alerta='TECNICA',
                severidad=severidad,
                estado_alerta='ACTIVA',
                origen_evento='HEARTBEAT',
                tipo_variable=causa,
                fecha_evento=ahora,
                fecha_generacion=ahora,
                id_dispositivo_ioit=id_dispositivo,
                id_infraestructura=id_infraestructura,
            )
            alerta_guardada = self.alerta_repo.guardar(alerta)
            self.historico_alerta_repo.registrar(
                id_alerta=alerta_guardada.id_alerta,
                estado_anterior='',
                estado_nuevo='ACTIVA',
                motivo=f'Alerta técnica generada: {causa}',
            )
