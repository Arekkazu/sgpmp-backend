import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { marcas, fixture, evaluarHistorial, sincronizacion, CASOS, CAPACIDADES } from '../lib/g120_escenario.mjs';
import PRESUPUESTO from '../lib/g120_presupuesto.cjs';
import { contieneMojibake } from '../lib/seguridad.mjs';
import { preflight } from '../g120.mjs';
import { validarObligatorias, clasificarRegistro } from './registro_qa.mjs';

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const fuentes = ['README.md', 'g120.mjs', 'G120.postman_collection.json',
  ...['lib', 'pruebas'].flatMap(d => fs.readdirSync(path.join(raiz, d)).map(f => `${d}/${f}`))];
for (const fuente of fuentes) {
  const bytes = fs.readFileSync(path.join(raiz, fuente));
  const contenido = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  assert.equal(contieneMojibake(contenido), false, `Texto mojibake: ${fuente}`);
}
assert.equal(contieneMojibake('Validaci\u00c3\u00b3n'), true);
assert.equal(contieneMojibake('valor\u00c2'), true);
assert.equal(contieneMojibake('texto \u00e2\u20ac'), true);

const m = marcas('2026-10-26T12:00:17.937Z');
assert.equal(Date.parse(m.envio) - Date.parse(m.bordes[0]), 23 * 3600000);
assert.equal(Date.parse(m.envio) - Date.parse(m.bordes[1]), 24 * 3600000);
assert.equal(m.intervalo.length, 3);
const semilla = { device_id: 1, sensor_id: 2, serial: 'SINTETICO', id_variable: 8,
  tipo_variable: 'TEMPERATURA_AMBIENTAL', nombre_variable: 'Temperatura Ambiental', unidad: '°C', valor: 25 };
const cuerpo = fixture(semilla, m.bordes[0], 'BUFFER_LOCAL', m.envio);
assert.equal(cuerpo.serial, 'SINTETICO');
assert.equal(cuerpo.id_variable, 8);
assert.equal(cuerpo.tipo_variable, 'TEMPERATURA_AMBIENTAL');
assert.equal(cuerpo.timestamp_envio, m.envio);
assert.equal(cuerpo.origen, 'BUFFER_LOCAL');
assert.deepEqual(Object.keys(validarObligatorias(CAPACIDADES)).sort(), CASOS.slice().sort());
const item = (ts, origen = 'BUFFER_LOCAL') => ({ id_sensor: 2, id_variable: 8,
  tipo_variable: semilla.nombre_variable,
  timestamp_captura: ts, origen_dato: origen, id_telemetria: 1 });
const items = [...m.intervalo.map(x => item(x)), item(m.duplicado), ...m.bordes.map(x => item(x)),
  item(m.real, 'TIEMPO_REAL')];
const sync = sincronizacion({ detalle: m.bordes.map(ts => ({ timestamp_captura: ts,
  timestamp_sincronizacion: new Date(Date.parse(ts) + (ts === m.bordes[0] ? 23 : 24) * 3600000 + 10000).toISOString() })) }, m.bordes);
assert.equal(sync.estado, 'valido');
assert.deepEqual(evaluarHistorial(items, semilla, m, sync).map(x => x.estado), ['APROBADO', 'APROBADO', 'APROBADO']);
assert.deepEqual(evaluarHistorial(items.map(x => x === items[0] ? { ...x,
  timestamp_captura: new Date(Date.parse(x.timestamp_captura) + 1000).toISOString() } : x), semilla, m, sync)
  .map(x => x.estado), ['RECHAZADO', 'APROBADO', 'APROBADO']);
assert.equal(evaluarHistorial([...items, item(m.duplicado)], semilla, m, sync)[1].estado, 'RECHAZADO');
assert.equal(evaluarHistorial(items.map(x => x === items[1] ? { ...x, origen_dato: 'TIEMPO_REAL' } : x), semilla, m, sync)[0].estado, 'RECHAZADO');
assert.equal(evaluarHistorial(items, semilla, m, { estado: 'invalido' })[2].estado, 'APROBADO');
assert.equal(evaluarHistorial(items, semilla, m, { estado: 'ausente' })[2].estado, 'APROBADO');
assert.deepEqual(CAPACIDADES.comprobaciones_obligatorias, {
  'TC-M03-241': { API: ['API-241-01'] },
  'TC-M03-242': { API: ['API-242-01'] },
  'TC-M03-243': { API: ['API-243-01'] },
});
assert.equal(Object.values(PRESUPUESTO.desglose_maximo).reduce((a, b) => a + b, 0), PRESUPUESTO.solicitudes_directas);
const contextoReal = { grupo: 'G120', version: 1, intento: 1, run_id: 'RUN-G120-V1-20261026-120000',
  operacion: 'EVALUAR', referencia: 'SOL-G120-LOCAL', casos: CASOS,
  alcance_reevaluacion: null, version_anterior: null };
const envLocal = { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: 'https://www.api.inmero.co/api-sgpmp-test',
  QA_SANDBOX_SECRET: 'SINTETICO', BROKER_SERVICE_TOKEN: 'SINTETICO',
  QA_PROD_EMAIL: 'sintetico@example.invalid', QA_PROD_PASSWORD: 'SINTETICO' };
const p = preflight({ version: 1, runId: contextoReal.run_id, operacion: 'evaluar' }, envLocal);
assert.equal(p.ok, true);
assert.equal(p.barreras.length, 0);
assert.equal(p.decision_qa.fecha, '2026-10-26');
assert.equal(JSON.stringify(p).includes('QA_G120_EFECTOS_AUTORIZADOS'), false);
const run = 'RUN-G120-V1-20261026-120000';
const resultado = { run_id: run, version: 1, consume_version: true, oficial: true,
  cierre: { run: { cierre_http: 200 }, rollback: { verificado: true } },
  casos: Object.fromEntries(CASOS.map(x => [x, { estado: 'APROBADO' }])),
  comprobaciones: CASOS.map((caso, i) => ({ caso, fuente: 'API', id: `API-${caso.slice(-3)}-01`,
    tipo: 'ASSERT', estado: 'APROBADO' })),
  evidencias: ['resultado.json', 'TC-M03-G120_resultado.md', 'newman/newman-G120.json'] };
const presentes = new Set(resultado.evidencias);
assert.equal(clasificarRegistro(CAPACIDADES, resultado, presentes, { runId: run, version: 1 }), true);
const rechazo = structuredClone(resultado); rechazo.casos[CASOS[1]].estado = 'RECHAZADO';
rechazo.comprobaciones[1].estado = 'RECHAZADO';
assert.equal(clasificarRegistro(CAPACIDADES, rechazo, presentes, { runId: run, version: 1 }), true);
const mixto = structuredClone(resultado); mixto.casos[CASOS[2]].estado = 'NO_CONCLUYENTE';
assert.equal(clasificarRegistro(CAPACIDADES, mixto, presentes, { runId: run, version: 1 }), false);
console.log('G120 PURE 20/20');
