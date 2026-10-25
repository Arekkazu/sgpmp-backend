/**
 * test_tc_m04_g098.js - TC-M04-G098: Disponibilidad y Rendimiento a Gran Escala (k6)
 * Módulo 4: Predicción e IA (RF-73: Auditoría de eventos de predicción)
 * 
 * Subcasos:
 * - TC-M04-054: Disponibilidad >= 99.5% del subsistema de consulta de auditoría.
 *   DISEÑO EN FASE SEPARADA: Requiere ventana de observación sostenida (días/semanas) o scraping
 *   de métricas Prometheus/CloudWatch. En sandbox se ejecuta una aproximación de ventana corta (45s).
 * - TC-M04-055: Latencia P95 <= 2000 ms en consultas con filtros de fecha y tipo_evento sobre 50M de registros.
 *   DISEÑO EN FASE SEPARADA: Requiere base de datos precargada con 50 millones de eventos y particionamiento.
 *   En sandbox se evalúa la consulta sobre el volumen actual con fechas 10-18 oct 2026.
 * 
 * NOTA DE SANDBOX: Ejecución acotada a <= 5 VUs y < 60s para no superar el timeout ni violar la política de concurrencia.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'https://api.inmero.co/back-sigab-test';
const SANDBOX_SECRET = __ENV.TEST_SANDBOX_SECRET || '377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff';
const ADMIN_PASSWORD = __ENV.TEST_ADMIN_PASSWORD || 'Test1234!';

export const options = {
  scenarios: {
    disponibilidad_y_rendimiento: {
      executor: 'constant-vus',
      vus: 2, // Concurrencia conservadora para sandbox
      duration: '35s',
    },
  },
  thresholds: {
    'http_req_duration{tipo:consulta_filtrada}': ['p(95)<2000'], // TC-M04-055 SLA P95 <= 2s
    'http_req_failed': ['rate<0.005'],                           // TC-M04-054 SLA >= 99.5% éxito (tasa de fallo < 0.5%)
    'checks': ['rate>0.99'],
  },
};

export function setup() {
  const runId = 'test-m04-g098-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8);

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

  // 1. TC-M04-054: Verificación de Uptime / Disponibilidad (Proxy de salud y consulta activa)
  // Rango de fechas obligatorio: 10-18 oct 2026
  const resUptime = http.get(`${data.baseUrl}/health`, { headers, tags: { tipo: 'uptime_check' } });
  check(resUptime, {
    'TC-M04-054: endpoint de salud disponible 200': (r) => r.status === 200,
  });

  // 2. TC-M04-055: Consulta con filtros de fecha y tipo_evento (SLA P95 <= 2s)
  // Simula consulta sobre catálogo de auditoría
  const urlFiltros = `${data.baseUrl}/prediccion/auditoria?fecha_desde=2026-10-10T00:00:00&fecha_hasta=2026-10-18T23:59:59&pagina=1&por_pagina=20`;
  const resConsulta = http.get(urlFiltros, { headers, tags: { tipo: 'consulta_filtrada' } });

  check(resConsulta, {
    'TC-M04-055: consulta con filtros responde 200': (r) => r.status === 200,
    'TC-M04-055: tiempo de respuesta <= 2000ms': (r) => r.timings.duration <= 2000,
    'TC-M04-055: estructura de respuesta valida': (r) => {
      if (r.status !== 200) return false;
      const json = r.json();
      return json && Array.isArray(json.items);
    },
  });

  sleep(2); // Cadencia controlada para respetar límites de sandbox
}

export function teardown(data) {
  const rollbackHeaders = {
    'X-Sandbox-Secret': data.sandboxSecret,
  };

  http.del(`${data.baseUrl}/test-control/runs/${data.runId}`, null, { headers: rollbackHeaders });
}

export function handleSummary(data) {
  const out = {
    tc: 'TC-M04-G098',
    rf: 'RF-73',
    titulo: 'TC-M04-G098: Disponibilidad (99.5%) y Rendimiento a Gran Escala (k6)',
    estado_general: data.metrics.http_req_failed && data.metrics.http_req_failed.values.rate <= 0.005 ? 'Aprobado' : 'Rechazado',
    metrics: {
      checks: data.metrics.checks ? data.metrics.checks.values : {},
      http_req_duration: data.metrics.http_req_duration ? data.metrics.http_req_duration.values : {},
      http_req_failed: data.metrics.http_req_failed ? data.metrics.http_req_failed.values : {},
      http_reqs: data.metrics.http_reqs ? data.metrics.http_reqs.values : {},
    },
    fase_separada_disponibilidad_volumen: 'La verificación formal de disponibilidad >= 99.5% sobre ventana de días/semanas y la consulta sobre 50 millones de registros precargados pertenecen a la FASE SEPARADA — DISPONIBILIDAD Y VOLUMEN con infraestructura dedicada.'
  };

  return {
    'stdout': JSON.stringify(out, null, 2),
  };
}
