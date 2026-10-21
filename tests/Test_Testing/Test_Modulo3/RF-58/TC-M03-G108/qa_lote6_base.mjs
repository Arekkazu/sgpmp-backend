import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../../..');
export const ENV_PATH = path.join(ROOT, '.env.qa');
export const nativeFetch = globalThis.fetch;
globalThis.fetch = async () => { throw Error('BLOQUEO_RED_LOTE6'); };

export function parseEnv(raw) {
  return Object.fromEntries(raw.split(/\r?\n/).map(line => /^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$/.exec(line)).filter(Boolean).map(m => [m[1], m[2].replace(/^(['"])(.*)\1$/, '$2')]));
}
export function args(argv) {
  const a = { modo: 'local', efectos: [] };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === '--validar-local') a.modo = 'local';
    else if (k === '--ejecutar') a.modo = 'ejecutar';
    else if (['--ambiente', '--autorizacion', '--tipo', '--version'].includes(k)) a[k.slice(2)] = argv[++i];
    else if (k === '--aceptar-efectos') a.efectos.push(...String(argv[++i] || '').split(','));
    else throw Error(`Argumento desconocido: ${k}`);
  }
  return a;
}
export function gate(v, a, { login = false, sandbox = false } = {}) {
  const errores = [];
  if (v.QA_AUTORIZADO !== 'SI') errores.push('QA_AUTORIZADO');
  if (a.ambiente !== 'TEST') errores.push('ambiente TEST');
  if (!a.autorizacion || a.autorizacion.trim().length < 8) errores.push('autorización de Desarrollo');
  if (!['evaluacion', 'reintento'].includes(a.tipo)) errores.push('tipo de evaluación');
  if (!a.efectos.includes(login ? 'notificacion-login' : 'ninguno')) errores.push('aceptación de efectos');
  const api = v.SIGAB_API_TEST_BASE?.replace(/\/+$/, '');
  if (api !== 'https://www.api.inmero.co/api-sgpmp-test') errores.push('API no coincide con la URL oficial de TEST');
  if (!/^https:\/\/[^/]+/i.test(api || '') || /(^|[-/.])dev([-/.]|$)/i.test(api)) errores.push('API HTTPS TEST');
  if (api && v.SIGAB_API_DEV_BASE?.replace(/\/+$/, '') === api) errores.push('API DEV');
  if (v.SIGAB_API_BASE && v.SIGAB_API_BASE.replace(/\/+$/, '') !== api) errores.push('alias API inconsistente');
  if (login && (!(v.QA_PROD_EMAIL && (v.QA_PROD_PASSWORD || v.QA_COMMON_PASSWORD)))) errores.push('credenciales QA');
  if (sandbox && !v.QA_SANDBOX_SECRET) errores.push('secreto sandbox');
  return { ok: !errores.length, errores, api };
}
export function version(dir, tipo, esperada) {
  const ns = fs.readdirSync(dir, { withFileTypes: true }).filter(x => x.isDirectory()).map(x => /^EvaluacionV(\d+)$/.exec(x.name)?.[1]).filter(Boolean).map(Number);
  const ultima = Math.max(1, ...ns);
  const folder = n => path.join(dir, ...(n === 1 ? [] : [`EvaluacionV${n}`]), 'RESULTADOS');
  const runs = fs.existsSync(folder(ultima)) ? fs.readdirSync(folder(ultima)).map(x => { try { return JSON.parse(fs.readFileSync(path.join(folder(ultima), x, 'evidencia.json'))).estado; } catch { return 'INCIERTO'; } }) : [];
  const n = tipo === 'reintento' ? (runs.length ? ultima : null) : !runs.length ? ultima : runs.includes('CONCLUIDA') ? ultima + 1 : runs.every(x => x === 'ABORTADA_PREFLIGHT') ? ultima : null;
  if (!n || (esperada && Number(esperada) !== n)) throw Error('Historial o versión ambiguos');
  return { n, folder: folder(n) };
}
export function verdict(estado, pre, asserts, rollback = true) {
  if (estado !== 'CONCLUIDA' || !rollback || pre.some(x => !x.ok)) return 'BLOQUEADO';
  if (asserts.some(x => !x.ok && x.observado)) return 'RECHAZADO';
  return asserts.length && asserts.every(x => x.ok) ? 'APROBADO' : 'BLOQUEADO';
}
export function redact(s, secrets = []) {
  return secrets.filter(x => x?.length > 3).reduce((t, x) => t.replaceAll(x, '[REDACTADO]'), String(s)).replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[JWT]');
}
export function evidence(dir, group, cases, a, v) {
  const { n, folder } = version(dir, a.tipo, a.version);
  const run = `G${group}-${n === 1 ? 'EVAL' : 'REEVAL'}-V${n}-${new Date().toISOString().replace(/\D/g, '').slice(0, 14)}`;
  const out = path.join(folder, run);
  fs.mkdirSync(out, { recursive: true });
  const secrets = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_PROD_PASSWORD, v.QA_SETUP_PASSWORD];
  const ev = { grupo: `TC-M03-G${group}`, casos, version: n, run_id: run, estado: 'EN_CURSO', pre: [], asserts: [], info: [], dependencias: [], sandbox: {}, inicio: new Date().toISOString() };
  const save = () => fs.writeFileSync(path.join(out, 'evidencia.json'), redact(JSON.stringify(ev, null, 2), secrets));
  const finish = () => {
    ev.veredicto = verdict(ev.estado, ev.pre, ev.asserts, ev.sandbox.rollback ?? true);
    ev.fin = new Date().toISOString(); save();
    const name = n === 1 ? `TC-M03-G${group}_resultado.md` : `TC-M03-G${group}_reevaluacion_V${n}.md`;
    fs.writeFileSync(path.join(out, name), redact(`# TC-M03-G${group} — ${cases.join(', ')}\n\nRUN: ${run}. Estado: ${ev.estado}. Resultado propuesto: ${ev.veredicto}; requiere revisión QA.\n\nPRE: ${JSON.stringify(ev.pre)}\n\nASSERT: ${JSON.stringify(ev.asserts)}\n\nINFO: ${JSON.stringify(ev.info)}\n\nDependencias: ${ev.dependencias.join('; ') || 'ninguna'}\n\nSandbox: ${JSON.stringify(ev.sandbox)}\n`, secrets));
  };
  return { n, run, out, ev, secrets, save, finish };
}
export async function request(api, run, secret, method, route, { token, body, control = false, timeout = 30000 } = {}) {
  const headers = { Accept: 'application/json', 'X-Sandbox-Secret': secret };
  if (!control) headers['X-Test-Run-Id'] = run;
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const response = await nativeFetch(`${api}${route}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), redirect: 'manual', signal: AbortSignal.timeout(timeout) });
  const data = await response.json().catch(() => null);
  if (!control && response.headers.get('x-test-run-id') !== run) throw Error('Falta eco de sandbox');
  return { status: response.status, data };
}
