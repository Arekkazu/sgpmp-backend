#!/usr/bin/env node
// RF-58 / CU04: TC-M03-192 y TC-M03-193. Solo la ejecución autorizada usa red.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';

export const CASOS = ['TC-M03-192', 'TC-M03-193'];
const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const ENV = path.join(ROOT, '.env.qa');
const COLLECTION = path.join(DIR, 'TC-M03-G99.postman_collection.json');
const SPEC = path.join(DIR, 'tc_m03_g99.cy.js');
const realFetch = globalThis.fetch;
export const fetchAutorizado = realFetch;
globalThis.fetch = async () => { throw Error('BLOQUEO_RED_G99'); };

export function envQa(raw) {
  return Object.fromEntries(raw.split(/\r?\n/).map(x => /^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$/.exec(x)).filter(Boolean).map(m => [m[1], m[2].replace(/^(['"])(.*)\1$/, '$2')]));
}
export function autorizar(v, a) {
  const errores = [];
  if (v.QA_AUTORIZADO !== 'SI') errores.push('QA_AUTORIZADO');
  if (a.ambiente !== 'TEST') errores.push('ambiente TEST');
  if (!a.autorizacion || a.autorizacion.trim().length < 8) errores.push('autorización de Desarrollo');
  if (!a.efectos?.includes('notificacion-login')) errores.push('efecto notificacion-login');
  for (const k of ['QA_SETUP_EMAIL', 'QA_PROD_EMAIL', 'QA_SANDBOX_SECRET', 'SIGAB_API_TEST_BASE', 'SIGAB_FRONT_TEST_URL']) if (!v[k]) errores.push(k);
  if (!(v.QA_SETUP_PASSWORD || v.QA_COMMON_PASSWORD) || !(v.QA_PROD_PASSWORD || v.QA_COMMON_PASSWORD)) errores.push('contraseñas QA');
  const api = v.SIGAB_API_TEST_BASE?.replace(/\/+$/, '');
  const web = v.SIGAB_FRONT_TEST_URL?.replace(/\/+$/, '');
  if (api !== 'https://www.api.inmero.co/api-sgpmp-test' || web !== 'https://api.inmero.co/sigab-test') errores.push('destinos no coinciden con las URLs oficiales de TEST');
  if (!/^https:\/\//.test(api || '') || !/^https:\/\//.test(web || '') || /(^|[-/.])dev([-/.]|$)/i.test(`${api} ${web}`)) errores.push('destinos HTTPS TEST');
  if (api && api === v.SIGAB_API_DEV_BASE?.replace(/\/+$/, '')) errores.push('API apunta a DEV');
  if (web && web === v.SIGAB_FRONT_DEV_URL?.replace(/\/+$/, '')) errores.push('WEB apunta a DEV');
  if (v.SIGAB_API_BASE && v.SIGAB_API_BASE.replace(/\/+$/, '') !== api) errores.push('alias API inconsistente');
  if (v.SIGAB_FRONT_URL && v.SIGAB_FRONT_URL.replace(/\/+$/, '') !== web) errores.push('alias WEB inconsistente');
  return { ok: !errores.length, errores, api, web };
}
export function version(dir, tipo, esperada) {
  const ns = fs.readdirSync(dir, { withFileTypes: true }).filter(x => x.isDirectory()).map(x => /^EvaluacionV(\d+)$/.exec(x.name)?.[1]).filter(Boolean).map(Number);
  const ultima = Math.max(1, ...ns);
  const carpeta = n => path.join(dir, ...(n === 1 ? [] : [`EvaluacionV${n}`]), 'RESULTADOS');
  const runs = fs.existsSync(carpeta(ultima)) ? fs.readdirSync(carpeta(ultima)).map(x => { try { return JSON.parse(fs.readFileSync(path.join(carpeta(ultima), x, 'evidencia.json'))).estado; } catch { return 'INCIERTO'; } }) : [];
  const n = decidirVersion(ultima, runs, tipo);
  if (!n || (esperada && Number(esperada) !== n)) throw Error('Historial o versión ambiguos');
  return { n, carpeta: carpeta(n) };
}
export function decidirVersion(ultima, runs, tipo) {
  return tipo === 'reintento' ? (runs.length ? ultima : null) : !runs.length ? ultima : runs.includes('CONCLUIDA') ? ultima + 1 : runs.every(x => x === 'ABORTADA_PREFLIGHT') ? ultima : null;
}
export function clasificar(pre, asserts, rollback) {
  if (!rollback || pre.some(x => !x.ok)) return 'BLOQUEADO';
  if (asserts.some(x => !x.ok && x.observado)) return 'RECHAZADO';
  return asserts.length >= 5 && asserts.every(x => x.ok) ? 'APROBADO' : 'BLOQUEADO';
}
export function tipoFallo(mensaje) {
  if (/ECONN|ETIMEDOUT|fetch failed|HTTP 50[234]|timeout/i.test(mensaje)) return 'INFRAESTRUCTURA';
  if (/Cypress no completó|Newman técnico|BLOQUEO_|TypeError|SyntaxError/i.test(mensaje)) return 'AUTOMATIZACION';
  if (/credencial|contraseña|Login QA|rol Productor|Administrador/i.test(mensaje)) return 'CONFIGURACION';
  return 'PRECONDICION_O_CAPACIDAD';
}
export function clienteSoloRenderiza({ hook, card, escala, pill }) {
  const mapper = /export function semaforoToGauge[\s\S]*?\n\}/.exec(escala)?.[0] || '';
  return /estado_semaforo:\s*x\.estado_semaforo/.test(hook)
    && /semaforoToGauge\(sensor\.estado_semaforo\)/.test(card)
    && /<SemaforoPill estado=\{sensor\.estado_semaforo\}/.test(card)
    && /switch\s*\(\(estado\s*\?\?\s*''\)\.toUpperCase\(\)\)/.test(mapper)
    && !/ultimo_valor|valor\s*[<>]=?/.test(mapper)
    && /META\[normalizar\(estado\)\]/.test(pill);
}
export function sqlTestigo(serial) {
  if (!/^[A-Za-z0-9_-]{1,50}$/.test(serial)) throw Error('Serial inválido');
  return `SELECT count(*) AS n FROM auditoria.logs_dml WHERE esquema_afectado='modulo9' AND tabla_afectada='dispositivos_iot' AND tipo_operacion='INSERT' AND datos_nuevos->>'serial'='${serial}'`;
}
export const SQL_HUELLA = "SELECT count(*) AS n, md5(coalesce(string_agg(md5(row_to_json(t)::text), '' ORDER BY t.id_telemetria), '')) AS huella FROM modulo3.telemetrias t";
export function huella(r) {
  const d = r?.data?.data?.[0];
  return r?.status === 200 && /^\d+$/.test(String(d?.n)) && /^[a-f0-9]{32}$/.test(String(d?.huella)) ? { n: Number(d.n), huella: d.huella } : null;
}
export function argumentos(argv) {
  const a = { modo: 'local', efectos: [] };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === '--validar-local') a.modo = 'local';
    else if (k === '--ejecutar') a.modo = 'ejecutar';
    else if (['--ambiente', '--autorizacion', '--tipo', '--version'].includes(k)) a[k.slice(2)] = argv[++i];
    else if (k === '--aceptar-efectos') a.efectos.push(...String(argv[++i] || '').split(','));
    else throw Error(`Argumento desconocido ${k}`);
  }
  return a;
}
function moduloGlobal(nombre) {
  if (nombre === 'cypress') return createRequire(path.join(ROOT, 'package.json'))('cypress');
  const npm = spawnSync('npm', ['root', '-g'], { encoding: 'utf8', shell: process.platform === 'win32' });
  if (npm.status !== 0) throw Error(`npm global no disponible (${nombre})`);
  return createRequire(path.join(ROOT, 'package.json'))(path.join(npm.stdout.trim(), nombre));
}
function validarLocal() {
  const v = envQa(fs.readFileSync(ENV, 'utf8'));
  const col = JSON.parse(fs.readFileSync(COLLECTION, 'utf8'));
  const spec = fs.readFileSync(SPEC, 'utf8');
  const checks = [];
  const ck = (n, ok) => checks.push([n, !!ok]);
  ck('casos originales', CASOS.join() === 'TC-M03-192,TC-M03-193');
  ck('configuración compartida', v.QA_AUTORIZADO === 'NO');
  ck('barrera actual', !autorizar(v, { ambiente: 'TEST', autorizacion: '', efectos: [] }).ok);
  ck('barrera DEV', !autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ambiente: 'DEV', autorizacion: 'DEV-REF-1234', efectos: ['notificacion-login'] }).ok);
  ck('colección y aserciones', /v2\.1\.0/.test(col.info.schema) && col.item.length === 1 && ['TC-M03-193', 'estado_semaforo', 'VERDE', 'AMARILLO', 'ROJO', 'GRIS'].every(x => JSON.stringify(col).includes(x)));
  ck('guardia Newman', JSON.stringify(col.event).includes('BLOQUEO_G99'));
  ck('variables Newman resueltas', [...JSON.stringify(col).matchAll(/\{\{([a-z_]+)\}\}/g)].every(x => ['base_url', 'token', 'run_id', 'sandbox_secret', 'id_infraestructura', 'id_sensor'].includes(x[1])));
  try { for (const e of [...col.event, ...col.item.flatMap(x => x.event || [])]) new Function(e.script.exec.join('\n')); ck('scripts Postman', true); } catch { ck('scripts Postman', false); }
  ck('spec cubre 192 y 193', ['TC-M03-192', 'TC-M03-193', 'estado_semaforo', 'Sin se'].every(x => spec.includes(x)));
  ck('canal push no aislado bloqueado', ['WebSocket', 'EventSource', '__qaPushSinSandbox'].every(x => spec.includes(x)));
  ck('sintaxis ejecutor', spawnSync(process.execPath, ['--check', fileURLToPath(import.meta.url)]).status === 0);
  ck('sintaxis spec', spawnSync(process.execPath, ['--check', SPEC]).status === 0);
  ck('sin RESULTADOS', !fs.existsSync(path.join(DIR, 'RESULTADOS')));
  ck('sin secretos literales', [COLLECTION, SPEC, fileURLToPath(import.meta.url)].every(f => ![v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_PROD_PASSWORD, v.QA_SETUP_PASSWORD].filter(x => x?.length > 5).some(x => fs.readFileSync(f, 'utf8').includes(x))));
  try { ck('Newman y Cypress disponibles', !!moduloGlobal('newman').run && !!moduloGlobal('cypress').run); } catch { ck('Newman y Cypress disponibles', false); }
  for (const [n, ok] of checks) console.log(`${ok ? 'OK' : 'FALLO'} ${n}`);
  console.log(`G99 ${checks.filter(x => x[1]).length}/${checks.length}`);
  return checks.every(x => x[1]) ? 0 : 1;
}

async function ejecutar(a) {
  const v = envQa(fs.readFileSync(ENV, 'utf8'));
  const gate = autorizar(v, a);
  if (!gate.ok) { console.error(`EJECUCIÓN NO AUTORIZADA: ${gate.errores.join(', ')}`); return 2; }
  if (!['evaluacion', 'reintento'].includes(a.tipo)) throw Error('--tipo evaluacion|reintento obligatorio');
  const { n, carpeta } = version(DIR, a.tipo, a.version);
  const newman = moduloGlobal('newman'), cypress = moduloGlobal('cypress');
  const stamp = new Date().toISOString().replace(/\D/g, '').slice(0, 14);
  const run = `G99-${n === 1 ? 'EVAL' : 'REEVAL'}-V${n}-${stamp}`;
  const out = path.join(carpeta, run);
  fs.mkdirSync(carpeta, { recursive: true }); fs.mkdirSync(out);
  const serial = `${v.QA_DEVICE_PREFIX || 'QAAUTO'}-G99-${stamp}`.slice(0, 50);
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_PROD_PASSWORD].filter(Boolean);
  const limpiar = x => secretos.reduce((s, k) => s.replaceAll(k, '[REDACTADO]'), String(x)).replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[JWT]');
  const ev = { grupo: 'TC-M03-G99', casos: CASOS, rf: 'RF-58', cu: 'CU04', version: n, run_id: run, estado: 'EN_CURSO', fase: 'PREFLIGHT', pre: [], asserts: [], dependencias: [], sandbox: {}, inicio: new Date().toISOString() };
  const guardar = () => fs.writeFileSync(path.join(out, 'evidencia.json'), limpiar(JSON.stringify(ev, null, 2)));
  let abierto = false, creado = false;
  async function req(method, ruta, { token, body, rid = run, control = false } = {}) {
    const h = { Accept: 'application/json', 'X-Sandbox-Secret': v.QA_SANDBOX_SECRET };
    if (!control) h['X-Test-Run-Id'] = rid;
    if (token) h.Authorization = `Bearer ${token}`;
    if (body !== undefined) h['Content-Type'] = 'application/json';
    const r = await realFetch(`${gate.api}${ruta}`, { method, headers: h, body: body === undefined ? undefined : JSON.stringify(body), redirect: 'manual', signal: AbortSignal.timeout(30000) });
    const data = await r.json().catch(() => null);
    if (!control && r.headers.get('x-test-run-id') !== rid) throw Error(`Falta eco de sandbox: ${ruta}`);
    return { status: r.status, data };
  }
  const need = (r, s, what) => { if (r.status !== s) throw Error(`${what}: HTTP ${r.status}`); return r.data; };
  const query = async (sql, rid = run) => req('POST', '/test-control/query', { body: { query: sql }, rid });
  async function fuera(sql, suffix) {
    const rid = `${run}-${suffix}`;
    try { return await query(sql, rid); } finally { await req('DELETE', `/test-control/runs/${rid}`, { control: true }); }
  }
  try {
    const s = await req('DELETE', `/test-control/runs/${run}-PREFLIGHT`, { control: true });
    if (s.status !== 404) throw Error('Sandbox de TEST no disponible');
    abierto = true;
    const login = async (email, pass) => { const d = need(await req('POST', '/sesiones/', { body: { correo_electronico: email, contrasena: pass } }), 200, 'Login QA'); if (!d?.token) throw Error('Login sin token'); secretos.push(d.token); return d.token; };
    const setup = await login(v.QA_SETUP_EMAIL, v.QA_SETUP_PASSWORD || v.QA_COMMON_PASSWORD);
    const prod = await login(v.QA_PROD_EMAIL, v.QA_PROD_PASSWORD || v.QA_COMMON_PASSWORD);
    const me = need(await req('GET', '/usuarios/me', { token: prod }), 200, 'Productor');
    if (!/productor/i.test(me.nombre_rol || '')) throw Error('La cuenta QA carece del rol Productor');
    const admin = need(await req('GET', '/usuarios/me', { token: setup }), 200, 'Preparador');
    if (!/administrador/i.test(admin.nombre_rol || '')) throw Error('La cuenta preparadora no es Administrador');
    // La sonda fuera del RUN debe poder ver un testigo real del catálogo de auditoría.
    const meta = "SELECT c.relrowsecurity AS rls, has_table_privilege(current_user,'auditoria.logs_dml','SELECT') AS lectura, EXISTS (SELECT 1 FROM pg_trigger t WHERE t.tgrelid='modulo9.dispositivos_iot'::regclass AND NOT t.tgisinternal AND t.tgenabled<>'D' AND pg_get_triggerdef(t.oid) ILIKE '%audit%') AS trigger_activo FROM pg_class c WHERE c.oid='auditoria.logs_dml'::regclass";
    const m = need(await fuera(meta, 'META'), 200, 'Metadatos testigo')?.data?.[0];
    if (!m || m.rls !== false || m.lectura !== true || m.trigger_activo !== true) throw Error('Testigo auditoría sin SELECT, RLS o trigger verificable');
    const control = need(await fuera("SELECT count(*) AS n FROM auditoria.logs_dml", 'CONTROL'), 200, 'Control visible')?.data?.[0];
    if (!control || !Number.isFinite(Number(control.n)) || Number(control.n) < 1) throw Error('No hay control observable fuera del RUN');
    // Preparación por contratos oficiales, todos los registros propios identificados por RUN.
    ev.fase = 'PREPARACION';
    const fp = new Set((need(await req('GET', '/configuracion/fincas', { token: prod }), 200, 'Fincas Productor').items || []).map(x => Number(x.id_finca)));
    const fsu = (need(await req('GET', '/configuracion/fincas', { token: setup }), 200, 'Fincas preparador').items || []).map(x => Number(x.id_finca));
    let finca = fsu.find(id => fp.has(id));
    if (!finca) finca = need(await req('POST', '/configuracion/fincas', { token: setup, body: { nombre: `QA Monitoreo ${stamp}`.replace(/\d/g, d => 'abcdefghij'[Number(d)]), ubicacion: { departamento: 'Huila', municipio: 'Neiva', vereda: 'QA', latitud: 2.9273, longitud: -75.2819 }, tamano_h: 1, id_usuario: me.id_usuario } }), 201, 'Crear finca').id_finca;
    const tipo = (need(await req('GET', '/configuracion/tipos-area?solo_activos=true', { token: setup }), 200, 'Tipos área').items || []).find(x => x.es_activo);
    const especie = (need(await req('GET', '/configuracion/especies?solo_activas=true', { token: setup }), 200, 'Especies').items || []).find(x => x.es_activo);
    const dispositivo = (need(await req('GET', '/configuracion/tipos-dispositivo-iot', { token: setup }), 200, 'Tipos dispositivo').items || []).find(x => x.categoria === 'SENSOR');
    const rango = (need(await req('GET', '/configuracion/sensores/rangos-calibracion', { token: setup }), 200, 'Rangos').items || []).find(x => x.categoria === 'TEMPERATURA');
    if (![tipo, especie, dispositivo, rango].every(Boolean)) throw Error('Catálogos de preparación incompletos');
    const area = need(await req('POST', '/configuracion/infraestructuras', { token: setup, body: { nombre_infraestructura: `QA G99 ${stamp}`, tipo_area: tipo.nombre, superficie: 25, finca_id: finca, descripcion_infraestructura: `QA ${run}`, especie_id: especie.id_especie } }), 201, 'Crear área');
    const disp = need(await req('POST', '/configuracion/dispositivos-iot', { token: setup, body: { serial, descripcion: `QA ${run}`, id_infraestructura: area.id_infraestructura, id_tipo_dispositivo: dispositivo.id_tipo_dispositivo, es_activo: true } }), 201, 'Crear dispositivo');
    creado = true;
    const sensor = need(await req('POST', `/configuracion/dispositivos-iot/${disp.id_dispositivo_iot}/sensores`, { token: setup, body: { nombre: `QA G99 ${stamp}`, categoria: 'TEMPERATURA' } }), 201, 'Crear sensor');
    need(await req('POST', `/configuracion/sensores/${sensor.id_sensores}/asociar`, { token: setup, body: { id_dispositivo_iot: disp.id_dispositivo_iot, id_infraestructura: area.id_infraestructura, punto_instalacion: 'QA G99' } }), 201, 'Asociar sensor');
    need(await req('POST', `/configuracion/sensores/${sensor.id_sensores}/calibrar`, { token: setup, body: { id_dispositivo_iot: disp.id_dispositivo_iot, id_infraestructura: area.id_infraestructura, valor_referencia: Number(((Number(rango.valor_min) + Number(rango.valor_max)) / 2).toFixed(2)), ganancia: 1, offset: 0, fecha_calibracion: new Date(Date.now() - 600000).toISOString(), observaciones: `QA ${run}`, modo_calibracion: 'SENSOR' } }), 201, 'Calibrar sensor');
    need(await req('GET', `/configuracion/infraestructuras/${area.id_infraestructura}`, { token: prod }), 200, 'Visibilidad Productor');
    const ins = need(await query(sqlTestigo(serial)), 200, 'Testigo dentro').data?.[0];
    const ext = need(await fuera(sqlTestigo(serial), 'SONDA'), 200, 'Testigo fuera').data?.[0];
    if (Number(ins?.n) !== 1 || Number(ext?.n) !== 0) throw Error('Aislamiento no demostrado');
    ev.sandbox.aislamiento = { dentro: Number(ins.n), fuera: Number(ext.n), control: Number(control.n) };
    const lectura = await req('POST', '/iot/telemetria', { body: { device_id: disp.id_dispositivo_iot, sensor_id: sensor.id_sensores, tipo_variable: 'TEMPERATURA_AMBIENTAL', valor: 25, unidad: '°C', timestamp_captura: new Date(Date.now() - 30000).toISOString(), access_key: serial, origen: 'TIEMPO_REAL', estado_conectividad: true } });
    if (lectura.status !== 201) throw Error(`Ingesta de preparación: HTTP ${lectura.status}; revisar contrato DEV-06`);
    const tabla = need(await query("SELECT c.relrowsecurity AS rls, has_table_privilege(current_user,'modulo3.telemetrias','SELECT') AS lectura FROM pg_class c WHERE c.oid='modulo3.telemetrias'::regclass"), 200, 'Metadatos telemetría')?.data?.[0];
    if (!tabla || tabla.rls !== false || tabla.lectura !== true) throw Error('Snapshot de tabla completa no demostrable: RLS o permiso SELECT');
    const antes = huella(await query(SQL_HUELLA));
    if (!antes || antes.n < 1) throw Error('Snapshot completo de telemetría no consultable o testigo de lectura ausente; no interpretar como tabla vacía');
    const contrato = need(await req('GET', '/openapi.json'), 200, 'Contrato OpenAPI');
    const mutaciones = Object.entries(contrato.paths || {}).filter(([ruta, metodos]) => ruta.startsWith('/iot/monitoreo') && ['post', 'put', 'patch', 'delete'].some(m => Object.hasOwn(metodos, m)));
    ev.asserts.push({ nombre: '[TC-M03-192][ASSERT] monitoreo no expone mutaciones de telemetría', ok: mutaciones.length === 0, observado: true, rutas: mutaciones.map(x => x[0]) });
    const front = path.resolve(ROOT, '../SGPMP-FRONT-END-PWA/src/telemetry');
    const fuentes = Object.fromEntries(Object.entries({ hook: 'hooks/useMonitoreo.ts', card: 'components/SensorCard.tsx', escala: 'lib/sensorEscala.ts', pill: 'components/SemaforoPill.tsx' }).map(([k, p]) => [k, fs.readFileSync(path.join(front, p), 'utf8')]));
    ev.info = { fuentes_frontend_sha256: Object.fromEntries(Object.entries(fuentes).map(([k, s]) => [k, createHash('sha256').update(s).digest('hex')])) };
    ev.asserts.push({ nombre: '[TC-M03-193][ASSERT] código cliente pasa estado_semaforo del backend sin recalcularlo', ok: clienteSoloRenderiza(fuentes), observado: true });
    const dash = need(await req('GET', `/iot/monitoreo/dashboard/${area.id_infraestructura}?pagina=1&por_pagina=50`, { token: prod }), 200, 'Dashboard preparado');
    if (!(dash.sensores || []).some(x => Number(x.id_sensor) === Number(sensor.id_sensores))) throw Error('Sensor preparado no observable en dashboard');
    ev.pre.push({ nombre: 'fixture y snapshot completo', ok: true });
    ev.datos = { area: area.id_infraestructura, sensor: sensor.id_sensores, nombre_sensor: sensor.nombre || `QA G99 ${stamp}`, snapshot_antes: antes };
    guardar();
    ev.fase = 'ESCENARIO';
    const nr = await new Promise(resolve => newman.run({ ignoreRedirects: true,  collection: JSON.parse(fs.readFileSync(COLLECTION, 'utf8')), environment: { values: Object.entries({ base_url: gate.api, test_base_url: gate.api, run_id: run, sandbox_secret: v.QA_SANDBOX_SECRET, token: prod, id_infraestructura: String(area.id_infraestructura), id_sensor: String(sensor.id_sensores), autorizado_run: 'SI', qa_autorizado: v.QA_AUTORIZADO, ambiente: a.ambiente, autorizacion: a.autorizacion }).map(([key, value]) => ({ key, value })) }, reporters: [], silent: true }, (error, summary) => resolve({ error, summary })));
    if (nr.error || nr.summary?.run?.failures?.some(x => x.error?.name !== 'AssertionError')) throw Error('Fallo técnico Newman');
    ev.asserts.push(...(nr.summary?.run?.executions || []).flatMap(x => (x.assertions || []).map(y => ({ nombre: y.assertion, ok: !y.error, observado: true }))));
    delete process.env.ELECTRON_RUN_AS_NODE;
    const cr = await cypress.run({ project: DIR, configFile: path.join(DIR, 'cypress.config.cjs'), testingType: 'e2e', spec: SPEC, browser: 'electron', headless: true, quiet: true, reporter: 'spec', config: { e2e: { baseUrl: gate.web, specPattern: path.basename(SPEC), supportFile: false, fixturesFolder: false, video: false, screenshotOnRunFailure: false, trashAssetsBeforeRuns: false, screenshotsFolder: path.join(out, 'capturas'), downloadsFolder: path.join(out, 'descargas'), reporter: 'spec' } }, env: { API_BASE: gate.api, API_TEST_BASE: gate.api, RUN_ID: run, SANDBOX_SECRET: v.QA_SANDBOX_SECRET, PROD_EMAIL: v.QA_PROD_EMAIL, PROD_PASSWORD: v.QA_PROD_PASSWORD || v.QA_COMMON_PASSWORD, ID_INFRA: area.id_infraestructura, SENSOR_NOMBRE: `QA G99 ${stamp}`, SENSOR_ID: sensor.id_sensores, AUTORIZADO_RUN: 'SI', QA_AUTORIZADO: v.QA_AUTORIZADO, AMBIENTE: a.ambiente, AUTORIZACION: a.autorizacion } });
    const pruebasUi = cr.runs?.flatMap(x => x.tests || []) || [];
    if (pruebasUi.filter(t => ['passed', 'failed'].includes(t.state)).length !== 2) throw Error('Cypress no completó las dos comprobaciones de interfaz');
    ev.asserts.push({ nombre: '[TC-M03-192/193][ASSERT] navegación y comparación UI', ok: !cr.failures && !cr.totalFailed, observado: true });
    const despues = huella(await query(SQL_HUELLA));
    if (!despues) throw Error('Snapshot posterior no consultable');
    ev.asserts.push({ nombre: '[TC-M03-192][ASSERT] count y contenido de telemetría idénticos', ok: antes.n === despues.n && antes.huella === despues.huella, observado: true });
    ev.datos.snapshot_despues = despues;
    ev.estado = 'CONCLUIDA';
  } catch (e) { ev.estado = ev.fase === 'ESCENARIO' ? 'INTERRUMPIDA' : 'ABORTADA_PREFLIGHT'; ev.fallo_tipo = tipoFallo(String(e.message)); ev.dependencias.push(limpiar(e.message)); }
  finally {
    if (abierto) try {
      const c = await req('DELETE', `/test-control/runs/${run}`, { control: true });
      const d = await req('DELETE', `/test-control/runs/${run}`, { control: true });
      const p = creado ? await fuera(sqlTestigo(serial), 'POST') : null;
      ev.sandbox.rollback = c.status === 200 && d.status === 404 && (!creado || p?.status === 200 && Number(p.data?.data?.[0]?.n) === 0);
      if (!ev.sandbox.rollback) ev.dependencias.push('Rollback no confirmado');
    } catch (e) { ev.sandbox.rollback = false; ev.dependencias.push(limpiar(e.message)); }
    ev.veredicto = ev.estado === 'CONCLUIDA' ? clasificar(ev.pre, ev.asserts, ev.sandbox.rollback) : 'BLOQUEADO';
    ev.fin = new Date().toISOString(); guardar();
    const informe = n === 1 ? 'TC-M03-G99_resultado.md' : `TC-M03-G99_reevaluacion_V${n}.md`;
    fs.writeFileSync(path.join(out, informe), limpiar(`# TC-M03-G99 — ${CASOS.join(', ')}\n\nRUN ${run}; TEST; ${ev.estado}; resultado propuesto ${ev.veredicto}. Revisión QA requerida.\n\nFase: ${ev.fase}; naturaleza del fallo técnico: ${ev.fallo_tipo || 'ninguna'}.\n\nPrecondiciones: ${JSON.stringify(ev.pre)}\n\nAserciones: ${JSON.stringify(ev.asserts)}\n\nDependencias: ${ev.dependencias.join('; ') || 'ninguna'}\n\nRollback: ${ev.sandbox.rollback ? 'confirmado' : 'NO confirmado'}\n`));
  }
  return ev.estado === 'CONCLUIDA' ? 0 : 4;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { const a = argumentos(process.argv.slice(2)); process.exitCode = a.modo === 'local' ? validarLocal() : await ejecutar(a); }
  catch (e) { console.error(e.message); process.exitCode = 2; }
}
