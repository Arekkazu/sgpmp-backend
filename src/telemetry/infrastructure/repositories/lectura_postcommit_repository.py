# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-41 RF-53/57: contexto de alerta desde M09     |
# | 2026-10-21 | Leandro | DEV-43 RF-62: integra calidad temporal y alertas tecnicas |
# | 2026-10-22 | Leandro | DEV-44 RF-61: excluye vinculaciones SUPERADA del consumo vigente |
"""Consultas derivadas: nunca se leen los flags obsoletos de telemetrias."""
from sqlalchemy import select, text

from src.telemetry.domain.entities.telemetria import Telemetria
from src.telemetry.infrastructure.models.telemetria_model import TelemetriaModel
from src.telemetry.infrastructure.repositories.telemetria_repository import SqlAlchemyTelemetriaRepository
from src.telemetry.infrastructure.adapters.variable_alerta_m09_adapter import variable_para_alerta


class SqlAlchemyLecturaPostcommitRepository(SqlAlchemyTelemetriaRepository):
    def contexto_alerta(self, lectura):
        variable = variable_para_alerta(self.db, id_variable=lectura.id_variable)
        dispositivo = self.db.execute(text('''SELECT d.serial,d.id_infraestructura,i.id_finca
            FROM modulo9.dispositivos_iot d JOIN modulo9.infraestructuras i
              ON i.id_infraestructura=d.id_infraestructura WHERE d.id_dispositivo_iot=:id'''),
            {'id': lectura.id_dispositivo_iot}).mappings().one()
        return {'variable': variable, **dict(dispositivo)}

    def obtener_por_id(self, id_telemetria):
        columnas = [c for c in TelemetriaModel.__table__.c
                    if c.name not in ('apto_para_ia', 'apto_para_nic41')]
        fila = self.db.execute(select(*columnas).where(
            TelemetriaModel.id_telemetria == id_telemetria)).mappings().first()
        if fila is None:
            return None
        datos = dict(fila)
        datos['dato_agregado_edge'] = datos.pop('dato_agredado_edge')
        return Telemetria(**datos)

    def vinculacion(self, identificador):
        return self.db.execute(text("""SELECT id_vinculacion_lectura, id_activo_biologico
            FROM modulo3.vinculaciones_lecturas WHERE id_telemetria=:id
              AND fecha_fin_vinculacion IS NULL
              AND estado_vinculacion<>'SUPERADA'
            ORDER BY fecha_creacion DESC, id_vinculacion_lectura DESC LIMIT 1
        """), {'id': identificador}).mappings().first()

    def vinculacion_historica(self, identificador):
        """Contexto de una lectura ya capturada, sin declarar vigente un periodo cerrado."""
        return self.db.execute(text("""SELECT id_vinculacion_lectura, id_activo_biologico
            FROM modulo3.vinculaciones_lecturas WHERE id_telemetria=:id
            ORDER BY fecha_creacion DESC, id_vinculacion_lectura DESC LIMIT 1
        """), {'id': identificador}).mappings().first()

    def evaluacion_omitida(self, identificador):
        return self.db.execute(text("""SELECT EXISTS(SELECT 1 FROM modulo3.bitacora_auditoria_iot
            WHERE componente_origen='RF62' AND entidad_afectada_tipo='CALIDAD_DATO'
              AND entidad_afectada_id=:id AND tipo_evento='EVALUACION_OMITIDA_POR_INACTIVIDAD')"""),
            {'id':str(identificador)}).scalar_one()

    def evaluacion_vigente(self, identificador):
        return self.db.execute(text("""SELECT q.id_evaluacion, q.apto_para_ia, q.apto_para_nic41
            FROM modulo3.telemetria_calidad q
            WHERE q.id_telemetria=:id AND q.estado_evaluacion='VIGENTE'
              AND NOT EXISTS (SELECT 1 FROM modulo3.telemetria_calidad posterior
                WHERE posterior.id_telemetria=q.id_telemetria
                  AND posterior.id_evaluacion_superada=q.id_evaluacion)
            ORDER BY q.timestamp_evaluacion DESC, q.fecha_creacion DESC, q.id_evaluacion DESC LIMIT 1
        """), {'id': identificador}).mappings().first()

    def infraestructura(self, dispositivo):
        return self.db.execute(text('SELECT id_infraestructura FROM modulo9.dispositivos_iot WHERE id_dispositivo_iot=:id'),
                               {'id': dispositivo}).scalar_one()

    def ultima_lectura_valida(self, sensor):
        identificador = self.db.execute(text("""SELECT id_telemetria FROM modulo3.telemetrias
            WHERE id_sensor=:id AND estado_calidad='LECTURA_VALIDA'
            ORDER BY timestamp_captura DESC, id_telemetria DESC LIMIT 1
        """), {'id': sensor}).scalar_one_or_none()
        return self.obtener_por_id(identificador) if identificador else None

    def restaurar_cache(self, lectura):
        # El trigger vigente sobrescribe el cache aun con lecturas tardías. Se
        # reconstruye desde la mayor captura sin alterar la fila RF-53 original.
        self.db.execute(text("""UPDATE modulo3.estados_actuales_sensores SET
            ultimo_valor=:valor, ultima_unidad=:unidad, ultimo_timestamp_captura=:captura,
            estado_calidad=CAST(:calidad AS modulo3.enum_telemetria_estado_calidad),
            ultimo_timestamp_actualizacion=now(),
            estado_conectividad=COALESCE(
                (SELECT CASE WHEN d.estado_actual IN ('SIN_SEÑAL','INACTIVO','EN_MANTENIMIENTO')
                    THEN d.estado_actual END FROM modulo3.estados_dispositivos_iot d
                 WHERE d.id_dispositivo_iot=:dispositivo),
                CASE WHEN :conectividad=false THEN 'SIN_SEÑAL'::modulo3.enum_estado_dispositivo
                     ELSE 'ACTIVO'::modulo3.enum_estado_dispositivo END),
            dato_desactualizado=COALESCE((SELECT d.estado_actual IN ('SIN_SEÑAL','INACTIVO')
                FROM modulo3.estados_dispositivos_iot d WHERE d.id_dispositivo_iot=:dispositivo),false)
            WHERE id_sensor=:sensor AND ultimo_timestamp_captura <= :captura
        """), {'valor': lectura.valor_ajustado, 'unidad': lectura.unidad_medida,
               'captura': lectura.timestamp_captura, 'calidad': lectura.estado_calidad, 'sensor': lectura.id_sensor,
               'dispositivo': lectura.id_dispositivo_iot, 'conectividad': lectura.estado_conectividad})

    def aplicar_prioridades(self, lectura, color):
        self.db.execute(text("""UPDATE modulo3.estados_actuales_sensores eas
            SET estado_semaforo=CASE
              WHEN eas.dato_desactualizado OR eas.estado_conectividad IN ('SIN_SEÑAL','INACTIVO','EN_MANTENIMIENTO')
                OR EXISTS (SELECT 1 FROM modulo3.estados_dispositivos_iot d
                  WHERE d.id_dispositivo_iot=eas.id_dispositivo_iot
                    AND d.estado_actual IN ('SIN_SEÑAL','INACTIVO','EN_MANTENIMIENTO')) THEN 'GRIS'
              WHEN EXISTS (SELECT 1 FROM modulo3.alertas a WHERE a.id_sensor=eas.id_sensor
                  AND a.estado_alerta IN ('ACTIVA','EN_ATENCION') AND a.severidad='CRITICO') THEN 'ROJO'
              WHEN :color='VERDE' AND EXISTS (SELECT 1 FROM modulo3.alertas a
                  WHERE a.id_sensor=eas.id_sensor AND a.estado_alerta IN ('ACTIVA','EN_ATENCION')) THEN 'AMARILLO'
              ELSE :color END
            WHERE eas.id_sensor=:sensor AND eas.ultimo_timestamp_captura=:captura
        """), {'color': color or 'GRIS', 'sensor': lectura.id_sensor, 'captura': lectura.timestamp_captura})
