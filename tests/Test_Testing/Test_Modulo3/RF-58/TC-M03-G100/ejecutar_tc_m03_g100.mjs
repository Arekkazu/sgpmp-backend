#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { argumentos, autorizar, clasificar, envPath, envQa, ejecutarGrupo, lectura, modulos } from './qa_lote5_base.mjs';

export const CASOS = ['TC-M03-195'];
const DIR = path.dirname(fileURLToPath(import.meta.url));
const SPEC = path.join(DIR, 'tc_m03_g100.cy.js');
const COLLECTION = path.join(DIR, 'TC-M03-G100.postman_collection.json');
export function rafagas(sensores, dispositivo, serial, inicio) {
  return { registros: Array.from({ length: 10 }, (_, ciclo) => sensores.map(s => lectura({ dispositivo, sensor: s.id, serial, valor: 26 + ciclo, fecha: new Date(inicio + ciclo * 100 + sensores.indexOf(s)).toISOString(), origen: 'BUFFER_LOCAL' }))).flat() };
}
export function aceptarBatch(r, esperados) {
  return r?.status === 200 && Number(r.data?.total) === esperados && Number(r.data?.aceptados) === esperados && Number(r.data?.rechazados) === 0 && Number(r.data?.duplicados) === 0;
}
function validar() {
  const v = envQa(fs.readFileSync(envPath, 'utf8'));
  const col = JSON.parse(fs.readFileSync(COLLECTION, 'utf8'));
  const spec = fs.readFileSync(SPEC, 'utf8');
  const ck = [];
  const add = (n, ok) => ck.push([n, !!ok]);
  add('matriz TC-M03-195', CASOS.join() === 'TC-M03-195');
  add('QA_AUTORIZADO=NO', v.QA_AUTORIZADO === 'NO');
  add('barrera actual', !autorizar(v, { ambiente: 'TEST', autorizacion: '', efectos: [] }).ok);
  add('barrera DEV', !autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ambiente: 'DEV', autorizacion: 'DEV-12345678', efectos: ['notificacion-login'] }).ok);
  add('colección API', /v2\.1\.0/.test(col.info.schema) && col.item.length === 1 && JSON.stringify(col).includes('TC-M03-195'));
  add('guardia Newman', JSON.stringify(col.event).includes('BLOQUEO_G100'));
  add('variables Newman resueltas', [...JSON.stringify(col).matchAll(/\{\{([a-z_]+)\}\}/g)].every(x => ['base_url', 'token', 'run_id', 'sandbox_secret', 'id_infraestructura'].includes(x[1])));
  try { for (const e of [...col.event, ...col.item.flatMap(x => x.event || [])]) new Function(e.script.exec.join('\n')); add('scripts Postman', true); } catch { add('scripts Postman', false); }
  add('Cypress: rafaga, indicador, tasa, último estado', ['TC-M03-195', 'Sincronizando datos', 'intervalos', 'latest'].every(x => spec.includes(x)));
  add('canal push no aislado bloqueado', ['WebSocket', 'EventSource', '__qaPushSinSandbox'].every(x => spec.includes(x)));
  add('sintaxis ejecutor y spec', [fileURLToPath(import.meta.url), SPEC, path.join(DIR, 'qa_lote5_base.mjs')].every(p => spawnSync(process.execPath, ['--check', p]).status === 0));
  add('sin RESULTADOS', !fs.existsSync(path.join(DIR, 'RESULTADOS')));
  add('sin secretos literales', [SPEC, COLLECTION, fileURLToPath(import.meta.url), path.join(DIR, 'qa_lote5_base.mjs')].every(p => ![v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD].filter(x => x?.length > 5).some(x => fs.readFileSync(p, 'utf8').includes(x))));
  try { const m = modulos(); add('Newman/Cypress disponibles', !!m.newman.run && !!m.cypress.run); } catch { add('Newman/Cypress disponibles', false); }
  add('PRE distinto de ASSERT', clasificar('CONCLUIDA', [{ ok: false }], [{ ok: false, observado: true }], true) === 'BLOQUEADO');
  ck.forEach(([n, ok]) => console.log(`${ok ? 'OK' : 'FALLO'} ${n}`));
  console.log(`G100 ${ck.filter(x => x[1]).length}/${ck.length}`);
  return ck.every(x => x[1]) ? 0 : 1;
}

async function escenario(c) {
  const { req, need, pre, assert, v, gate, run, out, sensores, dispositivo, serial, prod, newman, cypress } = c;
  const nr = await new Promise(resolve => newman.run({ ignoreRedirects: true,  collection: JSON.parse(fs.readFileSync(COLLECTION, 'utf8')), environment: { values: Object.entries({ base_url: gate.api, test_base_url: gate.api, run_id: run, sandbox_secret: v.QA_SANDBOX_SECRET, token: prod, id_infraestructura: String(c.area), autorizado_run: 'SI', qa_autorizado: v.QA_AUTORIZADO, ambiente: c.a.ambiente, autorizacion: c.a.autorizacion }).map(([key, value]) => ({ key, value })) }, reporters: [], silent: true }, (error, summary) => resolve({ error, summary })));
  pre('Newman técnico', !nr.error && !(nr.summary?.run?.failures || []).some(x => x.error?.name !== 'AssertionError'));
  for (const x of nr.summary?.run?.executions || []) for (const y of x.assertions || []) (y.assertion.includes('[PRE]') ? pre : assert)(y.assertion, !y.error);
  const llave = randomUUID();
  c.registrarSecreto(llave);
  const servidor = http.createServer(async (request, response) => {
    if (request.method !== 'POST' || request.url !== '/burst' || request.headers['x-qa-key'] !== llave) { response.writeHead(403); response.end(); return; }
    try {
      const inicio = Date.now() - 1000;
      const payload = rafagas(sensores, dispositivo, serial, inicio);
      const r = await req('POST', '/iot/telemetria/batch', { body: payload, timeout: 60000 });
      const aceptado = aceptarBatch(r, payload.registros.length);
      let visible = false;
      if (aceptado) for (let i = 0; i < 10; i++) {
        const d = await req('GET', `/iot/monitoreo/dashboard/${c.area}?pagina=1&por_pagina=50`, { token: prod });
        visible = d.status === 200 && sensores.every(s => Number(d.data?.sensores?.find(x => Number(x.id_sensor) === Number(s.id))?.ultimo_valor) === 35);
        if (visible) break;
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      const data = { accepted: aceptado, visible, count: Number(r.data?.aceptados) || 0, latest: 35, status: r.status };
      response.writeHead(200, { 'Content-Type': 'application/json' }); response.end(JSON.stringify(data));
    } catch (e) { response.writeHead(200, { 'Content-Type': 'application/json' }); response.end(JSON.stringify({ accepted: false, visible: false, error: c.limpiar(e.message) })); }
  });
  await new Promise((resolve, reject) => { servidor.once('error', reject); servidor.listen(0, '127.0.0.1', resolve); });
  try {
    delete process.env.ELECTRON_RUN_AS_NODE;
    const cr = await cypress.run({ project: DIR, configFile: path.join(DIR, 'cypress.config.cjs'), testingType: 'e2e', spec: SPEC, browser: 'electron', headless: true, quiet: true, reporter: 'spec', config: { e2e: { baseUrl: gate.web, specPattern: path.basename(SPEC), supportFile: false, fixturesFolder: false, video: false, screenshotOnRunFailure: false, trashAssetsBeforeRuns: false, screenshotsFolder: path.join(out, 'capturas'), downloadsFolder: path.join(out, 'descargas'), defaultCommandTimeout: 15000, reporter: 'spec' } }, env: { API_BASE: gate.api, API_TEST_BASE: gate.api, RUN_ID: run, SANDBOX_SECRET: v.QA_SANDBOX_SECRET, PROD_EMAIL: v.QA_PROD_EMAIL, PROD_PASSWORD: v.QA_PROD_PASSWORD || v.QA_COMMON_PASSWORD, ID_INFRA: c.area, SENSORES: sensores, CONTROL_URL: `http://127.0.0.1:${servidor.address().port}/burst`, CONTROL_KEY: llave, AUTORIZADO_RUN: 'SI', QA_AUTORIZADO: v.QA_AUTORIZADO, AMBIENTE: c.a.ambiente, AUTORIZACION: c.a.autorizacion } });
    const tests = cr.runs?.flatMap(x => x.tests || []) || [];
    pre('Cypress ejecutó caso original', tests.filter(t => ['passed', 'failed'].includes(t.state)).length === 1, `tests=${tests.length}`);
    pre('ráfaga observable por backend', !tests.some(x => /PRE:/.test(x.displayError || '')));
    assert('[TC-M03-195][ASSERT] throttling, sincronización y último estado', !cr.failures && !cr.totalFailed);
  } finally { await new Promise(resolve => servidor.close(resolve)); }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { const a = argumentos(process.argv.slice(2)); process.exitCode = a.modo === 'local' ? validar() : await ejecutarGrupo({ numero: 100, casos: CASOS, cantidad: 3, carpeta: DIR, escenario, a }); }
  catch (e) { console.error(e.message); process.exitCode = 2; }
}
