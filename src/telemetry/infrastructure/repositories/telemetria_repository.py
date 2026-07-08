from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.telemetria import Telemetria
from src.telemetry.domain.repositories.telemetria_repository import TelemetriaRepository
from src.telemetry.infrastructure.models.telemetria_model import TelemetriaModel


class SqlAlchemyTelemetriaRepository(TelemetriaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def guardar(self, entidad: Telemetria) -> Telemetria:
        try:
            orm = TelemetriaModel(
                id_sensor=entidad.id_sensor,
                id_variable=entidad.id_variable,
                id_dispositivo_iot=entidad.id_dispositivo_iot,
                valor_crudo=entidad.valor_crudo,
                valor_ajustado=entidad.valor_ajustado,
                timestamp_captura=entidad.timestamp_captura,
                timestamp_envio=entidad.timestamp_envio,
                timestamp_procesamiento=entidad.timestamp_procesamiento,
                origen=entidad.origen,
                estado_calidad=entidad.estado_calidad,
                calibrado=entidad.calibrado,
                latitud=entidad.latitud,
                longitud=entidad.longitud,
                metadatos=entidad.metadatos,
                categoria_variable=entidad.categoria_variable,
                unidad_medida=entidad.unidad_medida,
                version_calibracion=entidad.version_calibracion,
                parametros_calibracion=entidad.parametros_calibracion,
                valor_agregado=entidad.valor_agregado,
                ventana_agregacion_min=entidad.ventana_agregacion_min,
                tipo_dato=entidad.tipo_dato,
                latencia_alta=entidad.latencia_alta,
                frecuencia_anomala=entidad.frecuencia_anomala,
                posible_drift=entidad.posible_drift,
                dato_buferizado=entidad.dato_buferizado,
                dato_agredado_edge=entidad.dato_agregado_edge,
                reloj_desincronizado=entidad.reloj_desincronizado,
                latencia_procesamiento_ms=entidad.latencia_procesamiento_ms,
                nivel_bateria_pct=entidad.nivel_bateria_pct,
                calidad_senal_rssi=entidad.calidad_senal_rssi,
                calidad_senal_snr=entidad.calidad_senal_snr,
                frecuencia_muestreo_min=entidad.frecuencia_muestreo_min,
                estado_conectividad=entidad.estado_conectividad,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc, {
                'uq_telemetria_sensor_variable_captura_origen': (
                    'Ya existe un registro para este sensor, variable y timestamp.'
                ),
            })

    def existe_duplicado(
        self,
        id_sensor: int,
        id_variable: int,
        timestamp_captura: datetime,
        origen: str,
        ventana_agregacion_min: Optional[int] = None,
    ) -> bool:
        if origen == 'EDGE_AGREGADO' and ventana_agregacion_min is not None:
            result = self.db.execute(
                text(
                    'SELECT 1 FROM modulo3.telemetrias '
                    'WHERE id_sensor = :sensor AND id_variable = :variable '
                    '  AND timestamp_captura = :ts AND origen = :origen '
                    '  AND ventana_agregacion_min = :ventana '
                    'LIMIT 1'
                ),
                {
                    'sensor': id_sensor,
                    'variable': id_variable,
                    'ts': timestamp_captura,
                    'origen': origen,
                    'ventana': ventana_agregacion_min,
                },
            ).fetchone()
        else:
            result = self.db.execute(
                text(
                    'SELECT 1 FROM modulo3.telemetrias '
                    'WHERE id_sensor = :sensor AND id_variable = :variable '
                    '  AND timestamp_captura = :ts AND origen = :origen '
                    'LIMIT 1'
                ),
                {
                    'sensor': id_sensor,
                    'variable': id_variable,
                    'ts': timestamp_captura,
                    'origen': origen,
                },
            ).fetchone()
        return result is not None

    def obtener_serie_temporal(
        self,
        id_sensor: int,
        n: int,
        hasta_timestamp: datetime,
    ) -> list[Decimal]:
        rows = self.db.execute(
            text(
                'SELECT valor_crudo FROM modulo3.telemetrias '
                'WHERE id_sensor = :sensor '
                '  AND estado_calidad = :estado '
                '  AND timestamp_captura < :ts '
                'ORDER BY timestamp_captura DESC LIMIT :n'
            ),
            {'sensor': id_sensor, 'estado': 'LECTURA_VALIDA', 'ts': hasta_timestamp, 'n': n},
        ).fetchall()
        return [Decimal(str(r[0])) for r in rows]

    def actualizar_flags_aptitud(
        self,
        id_telemetria: int,
        apto_para_ia: bool,
        apto_para_nic41: bool,
    ) -> None:
        self.db.execute(
            text(
                'UPDATE modulo3.telemetrias '
                'SET apto_para_ia = :ia, apto_para_nic41 = :nic41 '
                'WHERE id_telemetria = :id'
            ),
            {'ia': apto_para_ia, 'nic41': apto_para_nic41, 'id': id_telemetria},
        )

    @staticmethod
    def _a_entidad(orm: TelemetriaModel) -> Telemetria:
        return Telemetria(
            id_telemetria=orm.id_telemetria,
            id_sensor=orm.id_sensor,
            id_variable=orm.id_variable,
            id_dispositivo_iot=orm.id_dispositivo_iot,
            valor_crudo=orm.valor_crudo,
            valor_ajustado=orm.valor_ajustado,
            timestamp_captura=orm.timestamp_captura,
            timestamp_envio=orm.timestamp_envio,
            timestamp_procesamiento=orm.timestamp_procesamiento,
            origen=orm.origen,
            estado_calidad=orm.estado_calidad,
            calibrado=orm.calibrado,
            latitud=orm.latitud,
            longitud=orm.longitud,
            metadatos=orm.metadatos or {},
            categoria_variable=orm.categoria_variable,
            unidad_medida=orm.unidad_medida,
            version_calibracion=orm.version_calibracion,
            parametros_calibracion=orm.parametros_calibracion,
            valor_agregado=orm.valor_agregado,
            ventana_agregacion_min=orm.ventana_agregacion_min,
            tipo_dato=orm.tipo_dato,
            latencia_alta=orm.latencia_alta,
            frecuencia_anomala=orm.frecuencia_anomala,
            posible_drift=orm.posible_drift,
            dato_buferizado=orm.dato_buferizado,
            dato_agregado_edge=orm.dato_agredado_edge,
            reloj_desincronizado=orm.reloj_desincronizado,
            latencia_procesamiento_ms=orm.latencia_procesamiento_ms,
            nivel_bateria_pct=orm.nivel_bateria_pct,
            calidad_senal_rssi=orm.calidad_senal_rssi,
            calidad_senal_snr=orm.calidad_senal_snr,
            frecuencia_muestreo_min=orm.frecuencia_muestreo_min,
            estado_conectividad=orm.estado_conectividad,
            apto_para_ia=orm.apto_para_ia,
            apto_para_nic41=orm.apto_para_nic41,
        )
