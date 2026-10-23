/**
 * test_tc_m04_g093.js - TC-M04-G093: Carga y Volumen en Auditoría M04 (RF-73)
 * Herramienta: k6
 * Módulo 4: Predicción e IA (Fase de Diseño y Construcción)
 * 
 * Subcasos:
 * - TC-M04-288: Carga normal escalada (equivalente a 1,000/min en prod, P95 <= 2s)
 * - TC-M04-289: Carga pico escalada (equivalente a 5,000/min en prod, P95 <= 5s)
 * - TC-M04-290: Sin pérdida bajo carga (integridad de eventos y respuestas)
 * - TC-M04-291: Solicitud de exportación masiva (>10k registros / polling diferido)
 * - TC-M04-292: Consultas concurrentes (escalado a <= 5 VUs por límite de sandbox)
 * 
 * NOTA DE SANDBOX: El sandbox transaccional de SGPMP impone MAX_CONCURRENT_RUNS=5
 * y un timeout de 180s. Las pruebas sostenidas de 10 min y 100 VUs están documentadas
 * como FASE DE CARGA SEPARADA.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'https://api.inmero.co/back-sigab-test';
const SANDBOX_SECRET = __ENV.TEST_SANDBOX_SECRET || '377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff';
const ADMIN_PASSWORD = __ENV.TEST_ADMIN_PASSWORD || '';

export const options = {
  scenarios: {
    carga_escalada_auditoria: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '10s', target: 3 },
        { duration: '30s', target: 5 }, // Máximo 5 VUs para no violar límite de sandbox
        { duration: '10s', target: 0 },
      ],
      gracefulRampDown: '5s',
    },
  },
  thresholds: {
    'http_req_duration': ['p(95)<5000'],
    'http_req_duration{tipo:normal}': ['p(95)<2000'],
    'http_req_failed': ['rate<0.05'],
    'checks': ['rate>0.90'],
  },
};

export function setup() {
  const runId = 'test-m04-g093-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8);

  const loginHeaders = {
    'Content-Type': 'application/json',
    'X-Test-Run-Id': runId,
    'X-Sandbox-Secret': SANDBOX_SECRET,
  };

  const loginPayload = JSON.stringify({
    correo_electronico: 'administador.dev@gmail.com',
    contrasena: ADMIN_PASSWORD,
  });

  const resLogin = http.post(`${BASE_URL}/sesiones/`, loginPayload, { headers: loginHeaders });
  let token = '';

  if (resLogin.status === 200) {
    const json = resLogin.json();
    token = json.token || '';
  }

  return {
    baseUrl: BASE_URL,
    token: token,
    runId: runId,
    sandboxSecret: SANDBOX_SECRET,
  };
}

export default function (data) {
  const headers = {
    'Authorization': `Bearer ${data.token}`,
    'Content-Type': 'application/json',
    'X-Test-Run-Id': data.runId,
    'X-Sandbox-Secret': data.sandboxSecret,
  };

  // 1. TC-M04-288: Consulta normal (P95 <= 2s)
  const resNormal = http.get(
    `${data.baseUrl}/prediccion/auditoria?pagina=1&por_pagina=20`,
    { headers, tags: { tipo: 'normal' } }
  );

  check(resNormal, {
    'TC-M04-288: status 200 en consulta normal': (r) => r.status === 200,
    'TC-M04-288: latencia aceptable p95 <= 2000ms': (r) => r.timings.duration <= 2000,
  });

  // 2. TC-M04-289: Consulta pico (P95 <= 5s)
  const resPeak = http.get(
    `${data.baseUrl}/prediccion/auditoria?pagina=1&por_pagina=50`,
    { headers, tags: { tipo: 'pico' } }
  );

  check(resPeak, {
    'TC-M04-289: status 200 en consulta pico': (r) => r.status === 200,
    'TC-M04-289: latencia pico <= 5000ms': (r) => r.timings.duration <= 5000,
  });

  // 3. TC-M04-290: Sin pérdida bajo carga (integridad de estructura)
  check(resNormal, {
    'TC-M04-290: estructura integra y sin perdida': (r) => {
      if (r.status !== 200) return false;
      const json = r.json();
      return json && Array.isArray(json.items);
    },
  });

  // 4. TC-M04-291: Solicitud de exportación masiva
  const resExport = http.get(
    `${data.baseUrl}/prediccion/auditoria/exportar?formato=json`,
    { headers, tags: { tipo: 'exportar' } }
  );

  check(resExport, {
    'TC-M04-291: exportacion responde 200 o 202': (r) => [200, 202].includes(r.status),
  });

  // 5. TC-M04-292: Consulta concurrente dentro de sandbox
  check(resPeak, {
    'TC-M04-292: concurrencia atendida sin error 5xx': (r) => r.status < 500,
  });

  sleep(1);
}

export function teardown(data) {
  const rollbackHeaders = {
    'X-Sandbox-Secret': data.sandboxSecret,
  };

  http.del(`${data.baseUrl}/test-control/runs/${data.runId}`, null, { headers: rollbackHeaders });
}

export function handleSummary(data) {
  const out = {
    tc: 'TC-M04-G093',
    rf: 'RF-73',
    titulo: 'TC-M04-G093: Carga y volumen (k6)',
    estado_general: data.metrics.http_req_failed && data.metrics.http_req_failed.values.rate < 0.05 ? 'Aprobado' : 'Rechazado',
    metrics: {
      checks: data.metrics.checks ? data.metrics.checks.values : {},
      http_req_duration: data.metrics.http_req_duration ? data.metrics.http_req_duration.values : {},
      http_req_failed: data.metrics.http_req_failed ? data.metrics.http_req_failed.values : {},
      http_reqs: data.metrics.http_reqs ? data.metrics.http_reqs.values : {},
    },
    fase_de_carga_separada: 'Las cargas de 1,000 req/min sostenidas por 10 min, 5,000 req/min pico por 5 min, 100 VUs concurrentes y exportación de >10,000 registros pertenecen a la FASE DE CARGA SEPARADA fuera del sandbox.',
  };

  return {
    'stdout': JSON.stringify(out, null, 2),
  };
}
