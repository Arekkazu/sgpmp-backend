# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-41 RF-53/57: alerta critica del origen confirmado |
# | 2026-10-26 | Arekkazu | INC-M03-179-G57F RF-57: la alerta guarda el umbral que la disparó en reglas_activas |
# | 2026-10-31 | Arekkazu | USAB-M03-M04 M3-09/M3-12 RF-57/58: sin activo se clasifica con la especie del área |
"""Orquesta RF-17 → RF-57 dentro de la unidad post-commit existente."""
from src.shared.errors import ServiceUnavailableError
from src.telemetry.domain.entities.alerta import regla_umbral
from src.telemetry.infrastructure.dto.procesar_evento_alerta_dto import ProcesarEventoAlertaDTO



class GenerarAlertaTelemetriaUseCase:
    def __init__(self, lecturas, clasificador, generador):
        self.lecturas = lecturas
        self.clasificador = clasificador
        self.generador = generador

    def execute(self, identificador):
        lectura = self.lecturas.obtener_por_id(identificador)
        if lectura is None:
            raise RuntimeError('No existe la telemetría confirmada del procesamiento.')
        if lectura.estado_calidad != 'LECTURA_VALIDA':
            return {'decision': 'EXCLUIDA_POR_CALIDAD', 'estado_calidad': lectura.estado_calidad}
        if self.lecturas.evaluacion_vigente(identificador) is None:
            raise ServiceUnavailableError('CALIDAD_PENDIENTE', 'Falta la evaluación vigente RF-62.')
        vinculo = self.lecturas.vinculacion(identificador)
        if vinculo is None:
            raise ServiceUnavailableError('CONTEXTO_ALERTA_PENDIENTE', 'Falta resolver el contexto RF-61 para clasificar la lectura.')
        # M3-12: sin activo (sensor ambiental del área) se clasifica con la especie del área.
        # Antes esto también era CONTEXTO_ALERTA_PENDIENTE: la lectura nunca tendrá activo,
        # así que se reintentaba para siempre y dejaba millones de FALLIDO en la bitácora.
        clasificacion = self.clasificador.clasificar_lectura(identificador, vinculo['id_activo_biologico'])
        if clasificacion is None:
            return {'decision': 'SIN_CLASIFICACION_RF17'}
        color = clasificacion['estado_semaforo']
        if color != 'ROJO':
            return {'decision': 'NO_CRITICA', 'estado_semaforo': color}
        contexto = self.lecturas.contexto_alerta(lectura)
        variable = contexto['variable']
        if variable is None:
            raise ServiceUnavailableError('VARIABLE_ALERTA_NO_DISPONIBLE', 'Faltan los metadatos de la variable M09.')
        umbral = clasificacion['umbral']
        version = umbral.get('version')
        metadata = {
            'id_telemetria': identificador, 'id_variable': lectura.id_variable,
            'id_sensor': lectura.id_sensor, 'id_dispositivo_iot': lectura.id_dispositivo_iot,
            'timestamp_captura': lectura.timestamp_captura.isoformat(), 'unidad': lectura.unidad_medida,
            'id_finca': contexto['id_finca'], 'id_especie': clasificacion['id_especie'],
            'id_umbral_ambiental': umbral['id_umbral_ambiental'],
            'version_umbral': version.isoformat() if version else None,
            'estado_semaforo': color, 'origen_dato': lectura.origen,
            'valor_crudo': str(lectura.valor_crudo), 'valor_evaluado': str(clasificacion['valor']),
            'niveles_rf17': [{'nivel': n['nivel'], 'limite_inferior': str(n['limite_inferior']),
                            'limite_superior': str(n['limite_superior'])} for n in umbral['niveles']],
        }
        resultado = self.generador.execute(
            ProcesarEventoAlertaDTO(
                device_id=lectura.id_dispositivo_iot, sensor_id=lectura.id_sensor,
                serial=contexto['serial'], tipo_variable=variable['tipo_variable'],
                valor=clasificacion['valor'], unidad=lectura.unidad_medida,
                timestamp_evento=lectura.timestamp_captura, estado_dato=lectura.estado_calidad,
                severidad_edge='CRITICO', origen_evento='BACKEND', id_telemetria=identificador,
                reglas_activadas=[regla_umbral(umbral['id_umbral_ambiental'], variable['tipo_variable'], color,
                                               metadata['version_umbral'])],
                metadata_evento=metadata,
            ), id_activo_biologico=vinculo['id_activo_biologico'],
            id_dispositivo_ioit=lectura.id_dispositivo_iot, id_infraestructura=contexto['id_infraestructura'],
        )
        if resultado.id_alerta is None:
            raise RuntimeError('RF-57 no confirmó la generación o consolidación de la alerta.')
        return {'decision': 'CONSOLIDADA' if resultado.es_duplicado else 'CREADA',
                'id_alerta': resultado.id_alerta, 'id_telemetria': identificador,
                'id_variable': lectura.id_variable, 'estado_semaforo': color,
                'contexto_rf17': metadata}
