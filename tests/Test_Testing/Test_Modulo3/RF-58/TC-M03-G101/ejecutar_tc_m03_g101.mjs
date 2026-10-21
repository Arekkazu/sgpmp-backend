#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { argumentos, autorizar, clasificar, envPath, envQa, ejecutarGrupo, lectura, modulos } from '../TC-M03-G100/qa_lote5_base.mjs';
import { sqlTestigo } from '../TC-M03-G99/ejecutar_tc_m03_g99.mjs';

export const CASOS = ['TC-M03-196', 'TC-M03-197', 'TC-M03-198', 'TC-M03-199', 'TC-M03-200'];
const DIR = path.dirname(fileURLToPath(import.meta.url));
const SPEC = path.join(DIR, 'tc_m03_g101.cy.js');
const COLLECTION = path.join(DIR, 'TC-M03-G101.postman_collection.json');
export function rutaBitacora(paths) {
  return Object.entries(paths || {}).filter(([p, m]) => /bitacora|degradacion/i.test(p) && /monitoreo|latencia/i.test(p + JSON.stringify(m.get || {})) && !p.includes('{') && m.get && !(m.get.parameters || []).some(x => x.required)).map(([p]) => p)[0] || null;
}
export function eventosBitacora(obj, ids, desde) {
  const filas = Array.isArray(obj) ? obj : ['items', 'eventos', 'data', 'registros'].map(k => obj?.[k]).find(Array.isArray) || [];
  return filas.filter(x => ids.includes(Number(x.id_sensor ?? x.sensor_id)) && Date.parse(x.fecha_evento ?? x.timestamp ?? x.created_at) >= desde).map(x => String(x.tipo_evento ?? x.evento ?? x.codigo ?? ''));
}
export function crearVigenciaSandbox({ ttlMs = 180000, ahora = Date.now } = {}) {
  let ultima = null;
  let fallo = null;
  return {
    confirmar(resultado) {
      if (fallo) return false;
      const instante = ahora();
      if (ultima !== null && instante - ultima >= ttlMs) { fallo = 'TTL del sandbox agotado antes de confirmar continuidad'; return false; }
      if (resultado?.status !== 200 || Number(resultado?.data?.data?.[0]?.n) !== 1) { fallo = `testigo del RUN no verificable (HTTP ${resultado?.status ?? 'sin respuesta'})`; return false; }
      ultima = instante;
      return true;
    },
    vigente() {
      if (!fallo && ultima !== null && ahora() - ultima >= ttlMs) fallo = 'TTL del sandbox agotado';
      return !fallo && ultima !== null;
    },
    abortar(motivo) { fallo ||= String(motivo); },
    get fallo() { return fallo; },
    get ultimaConfirmacion() { return ultima; },
  };
}
export async function esperaVigilada({ duracionMs, intervaloMs, sonda, vigencia, signal }) {
  const comprobar = async () => {
    if (vigencia.fallo) return false;
    if (vigencia.ultimaConfirmacion !== null && !vigencia.vigente()) return false;
    try { return vigencia.confirmar(await sonda()); }
    catch (e) { vigencia.abortar(`mantenimiento del sandbox falló: ${e.message}`); return false; }
  };
  if (!(await comprobar())) return { ok: false, motivo: vigencia.fallo };
  return new Promise(resolve => {
    let terminado = false;
    let tickTimer;
    let finTimer;
    let comprobacion = Promise.resolve();
    const cancelarEspera = () => { vigencia.abortar('espera local cancelada'); terminar(false); };
    const terminar = ok => {
      if (terminado) return;
      terminado = true;
      clearTimeout(tickTimer); clearTimeout(finTimer);
      signal?.removeEventListener('abort', cancelarEspera);
      resolve({ ok, motivo: ok ? null : vigencia.fallo });
    };
    signal?.addEventListener('abort', cancelarEspera, { once: true });
    if (signal?.aborted) { cancelarEspera(); return; }
    const tick = () => {
      comprobacion = comprobacion.then(comprobar);
      comprobacion.then(ok => { if (!ok) terminar(false); else if (!terminado) tickTimer = setTimeout(tick, intervaloMs); });
    };
    tickTimer = setTimeout(tick, intervaloMs);
    finTimer = setTimeout(() => {
      comprobacion = comprobacion.then(comprobar);
      comprobacion.then(ok => terminar(ok));
    }, duracionMs);
  });
}
function validar() {
  const v = envQa(fs.readFileSync(envPath, 'utf8'));
  const col = JSON.parse(fs.readFileSync(COLLECTION, 'utf8'));
  const spec = fs.readFileSync(SPEC, 'utf8');
  const ck = []; const add = (n, ok) => ck.push([n, !!ok]);
  add('casos 196-200 exactos', CASOS.join() === 'TC-M03-196,TC-M03-197,TC-M03-198,TC-M03-199,TC-M03-200');
  add('QA_AUTORIZADO=NO', v.QA_AUTORIZADO === 'NO');
  add('barrera actual', !autorizar(v, { ambiente: 'TEST', autorizacion: '', efectos: [] }).ok);
  add('barrera DEV', !autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ambiente: 'DEV', autorizacion: 'DEV-12345678', efectos: ['notificacion-login'] }).ok);
  add('colección API', /v2\.1\.0/.test(col.info.schema) && col.item.length === 1 && JSON.stringify(col).includes('TC-M03-196'));
  add('guardia Newman', JSON.stringify(col.event).includes('BLOQUEO_G101'));
  add('variables Newman resueltas', [...JSON.stringify(col).matchAll(/\{\{([a-z_]+)\}\}/g)].every(x => ['base_url', 'token', 'run_id', 'sandbox_secret', 'id_infraestructura'].includes(x[1])));
  try { for (const e of [...col.event, ...col.item.flatMap(x => x.event || [])]) new Function(e.script.exec.join('\n')); add('scripts Postman', true); } catch { add('scripts Postman', false); }
  add('cinco escenarios Cypress', CASOS.every(x => spec.includes(x)));
  add('límites originales', ['500', '1200', '3500', '180000', '60000', '300', 'Actualización con retraso', 'Trabajando sin conexión'].every(x => x === '180000' ? fs.readFileSync(fileURLToPath(import.meta.url), 'utf8').includes('duracionMs: 180000') : spec.includes(x)));
  add('canal push no aislado bloqueado', ['WebSocket', 'EventSource', '__qaPushSinSandbox'].every(x => spec.includes(x)));
  add('sintaxis ejecutor/spec', [fileURLToPath(import.meta.url), SPEC].every(p => spawnSync(process.execPath, ['--check', p]).status === 0));
  add('sin RESULTADOS', !fs.existsSync(path.join(DIR, 'RESULTADOS')));
  add('sin secretos literales', [SPEC, COLLECTION, fileURLToPath(import.meta.url)].every(p => ![v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD].filter(x => x?.length > 5).some(x => fs.readFileSync(p, 'utf8').includes(x))));
  try { const m = modulos(); add('Newman/Cypress disponibles', !!m.newman.run && !!m.cypress.run); } catch { add('Newman/Cypress disponibles', false); }
  add('sin endpoint de bitácora inventado', rutaBitacora({ '/iot/monitoreo/dashboard': { get: {} } }) === null);
  add('PRE tiene prioridad sobre ASSERT', clasificar('CONCLUIDA', [{ ok: false }], [{ ok: false, observado: true }], true) === 'BLOQUEADO');
  add('espera Cypress vigilada sin espera ciega', spec.includes('/guard/wait') && spec.includes('/guard/status') && !spec.includes('cy.wait(180000)'));
  ck.forEach(([n, ok]) => console.log(`${ok ? 'OK' : 'FALLO'} ${n}`));
  console.log(`G101 ${ck.filter(x => x[1]).length}/${ck.length}`);
  return ck.every(x => x[1]) ? 0 : 1;
}

async function escenario(c) {
  const { req, pre, assert, v, gate, run, out, sensores, dispositivo, serial, prod, newman, cypress, ev } = c;
  const nr = await new Promise(resolve => newman.run({ ignoreRedirects: true,  collection: JSON.parse(fs.readFileSync(COLLECTION, 'utf8')), environment: { values: Object.entries({ base_url: gate.api, test_base_url: gate.api, run_id: run, sandbox_secret: v.QA_SANDBOX_SECRET, token: prod, id_infraestructura: String(c.area), autorizado_run: 'SI', qa_autorizado: v.QA_AUTORIZADO, ambiente: c.a.ambiente, autorizacion: c.a.autorizacion }).map(([key, value]) => ({ key, value })) }, reporters: [], silent: true }, (error, summary) => resolve({ error, summary })));
  pre('Newman técnico', !nr.error && !(nr.summary?.run?.failures || []).some(x => x.error?.name !== 'AssertionError'));
  for (const x of nr.summary?.run?.executions || []) for (const y of x.assertions || []) (y.assertion.includes('[PRE]') ? pre : assert)(y.assertion, !y.error);
  const inicioEscenario = Date.now();
  const contrato = await req('GET', '/openapi.json');
  const bitacora = contrato.status === 200 ? rutaBitacora(contrato.data?.paths) : null;
  if (!bitacora) { ev.pre.push({ nombre: 'bitácora RF-58 consultable por contrato oficial', ok: false }); ev.dependencias.push('No se descubrió contrato GET de bitácora de degradación RF-58; criterios de registro 197-199 no verificables todavía.'); }
  const llave = randomUUID();
  c.registrarSecreto(llave);
  const vigencia = crearVigenciaSandbox();
  const sonda = () => req('POST', '/test-control/query', { body: { query: sqlTestigo(serial) } });
  let secuencia = 0;
  const servidor = http.createServer(async (request, response) => {
    if (request.headers['x-qa-key'] !== llave) { response.writeHead(403); response.end(); return; }
    if (request.method === 'GET' && request.url === '/guard/status') {
      response.writeHead(vigencia.fallo ? 503 : 200, { 'Content-Type': 'application/json' });
      response.end(JSON.stringify({ ok: !vigencia.fallo, motivo: vigencia.fallo }));
      return;
    }
    if (request.method === 'POST' && request.url === '/guard/wait') {
      const cancelar = new AbortController();
      response.once('close', () => { if (!response.writableEnded) cancelar.abort(); });
      const resultado = await esperaVigilada({ duracionMs: 180000, intervaloMs: 45000, sonda, vigencia, signal: cancelar.signal });
      if (response.destroyed) return;
      response.writeHead(resultado.ok ? 200 : 503, { 'Content-Type': 'application/json' });
      response.end(JSON.stringify(resultado));
      return;
    }
    if (request.method !== 'POST' || request.url !== '/ingest') { response.writeHead(404); response.end(); return; }
    if (vigencia.fallo) { response.writeHead(503); response.end(JSON.stringify({ error: 'PRE: vigencia del sandbox no confirmada' })); return; }
    try {
      const s = sensores[0];
      const antes = await req('GET', `/iot/monitoreo/dashboard/${c.area}?pagina=1&por_pagina=50`, { token: prod });
      const previo = antes.data?.sensores?.find(x => Number(x.id_sensor) === Number(s.id))?.estado_semaforo;
      const valor = 35 + secuencia++;
      if (vigencia.fallo) throw Error('PRE: vigencia del sandbox no confirmada');
      const r = await req('POST', '/iot/telemetria', { body: lectura({ dispositivo, sensor: s.id, serial, valor, fecha: new Date().toISOString() }) });
      const confirmado = Date.now();
      let visible = false, semaforo = null;
      if (r.status === 201) for (let i = 0; i < 8; i++) {
        const d = await req('GET', `/iot/monitoreo/dashboard/${c.area}?pagina=1&por_pagina=50`, { token: prod });
        const actual = d.data?.sensores?.find(x => Number(x.id_sensor) === Number(s.id));
        visible = d.status === 200 && Number(actual?.ultimo_valor) === valor;
        if (visible) semaforo = actual?.estado_semaforo;
        if (visible) break;
        await new Promise(resolve => setTimeout(resolve, 250));
      }
      response.writeHead(200, { 'Content-Type': 'application/json' }); response.end(JSON.stringify({ accepted: r.status === 201, committedAt: confirmado, visible, valor, sensor: s.id, semaforo, previo, transition: !!semaforo && semaforo !== previo }));
    } catch (e) { response.writeHead(200, { 'Content-Type': 'application/json' }); response.end(JSON.stringify({ accepted: false, visible: false, error: c.limpiar(e.message) })); }
  });
  await new Promise((resolve, reject) => { servidor.once('error', reject); servidor.listen(0, '127.0.0.1', resolve); });
  try {
    delete process.env.ELECTRON_RUN_AS_NODE;
    const cr = await cypress.run({ project: DIR, configFile: path.join(DIR, 'cypress.config.cjs'), testingType: 'e2e', spec: SPEC, browser: 'electron', headless: true, quiet: true, reporter: 'spec', config: { e2e: { baseUrl: gate.web, specPattern: path.basename(SPEC), supportFile: false, fixturesFolder: false, video: false, screenshotOnRunFailure: false, trashAssetsBeforeRuns: false, screenshotsFolder: path.join(out, 'capturas'), downloadsFolder: path.join(out, 'descargas'), defaultCommandTimeout: 15000, responseTimeout: 30000, testIsolation: false, reporter: 'spec' } }, env: { API_BASE: gate.api, API_TEST_BASE: gate.api, RUN_ID: run, SANDBOX_SECRET: v.QA_SANDBOX_SECRET, PROD_EMAIL: v.QA_PROD_EMAIL, PROD_PASSWORD: v.QA_PROD_PASSWORD || v.QA_COMMON_PASSWORD, ID_INFRA: c.area, SENSORES: sensores, CONTROL_URL: `http://127.0.0.1:${servidor.address().port}/ingest`, CONTROL_KEY: llave, AUTORIZADO_RUN: 'SI', QA_AUTORIZADO: v.QA_AUTORIZADO, AMBIENTE: c.a.ambiente, AUTORIZACION: c.a.autorizacion } });
    if (vigencia.fallo) {
      ev.pre.push({ nombre: 'continuidad del sandbox durante espera temporal', ok: false, detalle: c.limpiar(vigencia.fallo) });
      throw Error(`PRE: mantenimiento del sandbox falló; se interrumpe G101: ${vigencia.fallo}`);
    }
    const tests = cr.runs?.flatMap(x => x.tests || []) || [];
    pre('Cypress ejecutó los cinco casos', tests.filter(t => ['passed', 'failed'].includes(t.state)).length === 5, `tests=${tests.length}`);
    for (const id of CASOS) {
      const t = tests.find(x => x.title?.join(' ').includes(id));
      if (/PRE:/.test(t?.displayError || '')) { ev.pre.push({ nombre: `${id} estímulo o observabilidad`, ok: false, detalle: c.limpiar(t.displayError).slice(0, 300) }); ev.dependencias.push(`${id}: estímulo/observabilidad no verificable`); }
      else assert(`[${id}][ASSERT] condiciones originales UI/latencia`, t?.state === 'passed', !!t);
    }
    if (vigencia.ultimaConfirmacion !== null) pre('continuidad del sandbox durante espera temporal', vigencia.vigente());
  } catch (e) {
    if (vigencia.fallo && !ev.pre.some(x => x.nombre === 'continuidad del sandbox durante espera temporal')) {
      ev.pre.push({ nombre: 'continuidad del sandbox durante espera temporal', ok: false, detalle: c.limpiar(vigencia.fallo) });
      throw Error(`PRE: mantenimiento del sandbox falló; se interrumpe G101: ${vigencia.fallo}`);
    }
    throw e;
  } finally { await new Promise(resolve => servidor.close(resolve)); }
  // Descubrimiento por OpenAPI: ninguna ruta ni estructura de bitácora se presupone.
  if (bitacora) {
    const r = await req('GET', bitacora, { token: prod });
    const filas = Array.isArray(r.data) ? r.data : ['items', 'eventos', 'data', 'registros'].map(k => r.data?.[k]).find(Array.isArray);
    const correlacionable = Array.isArray(filas) && filas.length > 0 && filas.some(x => Number.isSafeInteger(Number(x.id_sensor ?? x.sensor_id)) && !Number.isNaN(Date.parse(x.fecha_evento ?? x.timestamp ?? x.created_at)) && !!(x.tipo_evento ?? x.evento ?? x.codigo));
    const eventos = correlacionable ? eventosBitacora(r.data, sensores.map(x => x.id), inicioEscenario) : [];
    if (r.status !== 200 || !correlacionable) {
      ev.pre.push({ nombre: 'bitácora correlacionable con sensores del RUN', ok: false });
      ev.dependencias.push('Bitácora descubierta sin control observable/correlacionable; no interpretar una consulta vacía como ausencia de eventos.');
    } else for (const [id, tipo] of [['TC-M03-197', 'DEGRADACION_LEVE'], ['TC-M03-198', 'DEGRADACION_MODERADA'], ['TC-M03-199', 'DEGRADACION_SEVERA']]) {
      if (ev.pre.some(x => !x.ok && x.nombre.includes(id))) ev.dependencias.push(`${id}: bitácora no juzgada porque el estímulo original quedó bloqueado.`);
      else assert(`[${id}][ASSERT] evento ${tipo} en bitácora`, eventos.includes(tipo));
    }
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { const a = argumentos(process.argv.slice(2)); process.exitCode = a.modo === 'local' ? validar() : await ejecutarGrupo({ numero: 101, casos: CASOS, cantidad: 50, carpeta: DIR, escenario, a }); }
  catch (e) { console.error(e.message); process.exitCode = 2; }
}
