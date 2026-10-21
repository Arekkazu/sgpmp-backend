#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { args, gate, parseEnv, ENV_PATH, ROOT, evidence, request, verdict } from './qa_lote6_base.mjs';

export const CASOS = ['TC-M03-211'];
const DIR = path.dirname(fileURLToPath(import.meta.url));
const COLLECTION = path.join(DIR, 'TC-M03-G108.postman_collection.json');
export function expired(jwt, now = Date.now()) {
  try { const [h, p, s] = jwt.split('.'); return !!(h && p && s && Number(JSON.parse(Buffer.from(p, 'base64url').toString()).exp) * 1000 < now); } catch { return false; }
}
export function tamper(jwt) {
  const parts = jwt.split('.');
  if (parts.length !== 3 || !parts[2]) throw Error('PRE: token QA no es JWT');
  parts[2] = (parts[2][0] === 'A' ? 'B' : 'A') + parts[2].slice(1);
  return parts.join('.');
}
function newmanModule() {
  const require = createRequire(path.join(ROOT, 'package.json'));
  try { return require('newman'); } catch {
    const npm = spawnSync('npm', ['root', '-g'], { encoding: 'utf8', shell: process.platform === 'win32' });
    if (npm.status) throw Error('Newman no disponible');
    return require(path.join(npm.stdout.trim(), 'newman'));
  }
}
function local() {
  const v = parseEnv(fs.readFileSync(ENV_PATH, 'utf8'));
  const col = JSON.parse(fs.readFileSync(COLLECTION, 'utf8'));
  const checks = [];
  const ck = (n, ok) => checks.push([n, !!ok]);
  ck('caso oficial único', CASOS.join() === 'TC-M03-211');
  ck('autorización desactivada', v.QA_AUTORIZADO === 'NO');
  ck('barrera ejecutor', !gate(v, { ambiente: 'TEST', autorizacion: 'DEV-12345678', tipo: 'evaluacion', efectos: ['notificacion-login'] }, { login: true, sandbox: true }).ok);
  ck('barrera DEV', !gate({ ...v, QA_AUTORIZADO: 'SI' }, { ambiente: 'DEV', autorizacion: 'DEV-12345678', tipo: 'evaluacion', efectos: ['notificacion-login'] }, { login: true, sandbox: true }).ok);
  ck('seis combinaciones', col.item.length === 6 && ['ausente', 'expirado', 'firma'].every(x => col.item.filter(i => i.name.includes(x)).length === 2));
  ck('guardia colección', JSON.stringify(col.event).includes('BLOQUEO_G108'));
  ck('aserciones 401 y sin datos', col.item.every(i => JSON.stringify(i.event).includes('401') && JSON.stringify(i.event).includes('sensores')));
  try { for (const e of [...col.event, ...col.item.flatMap(i => i.event || [])]) new Function(e.script.exec.join('\n')); ck('scripts Postman', true); } catch { ck('scripts Postman', false); }
  ck('JWT expirado real como condición', expired('a.' + Buffer.from(JSON.stringify({ exp: 1 })).toString('base64url') + '.s'));
  ck('firma manipulada distinta', tamper('a.b.ABC') !== 'a.b.ABC');
  ck('clasificación PRE/ASSERT', verdict('CONCLUIDA', [{ ok: false }], [{ ok: false, observado: true }]) === 'BLOQUEADO' && verdict('CONCLUIDA', [], [{ ok: false, observado: true }]) === 'RECHAZADO');
  ck('sintaxis Node', spawnSync(process.execPath, ['--check', fileURLToPath(import.meta.url)]).status === 0);
  ck('sin RESULTADOS', !fs.existsSync(path.join(DIR, 'RESULTADOS')));
  ck('sin secretos literales', [COLLECTION, fileURLToPath(import.meta.url)].every(p => ![v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_PROD_PASSWORD].filter(x => x?.length > 5).some(x => fs.readFileSync(p, 'utf8').includes(x))));
  checks.forEach(([n, ok]) => console.log(`${ok ? 'OK' : 'FALLO'} ${n}`));
  console.log(`G108 ${checks.filter(x => x[1]).length}/${checks.length}`);
  return checks.every(x => x[1]) ? 0 : 1;
}
async function execute(a) {
  const v = parseEnv(fs.readFileSync(ENV_PATH, 'utf8'));
  const g = gate(v, a, { login: true, sandbox: true });
  if (!g.ok) { console.error(`EJECUCIÓN NO AUTORIZADA: ${g.errores.join(', ')}`); return 2; }
  const c = evidence(DIR, 108, CASOS, a, v);
  const { ev, run } = c;
  ev.rf = 'RF-58'; ev.cu = 'CU04';
  let opened = false;
  const req = (method, route, options = {}) => request(g.api, run, v.QA_SANDBOX_SECRET, method, route, options);
  try {
    const probe = await req('DELETE', `/test-control/runs/${run}-PREFLIGHT`, { control: true });
    if (probe.status !== 404) throw Error('PRE: sandbox de TEST no verificable');
    opened = true;
    const login = await req('POST', '/sesiones/', { body: { correo_electronico: v.QA_PROD_EMAIL, contrasena: v.QA_PROD_PASSWORD || v.QA_COMMON_PASSWORD } });
    if (login.status !== 200 || !login.data?.token) throw Error('PRE: login QA');
    const token = login.data.token; c.secrets.push(token);
    const dash = await req('GET', '/iot/monitoreo/dashboard', { token });
    if (dash.status !== 200) throw Error(`PRE: descubrir unidad con permiso de monitoreo HTTP ${dash.status}`);
    const id = dash.data?.resumen_unidades?.find(x => Number.isSafeInteger(Number(x.id_infraestructura)))?.id_infraestructura;
    if (!id) throw Error('PRE: unidad visible para ruta parametrizada');
    ev.pre.push({ nombre: 'unidad y token QA válidos descubiertos por API', ok: true });
    const expiredToken = process.env.QA_G108_EXPIRED_TOKEN;
    const hasExpired = expired(expiredToken || '');
    if (expiredToken) c.secrets.push(expiredToken);
    if (!hasExpired) { ev.pre.push({ nombre: 'token JWT genuino expirado provisto por QA', ok: false }); ev.dependencias.push('Se requiere QA_G108_EXPIRED_TOKEN emitido oficialmente y ya expirado; no se puede fabricar una firma válida desde QA.'); }
    const collection = JSON.parse(fs.readFileSync(COLLECTION, 'utf8'));
    if (!hasExpired) collection.item = collection.item.filter(i => !i.name.includes('expirado'));
    const tokenFirma = tamper(token); c.secrets.push(tokenFirma);
    const vars = { base_url: g.api, test_base_url: g.api, qa_autorizado: v.QA_AUTORIZADO, ambiente: a.ambiente, autorizacion: a.autorizacion, run_id: run, sandbox_secret: v.QA_SANDBOX_SECRET, id_infraestructura: String(id), token_expirado: expiredToken || '', token_firma: tokenFirma, autorizado_run: 'SI' };
    const nr = await new Promise(resolve => newmanModule().run({ collection, environment: { values: Object.entries(vars).map(([key, value]) => ({ key, value })) }, reporters: [], silent: true }, (error, summary) => resolve({ error, summary })));
    if (nr.error) throw Error(`AUTOMATIZACION: Newman ${nr.error.message}`);
    for (const x of nr.summary?.run?.executions || []) for (const y of x.assertions || []) (y.assertion.includes('[PRE]') ? ev.pre : ev.asserts).push({ nombre: `${x.item.name}: ${y.assertion}`, ok: !y.error, observado: !y.assertion.includes('[PRE]'), detalle: y.error?.message });
    if (ev.asserts.length !== collection.item.length || ev.pre.length !== collection.item.length + (hasExpired ? 1 : 2)) throw Error('AUTOMATIZACION: faltan aserciones Newman');
    ev.estado = 'CONCLUIDA';
  } catch (e) { ev.estado = 'INTERRUMPIDA'; ev.dependencias.push(String(e.message)); }
  finally {
    if (opened) try {
      const x = await req('DELETE', `/test-control/runs/${run}`, { control: true });
      const y = await req('DELETE', `/test-control/runs/${run}`, { control: true });
      ev.sandbox.rollback = x.status === 200 && y.status === 404;
    } catch { ev.sandbox.rollback = false; }
    c.finish();
  }
  return ev.veredicto === 'APROBADO' ? 0 : 4;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { const a = args(process.argv.slice(2)); process.exitCode = a.modo === 'local' ? local() : await execute(a); }
  catch (e) { console.error(e.message); process.exitCode = 2; }
}
