// TC-M07-G035 (RF-97 CA-7, RNF-97.2, parte de RNF-97.1) - Carga real con k6.
//
// Cubre, con trafico real contra TEST:
//   - CA-7 bajo concurrencia: N solicitudes concurrentes de titulares DISTINTOS nunca mezclan
//     datos (cada respuesta debe traer su propio SystemNIT, nunca el de otro titular).
//   - RNF-97.2 bajo concurrencia: N solicitudes concurrentes del MISMO rango deben devolver el
//     mismo X-Content-SHA256 (determinismo del hash de contenido).
//   - Tiempo de respuesta real de 'vista-previa' con los datos reales disponibles en TEST (no es
//     RNF-97.1 completo: no hay un periodo con 2.000 facturas/50 comprobantes en TEST hoy).
//
// NO cubre (requiere infraestructura o acceso que no existe en este entorno):
//   - RNF-97.1 literal (2.000 facturas, 50 comprobantes, <=5s) -- no hay un periodo con ese
//     volumen real en TEST; medir con datos pequenos no probaria el limite real.
//   - RNF-97.7 (escalado a 2/4 instancias) -- no controlamos el despliegue de TEST, no podemos
//     forzar cuantas instancias atienden la corrida.
//   - RNF-97.8 (tiempo maximo excedido -> error controlado) -- no conocemos el valor configurado
//     en M09 ni podemos inducir una lectura lenta real de M06 sin inyeccion de fallos.
//   - CA-14 (interoperabilidad real con AgroFusion) -- no hay acceso a un entorno de AgroFusion
//     de pruebas desde este hilo.
//
// Como correrlo (Windows, PowerShell):
//   $env:CONTADOR_PASS = "<clave real del Contador>"
//   k6 run carga_k6_concurrencia_y_determinismo.js
//
// No escribe nada: toda la carga es GET /integracion/aaef/vista-previa/... (solo lectura).

import http from 'k6/http';
import { check, fail } from 'k6';
import { Counter } from 'k6/metrics';

const BASE = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const CORREO = 'contador@pecuaria.co';
const CONTRASENA = __ENV.CONTADOR_PASS;

// Titulares reales y accesibles con periodo CERRADO, confirmados en vivo 2026-11-21.
// Varios dan 0 documentos (sin costos FACTURA_COMPRA), pero igual sirven para el chequeo de
// aislamiento: lo que importa es que SystemNIT nunca se mezcle entre respuestas concurrentes.
const TITULARES = [
  { nit: '901444215', desde: '2026-10-01', hasta: '2026-10-31' }, // 3 documentos reales
  { nit: '901333217', desde: '2026-11-01', hasta: '2026-11-30' }, // 2 documentos reales
  { nit: '900000001', desde: '2026-11-01', hasta: '2026-11-30' }, // 0 documentos
  { nit: '900000002', desde: '2026-11-01', hasta: '2026-11-30' }, // 0 documentos
];

// Rango fijo para el chequeo de determinismo (CA-9/RNF-97.2): mismo titular, mismo rango, N
// solicitudes concurrentes deben dar el mismo hash de contenido.
const RANGO_DETERMINISMO = TITULARES[0];

const mezclas = new Counter('mezclas_de_datos_entre_titulares');
const hashes_distintos = new Counter('hashes_distintos_para_el_mismo_rango');

export const options = {
  scenarios: {
    aislamiento_entre_titulares: {
      executor: 'per-vu-iterations',
      vus: 20,
      iterations: 1,
      exec: 'chequearAislamiento',
      startTime: '0s',
    },
    determinismo_del_hash: {
      executor: 'per-vu-iterations',
      vus: 1, // un solo VU dispara el lote concurrente con http.batch() (ver mas abajo)
      iterations: 1,
      exec: 'chequearDeterminismo',
      startTime: '15s', // corre despues del escenario anterior, no al mismo tiempo
    },
  },
  thresholds: {
    'http_req_duration': ['p(95)<2000'], // informativo: tiempo real con los datos chicos de TEST
    'mezclas_de_datos_entre_titulares': ['count==0'],
    'hashes_distintos_para_el_mismo_rango': ['count==0'],
  },
};

// Un solo login compartido por todos los VUs (setup() de k6 corre una sola vez, antes de las
// iteraciones) -- 20 VUs logueandose a la vez disparaba el rate limit del propio login y
// arrastraba falsos negativos en todo lo demas. Un token real dura mas que la corrida.
export function setup() {
  if (!CONTRASENA) fail('Falta la variable de entorno CONTADOR_PASS con la clave real del Contador.');
  const res = http.post(`${BASE}/sesiones/`, JSON.stringify({ correo_electronico: CORREO, contrasena: CONTRASENA }),
    { headers: { 'Content-Type': 'application/json' } });
  check(res, { 'login 200': (r) => r.status === 200 });
  return { token: res.json('token') };
}

export function chequearAislamiento(data) {
  const token = data.token;
  const titular = TITULARES[__VU % TITULARES.length];
  const url = `${BASE}/integracion/aaef/vista-previa/productores/${titular.nit}?desde=${titular.desde}&hasta=${titular.hasta}`;
  const res = http.get(url, { headers: { Authorization: `Bearer ${token}` } });

  const ok = check(res, { '200 OK': (r) => r.status === 200 });
  if (!ok) return; // un 403/422 puntual no es una mezcla de datos, solo se registra como fallo de check

  const body = res.json();
  const nitDevuelto = body.metadata.SourceSystem.SystemNIT;
  if (nitDevuelto !== titular.nit) {
    mezclas.add(1);
  }
  check(res, { 'SystemNIT coincide con el solicitado': () => nitDevuelto === titular.nit });
}

export function chequearDeterminismo(data) {
  const token = data.token;
  const r = RANGO_DETERMINISMO;
  const url = `${BASE}/integracion/aaef/vista-previa/productores/${r.nit}?desde=${r.desde}&hasta=${r.hasta}`;

  // http.batch() dispara las 20 solicitudes de verdad en paralelo desde este unico VU -- permite
  // comparar los 20 hashes entre si en el mismo scope de JS, sin necesitar estado compartido
  // entre VUs (que k6 no da de forma simple).
  const peticiones = Array.from({ length: 20 }, () => ['GET', url, null, { headers: { Authorization: `Bearer ${token}` } }]);
  const respuestas = http.batch(peticiones);

  const hashes = respuestas.map((res) => res.headers['X-Content-Sha256']).filter(Boolean);
  check(respuestas, { 'las 20 respondieron 200': () => respuestas.every((r) => r.status === 200) });
  check(hashes, { 'se recibieron 20 hashes': () => hashes.length === 20 });

  const distintos = new Set(hashes).size;
  if (distintos > 1) {
    hashes_distintos.add(distintos - 1);
  }
  check(hashes, { 'las 20 solicitudes concurrentes dan el mismo hash': () => distintos <= 1 });
}
