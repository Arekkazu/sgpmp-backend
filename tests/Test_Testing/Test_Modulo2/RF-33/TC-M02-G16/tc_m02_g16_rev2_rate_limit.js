/**
 * TC-M02-G16 rev2 / TC-M02-032 — k6 POST /activos-biologicos (cuerpos validos).
 * Restaurar IDs creados con PATCH /estado INACTIVO (API oficial).
 * k6 no estaba en PATH en la corrida QA; la rafaga ejecutada es pytest.
 */
import http from 'k6/http';
import { Counter } from 'k6/metrics';

const BASE = __ENV.BASE_URL || 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const CORREO = __ENV.SGPMP_TEST_USER || 'productor@pecuaria.co';
const PASS = __ENV.SGPMP_TEST_PASSWORD || __ENV.CONTRASENA || '';
const TOTAL = Number(__ENV.G16_TOTAL || 101);
const ESPECIE = Number(__ENV.ESPECIE_ID || 5);
const INFRA = Number(__ENV.INFRA_ID || 3);
const STAMP = `${Date.now()}`.slice(-8);

const c429 = new Counter('g16_http_429');
const c201 = new Counter('g16_http_201');
const cOtras = new Counter('g16_http_otras');

export const options = {
  insecureSkipTLSVerify: true,
  scenarios: {
    rafaga: {
      executor: 'shared-iterations',
      vus: 1,
      iterations: TOTAL,
      maxDuration: '59s',
    },
  },
};

function payload(i) {
  return JSON.stringify({
    tipo_activo: 'INDIVIDUAL',
    id_especie: ESPECIE,
    fecha_inicio_ciclo: '2026-09-09',
    origen_financiero: 'nacimiento',
    costo_adquisicion: null,
    soporte_documental: null,
    id_infraestructura: INFRA,
    atributos_dinamicos: {},
    identificador: `G16R2${STAMP}${String(i).padStart(3, '0')}`,
    raza: 'QA-G16-R2',
    sexo: 'Macho',
    fecha_nacimiento: '2025-01-15T00:00:00Z',
    peso_inicial: 2.5,
  });
}

export function setup() {
  if (!PASS) throw new Error('BLOQUEADO: SGPMP_TEST_PASSWORD o CONTRASENA');
  const login = http.post(`${BASE}/sesiones/`, JSON.stringify({
    correo_electronico: CORREO,
    contrasena: PASS,
  }), { headers: { 'Content-Type': 'application/json' } });
  if (login.status !== 200) throw new Error(`Login HTTP ${login.status}`);
  const body = login.json();
  const token = body.token || (body.data && body.data.token);
  if (!token) throw new Error('Login sin token');
  return { token, ids: [] };
}

export default function (data) {
  const res = http.post(`${BASE}/activos-biologicos`, payload(__ITER), {
    headers: {
      Authorization: `Bearer ${data.token}`,
      'Content-Type': 'application/json',
    },
  });
  if (res.status === 429) c429.add(1);
  else if (res.status === 201) {
    c201.add(1);
    try {
      const id = res.json().id_activo_biologico;
      if (id) data.ids.push(id);
    } catch (e) {}
  } else cOtras.add(1);
}

export function teardown(data) {
  const token = data.token;
  const ids = data.ids || [];
  for (const id of ids) {
    http.patch(`${BASE}/activos-biologicos/${id}/estado`, JSON.stringify({
      estado_nuevo: 'INACTIVO',
      fecha_cambio_estado: '2026-09-26',
      motivo_cambio: 'Restauracion TC-M02-G16 rev2 k6',
    }), {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });
  }
}
