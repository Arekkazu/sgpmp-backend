export const CASOS = Object.freeze(['TC-M03-173', 'TC-M03-174']);
export const COMPROBACIONES_OBLIGATORIAS = Object.freeze({
  'TC-M03-173': { API: ['API-173-01'] },
  'TC-M03-174': { API: ['API-174-01', 'API-174-02', 'API-174-03', 'API-174-04'] },
});
export const CAPACIDADES = Object.freeze({
  contrato: 'sigab-qa-ejecutor/1',
  operaciones: ['evaluar', 'reintentar', 'reevaluar'],
  versiones: '1..n',
  comprobaciones_obligatorias: COMPROBACIONES_OBLIGATORIAS,
});
export const SEMILLA = Object.freeze({ finca: 184, area: 349, especie: 126,
  dispositivo: 357, sensor: 552, variable: 1, umbral: 70, calibracion: 68,
  valor: 25, unidad: '°C', tipo_variable: 'TEMPERATURA_AMBIENTAL',
  valores_alerta: Object.freeze({ CRITICO: 37, LEVE: 31, MODERADO: 34 }) });
export const LIMITE = Object.freeze({ solicitudes: 80, ingestas: 8, alertas: 3,
  transiciones: 5, newman: 1 });

export function planTemporal(inicio = new Date().toISOString()) {
  const n = Date.parse(inicio);
  if (!Number.isFinite(n)) throw new Error('INICIO_INVALIDO');
  const ancla = n - 120_000;
  return { inicio, ancla: new Date(ancla).toISOString(),
    marcas: [8, 7, 6, 5, 4, 3, 2, 1].map((pasos) => new Date(ancla - pasos * 5000).toISOString()) };
}

export function cuerpoAlerta({ serial, severidad, idTelemetria, timestampEvento }) {
  return { device_id: SEMILLA.dispositivo, sensor_id: SEMILLA.sensor, serial,
    tipo_variable: SEMILLA.tipo_variable, valor: SEMILLA.valores_alerta[severidad], unidad: SEMILLA.unidad,
    timestamp_evento: timestampEvento, estado_dato: 'LECTURA_VALIDA',
    severidad_edge: severidad, origen_evento: 'EDGE',
    id_telemetria: idTelemetria, reglas_activadas: [],
    correlacion_variables: { HUMEDAD_RELATIVA: 40 } };
}

export function exigirAlertaNueva(respuesta, severidad) {
  if (respuesta.status === 201 && respuesta.json?.es_duplicado === true)
    throw new Error(`ALERTA_DUPLICADA_${severidad}_ID_EXISTENTE_${Number(respuesta.json.id_alerta) || 'NO_INFORMADO'}`);
  if (respuesta.status === 201 && respuesta.json?.es_duplicado === false && !respuesta.json?.id_alerta)
    throw new Error(`ALERTA_DESCARTADA_${severidad}_MOTIVO_${respuesta.json.motivo_descarte || 'NO_INFORMADO'}`);
  if (respuesta.status !== 201 || !respuesta.json?.id_alerta || respuesta.json.es_duplicado !== false)
    throw new Error(`ALERTA_${severidad}_HTTP_${respuesta.status}_MOTIVO_` +
      `${respuesta.json?.error_code ?? 'SIN_CODIGO'}: ${respuesta.json?.message ?? 'SIN_MENSAJE'}` +
      `${respuesta.json?.fields?.length ? `; fields=${JSON.stringify(respuesta.json.fields)}` : ''}`);
  if (respuesta.json.severidad !== severidad)
    throw new Error(`ERROR_QA_SEVERIDAD_POST_${severidad}_OBSERVADA_${respuesta.json.severidad ?? 'NO_INFORMADA'}`);
  return Number(respuesta.json.id_alerta);
}

export function escrituraPermitida(metodo, ruta, cuerpo, contadores, permitidos = null) {
  const reglas = [
    ['POST', '/iot/telemetria', 'ingestas', LIMITE.ingestas],
    ['POST', '/iot/alertas', 'alertas', LIMITE.alertas],
    ['PATCH', /^\/iot\/alertas\/\d+\/estado$/, 'transiciones', LIMITE.transiciones],
  ];
  const regla = reglas.find(([m, r]) => metodo === m && (typeof r === 'string' ? ruta === r : r.test(ruta)));
  if (!regla || !cuerpo || typeof cuerpo !== 'object') throw new Error('ESCRITURA_FUERA_LISTA_BLANCA');
  const [, , clave, limite] = regla;
  if ((contadores[clave] ?? 0) >= limite) throw new Error('LIMITE_ESCRITURAS');
  if (metodo === 'POST' && (Number(cuerpo.device_id) !== SEMILLA.dispositivo
      || Number(cuerpo.sensor_id) !== SEMILLA.sensor || cuerpo.tipo_variable !== SEMILLA.tipo_variable
      || ![SEMILLA.valor, ...Object.values(SEMILLA.valores_alerta)].includes(Number(cuerpo.valor))))
    throw new Error('ESCRITURA_OTRA_SEMILLA');
  if (metodo === 'PATCH' && (!['EN_ATENCION', 'RESUELTA', 'DESCARTADA'].includes(cuerpo.nuevo_estado)
    || Object.keys(cuerpo).length !== 2 || typeof cuerpo.motivo !== 'string'
    || !cuerpo.motivo.trim() || cuerpo.motivo.length > 500))
    throw new Error('TRANSICION_NO_PREVISTA');
  if (permitidos) {
    if (metodo === 'POST' && ruta === '/iot/telemetria') {
      const paso = contadores.ingestas ?? 0;
      if (cuerpo.timestamp_captura !== permitidos.marcas[paso]
        || Number(cuerpo.valor) !== permitidos.valores[paso]
        || cuerpo.serial !== permitidos.serial
        || (contadores.marcas_usadas ?? []).includes(cuerpo.timestamp_captura))
        throw new Error('INGESTA_FUERA_ESCENARIO');
      (contadores.marcas_usadas ??= []).push(cuerpo.timestamp_captura);
    }
    if (metodo === 'POST' && ruta === '/iot/alertas') {
      const evento = permitidos.eventos.find((e) => e.id === cuerpo.id_telemetria);
      const esperado = cuerpoAlerta({ serial: permitidos.serial, severidad: cuerpo.severidad_edge,
        idTelemetria: cuerpo.id_telemetria, timestampEvento: evento?.marca });
      if (!['CRITICO', 'LEVE', 'MODERADO'].includes(cuerpo.severidad_edge)
        || !evento || evento.valor !== SEMILLA.valores_alerta[cuerpo.severidad_edge]
        || !Number.isInteger(cuerpo.id_telemetria) || cuerpo.id_telemetria <= 0
        || !permitidos.telemetrias.includes(cuerpo.id_telemetria)
        || Object.keys(cuerpo).length !== Object.keys(esperado).length
        || Object.entries(esperado).some(([k, v]) => JSON.stringify(cuerpo[k]) !== JSON.stringify(v)))
        throw new Error('ALERTA_FUERA_ESCENARIO');
    }
    if (metodo === 'PATCH' && !permitidos.alertas.includes(Number(ruta.split('/')[3])))
      throw new Error('ALERTA_AJENA');
  }
  contadores[clave] = (contadores[clave] ?? 0) + 1;
}

export function evaluarComprobacion(id, etapa, respuesta, idAlerta, lecturaEsperada = null) {
  const sensor = (respuesta?.sensores ?? []).find((s) => Number(s.id_sensor) === SEMILLA.sensor);
  const esperado = { base173: 'VERDE', critica: 'ROJO', base174: 'VERDE',
    noCriticaActiva: 'AMARILLO', resuelta: 'VERDE',
    baseDescarte: 'VERDE', noCriticaDescarte: 'AMARILLO', descartada: 'VERDE' }[etapa];
  if (!esperado || !CASOS.includes(id)) throw new Error('COMPROBACION_DESCONOCIDA');
  const idCorrecto = etapa === 'critica' ? Number(sensor?.id_alerta) === Number(idAlerta)
    : ['resuelta', 'descartada'].includes(etapa) ? sensor?.id_alerta == null : true;
  const valor = Number(sensor?.ultimo_valor);
  const lecturaEnRango = lecturaEsperada ? Number.isFinite(valor)
    && valor >= lecturaEsperada.minimo && valor <= lecturaEsperada.maximo : true;
  const marcaCoincide = lecturaEsperada ? Number.isFinite(Date.parse(sensor?.ultimo_timestamp_captura))
    && Date.parse(sensor.ultimo_timestamp_captura) === Date.parse(lecturaEsperada.marca) : true;
  return { id, etapa, esperado, observado: sensor ? {
    estado_semaforo: sensor.estado_semaforo, id_alerta: sensor.id_alerta ?? null,
    ultimo_valor: sensor.ultimo_valor, ultimo_timestamp_captura: sensor.ultimo_timestamp_captura,
    dato_desactualizado: sensor.dato_desactualizado } : null,
    lectura_en_rango: lecturaEnRango, lectura_vigente: marcaCoincide,
    id_alerta_esperado: etapa === 'critica' ? Number(idAlerta) : null,
    cumple: !!sensor && sensor.estado_semaforo === esperado && idCorrecto
      && lecturaEnRango && marcaCoincide,
    id_alerta_asociado_correcto: idCorrecto };
}

export function decidirCaso({ comprobaciones, prerequisitos = [], errorTecnico = null }) {
  if (errorTecnico) return { veredicto: null, estado_tecnico: 'ERROR_QA', motivo: errorTecnico };
  if (prerequisitos.length) return { veredicto: null, estado_tecnico: 'NO_CONCLUYENTE', motivo: prerequisitos.join('; ') };
  if (!comprobaciones.length) return { veredicto: null, estado_tecnico: 'NO_EJECUTADA', motivo: 'Sin comprobaciones API.' };
  return { veredicto: comprobaciones.every((c) => c.cumple) ? 'APROBADO' : 'RECHAZADO', estado_tecnico: 'OK' };
}
