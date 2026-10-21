#!/usr/bin/env node
// TC-M03-191: panel agregado de alertas activas del dashboard.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

export const GRUPO = 'TC-M03-G98';
export const CASOS = ['TC-M03-191'];
export const SEVERIDADES = ['CRITICO', 'ALTA', 'MEDIA'];
const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const ENV = path.join(ROOT, '.env.qa');
const COLLECTION = path.join(DIR, `${GRUPO}.postman_collection.json`);
const fetchReal = globalThis.fetch;
globalThis.fetch = async () => { throw Error('BLOQUEO_RED_G98'); };

export function leerEnv(texto) {
  const v = {};
  for (const linea of texto.split(/\r?\n/)) {
    const m = linea.match(/^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*)$/);
    if (m) v[m[1]] = m[2].trim().replace(/^(['"])(.*)\1$/, '$2');
  }
  return v;
}
export function autorizar(v, a) {
  const motivos = [];
  if (v.QA_AUTORIZADO !== 'SI') motivos.push('QA_AUTORIZADO debe ser SI');
  if (a.ambiente !== 'TEST') motivos.push('Ambiente distinto de TEST');
  if (!a.autorizacion || a.autorizacion.trim().length < 8) motivos.push('Falta referencia verificable de Desarrollo');
  if (!a.efectos.includes('notificacion-login')) motivos.push('Falta aceptar notificacion-login');
  for (const k of ['QA_PROD_EMAIL', 'QA_SANDBOX_SECRET', 'SIGAB_API_TEST_BASE']) if (!v[k]) motivos.push(`Falta ${k}`);
  if (!(v.QA_PROD_PASSWORD || v.QA_COMMON_PASSWORD)) motivos.push('Falta contraseña QA del Productor');
  const api = v.SIGAB_API_TEST_BASE?.replace(/\/+$/, '');
  if (api !== 'https://www.api.inmero.co/api-sgpmp-test') motivos.push('API no coincide con la URL oficial de TEST');
  if (!/^https:\/\//i.test(api || '') || /(^|[-/.])dev([-/.]|$)/i.test(api || '')) motivos.push('API no es HTTPS TEST');
  if (v.SIGAB_API_BASE && v.SIGAB_API_BASE.replace(/\/+$/, '') !== api) motivos.push('Alias de API distinto de TEST');
  if (api && api === v.SIGAB_API_DEV_BASE?.replace(/\/+$/, '')) motivos.push('API coincide con DEV');
  return { ok: motivos.length === 0, motivos, api };
}
export function version(dir, tipo, confirmada) {
  const dirs = fs.readdirSync(dir, { withFileTypes: true }).filter(x => x.isDirectory()).map(x => /^EvaluacionV(\d+)$/.exec(x.name)?.[1]).filter(Boolean).map(Number);
  const ultima = Math.max(1, ...dirs);
  const base = n => n === 1 ? path.join(dir, 'RESULTADOS') : path.join(dir, `EvaluacionV${n}`, 'RESULTADOS');
  const runs = fs.existsSync(base(ultima)) ? fs.readdirSync(base(ultima)).map(x => { try { return JSON.parse(fs.readFileSync(path.join(base(ultima), x, 'evidencia.json'), 'utf8')).estado; } catch { return 'INCIERTO'; } }) : [];
  const n = tipo === 'reintento' ? (runs.length ? ultima : null) : !runs.length ? ultima : runs.includes('CONCLUIDA') ? ultima + 1 : runs.every(x => x === 'ABORTADA_PREFLIGHT') ? ultima : null;
  if (!n || (confirmada && Number(confirmada) !== n)) throw Error('Historial ambiguo o versión incoherente');
  return n;
}
export function cobertura(alertas) {
  const porUnidad = new Map();
  for (const a of alertas) {
    if (a.estado_alerta !== 'ACTIVA' || !Number.isSafeInteger(Number(a.id_infraestructura)) || Number(a.id_infraestructura) <= 0) continue;
    const lista = porUnidad.get(Number(a.id_infraestructura)) || [];
    lista.push(a); porUnidad.set(Number(a.id_infraestructura), lista);
  }
  for (const [id, lista] of porUnidad) {
    if (lista.length !== 3) continue;
    if (lista.some(a => !Number.isSafeInteger(Number(a.id_sensor)) || Number(a.id_sensor) <= 0 || !Number.isSafeInteger(Number(a.id_activo_biologico)) || Number(a.id_activo_biologico) <= 0)) continue;
    for (const c of lista.filter(x => x.severidad === 'CRITICO'))
      for (const a of lista.filter(x => x.severidad === 'ALTA' && x.id_sensor !== c.id_sensor))
        for (const m of lista.filter(x => x.severidad === 'MEDIA' && x.id_sensor !== c.id_sensor && x.id_sensor !== a.id_sensor))
          return [id, [c, a, m]];
  }
  return null;
}
export function resultado(aserciones) {
  const requeridas = ['API-191-01', 'API-191-02', 'API-191-03', 'API-191-04'];
  return requeridas.every(id => aserciones.some(a => a.nombre.includes(id) && a.ok)) && aserciones.every(a => a.ok);
}
function argumentos(argv) {
  const a = { modo: 'local', efectos: [] };
  for (let i = 0; i < argv.length; i++) {
    const x = argv[i];
    if (x === '--ejecutar') a.modo = 'ejecutar';
    else if (x === '--validar-local') a.modo = 'local';
    else if (['--ambiente', '--autorizacion', '--tipo', '--version'].includes(x)) a[x.slice(2)] = argv[++i];
    else if (x === '--aceptar-efectos') a.efectos.push(...String(argv[++i] || '').split(','));
    else throw Error(`Argumento desconocido: ${x}`);
  }
  return a;
}
function newmanModulo() {
  const npm = spawnSync('npm', ['root', '-g'], { encoding: 'utf8', shell: process.platform === 'win32' });
  if (npm.status !== 0) throw Error('Newman no disponible');
  const m = createRequire(path.join(ROOT, 'package.json'))(path.join(npm.stdout.trim(), 'newman'));
  if (typeof m.run !== 'function') throw Error('Newman sin API run');
  return m;
}
function local() {
  const checks = []; const ck = (n, x) => checks.push([n, !!x]);
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const col = JSON.parse(fs.readFileSync(COLLECTION, 'utf8'));
  ck('Matriz TC-M03-191', CASOS.join() === 'TC-M03-191');
  ck('Severidades de la matriz', SEVERIDADES.join() === 'CRITICO,ALTA,MEDIA');
  ck('Configuración compartida y QA_AUTORIZADO=NO', fs.existsSync(ENV) && v.QA_AUTORIZADO === 'NO');
  ck('Barrera rechaza ejecución actual', !autorizar(v, { ambiente: 'TEST', autorizacion: '', efectos: [] }).ok);
  ck('Barrera acepta condiciones futuras válidas', autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ambiente: 'TEST', autorizacion: 'REF-DESARROLLO', efectos: ['notificacion-login'] }).ok);
  ck('Barrera rechaza DEV', !autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ambiente: 'DEV', autorizacion: 'REF-DESARROLLO', efectos: ['notificacion-login'] }).ok);
  ck('Variables QA resueltas', !!v.QA_PROD_EMAIL && !!(v.QA_PROD_PASSWORD || v.QA_COMMON_PASSWORD) && !!v.QA_SANDBOX_SECRET);
  ck('Colección Postman v2.1', /v2\.1\.0/.test(col.info?.schema || '') && col.item?.length === 1);
  ck('Aserciones exactas', ['API-191-01', 'API-191-02', 'API-191-03', 'API-191-04'].every(x => JSON.stringify(col).includes(x)));
  const vars = new Set([...JSON.stringify(col).matchAll(/\{\{([a-z_]+)\}\}/g)].map(x => x[1]));
  ck('Variables Newman resueltas por el ejecutor', [...vars].every(x => ['base_url', 'run_id', 'sandbox_secret', 'token', 'id_unidad', 'ids_alertas', 'ids_activos'].includes(x)));
  ck('Barrera propia de Newman', JSON.stringify(col).includes('BLOQUEO_G98'));
  try { for (const e of [...(col.event || []), ...col.item.flatMap(x => x.event || [])]) new Function((e.script?.exec || []).join('\n')); ck('Sintaxis Postman', true); } catch { ck('Sintaxis Postman', false); }
  ck('Sintaxis ejecutor', spawnSync(process.execPath, ['--check', fileURLToPath(import.meta.url)]).status === 0);
  const fixture = SEVERIDADES.map((severidad, i) => ({ estado_alerta: 'ACTIVA', id_infraestructura: 11, id_sensor: i + 1, id_activo_biologico: 7, severidad }));
  ck('Descubrimiento exige tres severidades y sensores distintos de una unidad', !!cobertura(fixture) && !cobertura(fixture.slice(1)) && !cobertura(fixture.map(x => ({ ...x, id_sensor: 1 }))));
  const completas = ['API-191-01', 'API-191-02', 'API-191-03', 'API-191-04'].map(nombre => ({ nombre, ok: true }));
  ck('Veredicto exige todas las aserciones', resultado(completas) && !resultado(completas.slice(1)));
  ck('Sin RESULTS de preparación', !fs.existsSync(path.join(DIR, 'RESULTADOS')));
  ck('Sin secretos literales', [fileURLToPath(import.meta.url), COLLECTION].every(f => ![v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_PROD_PASSWORD].filter(x => x?.length > 4).some(x => fs.readFileSync(f, 'utf8').includes(x))));
  try { newmanModulo(); ck('Newman disponible', true); } catch { ck('Newman disponible', false); }
  for (const [n, ok] of checks) console.log(`${ok ? 'OK' : 'FALLO'} ${n}`);
  console.log(`G98 local ${checks.filter(x => x[1]).length}/${checks.length}`);
  return checks.every(x => x[1]) ? 0 : 1;
}
async function ejecutar(a) {
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const gate = autorizar(v, a);
  if (!gate.ok) { console.error(`EJECUCIÓN NO AUTORIZADA: ${gate.motivos.join('; ')}`); return 2; }
  if (!['evaluacion', 'reintento'].includes(a.tipo)) { console.error('Indique --tipo evaluacion|reintento'); return 2; }
  const n = version(DIR, a.tipo, a.version), newman = newmanModulo();
  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14);
  const run = `G98-${n === 1 ? 'EVAL' : 'REEVAL'}-V${n}-${stamp}`;
  const base = n === 1 ? path.join(DIR, 'RESULTADOS') : path.join(DIR, `EvaluacionV${n}`, 'RESULTADOS');
  const out = path.join(base, run); fs.mkdirSync(base, { recursive: true }); fs.mkdirSync(out);
  const ev = { grupo: GRUPO, rf: 'RF-58', cu: 'CU04', casos: CASOS, version: n, run_id: run, estado: 'EN_CURSO', fase: 'PREFLIGHT', autorizacion: a.autorizacion, dependencias: [], aserciones: [], sandbox: {}, inicio: new Date().toISOString() };
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_PROD_PASSWORD].filter(Boolean);
  const limpiar = x => secretos.reduce((s, y) => s.replaceAll(y, '[REDACTADO]'), String(x));
  const guardar = () => fs.writeFileSync(path.join(out, 'evidencia.json'), limpiar(JSON.stringify(ev, null, 2)));
  let token, abierto = false;
  async function req(m, ruta, body, control = false) {
    const headers = { Accept: 'application/json', 'X-Sandbox-Secret': v.QA_SANDBOX_SECRET };
    if (!control) headers['X-Test-Run-Id'] = run;
    if (token) headers.Authorization = `Bearer ${token}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const r = await fetchReal(`${gate.api}${ruta}`, { method: m, headers, body: body === undefined ? undefined : JSON.stringify(body), redirect: 'manual', signal: AbortSignal.timeout(30000) });
    const data = await r.json().catch(() => null);
    if (!control && r.headers.get('x-test-run-id') !== run) throw Error(`Sandbox sin eco: ${m} ${ruta}`);
    return { status: r.status, data };
  }
  function need(r, status, label) { if (r.status !== status) throw Error(`${label}: HTTP ${r.status}`); return r.data; }
  try {
    const probe = await req('DELETE', `/test-control/runs/${run}-PREFLIGHT`, undefined, true);
    need(probe, 404, 'Preflight sandbox'); abierto = true;
    const login = need(await req('POST', '/sesiones/', { correo_electronico: v.QA_PROD_EMAIL, contrasena: v.QA_PROD_PASSWORD || v.QA_COMMON_PASSWORD }), 200, 'Login Productor');
    token = login.token; if (!token) throw Error('Login sin token'); secretos.push(token);
    const me = need(await req('GET', '/usuarios/me'), 200, 'Identidad');
    if (!/productor/i.test(me.nombre_rol || '')) throw Error('La cuenta QA no tiene rol Productor');
    ev.fase = 'DESCUBRIMIENTO';
    const ruta = p => `/iot/alertas?estado=ACTIVA&pagina=${p}&por_pagina=200`;
    const first = need(await req('GET', ruta(1)), 200, 'Listado de alertas fuente');
    const alertas = [...(first.items || [])];
    const paginas = Math.ceil(Number(first.total || 0) / 200);
    if (!Number.isFinite(paginas) || paginas > 500) throw Error('Paginación de alertas no verificable');
    for (let p = 2; p <= paginas; p++) alertas.push(...(need(await req('GET', ruta(p)), 200, `Alertas p${p}`).items || []));
    if (alertas.length !== Number(first.total || 0)) throw Error('Paginación de alertas incompleta');
    const fixture = cobertura(alertas);
    if (!fixture) { ev.dependencias.push('No hay tres alertas ACTIVA de severidad CRITICO, ALTA y MEDIA en distintos sensores de una misma unidad accesible, con activo biológico asociado. El contrato de creación actual no permite preparar ALTA/MEDIA; no se inventa ni se simula una alerta.'); ev.estado = 'ABORTADA_PREFLIGHT'; return 3; }
    const [idUnidad, testigos] = fixture;
    ev.datos = { id_unidad: idUnidad, alertas: testigos.map(x => ({ id_alerta: x.id_alerta, severidad: x.severidad, id_sensor: x.id_sensor, id_activo_biologico: x.id_activo_biologico })), origen: 'GET /iot/alertas, solo lectura' };
    ev.fase = 'ESCENARIO'; guardar();
    const env = { base_url: gate.api, run_id: run, sandbox_secret: v.QA_SANDBOX_SECRET, token, autorizado_run: 'SI', id_unidad: String(idUnidad), ids_alertas: JSON.stringify(testigos.map(x => Number(x.id_alerta))), ids_activos: JSON.stringify(testigos.map(x => Number(x.id_activo_biologico))) };
    const nr = await new Promise(resolve => newman.run({ ignoreRedirects: true,  collection: JSON.parse(fs.readFileSync(COLLECTION, 'utf8')), environment: { values: Object.entries(env).map(([key, value]) => ({ key, value })) }, reporters: [], silent: true }, (error, summary) => resolve({ error, summary })));
    ev.aserciones = (nr.summary?.run?.executions || []).flatMap(e => (e.assertions || []).map(x => ({ nombre: x.assertion, ok: !x.error, error: x.error?.message })));
    ev.error_newman = nr.error ? limpiar(nr.error.message) : null;
    ev.fallos_newman = nr.summary?.run?.failures?.length || 0;
    ev.estado = 'CONCLUIDA';
  } catch (e) { ev.estado = ev.fase === 'ESCENARIO' ? 'INTERRUMPIDA' : 'ABORTADA_PREFLIGHT'; ev.dependencias.push(limpiar(e.message)); }
  finally {
    try { if (abierto) { const c = await req('DELETE', `/test-control/runs/${run}`, undefined, true); const d = await req('DELETE', `/test-control/runs/${run}`, undefined, true); ev.sandbox.rollback = c.status === 200 && d.status === 404; } } catch (e) { ev.sandbox.rollback = false; ev.dependencias.push(limpiar(e.message)); }
    ev.veredicto = ev.estado !== 'CONCLUIDA' || !ev.sandbox.rollback ? 'BLOQUEADO' : !ev.error_newman && !ev.fallos_newman && resultado(ev.aserciones) ? 'APROBADO' : 'RECHAZADO';
    ev.clasificacion = !ev.sandbox.rollback ? 'INFRAESTRUCTURA' : ev.estado === 'ABORTADA_PREFLIGHT' ? 'PRECONDICION' : ev.estado !== 'CONCLUIDA' || ev.error_newman ? 'AUTOMATIZACION_O_INFRAESTRUCTURA' : ev.veredicto === 'RECHAZADO' ? 'ASERCION_FUNCIONAL' : 'SIN_FALLOS';
    ev.fin = new Date().toISOString(); guardar();
    const informe = n === 1 ? `${GRUPO}_resultado.md` : `${GRUPO}_reevaluacion_V${n}.md`;
    fs.writeFileSync(path.join(out, informe), limpiar(`# ${GRUPO} — ${CASOS[0]}\n\nEstado: ${ev.estado}. Veredicto: ${ev.veredicto}.\n\nAlertas fuente: ${JSON.stringify(ev.datos || {})}.\n\nAserciones: ${JSON.stringify(ev.aserciones)}\n\nDependencias: ${ev.dependencias.join('; ') || 'ninguna'}\n\nRollback: ${ev.sandbox.rollback ? 'confirmado' : 'no confirmado'}\n`));
  }
  console.log(`${GRUPO}: ${ev.estado} — ${out}`); return ev.estado === 'CONCLUIDA' ? 0 : 4;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let code; try { const a = argumentos(process.argv.slice(2)); code = a.modo === 'local' ? local() : await ejecutar(a); } catch (e) { console.error(e.message); code = 2; } process.exitCode = code;
}
