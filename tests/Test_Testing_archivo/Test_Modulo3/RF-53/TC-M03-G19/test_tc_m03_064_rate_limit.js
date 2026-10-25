/*
 * TC-M03-064 - Limitar tasa de ingesta por dispositivo (RF-53, OWASP API4).
 *
 * Un único device_id envía 50 lecturas/s durante 3 min (debería enviar cada 5 min: ~15.000x su frecuencia)
 * mientras otro dispositivo de la "flota" envía a ritmo normal (1 cada 5 s).
 *
 * Esperado según la ficha:
 *   - el dispositivo abusivo recibe throttling (429 o equivalente) al superar un umbral por dispositivo;
 *   - el dispositivo de la flota no se degrada: todas sus lecturas 201 y latencia p95 < 500 ms;
 *   - sin errores 5xx.
 * El registro del evento en bitácora (modulo3.bitacora_ingest) no tiene endpoint de consulta.
 *
 * Nota del código actual: existe un limitador reutilizable (src/shared/rate_limit.py) pero cuenta por
 * usuario del JWT y no está aplicado a POST /iot/telemetria, que no usa JWT. Confirmar con Desarrollo si el
 * rate limiting por device_id está en el MVP (lo pide la ficha).
 *
 * Ejecución (carga el TEST compartido: coordinar horario):
 *   k6 run --summary-export=Resultados/resumen-TC-M03-064.json test_tc_m03_064_rate_limit.js
 */
import http from 'k6/http';
import exec from 'k6/execution';
import { check } from 'k6';
import { Counter, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';

const respuestas429 = new Counter('tc_m03_064_respuestas_429');
const aceptadasAbuso = new Counter('tc_m03_064_aceptadas_abusivo');
const errores5xx = new Counter('errores_5xx');
const latenciaFlota = new Trend('tc_m03_064_latencia_flota_ms', true);
const fallasFlota = new Counter('tc_m03_064_fallas_flota');

export const options = {
  scenarios: {
    abuso: {
      executor: 'constant-arrival-rate', rate: 50, timeUnit: '1s', duration: '3m',
      preAllocatedVUs: 60, maxVUs: 150, exec: 'abusivo',
    },
    flota: {
      executor: 'constant-arrival-rate', rate: 1, timeUnit: '5s', duration: '3m',
      preAllocatedVUs: 2, maxVUs: 5, exec: 'flota',
    },
  },
  thresholds: {
    tc_m03_064_respuestas_429: ['count>0'],          // hubo throttling al dispositivo abusivo
    errores_5xx: ['count==0'],
    tc_m03_064_fallas_flota: ['count==0'],          // la flota no fue afectada
    tc_m03_064_latencia_flota_ms: ['p(95)<500'],
  },
  setupTimeout: '2m',
};

const JSON_HEADERS = { 'Content-Type': 'application/json' };

function auth(token) {
  return { headers: { ...JSON_HEADERS, Authorization: `Bearer ${token}` } };
}

function crear(token, ruta, cuerpo, campo, descripcion) {
  const r = http.post(`${BASE_URL}${ruta}`, JSON.stringify(cuerpo), auth(token));
  if (!check(r, { [`setup: ${descripcion} (201)`]: (x) => x.status === 201 })) {
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

export function setup() {
  const login = http.post(`${BASE_URL}/sesiones/`, JSON.stringify({
    correo_electronico: 'admin@pecuaria.co', contrasena: 'Test1234!',
  }), { headers: JSON_HEADERS });
  check(login, { 'setup: login Administrador (200)': (r) => r.status === 200 });
  const token = login.json('token');
  const suf = sufijo();

  const idFinca = crear(token, '/configuracion/fincas', {
    nombre: `Finca Limite Telemetria ${suf}`,
    ubicacion: { departamento: 'Huila', municipio: 'Neiva', vereda: 'El Caguan', latitud: '2.93', longitud: '-75.28' },
    tamano_h: '10.0',
  }, 'id_finca', 'finca');
  const idEspecie = crear(token, '/configuracion/especies', {
    nombre: `Porcinos Limite ${suf}`, descripcion: 'Especie de prueba TC-M03-064',
    densidad_maxima_por_especie: '50.00', grupo_manejo: 'PORCINOS',
  }, 'id_especie', 'especie');
  const idArea = crear(token, '/configuracion/infraestructuras', {
    nombre_infraestructura: `Galpon Limite ${suf}`, tipo_area: 'Galpón', superficie: '500.00',
    finca_id: idFinca, especie_id: idEspecie,
  }, 'id_infraestructura', 'galpón');

  const dispositivos = {};
  for (const etiqueta of ['ABUSO', 'FLOTA']) {
    const r = http.post(`${BASE_URL}/configuracion/dispositivos-iot`, JSON.stringify({
      serial: `M03-064-${etiqueta}-${suf}`, descripcion: `Nodo ${etiqueta} TC-M03-064`,
      id_infraestructura: idArea, id_tipo_dispositivo: 2, es_activo: true, // NODO_BAJO_CONSUMO: >= 15 min entre capturas
    }), auth(token));
    if (!check(r, { [`setup: dispositivo ${etiqueta} (201)`]: (x) => x.status === 201 })) {
      throw new Error(`setup: dispositivo ${etiqueta} HTTP ${r.status} ${r.body}`);
    }
    const deviceId = r.json('id_dispositivo_iot');
    dispositivos[etiqueta] = {
      device_id: deviceId,
      access_key: r.json('serial'),
      sensor_id: crear(token, `/configuracion/dispositivos-iot/${deviceId}/sensores`,
        { nombre: `Sensor ${etiqueta} ${suf}`, categoria: 'TEMPERATURA' }, 'id_sensores', `sensor ${etiqueta}`),
    };
  }
  return { dispositivos, ts_base: Date.now() - 3600 * 1000 };
}

function lectura(d, ts) {
  return JSON.stringify({
    device_id: d.device_id, sensor_id: d.sensor_id, tipo_variable: 'TEMPERATURA_AMBIENTAL',
    valor: 25.0, unidad: '°C', timestamp_captura: ts, origen: 'TIEMPO_REAL', access_key: d.access_key,
    frecuencia_muestreo: 5,
  });
}

export function abusivo(data) {
  // Timestamp único por iteración (base + n ms) para que ningún 409 por duplicado se confunda con throttling.
  const ts = new Date(data.ts_base + exec.scenario.iterationInTest).toISOString();
  const r = http.post(`${BASE_URL}/iot/telemetria`, lectura(data.dispositivos.ABUSO, ts),
    { headers: JSON_HEADERS, tags: { dispositivo: 'abusivo' } });
  if (r.status === 429) respuestas429.add(1);
  if (r.status === 201) aceptadasAbuso.add(1);
  if (r.status >= 500) errores5xx.add(1);
  check(r, { 'TC-M03-064 abusivo: sin error 5xx': (x) => x.status < 500 });
}

export function flota(data) {
  const ts = new Date(Date.now() - 1000).toISOString();
  const r = http.post(`${BASE_URL}/iot/telemetria`, lectura(data.dispositivos.FLOTA, ts),
    { headers: JSON_HEADERS, tags: { dispositivo: 'flota' } });
  latenciaFlota.add(r.timings.duration);
  if (r.status !== 201) fallasFlota.add(1);
  if (r.status >= 500) errores5xx.add(1);
  check(r, { 'TC-M03-064 flota: lectura normal aceptada (201)': (x) => x.status === 201 });
}
