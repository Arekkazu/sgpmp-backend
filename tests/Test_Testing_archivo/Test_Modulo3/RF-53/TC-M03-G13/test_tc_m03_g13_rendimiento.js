/*
 * TC-M03-G13 - Rendimiento y capacidad de ingesta (RF-53, CU01).
 *
 *   TC-M03-027  Disponibilidad del dato en la consulta de tiempo real (RF-58) <= 500 ms (p95), carga normal.
 *   TC-M03-028  Carga objetivo del MVP: 50 msg/s sostenidos durante 5 min, sin pérdidas ni 5xx.
 *   TC-M03-061  Saturación (flujo alterno E15): 200 msg/s con mezcla de variables críticas (biométricas)
 *               y rutinarias (ambientales); sin pérdidas ni 5xx, y los críticos con prioridad.
 *
 * Endpoints reales: POST /iot/telemetria (ingesta, sin JWT; identidad = device_id + sensor_id + access_key)
 * y GET /iot/monitoreo/dashboard/{id_infraestructura} (estado actual por sensor, RF-58).
 *
 * El setup() crea datos propios: finca, especie, galpón, un dispositivo ambiental con 10 sensores de
 * temperatura, un dispositivo biométrico con 10 sensores de frecuencia cardíaca y un sensor dedicado a
 * TC-M03-027. El teardown() verifica en el historial RF-59 que no se perdieron lecturas.
 *
 * Notas del código actual (para interpretar 061): la ingesta es síncrona (no hay cola ni prioridad por
 * criticidad); la "priorización" se evalúa comparando la latencia p95 de críticos vs rutinarios, que se
 * imprime al final. Confirmar con Desarrollo si la priorización entra en el MVP (lo pide la ficha).
 *
 * Ejecución (un escenario por corrida; 028 y 061 cargan el TEST compartido: coordinar horario con el equipo):
 *   k6 run -e ESCENARIO=027 test_tc_m03_g13_rendimiento.js
 *   k6 run -e ESCENARIO=028 --summary-export=Resultados/resumen-TC-M03-028.json test_tc_m03_g13_rendimiento.js
 *   k6 run -e ESCENARIO=061 --summary-export=Resultados/resumen-TC-M03-061.json test_tc_m03_g13_rendimiento.js
 */
import http from 'k6/http';
import exec from 'k6/execution';
import { check, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.2/index.js';

const BASE_URL = __ENV.BASE_URL || 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const ESCENARIO = __ENV.ESCENARIO || '027';
const N_SENSORES = 10; // por tipo (ambiental / biométrico)

// --------------------------------------------------------------------------- métricas
const disponibilidad = new Trend('tc_m03_027_disponibilidad_ms', true);
const latenciaCritica = new Trend('tc_m03_061_latencia_critica_ms', true);
const latenciaRutinaria = new Trend('tc_m03_061_latencia_rutinaria_ms', true);
const ingestasOk = new Counter('ingestas_ok');
const errores5xx = new Counter('errores_5xx');
const noDisponible = new Counter('tc_m03_027_no_disponible');

// --------------------------------------------------------------------------- escenarios
const ESCENARIOS = {
  '027': {
    executor: 'constant-vus', vus: 1, duration: '2m', exec: 'disponibilidad027',
  },
  '028': {
    executor: 'constant-arrival-rate', rate: 50, timeUnit: '1s', duration: '5m',
    preAllocatedVUs: 60, maxVUs: 150, exec: 'carga028',
  },
  '061': {
    executor: 'ramping-arrival-rate', startRate: 50, timeUnit: '1s',
    preAllocatedVUs: 200, maxVUs: 600, exec: 'saturacion061',
    stages: [
      { target: 200, duration: '30s' }, // subida desde la carga MVP
      { target: 200, duration: '2m' },  // saturación sostenida
      { target: 0, duration: '15s' },
    ],
  },
};

const UMBRALES = {
  '027': {
    tc_m03_027_disponibilidad_ms: ['p(95)<500'],
    tc_m03_027_no_disponible: ['count==0'],
    errores_5xx: ['count==0'],
  },
  '028': {
    errores_5xx: ['count==0'],
    http_req_failed: ['rate==0'],
    dropped_iterations: ['count==0'],
    'http_req_duration{tipo:ingesta}': ['p(95)<500'],
    checks: ['rate==1'],
  },
  '061': {
    errores_5xx: ['count==0'],
    http_req_failed: ['rate==0'],
    dropped_iterations: ['count==0'],
    tc_m03_061_latencia_critica_ms: ['p(95)<500'],
  },
};

export const options = {
  scenarios: { [`tc_m03_${ESCENARIO}`]: ESCENARIOS[ESCENARIO] },
  thresholds: UMBRALES[ESCENARIO],
  setupTimeout: '3m',
  teardownTimeout: '3m',
};

// --------------------------------------------------------------------------- utilidades
const JSON_HEADERS = { 'Content-Type': 'application/json' };

function auth(token) {
  return { headers: { ...JSON_HEADERS, Authorization: `Bearer ${token}` } };
}

function crear(token, ruta, cuerpo, campo, descripcion) {
  const r = http.post(`${BASE_URL}${ruta}`, JSON.stringify(cuerpo), auth(token));
  const ok = check(r, { [`setup: ${descripcion} (201)`]: (x) => x.status === 201 });
  if (!ok) {
    throw new Error(`setup falló en "${descripcion}": HTTP ${r.status} ${r.body}`);
  }
  return r.json(campo);
}

function sufijo() {
  const letras = 'abcdefghijklmnopqrstuvwxyz';
  let s = '';
  for (let i = 0; i < 8; i++) s += letras.charAt(Math.floor(Math.random() * letras.length));
  return s;
}

function crearDispositivoConSensores(token, idArea, tipo, etiqueta, categoria, n, suf) {
  const disp = http.post(`${BASE_URL}/configuracion/dispositivos-iot`, JSON.stringify({
    serial: `M03-G13-${etiqueta}-${suf}`,
    descripcion: `Nodo ${etiqueta} TC-M03-G13`,
    id_infraestructura: idArea,
    id_tipo_dispositivo: tipo,
    es_activo: true,
  }), auth(token));
  check(disp, { [`setup: dispositivo ${etiqueta} (201)`]: (x) => x.status === 201 });
  if (disp.status !== 201) throw new Error(`setup: dispositivo ${etiqueta} HTTP ${disp.status} ${disp.body}`);
  const deviceId = disp.json('id_dispositivo_iot');
  const sensores = [];
  for (let i = 0; i < n; i++) {
    sensores.push(crear(token, `/configuracion/dispositivos-iot/${deviceId}/sensores`,
      { nombre: `Sensor ${etiqueta} ${i + 1} ${suf}`, categoria: categoria }, 'id_sensores',
      `sensor ${etiqueta} ${i + 1}`));
  }
  return { device_id: deviceId, access_key: disp.json('serial'), sensores: sensores };
}

function lectura(disp, sensorId, tipo, unidad, valor, ts) {
  return JSON.stringify({
    device_id: disp.device_id,
    sensor_id: sensorId,
    tipo_variable: tipo,
    valor: valor,
    unidad: unidad,
    timestamp_captura: ts,
    timestamp_envio: new Date().toISOString(),
    origen: 'TIEMPO_REAL',
    access_key: disp.access_key,
  });
}

function enviar(cuerpo, tags) {
  const r = http.post(`${BASE_URL}/iot/telemetria`, cuerpo, { headers: JSON_HEADERS, tags: tags });
  if (r.status >= 500) errores5xx.add(1, tags);
  if (r.status === 201) ingestasOk.add(1, tags);
  return r;
}

// Timestamp único por iteración: base del test + número de iteración (ms). Garantiza que dos mensajes del
// mismo sensor nunca compartan clave (sensor, variable, timestamp, origen) y así no hay 409 por choque.
function tsUnico(data) {
  return new Date(data.ts_base + exec.scenario.iterationInTest).toISOString();
}

// --------------------------------------------------------------------------- setup / teardown
export function setup() {
  const login = http.post(`${BASE_URL}/sesiones/`, JSON.stringify({
    correo_electronico: 'admin@pecuaria.co', contrasena: 'Test1234!',
  }), { headers: JSON_HEADERS });
  check(login, { 'setup: login Administrador (200)': (r) => r.status === 200 });
  const token = login.json('token');
  const suf = sufijo();

  const idFinca = crear(token, '/configuracion/fincas', {
    nombre: `Finca Rendimiento Telemetria ${suf}`,
    ubicacion: { departamento: 'Huila', municipio: 'Neiva', vereda: 'El Caguan', latitud: '2.93', longitud: '-75.28' },
    tamano_h: '10.0',
  }, 'id_finca', 'finca');
  const idEspecie = crear(token, '/configuracion/especies', {
    nombre: `Porcinos Rendimiento ${suf}`, descripcion: 'Especie de prueba TC-M03-G13',
    densidad_maxima_por_especie: '50.00', grupo_manejo: 'PORCINOS',
  }, 'id_especie', 'especie');
  const idArea = crear(token, '/configuracion/infraestructuras', {
    nombre_infraestructura: `Galpon Rendimiento ${suf}`, tipo_area: 'Galpón', superficie: '500.00',
    finca_id: idFinca, especie_id: idEspecie,
  }, 'id_infraestructura', 'galpón');

  const ambiental = crearDispositivoConSensores(token, idArea, 3, 'AMB', 'TEMPERATURA', N_SENSORES, suf);
  const biometrico = crearDispositivoConSensores(token, idArea, 1, 'BIO', null, N_SENSORES, suf);
  const dedicado = crearDispositivoConSensores(token, idArea, 3, 'LAT', 'TEMPERATURA', 1, suf);

  // Base de timestamps una hora atrás: con <= 1 lectura por ms, cubre 3.6 M iteraciones sin llegar al presente.
  const tsBase = Date.now() - 3600 * 1000;
  return {
    token, idArea, ambiental, biometrico, dedicado,
    ts_base: tsBase,
    desde: new Date(tsBase - 86400000).toISOString().slice(0, 10),
    hasta: new Date(Date.now() + 86400000).toISOString().slice(0, 10),
  };
}

export function teardown(data) {
  if (ESCENARIO === '027') return;
  // Sin pérdidas: el historial del área debe tener exactamente las lecturas planificadas por el escenario.
  const esperado = ESCENARIO === '028' ? 50 * 300 : null;
  const r = http.get(
    `${BASE_URL}/iot/monitoreo/historial?fecha_inicio=${data.desde}&fecha_fin=${data.hasta}` +
    `&id_infraestructura=${data.idArea}&por_pagina=1`, auth(data.token));
  const total = r.status === 200 ? r.json('total') : -1;
  console.log(`TC-M03-${ESCENARIO}: lecturas persistidas en el área ${data.idArea}: ${total}`);
  if (esperado !== null) {
    check(r, { [`TC-M03-028: sin pérdidas (${esperado} lecturas persistidas)`]: () => total === esperado });
  } else {
    check(r, { 'TC-M03-061: historial consultable tras la saturación': () => total > 0 });
  }
}

// --------------------------------------------------------------------------- TC-M03-027
export function disponibilidad027(data) {
  const sensor = data.dedicado.sensores[0];
  const ts = new Date(Date.now() - 1000).toISOString();
  const valor = Number((20 + Math.random() * 10).toFixed(2));
  const r = enviar(lectura(data.dedicado, sensor, 'TEMPERATURA_AMBIENTAL', '°C', valor, ts), { tipo: 'ingesta' });
  if (!check(r, { 'TC-M03-027: ingesta aceptada (201)': (x) => x.status === 201 })) {
    sleep(1);
    return;
  }

  // Desde la respuesta de ingesta hasta que el dashboard RF-58 muestra este timestamp para el sensor.
  const inicio = Date.now();
  let visible = false;
  while (Date.now() - inicio < 5000) {
    const d = http.get(`${BASE_URL}/iot/monitoreo/dashboard/${data.idArea}?por_pagina=50`,
      { ...auth(data.token), tags: { tipo: 'consulta' } });
    if (d.status >= 500) errores5xx.add(1);
    if (d.status === 200) {
      const s = (d.json('sensores') || []).find((x) => x.id_sensor === sensor);
      if (s && s.ultimo_timestamp_captura && Date.parse(s.ultimo_timestamp_captura) === Date.parse(ts)) {
        visible = true;
        break;
      }
    }
    sleep(0.05);
  }
  if (visible) {
    disponibilidad.add(Date.now() - inicio);
  } else {
    noDisponible.add(1);
  }
  check(null, { 'TC-M03-027: dato visible en la consulta de tiempo real': () => visible });
  sleep(1); // ~1 lectura/s: carga normal
}

// --------------------------------------------------------------------------- TC-M03-028
export function carga028(data) {
  const i = exec.scenario.iterationInTest;
  const usarBio = i % 2 === 1;
  const disp = usarBio ? data.biometrico : data.ambiental;
  const sensor = disp.sensores[Math.floor(i / 2) % N_SENSORES];
  const cuerpo = usarBio
    ? lectura(disp, sensor, 'FRECUENCIA_CARDIACA', 'bpm', 60 + (i % 40), tsUnico(data))
    : lectura(disp, sensor, 'TEMPERATURA_AMBIENTAL', '°C', 20 + (i % 10), tsUnico(data));
  const r = enviar(cuerpo, { tipo: 'ingesta' });
  check(r, { 'TC-M03-028: mensaje procesado (201)': (x) => x.status === 201 });
}

// --------------------------------------------------------------------------- TC-M03-061
export function saturacion061(data) {
  const i = exec.scenario.iterationInTest;
  const critico = i % 2 === 1;
  const disp = critico ? data.biometrico : data.ambiental;
  const sensor = disp.sensores[Math.floor(i / 2) % N_SENSORES];
  const cuerpo = critico
    ? lectura(disp, sensor, 'FRECUENCIA_CARDIACA', 'bpm', 60 + (i % 40), tsUnico(data))
    : lectura(disp, sensor, 'TEMPERATURA_AMBIENTAL', '°C', 20 + (i % 10), tsUnico(data));
  const tags = { tipo: 'ingesta', criticidad: critico ? 'critica' : 'rutinaria' };
  const r = enviar(cuerpo, tags);
  (critico ? latenciaCritica : latenciaRutinaria).add(r.timings.duration);
  check(r, {
    'TC-M03-061: mensaje aceptado sin pérdida (201/202)': (x) => x.status === 201 || x.status === 202,
    'TC-M03-061: sin error 5xx': (x) => x.status < 500,
  });
}

// --------------------------------------------------------------------------- resumen
export function handleSummary(data) {
  let extra = '';
  if (ESCENARIO === '061') {
    const p95 = (m) => (data.metrics[m] ? data.metrics[m].values['p(95)'] : NaN);
    const crit = p95('tc_m03_061_latencia_critica_ms');
    const rut = p95('tc_m03_061_latencia_rutinaria_ms');
    const prioriza = crit < rut;
    extra = `\nTC-M03-061 priorización: p95 críticos ${crit.toFixed(1)} ms vs rutinarios ${rut.toFixed(1)} ms -> ` +
      `${prioriza ? 'los críticos se atienden antes' : 'SIN priorización observable'}\n`;
  }
  return { stdout: textSummary(data, { indent: ' ', enableColors: true }) + extra };
}
