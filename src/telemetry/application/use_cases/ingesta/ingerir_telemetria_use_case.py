"""RF-53 B+: HTTP adapta el sobre; la función SQL valida y persiste la fila."""
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.shared.errors import (
    AppError, AuthenticationError, BusinessRuleError, ConflictError,
    ServiceUnavailableError, ValidationError,
)
from src.telemetry.domain.entities.telemetria import CATALOGO_I3P1, ResultadoIngesta, ResultadoItemBatch
from src.telemetry.domain.repositories.ingesta_telemetria_port import IngestaTelemetriaPort
from src.telemetry.infrastructure.dto.ingerir_telemetria_dto import IngerirTelemetriaDTO, IngerirTelemetriaBatchDTO

# Compatibilidad del flujo de visión; la ingesta escalar usa la regla SQL.
_MAX_DRIFT_FUTURO_SEG = 30

_RECHAZOS = {
    'ERROR_ESTRUCTURA': (ValidationError, 'La lectura no cumple la estructura requerida.'),
    'ERROR_AUTENTICACION': (AuthenticationError, 'Dispositivo o sensor no encontrado o inactivo.'),
    'ERROR_TIEMPO': (ValidationError, 'La fecha de captura de la lectura no es válida.'),
    'ERROR_UNIDAD': (ValidationError, 'La unidad no corresponde a la variable indicada.'),
    'ERROR_SENSOR': (BusinessRuleError, 'El valor excede los límites físicos del sensor.'),
    'ERROR_DUPLICADO': (ConflictError, 'La lectura ya se encuentra registrada.'),
}
_ESTADOS_PERSISTIDOS = {'LECTURA_VALIDA', 'FUERA_DE_RANGO', 'ERROR_CALIBRACION'}


class IngerirTelemetriaUseCase:
    def __init__(self, db, ingesta_port: IngestaTelemetriaPort, dispositivo_port, bitacora_repo):
        self.db = db
        self.ingesta_port = ingesta_port
        self.dispositivo_port = dispositivo_port
        self.bitacora_repo = bitacora_repo

    def execute(self, dto: IngerirTelemetriaDTO, gateway_id: Optional[str] = None) -> ResultadoIngesta:
        try:
            # Se conserva la credencial HTTP hasta DEV-06. No se guarda en metadata/logs.
            identidad = self.dispositivo_port.validar_dispositivo_heartbeat(dto.device_id, dto.access_key)
            if identidad is None:
                self.bitacora_repo.registrar_error(
                    estado_calidad='ERROR_AUTENTICACION', descripcion='Credenciales HTTP del dispositivo inválidas.',
                    payload={'device_id': dto.device_id, 'sensor_id': dto.sensor_id},
                    timestamp_captura=dto.timestamp_captura, gateway_id=gateway_id,
                )
                self.db.commit()
                raise AuthenticationError('ERROR_AUTENTICACION', 'Credenciales del dispositivo inválidas.')
            entrada = CATALOGO_I3P1.get(dto.tipo_variable)
            # El catálogo traduce el nombre público a su identificador SQL. Las reglas
            # de unidad, rango, tiempo, duplicados y calibración quedan en la función.
            resultado = self.ingesta_port.ingerir({
                'device_id': dto.device_id, 'sensor_id': dto.sensor_id,
                'id_variable': entrada['id_variable'] if entrada else None,
                'categoria': entrada['categoria'].value if entrada else None,
                'valor': dto.valor, 'unidad': dto.unidad,
                'timestamp_captura': dto.timestamp_captura,
                'timestamp_envio': dto.timestamp_envio or dto.timestamp_captura,
                'origen': dto.origen, 'tipo_dato': 'AGREGADO' if dto.valor_agregado else 'CRUDO',
                'valor_agregado': dto.valor_agregado, 'ventana_agregacion': dto.ventana_agregacion,
                'latitud': dto.latitud, 'longitud': dto.longitud, 'nivel_bateria': dto.nivel_bateria,
                'calidad_senal_rssi': dto.calidad_senal_rssi, 'calidad_senal_snr': dto.calidad_senal_snr,
                'estado_conectividad': dto.estado_conectividad,
                'metadatos': {'gateway_id': gateway_id, 'checksum': dto.checksum,
                              'frecuencia_muestreo': dto.frecuencia_muestreo},
            })
            rechazo = None
            if resultado.id_telemetria is None:
                codigo = resultado.mensaje.partition(':')[0]
                if codigo not in _RECHAZOS:
                    raise ServiceUnavailableError('INGESTA_NO_CONFIRMADA', 'La ingesta no pudo confirmarse.')
                clase, mensaje = _RECHAZOS[codigo]
                rechazo = clase(codigo, mensaje)
            elif resultado.estado_calidad not in _ESTADOS_PERSISTIDOS or resultado.timestamp_procesamiento is None:
                raise ServiceUnavailableError('INGESTA_NO_CONFIRMADA', 'La ingesta no pudo confirmarse.')
            # Incluso el rechazo funcional debe confirmar la bitácora escrita por SQL.
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        if rechazo is not None:
            raise rechazo
        return ResultadoIngesta(
            id_telemetria=resultado.id_telemetria, estado_calidad=resultado.estado_calidad,
            timestamp_procesamiento=resultado.timestamp_procesamiento,
            latencia_procesamiento_ms=resultado.latencia_procesamiento_ms,
        )


class SincronizarBufferUseCase:
    """Orquesta la ingesta en lote para el Flujo C (sincronización de BUFFER_LOCAL)."""

    def __init__(self, ingerir_use_case_factory, db: Session) -> None:
        self._factory = ingerir_use_case_factory
        self.db = db

    def execute(
        self,
        dto: IngerirTelemetriaBatchDTO,
        gateway_id: Optional[str] = None,
    ) -> dict[str, Any]:
        total = len(dto.registros)
        aceptados = 0
        rechazados = 0
        duplicados = 0
        detalle: list[ResultadoItemBatch] = []

        # Ordenar cronológicamente (garantía FIFO del buffer)
        registros_ordenados = sorted(dto.registros, key=lambda r: r.timestamp_captura)

        for registro in registros_ordenados:
            use_case = self._factory()
            try:
                resultado = use_case.execute(registro, gateway_id)
                aceptados += 1
                detalle.append(ResultadoItemBatch(
                    sensor_id=registro.sensor_id,
                    timestamp_captura=registro.timestamp_captura,
                    estado=resultado.estado_calidad,
                    id_telemetria=resultado.id_telemetria,
                ))
            except ConflictError:
                duplicados += 1
                detalle.append(ResultadoItemBatch(
                    sensor_id=registro.sensor_id,
                    timestamp_captura=registro.timestamp_captura,
                    estado='ERROR_DUPLICADO',
                    error='Dato duplicado — marcado como CONFIRMADO en buffer',
                ))
            except AppError as exc:
                if exc.status_code >= 500:
                    raise
                rechazados += 1
                detalle.append(ResultadoItemBatch(
                    sensor_id=registro.sensor_id,
                    timestamp_captura=registro.timestamp_captura,
                    estado='RECHAZADO',
                    error=str(exc),
                ))

        return {
            'total': total,
            'aceptados': aceptados,
            'rechazados': rechazados,
            'duplicados': duplicados,
            'detalle': detalle,
        }
