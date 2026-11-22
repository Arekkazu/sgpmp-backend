# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-43 RF-62/57: alerta tecnica por condicion de sensor |
# | 2026-10-26 | Leandro | INC-M03-104-G165 RF-62/RF-57: devolver alerta de drift pendiente para auditoria sin inventar severidad ni bloquear calidad. |
"""Notificación técnica usando el repositorio y catálogo de fallos existentes."""
from src.shared.errors import ServiceUnavailableError
from src.telemetry.domain.entities.alerta import Alerta, SeveridadAlerta


class GenerarAlertaCalidadUseCase:
    def __init__(self, alerta_repo):
        self.alerta_repo = alerta_repo

    def execute(self, evaluacion):
        """Devuelve avisos pendientes; el evaluador los audita en su transacción.

        La falta de una severidad aprobada de drift no es un fallo de
        persistencia. Las excepciones del repositorio siguen propagándose.
        """
        pendientes = []
        for anomalia in ('sensor_congelado', 'posible_drift'):
            flag = evaluacion.flags_detectados.get(anomalia, {})
            if not flag.get('activo'):
                continue
            if anomalia == 'posible_drift':
                umbral = evaluacion.parametros_aplicados['umbral_drift_significativo']
                if flag['magnitud_drift_porcentaje'] <= umbral:
                    continue
            severidad = flag.get('severidad')
            if severidad not in {s.value for s in SeveridadAlerta}:
                if anomalia == 'posible_drift':
                    pendientes.append({
                        'anomalia': anomalia,
                        'motivo': 'SEVERIDAD_DRIFT_NO_CONFIGURADA',
                        'magnitud_drift_porcentaje': flag['magnitud_drift_porcentaje'],
                    })
                    continue
                raise ServiceUnavailableError('SEVERIDAD_DRIFT_NO_CONFIGURADA',
                    'Falta la regla aprobada de severidad para la alerta técnica de drift significativo.')
            self.alerta_repo.bloquear_condicion_calidad(evaluacion.id_sensor, anomalia)
            existente = self.alerta_repo.buscar_tecnica_calidad(
                evaluacion.id_sensor, anomalia, evaluacion.id_telemetria)
            if existente:
                orden = {s.value:i for i,s in enumerate(SeveridadAlerta)}
                if (existente.estado_alerta in ('ACTIVA','EN_ATENCION') and
                        orden[severidad] > orden.get(existente.severidad,-1)):
                    self.alerta_repo.escalar_calidad(existente.id_alerta,severidad)
                continue
            contexto = self.alerta_repo.contexto_sensor_calidad(evaluacion.id_sensor)
            alerta = Alerta(
                tipo_alerta='TECNICA', severidad=severidad, estado_alerta='ACTIVA',
                origen_evento='BACKEND', tipo_variable='SENSOR_FISICO_FALLIDO',
                id_sensor=evaluacion.id_sensor, id_telemetria=evaluacion.id_telemetria,
                id_dispositivo_ioit=contexto['id_dispositivo_iot'],
                id_infraestructura=contexto['id_infraestructura'],
                fecha_evento=evaluacion.timestamp_evaluacion,
                fecha_generacion=evaluacion.timestamp_evaluacion,
                metadato_evento={
                    'componente_origen':'RF62', 'anomalia':anomalia,
                    'id_evaluacion':str(evaluacion.id_evaluacion),
                    'id_variable':evaluacion.parametros_aplicados.get('id_variable'),
                    'evidencia':flag, 'parametros_aplicados':evaluacion.parametros_aplicados,
                    'version_limites_fisicos_aplicada':evaluacion.version_limites_fisicos_aplicada,
                },
            )
            alerta.fecha_vencimiento = alerta.calcular_fecha_vencimiento()
            self.alerta_repo.guardar(alerta)
            # El trigger conserva el historial inicial; sin commits en este servicio.
        return pendientes
