import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
export const PRESUPUESTO = require('./g98_presupuesto.cjs');
export const CASO = 'TC-M03-191';
export const ORACULO = 'HTTP 200. Se devuelve el total de alertas activas y la lista ordenada por severidad con CRITICO primero, indicando tipo de alerta, variable afectada y tiempo transcurrido, con navegación al detalle del activo biológico afectado.';
export const CAPACIDADES = Object.freeze({
  contrato: 'sigab-qa-ejecutor/1', grupo: 'G98', casos: [CASO],
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: { [CASO]: { API: ['API-191-01'] } },
  limite: { solicitudes_directas: PRESUPUESTO.solicitudes_en_run,
    margen_cierre: PRESUPUESTO.margen_cierre, duracion_segundos: PRESUPUESTO.duracion_segundos },
});
const objeto = x => x !== null && typeof x === 'object' && !Array.isArray(x);
const campos = (o, nombres) => nombres.find(k => Object.hasOwn(o, k));
const normalizar = x => typeof x === 'string' ? x.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase().trim() : '';
// RF-57: CRITICO > MODERADO > LEVE (línea 3785). La matriz usa CRITICO/ALTA/MEDIA.
const ESCALAS = [
  { CRITICO: 3, CRITICA: 3, MODERADO: 2, MODERADA: 2, LEVE: 1 },
  { CRITICO: 3, CRITICA: 3, ALTA: 2, MEDIA: 1, BAJA: 0 },
];
export function panelDe(body) {
  if (!objeto(body)) return { presente: false, campos: [] };
  const contenedores = [['raiz', body], ...['panel_alertas', 'panel_alertas_activas', 'alertas_activas_panel']
    .filter(k => objeto(body[k])).map(k => [k, body[k]])];
  for (const [ruta, o] of contenedores) {
    const lista = campos(o, ['alertas_activas', 'alertas', 'lista_alertas', 'items']);
    const total = campos(o, ['total_alertas_activas', 'alertas_activas_total', 'total_alertas']);
    // "items" solo pertenece a un contenedor explícito de panel.
    if (lista === 'items' && ruta === 'raiz') continue;
    if (lista && total) return { presente: true, ruta, lista, total, datos: o[lista], cantidad: o[total], campos: Object.keys(o) };
  }
  return { presente: false, campos: Object.keys(body), candidatos: contenedores.map(([ruta,o]) => ({ ruta, campos: Object.keys(o) })) };
}
export function evaluarPanel(body) {
  const panel = panelDe(body);
  if (!panel.presente) return { estado: 'RECHAZADO', motivo: 'Respuesta 200 sin panel de alertas activas (total + lista)', panel };
  if (!Number.isInteger(panel.cantidad) || panel.cantidad < 0 || !Array.isArray(panel.datos))
    return { estado: 'RECHAZADO', motivo: 'Total o lista del panel con tipo inválido', panel };
  const filas = panel.datos.map((a, i) => {
    if (!objeto(a)) return { indice: i, error: 'Elemento no es objeto' };
    const claves = { severidad: campos(a, ['severidad', 'nivel_severidad']),
      tipo: campos(a, ['tipo_alerta', 'tipo']), variable: campos(a, ['tipo_variable', 'variable_afectada', 'variable']),
      tiempo: campos(a, ['tiempo_transcurrido', 'tiempo_transcurrido_min', 'minutos_transcurridos', 'elapsed']),
      enlace: campos(a, ['enlace_activo', 'url_activo', 'href_activo', 'id_activo_biologico', 'id_animal']) };
    const enlace = claves.enlace && a[claves.enlace];
    const valido = Object.values(claves).every(Boolean)
      && (!Object.hasOwn(a, 'estado_alerta') || normalizar(a.estado_alerta) === 'ACTIVA')
      && [claves.tipo, claves.variable].every(k => typeof a[k] === 'string' && a[k].trim())
      && (typeof a[claves.tiempo] === 'string' && a[claves.tiempo].trim() || Number.isFinite(a[claves.tiempo]) && a[claves.tiempo] >= 0)
      && (typeof enlace === 'string' && enlace.trim() || Number.isInteger(enlace) && enlace > 0);
    return { indice: i, claves, severidad: claves.severidad ? a[claves.severidad] : null,
      valido: !!valido, error: valido ? null : 'Falta tipo, variable, tiempo transcurrido o enlace/identificador del activo' };
  });
  const resumen = { ruta: panel.ruta, campos: panel.campos, lista: panel.lista, total: panel.total,
    cantidad: panel.cantidad, largo_lista: panel.datos.length, filas };
  if (filas.some(x => !x.valido)) return { estado: 'RECHAZADO', motivo: 'Elementos del panel incompletos', panel: resumen };
  if (panel.datos.length > panel.cantidad) return { estado: 'RECHAZADO', motivo: 'Lista mayor que el total de alertas activas', panel: resumen };
  if (panel.cantidad > 0 && panel.datos.length === 0)
    return { estado: 'RECHAZADO', motivo: 'Total positivo sin alertas en la lista del panel', panel: resumen };
  const severidades = filas.map(x => normalizar(x.severidad));
  const escala = ESCALAS.find(e => severidades.every(s => Object.hasOwn(e, s)));
  if (!escala && severidades.length) return { estado: 'RECHAZADO', motivo: 'Severidad fuera de los catálogos RF-57/matriz o mezcla de escalas no definida', panel: resumen };
  if (severidades.some((s, i) => i > 0 && escala[s] > escala[severidades[i - 1]]))
    return { estado: 'RECHAZADO', motivo: 'Lista no ordenada por severidad descendente', panel: resumen };
  if (new Set(severidades.map(s => escala[s])).size < 2) return { estado: 'BLOQUEADO', motivo: 'Panel presente sin datos de severidad mixta', panel: resumen };
  if (!['CRITICO', 'CRITICA'].includes(severidades[0]))
    return { estado: 'RECHAZADO', motivo: 'La mayor severidad no es CRITICO primero', panel: resumen };
  return { estado: 'APROBADO', motivo: 'Panel completo y ordenado, con severidades mixtas', panel: resumen };
}
export function hayAlertas(body) {
  if (!objeto(body)) return false;
  return (Array.isArray(body.resumen_unidades) && body.resumen_unidades.some(u => Number(u?.alertas_activas_count) > 0))
    || (Array.isArray(body.sensores) && body.sensores.some(s => s?.id_alerta != null))
    || (panelDe(body).presente && Number(panelDe(body).cantidad) > 0);
}
