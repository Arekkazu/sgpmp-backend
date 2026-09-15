/**
 * TC-M02-G16 / TC-M02-032 — rate limiting POST /activos-biologicos
 *
 * 101 POST invalidos (sin crear activos) en < 60 s.
 * Credenciales: SGPMP_TEST_PASSWORD o CONTRASENA en el entorno. No hardcodear.
 *
 * k6 run --insecure-skip-tls-verify --summary-export=Resultados/TC-M02-G16-k6.json tc_m02_g16_rate_limit.js
 */
import http from 'k6/http';
import { Counter } from 'k6/metrics';

const BASE = __ENV.BASE_URL || 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const CORREO = __ENV.SGPMP_TEST_USER || 'admin@pecuaria.co';
const PASS = __ENV.SGPMP_TEST_PASSWORD || __ENV.CONTRASENA || '';
const TOTAL = 101;

const c429 = new Counter('g16_http_429');
const cOtras = new Counter('g16_http_otras');

export const options = {
  insecureSkipTLSVerify: true,
  scenarios: {
    rafaga: {
      executor: 'shared-iterations',
      vus: 1,
      iterations: TOTAL,
      maxDuration: '55s',
    },
  },
  thresholds: {
    g16_http_429: ['count>0'],
  },
};

export function setup() {
  if (!PASS) {
    throw new Error('BLOQUEADO: definir SGPMP_TEST_PASSWORD o CONTRASENA');
  }
  const login = http.post(`${BASE}/sesiones/`, JSON.stringify({
    correo_electronico: CORREO,
    contrasena: PASS,
  }), { headers: { 'Content-Type': 'application/json' } });
  if (login.status !== 200) {
    throw new Error(`Login HTTP ${login.status}`);
  }
  const body = login.json();
  const token = body.token || (body.data && body.data.token);
  if (!token) {
    throw new Error('Login sin token');
  }
  return { token };
}

export default function (data) {
  const res = http.post(`${BASE}/activos-biologicos`, JSON.stringify({}), {
    headers: {
      Authorization: `Bearer ${data.token}`,
      'Content-Type': 'application/json',
    },
  });
  if (res.status === 429) {
    c429.add(1);
  } else {
    cOtras.add(1);
  }
}
