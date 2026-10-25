import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    http_req_duration: ['p(100)<2000'], // Umbral estricto: tiempo de respuesta < 2000ms (2s)
  },
};

const BASE_URL = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';

export function setup() {
  // Autenticación previa para no contaminar la medición de rendimiento del catálogo
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
    'Login Admin exitoso (HTTP 200)': (r) => r.status === 200,
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

  // Medición de rendimiento de la consulta del catálogo de especies (GET /configuracion/especies)
  const res = http.get(`${BASE_URL}/configuracion/especies`, params);

  check(res, {
    'Consulta de catálogo responde HTTP 200 OK': (r) => r.status === 200,
    'Tiempo de respuesta < 2000ms': (r) => r.timings.duration < 2000,
  });
}
