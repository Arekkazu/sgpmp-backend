# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-43 RF-62: consulta serie temporal y contexto RF-60 |
# | 2026-10-31 | Claude | INC-M03-243-G169 RF-62: serie sin calibración y huella de límites físicos aplicados |
# | 2026-10-31 | Claude | INC-M03-236-G16 RF-62: deriva contra el valor de referencia de la calibración vigente |
"""Consultas reales sin reconstruir inactividad ni inventar versiones M09."""
import hashlib
from decimal import Decimal

from sqlalchemy import text

from src.shared.errors import ServiceUnavailableError
from src.telemetry.domain.repositories.contexto_calidad_port import (
    ContextoCalidad, ContextoCalidadPort, IntervaloInactividad,
    LecturaCalidad, LimitesFisicosCalidad,
)


class ContextoCalidadM09RF60Adapter(ContextoCalidadPort):
    def __init__(self, db):
        self.db = db

    def bloquear_evaluacion(self, id_telemetria):
        self.db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:clave,0))"),
                        {'clave': f'rf62:evaluacion:{id_telemetria}'})

    def omision_registrada(self, id_telemetria):
        return self.db.execute(text("""SELECT EXISTS(SELECT 1 FROM modulo3.bitacora_auditoria_iot
            WHERE tipo_evento='EVALUACION_OMITIDA_POR_INACTIVIDAD' AND componente_origen='RF62'
              AND entidad_afectada_tipo='CALIDAD_DATO' AND entidad_afectada_id=:id)"""),
            {'id':str(id_telemetria)}).scalar_one()

    def referencia_calibracion(self, id_sensor, captura):
        fila = self.db.execute(text('''SELECT valor_referencia FROM modulo9.calibraciones
            WHERE id_sensor=:sensor AND fecha_calibracion<=:captura
            ORDER BY fecha_calibracion DESC, id_calibracion DESC LIMIT 1'''),
            {'sensor': id_sensor, 'captura': captura}).one_or_none()
        return None if fila is None or fila[0] is None else Decimal(str(fila[0]))

    def limites_fisicos(self, id_variable):
        """G169 (#885, RF-62 R7/R9): M09 no versiona los límites físicos, así que la
        versión es la huella de lo aplicado: variable + mínimo + máximo. Mismo valor ⇒
        misma versión; cualquier cambio en M09 da otra, y la evaluación se puede
        reproducir con lo que dice su ``version_limites_fisicos_aplicada``."""
        limites = self.db.execute(text('''SELECT valor_fisico_min,valor_fisico_max
            FROM modulo9.variables_ambientales WHERE id_variable_ambiental=:id AND es_activo'''),
            {'id':id_variable}).one_or_none()
        if limites is None or limites[0] is None or limites[1] is None:
            return None
        minimo, maximo = Decimal(str(limites[0])), Decimal(str(limites[1]))
        huella = hashlib.sha256(f'{id_variable}|{minimo.normalize()}|{maximo.normalize()}'.encode()).hexdigest()[:16]
        return LimitesFisicosCalidad(minimo, maximo, f'va{id_variable}:{huella}', 'modulo9.variables_ambientales')

    def obtener(self, id_telemetria, id_sensor, id_variable, captura, n, *, incluir_sin_calibracion=False):
        # G169 (R7): con la lectura en ERROR_CALIBRACION se usan también las lecturas
        # sin calibración (valor crudo) para congelado, outlier y gap.
        estados = ['LECTURA_VALIDA', 'ERROR_CALIBRACION'] if incluir_sin_calibracion else ['LECTURA_VALIDA']
        fuente = self.db.execute(text('''SELECT id_dispositivo_iot,frecuencia_muestreo_min
            FROM modulo3.telemetrias WHERE id_telemetria=:id AND id_sensor=:sensor
              AND id_variable=:variable AND timestamp_captura=:captura'''),
            dict(id=id_telemetria, sensor=id_sensor, variable=id_variable, captura=captura)).mappings().one()
        filas = self.db.execute(text('''SELECT id_telemetria,timestamp_captura,valor_crudo,
                frecuencia_muestreo_min FROM modulo3.telemetrias
            WHERE id_sensor=:sensor AND id_variable=:variable
              AND timestamp_captura < :captura AND estado_calidad::text = ANY(:estados)
            ORDER BY timestamp_captura DESC,id_telemetria DESC LIMIT :n'''),
            dict(sensor=id_sensor, variable=id_variable, captura=captura, n=n, estados=estados)).mappings().all()
        lecturas = tuple(LecturaCalidad(r['id_telemetria'],r['timestamp_captura'],
                        Decimal(str(r['valor_crudo'])),r['frecuencia_muestreo_min']) for r in filas)
        inicio = min([captura] + [l.timestamp_captura for l in lecturas])
        periodos = self.db.execute(text('''SELECT fecha_inicio,fecha_fin FROM modulo3.periodos_inactividad
            WHERE id_dispositivo_iot=:dispositivo
              AND estado_durante_periodo IN ('SIN_SEÑAL','INACTIVO')
              AND (cardinality(sensores_afectados)=0 OR :sensor=ANY(sensores_afectados))
              AND (fecha_inicio IS NULL OR fecha_inicio<=:fin)
              AND (fecha_fin IS NULL OR fecha_fin>=:inicio)'''),
            dict(dispositivo=fuente['id_dispositivo_iot'],sensor=id_sensor,inicio=inicio,fin=captura)).all()
        if any(p[0] is None for p in periodos):
            raise ServiceUnavailableError('HISTORIAL_INACTIVIDAD_INCOMPLETO',
                                          'RF-60 contiene periodos sin inicio verificable.')
        snapshot = self.limites_fisicos(id_variable)
        # Recuperar N válidas DESPUÉS de excluir inactividad, no descartar
        # muestras y declarar insuficiencia si hay antecedentes activos.
        activas = self.db.execute(text('''SELECT t.id_telemetria,t.timestamp_captura,
                t.valor_crudo,t.frecuencia_muestreo_min FROM modulo3.telemetrias t
            WHERE t.id_sensor=:sensor AND t.id_variable=:variable
              AND t.timestamp_captura<:captura AND t.estado_calidad::text = ANY(:estados)
              AND NOT EXISTS(SELECT 1 FROM modulo3.periodos_inactividad p
                WHERE p.id_dispositivo_iot=t.id_dispositivo_iot
                  AND p.estado_durante_periodo IN ('SIN_SEÑAL','INACTIVO')
                  AND (cardinality(p.sensores_afectados)=0 OR t.id_sensor=ANY(p.sensores_afectados))
                  AND p.fecha_inicio<=t.timestamp_captura
                  AND (p.fecha_fin IS NULL OR p.fecha_fin>=t.timestamp_captura))
            ORDER BY t.timestamp_captura DESC,t.id_telemetria DESC LIMIT :n'''),
            dict(sensor=id_sensor,variable=id_variable,captura=captura,n=n,estados=estados)).mappings().all()
        estadisticas = tuple(LecturaCalidad(r['id_telemetria'],r['timestamp_captura'],
                         Decimal(str(r['valor_crudo'])),r['frecuencia_muestreo_min']) for r in activas)
        return ContextoCalidad(lecturas,tuple(IntervaloInactividad(*p) for p in periodos),
                               fuente['frecuencia_muestreo_min'],snapshot,estadisticas)
