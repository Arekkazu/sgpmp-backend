"""Evaluación del heartbeat confirmado, común a HTTP y MQTT (DEV-05).

Sin commits: las alertas y la evidencia RF-63 se confirman en la transacción de
la etapa. La indisponibilidad de temperatura/firmware no bloquea sensores.
"""
from src.shared.errors import ServiceUnavailableError
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.domain.repositories.diagnostico_heartbeat_port import DiagnosticoHeartbeatPort
from src.telemetry.infrastructure.dto.heartbeat_dto import DiagnosticoHeartbeatDTO


class EvaluarDiagnosticoHeartbeatUseCase:
    def __init__(self, alerta_repo, diagnostico_port: DiagnosticoHeartbeatPort | None = None):
        self.alerta_repo = alerta_repo
        self.diagnostico_port = diagnostico_port

    def sensores(self, heartbeat, id_infraestructura):
        if heartbeat.sensores_operativos is None:
            return
        # El broker escribe directo: también se valida la forma persistida.
        dto = DiagnosticoHeartbeatDTO(sensores_operativos=heartbeat.sensores_operativos)
        fallidos = sorted({s.sensor for s in dto.sensores_operativos if not s.operativo})
        if fallidos:
            self._registrar(heartbeat, id_infraestructura, 'SENSOR_FISICO_FALLIDO', 'MODERADO',
                            {'sensores_fallidos': fallidos}, sensores_fallidos=fallidos)

    def temperatura(self, heartbeat, id_infraestructura):
        if heartbeat.temperatura_dispositivo is None:
            return
        valor = DiagnosticoHeartbeatDTO(temperatura_dispositivo=heartbeat.temperatura_dispositivo).temperatura_dispositivo
        politica = self._politica('UMBRAL_SOBRECALENTAMIENTO_NO_DISPONIBLE')
        limites = politica.obtener_umbrales_temperatura(heartbeat.id_dispositivo_iot)
        if valor > limites.maximo_operativo:
            severidad = 'CRITICO' if limites.critico is not None and valor > limites.critico else 'MODERADO'
            self._registrar(heartbeat, id_infraestructura, 'SOBRECALENTAMIENTO', severidad,
                {'temperatura_dispositivo': str(valor), 'umbral_maximo_operativo': str(limites.maximo_operativo)})

    def firmware(self, heartbeat, id_infraestructura):
        if heartbeat.version_firmware is None:
            return
        politica = self._politica('POLITICA_FIRMWARE_NO_DISPONIBLE')
        comparacion = politica.comparar_firmware(heartbeat.id_dispositivo_iot, heartbeat.version_firmware)
        if comparacion.es_anterior:
            self._registrar(heartbeat, id_infraestructura, 'FIRMWARE_DESACTUALIZADO', 'LEVE',
                {'version_instalada': heartbeat.version_firmware, 'version_minima': comparacion.version_minima})

    def _politica(self, codigo):
        if self.diagnostico_port is None:
            raise ServiceUnavailableError(codigo, 'Falta la configuración autorizada M09/FW-06 para evaluar el diagnóstico del dispositivo.')
        return self.diagnostico_port

    def _registrar(self, heartbeat, infraestructura, causa, severidad, detalle, **filtro):
        existente = self.alerta_repo.buscar_tecnica_activa_dispositivo(heartbeat.id_dispositivo_iot, causa, **filtro)
        if existente:
            return
        self.alerta_repo.guardar(Alerta(
            tipo_alerta='TECNICA', severidad=severidad, estado_alerta='ACTIVA',
            origen_evento='HEARTBEAT', tipo_variable=causa,
            fecha_evento=heartbeat.fecha_registro, fecha_generacion=heartbeat.fecha_recepcion,
            id_dispositivo_ioit=heartbeat.id_dispositivo_iot, id_infraestructura=infraestructura,
            metadato_evento={'id_heartbeat': heartbeat.id_heartbeat, **detalle},
        ))
        # El trigger de alertas registra el historial inicial.
