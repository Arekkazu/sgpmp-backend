/**
 * TC-M02-G94 / TC-M02-158 - RF-50: rate limiting por modulo consumidor.
 *
 * ⚠ ESTE SCRIPT NO SE EJECUTO. El sub-caso quedo BLOQUEADO.
 *
 * TC-M02-158 exige, como precondicion fijada por la matriz, "M04 autenticado" y, para
 * demostrar que el limite es POR MODULO, un segundo modulo de control (M06 u M08). El
 * sistema no implementa identidades de modulo consumidor: la API autentica con un JWT de
 * usuario y autoriza por rol (require_permission(29, 2)); no existe catalogo de modulos,
 * ni de scopes, ni credenciales de servicio. Ver §4 del informe.
 *
 * Ademas, el endpoint de exposicion de RF-50 no aplica ningun limitador: el proyecto tiene
 * un helper `src/shared/rate_limit.py`, pero el router de activos biologicos no lo importa
 * ni lo usa, y el contrato no declara 429.
 *
 * El script se entrega listo para ejecutarse en cuanto Desarrollo Backend provea las
 * credenciales de M04 y del modulo de control. Deliberadamente:
 *   · emite 101 solicitudes, el minimo que supera el umbral de 100/min (no una carga masiva);
 *   · registra numero secuencial, status, duracion y cabeceras de cuota de cada respuesta;
 *   · se detiene en cuanto obtiene evidencia suficiente del 429;
 *   · lanza al final una consulta con el modulo de control para verificar el aislamiento.
 *
 * Ejecucion (cuando existan las credenciales):
 *   k6 run --summary-export=Resultados/reporte_tc_m02_g94_k6.json \
 *          -e TOKEN_M04=<token> -e TOKEN_CONTROL=<token> test_tc_m02_g94_rate_limit.js
 */

import http from 'k6/http';
import { check } from 'k6';
import { Counter, Trend } from 'k6/metrics';

const BASE = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const ACTIVO = 279;
const RUTA = `${BASE}/activos-biologicos/${ACTIVO}/datos-consolidados?tipo_dato=metricas`;

// RF-50: 100 solicitudes por minuto y por modulo.
const LIMITE = 100;
const TOTAL = 101;          // el minimo que supera el umbral (§6.7)
const VENTANA_MS = 60000;

const respuestas200 = new Counter('rf50_respuestas_200');
const respuestas429 = new Counter('rf50_respuestas_429');
const respuestasOtras = new Counter('rf50_respuestas_otras');
const duracion = new Trend('rf50_duracion_ms');

export const options = {
  scenarios: {
    rafaga_m04: {
      executor: 'shared-iterations',
      vus: 5,
      iterations: TOTAL,
      maxDuration: '60s',
    },
  },
  // Sin reintentos automaticos: cada iteracion es exactamente una solicitud (A15).
  noConnectionReuse: false,
  thresholds: {
    // R2: al exceder la cuota debe aparecer al menos un 429.
    rf50_respuestas_429: ['count>0'],
  },
};

const secuencia = [];

export function setup() {
  const tokenM04 = __ENV.TOKEN_M04;
  const tokenControl = __ENV.TOKEN_CONTROL;
  if (!tokenM04 || !tokenControl) {
    throw new Error(
      'BLOQUEADO: faltan las credenciales de M04 y/o del modulo de control. ' +
      'Este script no puede ejecutarse hasta que existan identidades de modulo consumidor.'
    );
  }
  // V2 - el request base debe responder 200 antes de iniciar la rafaga, fuera de la
  // ventana de medicion, para que un 429 posterior no se confunda con un request invalido.
  const verificacion = http.get(RUTA, { headers: { Authorization: `Bearer ${tokenM04}` } });
  if (verificacion.status !== 200) {
    throw new Error(`El request base no responde 200 (HTTP ${verificacion.status}); revisar activo, scope o parametros.`);
  }
  return { tokenM04, tokenControl, inicio: Date.now() };
}

export default function (datos) {
  const n = __ITER + 1;
  const respuesta = http.get(RUTA, {
    headers: { Authorization: `Bearer ${datos.tokenM04}` },
    tags: { secuencia: String(n) },
  });

  duracion.add(respuesta.timings.duration);
  if (respuesta.status === 200) respuestas200.add(1);
  else if (respuesta.status === 429) respuestas429.add(1);
  else respuestasOtras.add(1);

  // R5 - se conservan las cabeceras de cuota si el backend las expone.
  secuencia.push({
    n,
    status: respuesta.status,
    ms: Math.round(respuesta.timings.duration),
    t_relativo_ms: Date.now() - datos.inicio,
    retry_after: respuesta.headers['Retry-After'] || null,
    ratelimit: respuesta.headers['RateLimit-Remaining'] || respuesta.headers['X-RateLimit-Remaining'] || null,
  });

  check(respuesta, {
    // R1/R2: dentro del umbral se responde normalmente; al excederlo, 429.
    'dentro del umbral responde 200': (r) => n > LIMITE || r.status === 200,
    'al exceder el umbral responde 429': (r) => n <= LIMITE || r.status === 429,
    // R4: el error de cuota no debe filtrar datos del activo.
    'el 429 no expone datos del activo': (r) => r.status !== 429 || !r.body.includes('QAJE-CREC-OK'),
  });
}

export function teardown(datos) {
  // R6 - aislamiento por modulo: con la cuota de M04 agotada, el modulo de control debe
  // seguir respondiendo con normalidad. Si tambien recibiera 429, el limite seria global
  // y el sub-caso quedaria RECHAZADO.
  const control = http.get(RUTA, { headers: { Authorization: `Bearer ${datos.tokenControl}` } });
  check(control, {
    'R6: el modulo de control conserva acceso normal': (r) => r.status === 200,
    'R6: el modulo de control no recibe 429 por la cuota de M04': (r) => r.status !== 429,
  });
  console.log(JSON.stringify({
    secuencia,
    control: { status: control.status, retry_after: control.headers['Retry-After'] || null },
  }));
}
