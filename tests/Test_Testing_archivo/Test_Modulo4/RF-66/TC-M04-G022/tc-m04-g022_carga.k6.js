// TC-M04-G022 - Subcaso 2 (TC-M04-18): estabilidad bajo estres prolongado del motor de inferencia (RF-66 CA-14/CA-16, RNF-07/RNF-08).
// Carga sostenida >10 concurrentes durante >=15 min; criterio: >=80% de las inferencias con latencia <=3000 ms y sin perdida de resultados.
// Los cortes intermitentes de red se simulan en paralelo con tc-m04-g021_red_netem.sh (corte/retardo) sobre el nodo bajo prueba.
// AMBIENTE: backend TEST (DEV: https://api.inmero.co/api-sgpmp-dev). MAIN (https://api.inmero.co/sigab) NO se prueba: el script se niega a correr contra el.
// SANDBOX: esta prueba de carga NO usa el sandbox transaccional a proposito. El sandbox es una sola transaccion por run_id
// (maximo 5 corridas simultaneas) y serializaria las 15 VUs, asi que no mediria la concurrencia real. Se ejecuta directo contra TEST
// y deja inferencias persistidas: coordinar con el DBA la limpieza de la BD de TEST despues de correrla (o correrla en una BD desechable).
// SCRIPT SIN EJECUTAR: el endpoint de inferencia aun no existe (ruta provisional) y el ambiente no esta listo.
//
// Uso: k6 run -e BASE_URL=https://api.inmero.co/api-sgpmp-test -e CORREO=... -e CONTRASENA=... \
//        -e RUTA=/prediccion/inferencias -e ID_ACTIVO=1 -e ID_LOTE=1 [-e VUS=15 -e DURACION=16m] tc-m04-g022_carga.k6.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'https://api.inmero.co/api-sgpmp-test';
if (/\/sigab\/?$/.test(BASE_URL)) { throw new Error('MAIN no se prueba: usa /api-sgpmp-test o /api-sgpmp-dev'); }
const RUTA = __ENV.RUTA || '/prediccion/inferencias';
const VUS = parseInt(__ENV.VUS || '15');          // >10 concurrentes (se prueba con 15)
const DURACION = __ENV.DURACION || '16m';          // >=15 min

const rapidas = new Rate('inferencias_le_3000ms');
const sinResultado = new Counter('inferencias_sin_resultado');
const incoherentes = new Counter('inferencias_incoherentes');
const latencia = new Trend('latencia_inferencia', true);

export const options = {
  scenarios: {
    estres: { executor: 'constant-vus', vus: VUS, duration: DURACION },
  },
  thresholds: {
    inferencias_le_3000ms: ['rate>=0.80'],          // RNF-07: >=80% con latencia <=3000 ms
    inferencias_sin_resultado: ['count==0'],         // sin perdida de resultados
    inferencias_incoherentes: ['count==0'],          // sin inconsistencias en el resultado
  },
};

export function setup() {
  const r = http.post(`${BASE_URL}/sesiones/`, JSON.stringify({ correo_electronico: __ENV.CORREO, contrasena: __ENV.CONTRASENA }), { headers: { 'Content-Type': 'application/json' } });
  check(r, { 'login 200': (x) => x.status === 200 });
  return { token: r.json('token') };
}

export default function (data) {
  const ts = new Date().toISOString();
  const body = {
    id_paquete: `k6-${__VU}-${__ITER}-${Date.now()}`,
    id_activo_biologico: parseInt(__ENV.ID_ACTIVO || '1'), id_lote: parseInt(__ENV.ID_LOTE || '1'),
    especie: 'Bovino', categoria_tamano: 'GRANDE', timestamp_paquete: ts, modo_ejecucion: 'SERVIDOR',
    variables_telemetria: [
      { tipo_variable: 'TEMPERATURA_CORPORAL', valor: 38.6, unidad: '°C', timestamp_captura: ts },
      { tipo_variable: 'FRECUENCIA_CARDIACA', valor: 62, unidad: 'lpm', timestamp_captura: ts },
    ],
  };
  const r = http.post(`${BASE_URL}${RUTA}`, JSON.stringify(body), { headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${data.token}` } });
  latencia.add(r.timings.duration);
  rapidas.add(r.timings.duration <= 3000);
  let j = {}; try { j = r.json(); } catch (e) { /* respuesta no JSON */ }
  const R = j.resultado || j;
  if (r.status < 200 || r.status >= 300 || R.nivel_riesgo === undefined) { sinResultado.add(1); }
  else if (!(Number(R.nivel_riesgo) >= 0 && Number(R.nivel_riesgo) <= 3) || !(Number(R.confianza_global) >= 0 && Number(R.confianza_global) <= 1)) { incoherentes.add(1); }
  sleep(1);
}

export function handleSummary(data) {
  const ok = data.metrics.inferencias_le_3000ms.values.rate;
  const veredicto = ok >= 0.80 && data.metrics.inferencias_sin_resultado.values.count === 0 ? 'APROBADO' : 'FALLIDO';
  return { stdout: `\nTC-M04-G022 veredicto: ${veredicto} (${(ok * 100).toFixed(1)}% <= 3000 ms; sin resultado=${data.metrics.inferencias_sin_resultado.values.count})\n`, 'tc-m04-g022_resumen.json': JSON.stringify(data, null, 2) };
}
