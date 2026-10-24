/*
 * TC-M04-016 - Tiempo de respuesta de la consulta del catálogo de patologías (RF-64, RNF-01).
 *
 * Criterio de la ficha: consultas repetidas del catálogo completo y con filtros, con el volumen esperado en
 * producción: p95 <= 1 segundo.
 *
 * Endpoint real: GET /prediccion/patologias (filtros: especie_aplicable, solo_activas, solo_base) y el detalle
 * GET /prediccion/patologias/{id}.
 *
 * Mezcla de consultas por iteración (ponderada): catálogo completo, solo activas, solo base, por especie
 * ('TODAS' y la de una patología real) y detalle de una patología al azar. Carga: 10 consultas/s durante 2 min
 * (un catálogo se consulta al cargar pantallas, no en ráfaga). Ajustable con -e TASA=.. -e DURACION=..
 *
 * Umbrales: p95 < 1000 ms por tipo de consulta y global, sin errores.
 *
 * Ejecución (coordinar horario: carga TEST compartido):
 *   k6 run --summary-export=Resultados/resumen-TC-M04-016.json test_tc_m04_016_rendimiento_catalogo.js
 */
import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const TASA = Number(__ENV.TASA || 10);
const DURACION = __ENV.DURACION || '2m';

export const options = {
  scenarios: {
    consulta_catalogo: {
      executor: 'constant-arrival-rate', rate: TASA, timeUnit: '1s', duration: DURACION,
      preAllocatedVUs: 20, maxVUs: 60,
    },
  },
  thresholds: {
    'http_req_duration{consulta:completo}': ['p(95)<1000'],
    'http_req_duration{consulta:activas}': ['p(95)<1000'],
    'http_req_duration{consulta:base}': ['p(95)<1000'],
    'http_req_duration{consulta:especie}': ['p(95)<1000'],
    'http_req_duration{consulta:detalle}': ['p(95)<1000'],
    'http_req_duration{tipo:catalogo}': ['p(95)<1000'],
    http_req_failed: ['rate==0'],
    checks: ['rate==1'],
  },
};

export function setup() {
  const login = http.post(`${BASE_URL}/sesiones/`, JSON.stringify({
    correo_electronico: __ENV.CORREO || 'admin@pecuaria.co', contrasena: __ENV.CONTRASENA || 'Test1234!',
  }), { headers: { 'Content-Type': 'application/json' } });
  check(login, { 'setup: login (200)': (r) => r.status === 200 });
  const token = login.json('token');
  const catalogo = http.get(`${BASE_URL}/prediccion/patologias`, { headers: { Authorization: `Bearer ${token}` } });
  check(catalogo, { 'setup: catálogo disponible (200)': (r) => r.status === 200 });
  const items = catalogo.json('items') || [];
  if (!items.length) throw new Error('setup: el catálogo de patologías está vacío');
  const especies = [...new Set(items.map((p) => String(p.especie_aplicable)).filter((e) => e !== 'TODAS'))];
  console.log(`Catálogo: ${items.length} patologías; ${especies.length} especies con patologías propias`);
  return { token, ids: items.map((p) => p.id_patologia), especie: especies[0] || 'TODAS' };
}

const CONSULTAS = [
  // [etiqueta, peso, ruta]
  ['completo', 4, () => '/prediccion/patologias'],
  ['activas', 2, () => '/prediccion/patologias?solo_activas=true'],
  ['base', 1, () => '/prediccion/patologias?solo_base=true'],
  ['especie', 2, (d) => `/prediccion/patologias?especie_aplicable=${Math.random() < 0.5 ? 'TODAS' : d.especie}`],
  ['detalle', 1, (d) => `/prediccion/patologias/${d.ids[Math.floor(Math.random() * d.ids.length)]}`],
];
const RULETA = CONSULTAS.flatMap((c) => Array(c[1]).fill(c));

export default function (data) {
  const [etiqueta, , ruta] = RULETA[Math.floor(Math.random() * RULETA.length)];
  const r = http.get(`${BASE_URL}${ruta(data)}`, {
    headers: { Authorization: `Bearer ${data.token}` },
    tags: { tipo: 'catalogo', consulta: etiqueta },
  });
  check(r, { [`TC-M04-016 ${etiqueta}: 200`]: (x) => x.status === 200 });
}
