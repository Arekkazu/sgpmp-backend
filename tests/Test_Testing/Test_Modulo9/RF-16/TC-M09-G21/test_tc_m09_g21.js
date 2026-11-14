import http from 'k6/http';
import { check } from 'k6';
import { Trend } from 'k6/metrics';

// Métricas de tendencia personalizadas para obtener el desglose exacto por endpoint
const duracionCiclos = new Trend('duracion_ciclos');
const duracionPatologias = new Trend('duracion_patologias');
const duracionMetricas = new Trend('duracion_metricas');

export const options = {
  vus: 1,
  iterations: 10,
  thresholds: {
    http_req_duration: ['p(95)<2000'], // Umbral global
    duracion_ciclos: ['p(95)<2000'],   // Umbral desglosado Etapas
    duracion_patologias: ['p(95)<2000'],// Umbral desglosado Patologías
    duracion_metricas: ['p(95)<2000'],  // Umbral desglosado Métricas
  },
};

const BASE_URL = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';

export function setup() {
  // Autenticación previa en setup() para no contaminar la medición con la latencia del login
  const loginPayload = JSON.stringify({
    correo_electronico: 'admin@pecuaria.co',
    contrasena: 'Test1234!',
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };

  const loginRes = http.post(`${BASE_URL}/sesiones/`, loginPayload, params);
  check(loginRes, {
    'Setup Login Admin exitoso (HTTP 200)': (r) => r.status === 200,
  });

  const token = loginRes.json('token');
  return { token: token };
}

export default function (data) {
  const params = {
    headers: {
      'Authorization': `Bearer ${data.token}`,
      'Content-Type': 'application/json',
    },
  };

  // 1. Consulta de catálogo de etapas productivas (GET /configuracion/ciclos?id_especie=4)
  const resCiclos = http.get(`${BASE_URL}/configuracion/ciclos?id_especie=4&solo_activas=false`, params);
  duracionCiclos.add(resCiclos.timings.duration);
  check(resCiclos, {
    'Etapas HTTP 200 OK': (r) => r.status === 200,
    'Etapas latencia < 5000ms': (r) => r.timings.duration < 5000,
  });

  // 2. Consulta de catálogo de patologías (GET /configuracion/patologias?id_especie=4)
  const resPatologias = http.get(`${BASE_URL}/configuracion/patologias?id_especie=4&solo_activas=false`, params);
  duracionPatologias.add(resPatologias.timings.duration);
  check(resPatologias, {
    'Patologías HTTP 200 OK': (r) => r.status === 200,
    'Patologías latencia < 5000ms': (r) => r.timings.duration < 5000,
  });

  // 3. Consulta de catálogo de métricas de producción (GET /configuracion/metricas?id_especie=4)
  const resMetricas = http.get(`${BASE_URL}/configuracion/metricas?id_especie=4&solo_activas=false`, params);
  duracionMetricas.add(resMetricas.timings.duration);
  check(resMetricas, {
    'Métricas HTTP 200 OK': (r) => r.status === 200,
    'Métricas latencia < 5000ms': (r) => r.timings.duration < 5000,
  });
}
