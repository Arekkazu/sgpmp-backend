// TC-M07-G035 (RF-97, RNF-97.7, TC-97-077/078) - Script de triage para encontrar el umbral real
// de concurrencia de GET /integracion/aaef/vista-previa/productores/{nit} en TEST.
//
// Origen: carga_k6_concurrencia_y_determinismo.js (20 VUs fijos) mostro que a 20 solicitudes
// concurrentes casi todo falla por timeout. Este script barre N_VUS para encontrar el punto
// exacto donde empieza a degradarse. Resultado real medido 2026-11-20 (ver NOTA_rendimiento_
// concurrencia.md para la tabla completa y el analisis): responde rapido (~300-450ms) hasta
// 13 VUs, en 14 ya hay cola (~4.25s promedio pero sin fallar), y en 15 colapsa casi del todo
// (timeout a los 30s). Indica un pool de conexiones/recursos de tamano ~13-14 en el backend
// o su infraestructura (BD, proxy), no un problema del caso de uso en si.
//
// No escribe nada: GET de solo lectura contra vista-previa.
//
// Como correrlo (Windows, PowerShell):
//   $env:CONTADOR_PASS = "<clave real del Contador>"
//   $env:N_VUS = 14
//   k6 run carga_k6_umbral_concurrencia.js

import http from 'k6/http';
import { check } from 'k6';

const BASE = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const CORREO = 'contador@pecuaria.co';
const CONTRASENA = __ENV.CONTADOR_PASS;

export function setup() {
  const res = http.post(`${BASE}/sesiones/`, JSON.stringify({ correo_electronico: CORREO, contrasena: CONTRASENA }),
    { headers: { 'Content-Type': 'application/json' } });
  check(res, { 'login 200': (r) => r.status === 200 });
  return { token: res.json('token') };
}

const N = Number(__ENV.N_VUS || 5);
export const options = { vus: N, iterations: N };

export default function (data) {
  const url = `${BASE}/integracion/aaef/vista-previa/productores/901444215?desde=2026-10-01&hasta=2026-10-31`;
  const res = http.get(url, { headers: { Authorization: `Bearer ${data.token}` }, timeout: '30s' });
  check(res, { '200': (r) => r.status === 200 });
  console.log(`VU ${__VU}: status=${res.status} duration=${res.timings.duration}ms`);
}
