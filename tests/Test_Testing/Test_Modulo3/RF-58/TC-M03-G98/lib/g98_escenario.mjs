import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
export const PRESUPUESTO = require('./g98_presupuesto.cjs');
export const CASO = 'TC-M03-191';
export const ORACULO = 'HTTP 200. Se devuelve el total de alertas activas y la lista ordenada por severidad con CRITICO primero, indicando tipo de alerta, variable afectada y tiempo transcurrido, con navegación al detalle del activo biológico afectado.';
export const CAPACIDADES = Object.freeze({
  contrato: 'sigab-qa-ejecutor/1', grupo: 'G98', casos: [CASO],
  operaciones: ['reevaluar', 'reintentar'], versiones: { min: 2, max: 3 },
  comprobaciones_obligatorias: { [CASO]: { API: ['API-191-01', 'API-191-02', 'API-191-03'] } },
  limite: { solicitudes_directas: PRESUPUESTO.solicitudes_en_run,
    escrituras_alerta: PRESUPUESTO.escrituras_alerta, lecturas_cierre: PRESUPUESTO.lecturas_cierre,
    margen_cierre: PRESUPUESTO.margen_cierre, duracion_segundos: PRESUPUESTO.duracion_segundos },
});
const objeto = x => x !== null && typeof x === 'object' && !Array.isArray(x);
const texto = x => typeof x === 'string' && x.trim().length > 0;
const grado = { CRITICO: 3, MODERADO: 2, LEVE: 1 };
export function panelDe(body) {
  const p = body?.panel_alertas_activas;
  return objeto(p) && Object.hasOwn(p, 'total') && Object.hasOwn(p, 'alertas')
    ? { presente: true, total: p.total, alertas: p.alertas }
    : { presente: false, campos: objeto(body) ? Object.keys(body) : [] };
}
export function evaluarPanel(body, { ahora = Date.now(), inicioRun = ahora, esperado = null, unidad = null } = {}) {
  const panel = panelDe(body);
  if (!panel.presente) return { estado: 'RECHAZADO', motivo: 'Respuesta 200 sin panel de alertas activas (total + lista)', panel };
  if (!Number.isInteger(panel.total) || panel.total < 0 || !Array.isArray(panel.alertas))
    return { estado: 'RECHAZADO', motivo: 'Total o lista del panel inválido', panel: { presente: true } };
  const alertas = panel.alertas;
  const fallos = [];
  const observaciones = [];
  if (alertas.length && alertas[0]?.severidad !== 'CRITICO') fallos.push('CRITICO no aparece primero');
  if (alertas.length !== Math.min(panel.total, 50)) fallos.push('total distinto de la lista limitada a 50');
  if (esperado && panel.total !== esperado.total) fallos.push('total distinto de GET alertas ACTIVA del área');
  if (esperado && (esperado.total < 3 || panel.total < 3)) fallos.push('menos de tres alertas ACTIVA');
  const ids = new Set();
  for (const [i, a] of alertas.entries()) {
    if (!objeto(a)) { fallos.push(`alerta ${i} no es objeto`); continue; }
    if (!Number.isInteger(a.id_alerta) || ids.has(a.id_alerta)) fallos.push(`id_alerta inválido o duplicado ${i}`);
    ids.add(a.id_alerta);
    if (!texto(a.tipo_alerta) || !texto(a.tipo_variable)) fallos.push(`tipo o variable ausente ${i}`);
    if (!Object.hasOwn(grado, a.severidad)) fallos.push(`severidad fuera de RF-57 ${i}`);
    const fecha = Date.parse(a.fecha_generacion);
    const inferior = Math.floor((inicioRun - 120000 - fecha) / 60000) - 1;
    const superior = Math.floor((ahora - fecha) / 60000) + 1;
    const valor = Object.hasOwn(a, 'minutos_transcurridos') ? String(a.minutos_transcurridos) : 'ausente';
    if (!Number.isFinite(fecha) || !Number.isFinite(inicioRun) || !Number.isFinite(ahora)
      || fecha > ahora + 60000) fallos.push(`fecha_generacion de alerta ${a.id_alerta ?? i}: valor no válido o posterior a la respuesta más 60 s`);
    else if (!Number.isInteger(a.minutos_transcurridos) || a.minutos_transcurridos < inferior
      || a.minutos_transcurridos > superior)
      fallos.push(`minutos_transcurridos de alerta ${a.id_alerta ?? i}: valor ${valor}; se espera un entero entre ${inferior} y ${superior}`);
    else if (a.minutos_transcurridos < 0 && fecha > inicioRun)
      observaciones.push(`Alerta ${a.id_alerta ?? i}: minutos negativos por now() fijo del sandbox (indicadores_alertas_repository.py:70); en producción now() es por petición`);
    if (i && grado[a.severidad] > grado[alertas[i - 1]?.severidad]) fallos.push(`orden de severidad ${i}`);
    if (i && a.severidad === alertas[i - 1]?.severidad && fecha > Date.parse(alertas[i - 1]?.fecha_generacion))
      fallos.push(`orden de recencia ${i}`);
    if (unidad != null && a.id_infraestructura !== unidad) fallos.push(`alerta fuera del área ${i}`);
    if (esperado && !esperado.ids.has(a.id_alerta)) fallos.push(`alerta no ACTIVA o fuera del alcance ${i}`);
  }
  if (esperado && esperado.total <= 50 && alertas.length !== esperado.ids.size) fallos.push('lista no cubre alertas ACTIVA del alcance');
  if (fallos.length) return { estado: 'RECHAZADO', motivo: fallos.join('; '), observaciones,
    panel: { presente: true, total: panel.total, largo_lista: alertas.length, ids: [...ids] } };
  return { estado: 'APROBADO', motivo: 'Panel, total, estados, alcance, campos y orden acreditados',
    observaciones,
    panel: { presente: true, total: panel.total, largo_lista: alertas.length, ids: [...ids] } };
}
export function precondicion(items) {
  const filas = Array.isArray(items) ? items.filter(x => x?.estado_alerta === 'ACTIVA') : [];
  const porGrado = ['CRITICO', 'MODERADO', 'LEVE'].map(g => filas
    .filter(x => x.severidad === g && Number.isInteger(x.id_sensor) && x.id_sensor > 0)
    .map(x => x.id_sensor));
  return porGrado[0].some(a => porGrado[1].some(b => b !== a
    && porGrado[2].some(c => c !== a && c !== b)));
}
export function riesgoE7(body) {
  return !Array.isArray(body?.sensores) || body.sensores.some(x => x?.estado_semaforo === 'GRIS'
    && (x?.dato_desactualizado !== true || x?.sin_umbral === true));
}

// Valores comprobados con el DTO y las bandas RF-57 en validar_semilla_g98.py.
export const MODELOS_SEMILLA = Object.freeze({
  TEMPERATURA_AMBIENTAL: ['C', '10', '16', '19'],
  HUMEDAD_RELATIVA: ['%', '20', '35', '45'],
  PH_AGUA: ['pH', '5.0', '5.7', '6.2'],
  NH3: ['ppm', '50', '38', '28'],
  CO2: ['ppm', '4500', '3700', '3200'],
  TEMPERATURA_CORPORAL: ['C', '35', '35.7', '36.2'],
  FRECUENCIA_CARDIACA: ['bpm', '30', '41', '44'],
  OXIGENO_DISUELTO: ['mg/L', '1.5', '2.5', '4'],
  TDS: ['ppm', '2200', '1700', '1200'],
});
export const GRADOS_SEMILLA = Object.freeze(['CRITICO', 'MODERADO', 'LEVE']);
export const SEMILLA_G98 = Object.freeze({ id_finca: 184, id_infraestructura: 702,
  nombre: 'QA-G98-PANEL', id_dispositivo_iot: 789, sensores: Object.freeze([1210, 1211, 1212]),
  id_activo_biologico: 928 });
const claveVariable = x => typeof x === 'string' ? x.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
  .trim().replace(/\s+/g, ' ').toUpperCase() : '';
const NOMBRES_HISTORIAL = Object.freeze({
  'PH DEL AGUA': 'PH_AGUA', 'AMONIACO (NH3)': 'NH3',
  'TEMPERATURA CORPORAL': 'TEMPERATURA_CORPORAL', TEMP_CORPORAL: 'TEMPERATURA_CORPORAL',
});
export function normalizarTipoVariable(valor) {
  const clave = claveVariable(valor);
  return Object.hasOwn(MODELOS_SEMILLA, clave) ? clave : NOMBRES_HISTORIAL[clave] ?? null;
}
const enteroPositivo = x => Number.isInteger(x) && x > 0;

export function elegirTernaSemilla(candidatos) {
  // Una variable por alerta evita consolidación por la misma regla simple.
  for (const activo of new Set(candidatos.map(x => x.id_activo_biologico))) {
    const filas = candidatos.filter(x => x.id_activo_biologico === activo);
    for (const a of filas) for (const b of filas) for (const c of filas) {
      const terna = [a, b, c];
      if (enteroPositivo(activo) && new Set(terna.map(x => x.id_sensor)).size === 3
        && new Set(terna.map(x => x.tipo_variable)).size === 3) return terna;
    }
  }
  return null;
}

export function cuerpoSemilla(sensor, severidad, ahora = new Date()) {
  const modelo = MODELOS_SEMILLA[sensor.tipo_variable];
  const indice = GRADOS_SEMILLA.indexOf(severidad);
  if (!modelo || indice < 0 || !enteroPositivo(sensor.id_dispositivo_iot)
    || !enteroPositivo(sensor.id_sensor) || !enteroPositivo(sensor.id_telemetria)
    || !enteroPositivo(sensor.id_activo_biologico) || !texto(sensor.serial)) throw Error('SEMILLA_RECURSO_INVALIDO');
  const valor = modelo[indice + 1];
  return { device_id: sensor.id_dispositivo_iot, sensor_id: sensor.id_sensor, serial: sensor.serial,
    tipo_variable: sensor.tipo_variable, valor, unidad: modelo[0], timestamp_evento: ahora.toISOString(),
    estado_dato: 'LECTURA_VALIDA', severidad_edge: severidad, origen_evento: 'BACKEND',
    id_telemetria: sensor.id_telemetria,
    reglas_activadas: [{ id: `RF57_BASE_${sensor.tipo_variable}`, nombre: `${sensor.tipo_variable}_${severidad}`,
      tipo: 'REGLA_SIMPLE_RF57', valor, id_sensor: sensor.id_sensor, id_telemetria: sensor.id_telemetria }] };
}
