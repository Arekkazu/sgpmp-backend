#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import https from 'node:https';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { args, gate, parseEnv, ENV_PATH, evidence, request, verdict } from '../TC-M03-G108/qa_lote6_base.mjs';

export const CASOS = ['TC-M03-212'];
const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROUTE = '/iot/monitoreo/dashboard';
export function plainOutcome(x) {
  if (x.error === 'ECONNREFUSED' || x.error === 'ECONNRESET') return { ok: true, mode: 'rechazo de conexión' };
  if (x.error) return { ok: false, blocked: true, mode: x.error };
  const location = x.location ? new URL(x.location, x.url) : null;
  const redirected = x.status >= 300 && x.status < 400 && location?.protocol === 'https:' && location.hostname === new URL(x.url).hostname;
  const rejected = [400, 401, 403, 404, 405, 426].includes(x.status);
  return { ok: (redirected || rejected) && !x.telemetry, mode: redirected ? 'redirección HTTPS' : rejected ? 'rechazo HTTP' : 'respuesta no segura' };
}
function probe(url, headers = {}, secure = false) {
  return new Promise(resolve => {
    const client = secure ? https : http;
    let protocol = null;
    const req = client.get(url, { headers, timeout: 10000, maxHeaderSize: 16384, ...(secure ? { minVersion: 'TLSv1.2', rejectUnauthorized: true } : {}) }, res => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', chunk => { body += chunk; if (body.length > 65536) req.destroy(Error('BODY_EXCESIVO')); });
      res.on('end', () => resolve({ status: res.statusCode, location: res.headers.location, protocol, body, echo: res.headers['x-test-run-id'] }));
    });
    req.on('socket', socket => { if (secure) socket.on('secureConnect', () => { protocol = socket.getProtocol(); }); });
    req.on('timeout', () => req.destroy(Object.assign(Error('ETIMEDOUT'), { code: 'ETIMEDOUT' })));
    req.on('error', e => resolve({ error: e.code || e.message, protocol }));
  });
}
function local() {
  const v = parseEnv(fs.readFileSync(ENV_PATH, 'utf8'));
  const c = []; const ck = (n, ok) => c.push([n, !!ok]);
  ck('caso oficial', CASOS.join() === 'TC-M03-212');
  ck('autorización desactivada', v.QA_AUTORIZADO === 'NO');
  ck('barrera sin autorización', !gate(v, { ambiente: 'TEST', autorizacion: 'DEV-12345678', tipo: 'evaluacion', efectos: ['ninguno'] }, { sandbox: true }).ok);
  ck('barrera DEV', !gate({ ...v, QA_AUTORIZADO: 'SI' }, { ambiente: 'DEV', autorizacion: 'DEV-12345678', tipo: 'evaluacion', efectos: ['ninguno'] }, { sandbox: true }).ok);
  ck('rejection HTTP', plainOutcome({ error: 'ECONNREFUSED' }).ok);
  ck('redirect HTTPS mismo host', plainOutcome({ status: 301, location: 'https://test.example/iot/monitoreo/dashboard', url: 'http://test.example/iot/monitoreo/dashboard', telemetry: false }).ok);
  ck('redirección externa rechazada', !plainOutcome({ status: 302, location: 'https://other.example/', url: 'http://test.example/', telemetry: false }).ok);
  ck('contenido telemétrico inseguro rechazado', !plainOutcome({ status: 401, url: 'http://test.example/', telemetry: true }).ok);
  ck('timeout bloqueado', plainOutcome({ error: 'ETIMEDOUT' }).blocked);
  ck('PRE prevalece sobre ASSERT', verdict('CONCLUIDA', [{ ok: false }], [{ ok: false, observado: true }]) === 'BLOQUEADO');
  ck('sintaxis Node', spawnSync(process.execPath, ['--check', fileURLToPath(import.meta.url)]).status === 0);
  ck('sin RESULTADOS', !fs.existsSync(path.join(DIR, 'RESULTADOS')));
  ck('sin secretos literales', ![v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD].filter(x => x?.length > 5).some(x => fs.readFileSync(fileURLToPath(import.meta.url), 'utf8').includes(x)));
  c.forEach(([n, ok]) => console.log(`${ok ? 'OK' : 'FALLO'} ${n}`));
  console.log(`G109 ${c.filter(x => x[1]).length}/${c.length}`);
  return c.every(x => x[1]) ? 0 : 1;
}
async function execute(a) {
  const v = parseEnv(fs.readFileSync(ENV_PATH, 'utf8'));
  const g = gate(v, a, { sandbox: true });
  if (!g.ok) { console.error(`EJECUCIÓN NO AUTORIZADA: ${g.errores.join(', ')}`); return 2; }
  const c = evidence(DIR, 109, CASOS, a, v); const { ev } = c;
  ev.rf = 'RF-58'; ev.cu = 'CU04';
  try {
    const url = new URL(`${g.api}${ROUTE}`);
    const httpsResult = await probe(url, { 'X-Test-Run-Id': c.run, 'X-Sandbox-Secret': v.QA_SANDBOX_SECRET }, true);
    if (httpsResult.error) throw Error(`PRE: HTTPS no verificable (${httpsResult.error})`);
    ev.pre.push({ nombre: 'respuesta HTTPS aislada por sandbox', ok: httpsResult.echo === c.run });
    ev.asserts.push({ nombre: '[TC-M03-212][ASSERT] TLS negociado es 1.3', ok: httpsResult.protocol === 'TLSv1.3', observado: !!httpsResult.protocol, detalle: httpsResult.protocol });
    ev.info.push({ nombre: 'HTTP HTTPS sin autenticación', status: httpsResult.status });
    const plain = new URL(url); plain.protocol = 'http:'; plain.port = '80';
    const r = await probe(plain, {}, false); // Ningún secreto, token ni cabecera de sandbox viaja en claro.
    const p = plainOutcome({ ...r, url: plain.href, telemetry: /"(?:sensores|ultimo_valor|timestamp_captura|unidad_medida)"\s*:/.test(r.body || '') });
    if (p.blocked) ev.pre.push({ nombre: 'sonda HTTP concluyente', ok: false, detalle: p.mode });
    else ev.asserts.push({ nombre: '[TC-M03-212][ASSERT] HTTP plano rechazado o redirigido sin telemetría', ok: p.ok, observado: true, detalle: p.mode });
    ev.info.push({ nombre: 'sonda HTTP sin credenciales', status: r.status ?? null, error: r.error ?? null });
    ev.estado = 'CONCLUIDA';
  } catch (e) { ev.estado = 'INTERRUMPIDA'; ev.dependencias.push(String(e.message)); }
  finally {
    try {
      const x = await request(g.api, c.run, v.QA_SANDBOX_SECRET, 'DELETE', `/test-control/runs/${c.run}`, { control: true });
      const y = await request(g.api, c.run, v.QA_SANDBOX_SECRET, 'DELETE', `/test-control/runs/${c.run}`, { control: true });
      ev.sandbox.rollback = [200, 404].includes(x.status) && y.status === 404;
      ev.sandbox.cierre = { primero: x.status, segundo: y.status };
    } catch (e) { ev.sandbox.rollback = false; ev.dependencias.push(`Cierre sandbox no verificable: ${e.message}`); }
    c.finish();
  }
  return ev.veredicto === 'APROBADO' ? 0 : 4;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { const a = args(process.argv.slice(2)); process.exitCode = a.modo === 'local' ? local() : await execute(a); }
  catch (e) { console.error(e.message); process.exitCode = 2; }
}
