/*
 * TC-M04-027 - Tiempo de respuesta del historial diagnóstico de un mes (RF-67, RNF-01, CA-10).
 *
 * Criterio de la ficha: con un activo de ~4300 inferencias en un mes, la consulta con y sin filtros mantiene el
 * p95 por debajo de 1.5 s, sin pérdida de integridad ni de orden.
 *
 * Endpoint real: GET /prediccion/historial/{id_activo_biologico} (paginado por cursor, 50 eventos por página).
 * Los datos los siembra test_tc_m04_g014_rendimiento.py (TEST no tiene inferencias de RF-66), que también ejecuta
 * este script. Para correrlo a mano: k6 run -e ID_ACTIVO=<id> -e ESPERADO=4300 test_tc_m04_027_rendimiento_historial.js
 *
 * Escenarios:
 *   carga       - 5 consultas/s durante 1 min de la primera página del mes: sin filtros, nivel_riesgo=3,
 *                 id_patologia y incluir_alertas=true. Umbral p95 < 1500 ms por tipo de consulta.
 *   integridad  - 1 VU recorre todas las páginas del mes (≈86) y comprueba conteo, ausencia de duplicados y orden
 *                 DESC por fecha; cada página también debe responder en < 1500 ms (p95).
 */
import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const ID_ACTIVO = __ENV.ID_ACTIVO;
const ID_PATOLOGIA = __ENV.ID_PATOLOGIA || '';
const ESPERADO = Number(__ENV.ESPERADO || 4300);
const errores_integridad = new Counter('tc_m04_027_errores_integridad');

export const options = {
  scenarios: {
    carga: { executor: 'constant-arrival-rate', rate: 5, timeUnit: '1s', duration: '1m', preAllocatedVUs: 10, maxVUs: 30, exec: 'carga' },
    integridad: { executor: 'shared-iterations', vus: 1, iterations: 1, exec: 'integridad', startTime: '1m5s', maxDuration: '10m' },
  },
  thresholds: {
    'http_req_duration{consulta:sin_filtros}': ['p(95)<1500'],
    'http_req_duration{consulta:riesgo}': ['p(95)<1500'],
    'http_req_duration{consulta:patologia}': ['p(95)<1500'],
    'http_req_duration{consulta:alertas}': ['p(95)<1500'],
    'http_req_duration{consulta:recorrido}': ['p(95)<1500'],
    tc_m04_027_errores_integridad: ['count==0'],
    http_req_failed: ['rate==0'],
  },
};

function fechas() {
  const hoy = new Date();
  const desde = new Date(hoy.getTime() - 31 * 86400000);
  return { desde: desde.toISOString().slice(0, 10), hasta: hoy.toISOString().slice(0, 10) };
}

export function setup() {
  if (!ID_ACTIVO) throw new Error('Falta -e ID_ACTIVO (lo entrega test_tc_m04_g014_rendimiento.py)');
  const r = http.post(`${BASE_URL}/sesiones/`, JSON.stringify({
    correo_electronico: __ENV.CORREO || 'admin@pecuaria.co', contrasena: __ENV.CONTRASENA || 'Test1234!',
  }), { headers: { 'Content-Type': 'application/json' } });
  check(r, { 'setup: login (200)': (x) => x.status === 200 });
  return { token: r.json('token'), ...fechas() };
}

function consultar(data, extra, etiqueta) {
  const q = `fecha_inicio=${data.desde}&fecha_fin=${data.hasta}${extra}`;
  return http.get(`${BASE_URL}/prediccion/historial/${ID_ACTIVO}?${q}`, {
    headers: { Authorization: `Bearer ${data.token}` }, tags: { consulta: etiqueta },
  });
}

const VARIANTES = [
  ['sin_filtros', ''],
  ['riesgo', '&nivel_riesgo=3'],
  ['patologia', ID_PATOLOGIA ? `&id_patologia=${ID_PATOLOGIA}` : ''],
  ['alertas', '&incluir_alertas=true'],
];

export function carga(data) {
  const [etiqueta, extra] = VARIANTES[Math.floor(Math.random() * VARIANTES.length)];
  const r = consultar(data, extra, etiqueta);
  check(r, { [`TC-M04-027 ${etiqueta}: 200 con eventos`]: (x) => x.status === 200 && (x.json('eventos') || []).length > 0 });
}

export function integridad(data) {
  const vistos = new Set();
  let anterior = Infinity;
  let cursor = null;
  let paginas = 0;
  let total = 0;
  do {
    const r = consultar(data, cursor ? `&cursor_paginacion=${encodeURIComponent(cursor)}` : '', 'recorrido');
    if (!check(r, { 'TC-M04-027 recorrido: página 200': (x) => x.status === 200 })) { errores_integridad.add(1); return; }
    const eventos = r.json('eventos') || [];
    for (const e of eventos) {
      if (e.tipo_evento !== 'INFERENCIA') continue;
      const t = Date.parse(e.fecha_evento);
      if (t > anterior) errores_integridad.add(1, { motivo: 'orden' });
      anterior = t;
      if (vistos.has(e.id_resultado_inferencia)) errores_integridad.add(1, { motivo: 'duplicado' });
      vistos.add(e.id_resultado_inferencia);
      total += 1;
    }
    cursor = r.json('cursor_siguiente');
    paginas += 1;
  } while (cursor && paginas < 200);
  console.log(`TC-M04-027 recorrido: ${paginas} páginas, ${total} inferencias (${vistos.size} distintas), esperado ${ESPERADO}`);
  if (vistos.size !== ESPERADO) errores_integridad.add(1, { motivo: 'conteo' });
  check(null, { 'TC-M04-027 recorrido: todas las inferencias del mes, sin duplicados ni omisiones': () => vistos.size === ESPERADO && total === ESPERADO });
}
