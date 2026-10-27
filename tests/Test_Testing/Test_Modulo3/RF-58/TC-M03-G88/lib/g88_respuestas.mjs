// Lista positiva de campos para conservar respuestas API sin datos privados.
const campos = (dato, permitidos) => Object.fromEntries(permitidos
  .filter((k) => dato && Object.hasOwn(dato, k)).map((k) => [k, dato[k]]));

const VINCULO = ['id_vinculacion_lectura', 'id_telemetria', 'id_activo_biologico',
  'id_infraestructura', 'modelo_manejo', 'mecanismo_vinculacion', 'estado_vinculacion',
  'fecha_inicio_vinculacion', 'fecha_fin_vinculacion', 'fecha_creacion'];
const ASOCIACION = ['id_sensores_area_asociada', 'id_asociacion', 'id_sensor_area_asociada',
  'id_sensores_areas_asociadas', 'id_asociacion_sensor_area', 'id_sensor_area',
  'id_asociacion_sensor', 'id_sensor', 'id_infraestructura', 'tiene_estado',
  'fecha_inicio', 'fecha_finalizacion'];
const HISTORIAL = ['id_telemetria', 'id_sensor', 'id_variable', 'id_variable_ambiental',
  'id_activo_biologico', 'id_infraestructura', 'valor', 'valor_crudo', 'valor_ajustado',
  'unidad', 'unidad_medida', 'timestamp_captura', 'estado_calidad',
  'estado_semaforo_historico', 'id_alerta', 'severidad_alerta'];
const SENSOR = ['id_sensor', 'id_dispositivo_iot', 'id_infraestructura', 'id_telemetria',
  'tipo_variable', 'categoria_variable', 'ultimo_valor', 'ultima_unidad',
  'ultimo_timestamp_captura', 'estado_semaforo', 'estado_calidad', 'estado_desviacion',
  'estado_conectividad', 'dato_desactualizado', 'id_alerta', 'severidad_alerta',
  'etiqueta', 'etiqueta_estado', 'etiqueta_semaforo'];

export function respuestaSaneada(ruta, respuesta, sensorIds = []) {
  const ids = new Set(sensorIds.map(Number));
  if (ruta === '/configuracion/variables-ambientales') return {
    ...campos(respuesta, ['total']), items: (respuesta?.items ?? [])
      .map((x) => campos(x, ['id_variable_ambiental', 'nombre', 'tipo_variable', 'unidad',
        'valor_fisico_min', 'valor_fisico_max', 'es_activo'])) };
  if (ruta === '/configuracion/sensores/rangos-calibracion') return {
    ...campos(respuesta, ['total']), items: (respuesta?.items ?? [])
      .map((x) => campos(x, ['categoria', 'valor_min', 'valor_max'])) };
  if (ruta === '/configuracion/dispositivos-iot/520/sensores') return {
    ...campos(respuesta, ['total']), items: (respuesta?.items ?? [])
      .filter((x) => Number(x.id_sensores) === 738)
      .map((x) => campos(x, ['id_sensores', 'id_variable_ambiental', 'categoria', 'es_activo'])) };
  if (ruta.startsWith('/iot/vinculaciones?')) return {
    ...campos(respuesta, ['total', 'pagina', 'por_pagina']),
    items: (respuesta?.items ?? []).map((x) => campos(x, VINCULO)),
  };
  if (/^\/configuracion\/sensores\/\d+\/asociaciones$/.test(ruta)) return {
    ...campos(respuesta, ['total', 'pagina', 'por_pagina']),
    items: (respuesta?.items ?? []).map((x) => campos(x, ASOCIACION)),
  };
  if (ruta.startsWith('/iot/monitoreo/historial?')) return {
    ...campos(respuesta, ['total', 'pagina', 'por_pagina']),
    items: (respuesta?.items ?? []).filter((x) => ids.size === 0 || ids.has(Number(x.id_sensor)))
      .map((x) => campos(x, HISTORIAL)),
  };
  if (ruta.startsWith('/iot/monitoreo/dashboard?')) return {
    sensores: (respuesta?.sensores ?? []).filter((x) => ids.has(Number(x.id_sensor)))
      .map((x) => ({ ...campos(x, SENSOR),
        ...(Array.isArray(x.alertas_activas) ? { alertas_activas: x.alertas_activas.map((a) =>
          campos(a, ['id_alerta', 'estado', 'severidad', 'nivel', 'timestamp'])) } : {}) })),
  };
  return null;
}

export function lecturaDelRun(sensor, lectura) {
  if (!sensor || !lectura || !Number.isInteger(Number(lectura.id_telemetria))) return false;
  const ts = sensor.ultimo_timestamp_captura;
  const esperado = lectura.timestamp_captura;
  return Number(sensor.id_sensor) === Number(lectura.id_sensor)
    && !!ts && !!esperado && Date.parse(ts) === Date.parse(esperado)
    && Number(sensor.ultimo_valor) === Number(lectura.valor)
    && (sensor.id_telemetria == null || Number(sensor.id_telemetria) === Number(lectura.id_telemetria));
}
