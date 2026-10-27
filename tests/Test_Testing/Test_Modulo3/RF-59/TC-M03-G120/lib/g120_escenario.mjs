import PRESUPUESTO from './g120_presupuesto.cjs';

export const CASOS = ['TC-M03-241', 'TC-M03-242', 'TC-M03-243'];
export const IDS = ['API-241-01', 'API-242-01', 'API-243-01'];
export const CAPACIDADES = Object.freeze({
  contrato: 'sigab-qa-ejecutor/1', grupo: 'G120', casos: CASOS,
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: Object.fromEntries(CASOS.map((caso, i) => [caso, { API: [IDS[i]] }])),
  limite: { solicitudes_directas: PRESUPUESTO.solicitudes_directas,
    margen_cierre: PRESUPUESTO.margen_cierre, duracion_segundos: PRESUPUESTO.duracion_segundos,
    inactividad_maxima_segundos: PRESUPUESTO.inactividad_maxima_segundos },
});
const hora = 3_600_000;
export const instante = x => Number.isFinite(Date.parse(x)) ? Date.parse(x) : NaN;
export function marcas(ancla) {
  const t = instante(ancla);
  if (!Number.isFinite(t)) throw Error('ANCLA_INVALIDA');
  return { intervalo: [2, 1, 0].map(m => new Date(t - 12 * hora - m * 60_000).toISOString()),
    duplicado: new Date(t - 12 * hora + 120_000).toISOString(),
    bordes: [23, 24].map(h => new Date(t - h * hora).toISOString()),
    real: new Date(t - 30_000).toISOString(), envio: new Date(t).toISOString() };
}
export function fixture(semilla, timestamp_captura, origen, timestamp_envio) {
  if (![semilla.device_id, semilla.sensor_id].every(x => Number.isSafeInteger(x) && x > 0)
      || !Number.isSafeInteger(semilla.id_variable) || semilla.id_variable <= 0
      || !semilla.serial || !/^[A-Z][A-Z0-9_]{1,39}$/.test(semilla.tipo_variable)
      || !semilla.nombre_variable || !semilla.unidad || !Number.isFinite(Number(semilla.valor))) throw Error('SEMILLA_INVALIDA');
  return { device_id: semilla.device_id, sensor_id: semilla.sensor_id, serial: semilla.serial,
    id_variable: semilla.id_variable, tipo_variable: semilla.tipo_variable,
    valor: Number(semilla.valor), unidad: semilla.unidad,
    timestamp_captura, timestamp_envio, origen, estado_conectividad: true };
}
export function filas(items, semilla, captura, origen) {
  return items.filter(x => Number(x.id_sensor) === semilla.sensor_id &&
    Number(x.id_variable) === semilla.id_variable && String(x.tipo_variable) === semilla.nombre_variable
    && instante(x.timestamp_captura) === instante(captura)
    && (!origen || x.origen_dato === origen));
}
const respuesta = (estado, motivo, valores = {}) => ({ estado, motivo, valores });
export function evaluarHistorial(items, semilla, m) {
  if (!Array.isArray(items)) return CASOS.map(() => respuesta('NO_CONCLUYENTE', 'Historial sin lista de lecturas'));
  const intervalo = m.intervalo.map(ts => filas(items, semilla, ts, 'BUFFER_LOCAL'));
  const otra = filas(items, semilla, m.real, 'TIEMPO_REAL');
  const todos = [...m.intervalo, m.duplicado, ...m.bordes, m.real].map(ts => ({ captura: ts,
    filas: filas(items, semilla, ts).map(x => ({ id_telemetria: x.id_telemetria,
      timestamp_captura: x.timestamp_captura, origen_dato: x.origen_dato, tipo_variable: x.tipo_variable })) }));
  const intervaloAcreditado = intervalo.every((x, i) => x.length === 1
    && filas(items, semilla, m.intervalo[i]).length === 1
    && instante(x[0].timestamp_captura) === instante(m.intervalo[i]));
  const contrasteAcreditado = otra.length === 1 && filas(items, semilla, m.real).length === 1;
  const c241 = intervaloAcreditado && contrasteAcreditado;
  const duplicado = filas(items, semilla, m.duplicado, 'BUFFER_LOCAL');
  const totalDuplicado = filas(items, semilla, m.duplicado);
  const c242 = duplicado.length === 1 && totalDuplicado.length === 1
    && instante(duplicado[0].timestamp_captura) === instante(m.duplicado);
  const bordes = m.bordes.map(ts => filas(items, semilla, ts, 'BUFFER_LOCAL'));
  const integrado = bordes.every((x, i) => x.length === 1
    && filas(items, semilla, m.bordes[i]).length === 1
    && instante(x[0].timestamp_captura) === instante(m.bordes[i]));
  const c243 = integrado
    ? respuesta('APROBADO', 'Ambas lecturas de 23 h y 24 h integradas con captura original')
    : respuesta('RECHAZADO', 'Una lectura de 23 h o 24 h falta o alteró su captura');
  const valores241 = { todos, intervaloAcreditado, contrasteAcreditado };
  return [c241 ? respuesta('APROBADO', 'Intervalo completo, origen y contraste acreditados', valores241)
    : respuesta('RECHAZADO', 'Intervalo, timestamp, origen o contraste TIEMPO_REAL incumplido', valores241),
  c242 ? respuesta('APROBADO', 'Una lectura lógica tras segundo envío', { duplicado: totalDuplicado.length })
    : respuesta('RECHAZADO', 'Duplicado o timestamp alterado', { duplicado: totalDuplicado.length }),
  { ...c243, valores: { ...c243.valores, todos } }];
}
export function sincronizacion(batch, bordes) {
  const detalle = Array.isArray(batch?.detalle) ? batch.detalle : [];
  const campos = ['timestamp_sincronizacion', 'fecha_sincronizacion', 'momento_sincronizacion'];
  const campo = campos.find(k => detalle.some(x => Object.hasOwn(x, k)));
  if (!campo) return { estado: 'ausente', campo: null, momentos: [] };
  const momentos = bordes.map(ts => detalle.find(x => instante(x.timestamp_captura) === instante(ts))?.[campo]);
  return { estado: momentos.every(x => Number.isFinite(instante(x))) ? 'valido' : 'invalido', campo, momentos };
}
