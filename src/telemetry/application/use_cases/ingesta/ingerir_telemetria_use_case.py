from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.shared.errors import AuthenticationError, BusinessRuleError, ConflictError, ValidationError
from src.telemetry.domain.entities.telemetria import (
    CATALOGO_I3P1,
    EstadoCalidadBitacora,
    EstadoCalidadTelemetria,
    ReglaVariableI3P1,
    ResultadoIngesta,
    ResultadoItemBatch,
    Telemetria,
)
from src.telemetry.domain.repositories.bitacora_ingest_repository import BitacoraIngestRepository
from src.telemetry.domain.repositories.calibracion_port import CalibracionPort
from src.telemetry.domain.repositories.dispositivo_port import DispositivoPort
from src.telemetry.domain.repositories.telemetria_repository import TelemetriaRepository
from src.telemetry.domain.repositories.variable_catalogo_port import VariableCatalogoPort
from src.telemetry.infrastructure.adapters.variable_catalogo_m09_adapter import VariableCatalogoM09Adapter
from src.telemetry.infrastructure.dto.ingerir_telemetria_dto import IngerirTelemetriaDTO, IngerirTelemetriaBatchDTO

# Tolerancia máxima de timestamp futuro (leve desfase NTP, en segundos)
_MAX_DRIFT_FUTURO_SEG = 30
# Ventana máxima para datos de BUFFER_LOCAL (72 horas)
_MAX_VENTANA_BUFFER_HORAS = 72
# Umbral de latencia alta (30 segundos)
_UMBRAL_LATENCIA_ALTA_MS = 30_000


class IngerirTelemetriaUseCase:

    def __init__(
        self,
        db: Session,
        repo: TelemetriaRepository,
        bitacora_repo: BitacoraIngestRepository,
        dispositivo_port: DispositivoPort,
        variable_port: VariableCatalogoPort,
        calibracion_port: CalibracionPort,
    ) -> None:
        self.db = db
        self.repo = repo
        self.bitacora_repo = bitacora_repo
        self.dispositivo_port = dispositivo_port
        self.variable_port = variable_port
        self.calibracion_port = calibracion_port

    def execute(
        self,
        dto: IngerirTelemetriaDTO,
        gateway_id: Optional[str] = None,
    ) -> ResultadoIngesta:
        ahora = datetime.now(timezone.utc)
        timestamp_procesamiento = ahora
        payload_bitacora = self._dto_a_dict(dto)

        try:
            # --- Fase 1: Coherencia temporal ---
            self._validar_timestamp(dto, ahora)

            # --- Fase 2: Identidad del dispositivo (M09) ---
            dispositivo = self.dispositivo_port.obtener_dispositivo_activo(
                dto.device_id, dto.sensor_id, dto.access_key
            )
            if dispositivo is None:
                raise AuthenticationError(
                    code='ERROR_AUTENTICACION',
                    message='Dispositivo o sensor no encontrado, inactivo, o credenciales inválidas.',
                )
            if not dispositivo.es_activo_dispositivo or not dispositivo.es_activo_sensor:
                raise AuthenticationError(
                    code='ERROR_AUTENTICACION',
                    message='El dispositivo o sensor no está en estado ACTIVO.',
                )

            # --- Fase 3: Variable y unidad vs catálogo I3P-1 ---
            try:
                regla = self.variable_port.obtener_regla(dto.tipo_variable, dto.unidad)
            except ValueError as exc:
                raise ValidationError(
                    code='ERROR_UNIDAD',
                    message=str(exc),
                    field='unidad',
                )

            if regla is None:
                raise ValidationError(
                    code='ERROR_UNIDAD',
                    message=f"tipo_variable '{dto.tipo_variable}' no existe en el catálogo I3P-1.",
                    field='tipo_variable',
                )

            # Convertir unidad si es necesario
            valor_a_evaluar = dto.valor
            unidad_efectiva = dto.unidad
            if dto.unidad != regla.unidad_estandar and dto.unidad in [
                origen for origen, _ in [k for k in VariableCatalogoM09Adapter.__dict__ if False]
            ]:
                pass  # La conversión se hace en el adapter; usamos el valor ya convertido
            if dto.unidad != regla.unidad_estandar:
                from src.telemetry.infrastructure.adapters.variable_catalogo_m09_adapter import (
                    VariableCatalogoM09Adapter as Adapter,
                )
                valor_a_evaluar = Adapter.convertir_valor(dto.valor, dto.unidad, regla.unidad_estandar)
                unidad_efectiva = regla.unidad_estandar

            # --- Fase 4: Rango biológico ---
            estado_calidad_rango = self._evaluar_rango(valor_a_evaluar, regla)
            # ERROR_SENSOR rechaza sin persistir
            if estado_calidad_rango == EstadoCalidadBitacora.ERROR_SENSOR.value:
                raise BusinessRuleError(
                    code='ERROR_SENSOR',
                    message=(
                        f"Valor {valor_a_evaluar} para {dto.tipo_variable} es físicamente imposible. "
                        "Revise el hardware del sensor."
                    ),
                )

            # --- Fase 5: Detección de duplicados ---
            ventana = dto.ventana_agregacion if dto.origen == 'EDGE_AGREGADO' else None
            if self.repo.existe_duplicado(
                id_sensor=dto.sensor_id,
                id_variable=regla.id_variable,
                timestamp_captura=dto.timestamp_captura,
                origen=dto.origen,
                ventana_agregacion_min=ventana,
            ):
                raise ConflictError(
                    code='ERROR_DUPLICADO',
                    message='Ya existe un registro con la misma clave (sensor, variable, timestamp, origen).',
                )

            # --- Fase 6: Calibración ---
            params_cal = self.calibracion_port.obtener_parametros(
                dto.sensor_id, dispositivo.id_dispositivo_iot
            )
            if params_cal is not None:
                valor_ajustado = (valor_a_evaluar * params_cal.ganancia) + params_cal.offset
                calibrado = True
                version_cal = params_cal.version
                estado_calidad_final = estado_calidad_rango or EstadoCalidadTelemetria.LECTURA_VALIDA.value
            else:
                valor_ajustado = None
                calibrado = False
                version_cal = None
                # Si estaba FUERA_DE_RANGO mantiene ese estado; si no, pasa a ERROR_CALIBRACION
                estado_calidad_final = estado_calidad_rango or EstadoCalidadTelemetria.ERROR_CALIBRACION.value

            # --- Flags de metadata ---
            latencia_ms = self._calcular_latencia_ms(dto.timestamp_envio, timestamp_procesamiento)
            latencia_alta = latencia_ms is not None and latencia_ms > _UMBRAL_LATENCIA_ALTA_MS
            frecuencia_anomala = self._detectar_frecuencia_anomala(dto)
            dato_buferizado = dto.origen == 'BUFFER_LOCAL'
            dato_agregado_edge = dto.valor_agregado and dto.origen == 'EDGE_AGREGADO'

            tipo_dato = 'CRUDO'
            if dto.valor_agregado:
                tipo_dato = 'AGREGADO'

            # --- Construir entidad ---
            entidad = Telemetria(
                id_sensor=dto.sensor_id,
                id_variable=regla.id_variable,
                id_dispositivo_iot=dispositivo.id_dispositivo_iot,
                valor_crudo=dto.valor,
                valor_ajustado=valor_ajustado,
                timestamp_captura=dto.timestamp_captura,
                timestamp_envio=dto.timestamp_envio,
                timestamp_procesamiento=timestamp_procesamiento,
                origen=dto.origen,
                estado_calidad=estado_calidad_final,
                calibrado=calibrado,
                latitud=dto.latitud,
                longitud=dto.longitud,
                categoria_variable=regla.categoria,
                unidad_medida=unidad_efectiva,
                version_calibracion=version_cal,
                parametros_calibracion=(
                    {'ganancia': str(params_cal.ganancia), 'offset': str(params_cal.offset)}
                    if params_cal else None
                ),
                valor_agregado=dto.valor_agregado,
                ventana_agregacion_min=dto.ventana_agregacion,
                tipo_dato=tipo_dato,
                latencia_alta=latencia_alta,
                frecuencia_anomala=frecuencia_anomala,
                dato_buferizado=dato_buferizado,
                dato_agregado_edge=dato_agregado_edge,
                latencia_procesamiento_ms=latencia_ms,
                nivel_bateria_pct=dto.nivel_bateria,
                calidad_senal_rssi=dto.calidad_senal_rssi,
                calidad_senal_snr=dto.calidad_senal_snr,
                frecuencia_muestreo_min=dto.frecuencia_muestreo,
                estado_conectividad=dto.estado_conectividad,
                metadatos={
                    'checksum': dto.checksum,
                    'latencia_ms': latencia_ms,
                    'latencia_alta': latencia_alta,
                    'frecuencia_anomala': frecuencia_anomala,
                    'dato_agregado_edge': dato_agregado_edge,
                    'dato_buferizado': dato_buferizado,
                    'calibrado': calibrado,
                },
            )

            # --- Fase 8: Persistencia ---
            entidad = self.repo.guardar(entidad)

            # --- Bitácora de éxito ---
            self.bitacora_repo.registrar_exito(
                id_telemetria=entidad.id_telemetria,
                id_sensor=dto.sensor_id,
                id_dispositivo_iot=dispositivo.id_dispositivo_iot,
                estado_calidad=estado_calidad_final,
                timestamp_captura=dto.timestamp_captura,
                gateway_id=gateway_id,
            )

            self.db.commit()

            return ResultadoIngesta(
                id_telemetria=entidad.id_telemetria,
                estado_calidad=estado_calidad_final,
                timestamp_procesamiento=timestamp_procesamiento,
                latencia_procesamiento_ms=latencia_ms,
            )

        except (AuthenticationError, ValidationError, BusinessRuleError, ConflictError) as exc:
            self.db.rollback()
            estado_error = self._codigo_a_estado_bitacora(getattr(exc, 'code', None))
            self._registrar_bitacora_error(
                exc=exc,
                estado_calidad=estado_error,
                dto=dto,
                payload=payload_bitacora,
                gateway_id=gateway_id,
            )
            raise
        except Exception:
            self.db.rollback()
            raise

    def _registrar_bitacora_error(
        self,
        exc: Optional[Exception],
        estado_calidad: str,
        dto: IngerirTelemetriaDTO,
        payload: dict,
        gateway_id: Optional[str],
    ) -> None:
        try:
            self.bitacora_repo.registrar_error(
                estado_calidad=estado_calidad,
                descripcion=str(exc) if exc else estado_calidad,
                payload=payload,
                id_sensor=dto.sensor_id if dto else None,
                id_dispositivo_iot=dto.device_id if dto else None,
                timestamp_captura=dto.timestamp_captura if dto else None,
                gateway_id=gateway_id,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()

    def _validar_timestamp(self, dto: IngerirTelemetriaDTO, ahora: datetime) -> None:
        ts = dto.timestamp_captura
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        # Timestamp futuro (más allá del drift tolerado)
        limite_futuro = ahora + timedelta(seconds=_MAX_DRIFT_FUTURO_SEG)
        if ts > limite_futuro:
            raise ValidationError(
                code='ERROR_TIEMPO',
                message='El timestamp_captura es posterior a la hora del servidor.',
                field='timestamp_captura',
            )

        # Buffer local: máximo 72 horas de retraso
        if dto.origen == 'BUFFER_LOCAL':
            limite_pasado = ahora - timedelta(hours=_MAX_VENTANA_BUFFER_HORAS)
            if ts < limite_pasado:
                raise ValidationError(
                    code='ERROR_TIEMPO',
                    message=(
                        f'Dato de BUFFER_LOCAL con retraso superior a {_MAX_VENTANA_BUFFER_HORAS} horas. '
                        'No se puede procesar.'
                    ),
                    field='timestamp_captura',
                )

    def _evaluar_rango(self, valor: Decimal, regla: ReglaVariableI3P1) -> Optional[str]:
        if valor < regla.valor_fisico_min or valor > regla.valor_fisico_max:
            # Determinar si es físicamente imposible (fuera del rango físico absoluto)
            # Los rangos en la tabla son los físicamente posibles, así que cualquier valor
            # fuera de ellos se clasifica como ERROR_SENSOR
            return EstadoCalidadBitacora.ERROR_SENSOR.value

        # TODO: Cuando M09 exponga rangos biológicos (distintos a físicos), implementar
        # la lógica de FUERA_DE_RANGO vs LECTURA_VALIDA aquí.
        # Por ahora: si está dentro del rango físico, se marca como LECTURA_VALIDA (o ERROR_CALIBRACION)
        return None  # sin estado de rango especial → continúa flujo normal

    def _calcular_latencia_ms(
        self,
        timestamp_envio: Optional[datetime],
        timestamp_procesamiento: datetime,
    ) -> Optional[int]:
        if timestamp_envio is None:
            return None
        ts_e = timestamp_envio
        if ts_e.tzinfo is None:
            ts_e = ts_e.replace(tzinfo=timezone.utc)
        diff = timestamp_procesamiento - ts_e
        return max(0, int(diff.total_seconds() * 1000))

    def _detectar_frecuencia_anomala(self, dto: IngerirTelemetriaDTO) -> bool:
        # Si el DTO no incluye frecuencia_muestreo no podemos detectar anomalía
        return False

    @staticmethod
    def _dto_a_dict(dto: IngerirTelemetriaDTO) -> dict:
        return {
            'device_id': dto.device_id,
            'sensor_id': dto.sensor_id,
            'tipo_variable': dto.tipo_variable,
            'valor': str(dto.valor),
            'unidad': dto.unidad,
            'timestamp_captura': dto.timestamp_captura.isoformat() if dto.timestamp_captura else None,
            'origen': dto.origen,
        }

    @staticmethod
    def _extraer_estado_calidad_error() -> str:
        return EstadoCalidadBitacora.ERROR_ESTRUCTURA.value

    @staticmethod
    def _codigo_a_estado_bitacora(code: Optional[str]) -> str:
        mapping = {
            'ERROR_AUTENTICACION': EstadoCalidadBitacora.ERROR_AUTENTICACION.value,
            'ERROR_UNIDAD': EstadoCalidadBitacora.ERROR_UNIDAD.value,
            'ERROR_TIEMPO': EstadoCalidadBitacora.ERROR_TIEMPO.value,
            'ERROR_SENSOR': EstadoCalidadBitacora.ERROR_SENSOR.value,
            'ERROR_DUPLICADO': EstadoCalidadBitacora.ERROR_DUPLICADO.value,
        }
        return mapping.get(code or '', EstadoCalidadBitacora.ERROR_ESTRUCTURA.value)


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
            except Exception as exc:
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
