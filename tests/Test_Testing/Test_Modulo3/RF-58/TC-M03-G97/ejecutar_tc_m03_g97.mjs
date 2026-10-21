#!/usr/bin/env node
// TC-M03-188/189/190/210: vistas y payloads diferenciados por rol (RF-58 CA-8, Fase 4).
//
// El escenario se CONSTRUYE dentro del sandbox con APIs oficiales (no depende de encontrar una
// unidad preexistente): área QA con un único activo biológico INDIVIDUAL, dispositivo sin
// gateway, sensor biométrico calibrado, lectura TEMPERATURA_CORPORAL con batería/RSSI/SNR
// (vinculada al activo por RF-61), alerta activa por RF-57 y acceso de Productor, Ingeniero y
// Veterinario. La asignación de la finca a cada rol es ADITIVA y conserva exactamente sus
// asignaciones previas (verificado antes y después; se revierte con el rollback del RUN).
//
// Límite del contrato: ninguna API oficial asocia explícitamente una alerta a un activo
// (POST /iot/alertas y /iot/eventos-edge no reciben id_activo_biologico). La alerta se crea
// para el sensor biométrico vinculado; que el sistema la presente con el contexto del activo
// es lo que evalúa API-190-03 (no se fuerza).
//
// Autenticación del dispositivo: hoy access_key = serial (DEV-06 la sustituirá por un token de
// servicio aún no definido; la adaptación se concentra en `cuerpoDispositivo`).
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

export const GRUPO = 'TC-M03-G97';
export const CASOS = ['TC-M03-188', 'TC-M03-189', 'TC-M03-190', 'TC-M03-210'];
export const ASERCIONES = ['API-188-01', 'API-189-01', 'API-190-01', 'API-190-02', 'API-190-03', 'API-190-04', 'API-210-01', 'UI-188-01', 'UI-188-02', 'UI-188-03', 'UI-189-01', 'UI-190-01', 'UI-190-02'];
// Casos que dependen de cada rol (para bloquear solo lo afectado si falta un acceso).
export const CASOS_POR_ROL = { PROD: ['TC-M03-188', 'TC-M03-210'], ENG: ['TC-M03-189', 'TC-M03-210'], VETERINARIO: ['TC-M03-190'] };
const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const ENV = path.join(ROOT, '.env.qa');
const COLLECTION = path.join(DIR, `${GRUPO}.postman_collection.json`);
const SPEC = path.join(DIR, 'tc_m03_g97.cy.js');
const fetchReal = globalThis.fetch;
globalThis.fetch = async () => { throw Error('BLOQUEO_RED_G97'); };

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
  for (const k of ['QA_SETUP_EMAIL', 'QA_PROD_EMAIL', 'QA_ENG_EMAIL', 'QA_VETERINARIO_EMAIL', 'QA_SANDBOX_SECRET', 'SIGAB_API_TEST_BASE', 'SIGAB_FRONT_TEST_URL']) if (!v[k]) motivos.push(`Falta ${k}`);
  for (const rol of ['SETUP', 'PROD', 'ENG', 'VETERINARIO']) if (!(v[`QA_${rol}_PASSWORD`] || v.QA_COMMON_PASSWORD)) motivos.push(`Falta contraseña QA ${rol}`);
  const api = v.SIGAB_API_TEST_BASE?.replace(/\/+$/, '');
  if (api !== 'https://www.api.inmero.co/api-sgpmp-test') motivos.push('API no coincide con la URL oficial de TEST');
  if (!/^https:\/\//i.test(api || '') || /(^|[-/.])dev([-/.]|$)/i.test(api || '')) motivos.push('API no es HTTPS TEST');
  if (v.SIGAB_API_BASE && v.SIGAB_API_BASE.replace(/\/+$/, '') !== api) motivos.push('Alias de API distinto de TEST');
  if (api && api === v.SIGAB_API_DEV_BASE?.replace(/\/+$/, '')) motivos.push('API coincide con DEV');
  const front = v.SIGAB_FRONT_TEST_URL?.replace(/\/+$/, '');
  if (front !== 'https://api.inmero.co/sigab-test') motivos.push('Frontend no coincide con la URL oficial de TEST');
  if (!/^https:\/\//i.test(front || '') || /(^|[-/.])dev([-/.]|$)/i.test(front || '')) motivos.push('Frontend no es HTTPS TEST');
  if (v.SIGAB_FRONT_URL && v.SIGAB_FRONT_URL.replace(/\/+$/, '') !== front) motivos.push('Alias frontend distinto de TEST');
  if (front && front === v.SIGAB_FRONT_DEV_URL?.replace(/\/+$/, '')) motivos.push('Frontend coincide con DEV');
  if (v.QA_DEVICE_PREFIX && !/^[A-Za-z0-9][A-Za-z0-9_-]{1,19}$/.test(v.QA_DEVICE_PREFIX)) motivos.push('QA_DEVICE_PREFIX con formato inválido');
  return { ok: motivos.length === 0, motivos, api, front };
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

export const serialQa = (v, sello) => `${v.QA_DEVICE_PREFIX || 'QAAUTO'}-G97-${sello}`.slice(0, 50);
/** Identidad del dispositivo en el contrato actual (access_key = serial). Punto único para DEV-06. */
export const cuerpoDispositivo = ({ idDispositivo, idSensor, serial }) => ({ device_id: idDispositivo, sensor_id: idSensor, access_key: serial });
export const VALOR_BIOMETRICO = 38.6;
export const casoDeId = id => { const m = String(id).match(/^(?:API|UI)-(\d{3})-/); return m ? `TC-M03-${m[1]}` : null; };
export const casoDeTexto = t => (String(t).match(/TC-M03-\d{3}/) || [null])[0];

/** /test-control/query responde {"data": [filas]}; null si no hubo respuesta válida. */
export function filas(r) { return r?.status === 200 && Array.isArray(r?.data?.data) ? r.data.data : null; }
export function leerConteo(r) { const f = filas(r); if (!f || !f[0]) return null; const n = Number(f[0].n); return Number.isFinite(n) ? n : null; }
export function consultaTestigoDispositivo(serial) {
  if (!/^[A-Za-z0-9_-]{1,50}$/.test(serial)) throw Error('Serial no apto para el testigo');
  return `SELECT count(*) AS n FROM auditoria.logs_dml WHERE esquema_afectado = 'modulo9' AND tabla_afectada = 'dispositivos_iot' AND tipo_operacion = 'INSERT' AND datos_nuevos->>'serial' = '${serial}'`;
}

/**
 * Asignación aditiva verificable: solo se aplica si el conjunto que el usuario ve por API
 * coincide exactamente con sus filas activas en usuarios_fincas; después debe quedar
 * exactamente previo ∪ {nueva}.
 */
export function planAsignacion(visibles, asignadas, nueva) {
  const v = [...new Set(visibles)].sort((a, b) => a - b), s = [...new Set(asignadas)].sort((a, b) => a - b);
  if (JSON.stringify(v) !== JSON.stringify(s)) return { aplicar: false, motivo: `las fincas visibles (${v}) no coinciden con las asignaciones activas (${s}); no se puede garantizar su conservación exacta` };
  if (s.includes(nueva)) return { aplicar: false, ya: true, ids: s };
  return { aplicar: true, ids: [...s, nueva].sort((a, b) => a - b) };
}
export const conservaExactamente = (antes, despues, nueva) =>
  JSON.stringify([...new Set([...antes, nueva])].sort((a, b) => a - b)) === JSON.stringify([...new Set(despues)].sort((a, b) => a - b));

/**
 * Veredicto por caso. Bloquean: bloqueos del ejecutor, PRE del sandbox, hooks de Cypress
 * (login/sesión) y errores de script. Rechaza solo un [ASSERT] incumplido con respuesta real.
 */
export function veredictoCasos({ estado, rollback, aserciones, bloqueos = {} }) {
  const out = {};
  for (const caso of CASOS) {
    const propias = aserciones.filter(a => a.caso === caso);
    const requeridas = ASERCIONES.filter(id => casoDeId(id) === caso);
    let v;
    if (estado !== 'CONCLUIDA' || !rollback) v = 'BLOQUEADO';
    else if ((bloqueos[caso] || []).length) v = 'BLOQUEADO';
    else if (propias.some(a => a.tipo === 'PRE' && !a.ok)) v = 'BLOQUEADO';
    else if (propias.some(a => a.tipo === 'ASSERT' && !a.ok && a.evidencia)) v = 'RECHAZADO';
    else if (propias.some(a => !a.ok) || !requeridas.every(id => propias.some(a => a.id === id && a.ok))) v = 'BLOQUEADO';
    else v = 'APROBADO';
    out[caso] = v;
  }
  const estados = Object.values(out);
  return { casos: out, grupo: estados.includes('RECHAZADO') ? 'RECHAZADO' : estados.every(x => x === 'APROBADO') ? 'APROBADO' : 'BLOQUEADO' };
}

/**
 * Cypress usa el proyecto raiz para resolver el spec y el archivo propio del grupo para
 * evitar destinos heredados. Las opciones efectivas se anulan dentro de e2e.
 */
export function opcionesCypress({ front, out, env, configFile }) {
  return {
    project: ROOT, spec: SPEC, reporter: 'spec', quiet: true, env, configFile: configFile || VERIFICACION,
    config: { e2e: { baseUrl: front, supportFile: false, fixturesFolder: false, video: false, screenshotOnRunFailure: false, ...(out ? { screenshotsFolder: path.join(out, 'capturas'), downloadsFolder: path.join(out, 'descargas') } : {}), trashAssetsBeforeRuns: false, specPattern: path.relative(ROOT, SPEC).split(path.sep).join('/'), testIsolation: false, retries: 0, reporter: 'spec' } },
  };
}
/**
 * El binario de Cypress (Electron) no arranca si hereda ELECTRON_RUN_AS_NODE=1, como ocurre en la
 * terminal de VS Code ("bad option: --smoke-test"). Se retira solo para el proceso hijo de Cypress.
 */
export function entornoCypress() { delete process.env.ELECTRON_RUN_AS_NODE; }
const VERIFICACION = path.join(DIR, 'cypress.verificacion.config.cjs');
const LOOPBACK = /^https?:\/\/(127\.0\.0\.1|localhost|\[::1\])(:\d+)?(\/|$)/i;
/** Cadenas con forma de URL (recorrido profundo). */
export function urls(x, out = []) {
  if (typeof x === 'string') { if (/^[a-z]+:\/\//i.test(x)) out.push(x); }
  else if (x && typeof x === 'object') for (const v of Object.values(x)) urls(v, out);
  return out;
}
/**
 * Antes de lanzar Cypress en local: la configuración es la de verificación (nunca el cypress.config.cjs
 * raíz) y solo tiene loopback; ni las anulaciones, ni el entorno del spec, ni cypress.env.json, ni las
 * variables CYPRESS_* introducen destinos remotos; y la salida está bloqueada por un proxy de loopback
 * inexistente. Devuelve los motivos que impiden ejecutar (vacío = aislado).
 */
export function aislamientoVerificacion({ opciones, entorno }) {
  const motivos = [];
  if (!opciones.configFile || path.resolve(ROOT, opciones.configFile) !== VERIFICACION) motivos.push('no se usa la configuración de verificación de loopback');
  const remotas = [...urls(createRequire(VERIFICACION)(VERIFICACION)), ...urls(opciones.config), ...urls(opciones.env)].filter(u => !LOOPBACK.test(u));
  if (remotas.length) motivos.push(`destinos no loopback: ${remotas.join(', ')}`);
  if (opciones.config?.e2e?.baseUrl !== null) motivos.push('la anulación de baseUrl debe ser null');
  const envJson = path.join(ROOT, 'cypress.env.json');
  if (fs.existsSync(envJson) && urls(JSON.parse(fs.readFileSync(envJson, 'utf8'))).some(u => !LOOPBACK.test(u))) motivos.push('cypress.env.json contiene destinos remotos');
  const cyVars = Object.entries(entorno).filter(([k, v]) => /^CYPRESS_/i.test(k) && /:\/\//.test(String(v)) && !LOOPBACK.test(String(v)));
  if (cyVars.length) motivos.push(`variables ${cyVars.map(([k]) => k).join(', ')} con destinos remotos`);
  for (const k of ['HTTP_PROXY', 'HTTPS_PROXY']) if (!LOOPBACK.test(entorno[k] || '')) motivos.push(`${k} debe apuntar a un proxy de loopback inexistente`);
  if (entorno.ELECTRON_RUN_AS_NODE) motivos.push('ELECTRON_RUN_AS_NODE sigue definida');
  return motivos;
}
/**
 * Comprobación local del descubrimiento del spec, aislada de la red: configuración de verificación
 * (loopback, nunca la raíz), baseUrl null, salida bloqueada por un proxy inexistente y sin
 * autorización, de modo que el before() se detiene en BLOQUEO_G97. Si el aislamiento no se demuestra,
 * Cypress no se ejecuta.
 */
async function verificarSpec() {
  process.env.HTTP_PROXY = process.env.HTTPS_PROXY = 'http://127.0.0.1:9';
  process.env.NO_PROXY = 'localhost,127.0.0.1,::1';
  process.env.CYPRESS_CRASH_REPORTS = '0';
  entornoCypress();
  const opciones = opcionesCypress({ front: null, out: null, env: { ROLE: 'PROD' }, configFile: path.relative(ROOT, VERIFICACION).split(path.sep).join('/') });
  const motivos = aislamientoVerificacion({ opciones, entorno: process.env });
  if (motivos.length) { for (const m of motivos) console.log(`FALLO aislamiento: ${m}`); console.log('Cypress NO se ejecuta.'); return 1; }
  console.log('OK aislamiento: solo destinos loopback y salida bloqueada por proxy inexistente');
  const antes = new Set(fs.readdirSync(ROOT));
  const cypress = createRequire(path.join(ROOT, 'package.json'))('cypress');
  const r = await cypress.run(opciones);
  const nuevos = fs.readdirSync(ROOT).filter(x => !antes.has(x));
  const enCarpeta = fs.readdirSync(DIR).filter(x => /^_verificacion/.test(x));
  const specs = (r.runs || []).map(x => path.resolve(ROOT, x.spec?.relative || ''));
  const tests = (r.runs || []).flatMap(x => x.tests || []);
  const descubierto = r.status !== 'failed' && specs.length === 1 && specs[0] === SPEC;
  // Si falla el before all, Cypress marca la primera prueba con el error del hook y omite el resto.
  const barrera = tests.some(t => t.state === 'failed' && /BLOQUEO_G97/.test(String(t.displayError || ''))) && !tests.some(t => t.state === 'passed');
  const prevalecen = r.status !== 'failed' && !enCarpeta.length;
  console.log(`${descubierto ? 'OK' : 'FALLO'} Cypress descubre ${path.relative(ROOT, SPEC)}${r.status === 'failed' ? ` (${r.message})` : ''}`);
  console.log(`${barrera ? 'OK' : 'FALLO'} La barrera del spec detiene la ejecución sin autorización (BLOQUEO_G97 en el before; ninguna prueba superada)`);
  console.log(`${prevalecen ? 'OK' : 'FALLO'} Las anulaciones en e2e prevalecen (sin verificar 127.0.0.1:9 ni dejar capturas)${enCarpeta.length ? ` (${enCarpeta.join(', ')})` : ''}`);
  console.log(`${nuevos.length ? 'FALLO' : 'OK'} Sin artefactos nuevos en la raíz del proyecto${nuevos.length ? ` (${nuevos.join(', ')})` : ''}`);
  return descubierto && barrera && prevalecen && !nuevos.length ? 0 : 1;
}

function argumentos(argv) {
  const a = { modo: 'local', efectos: [] };
  for (let i = 0; i < argv.length; i++) {
    const x = argv[i];
    if (x === '--ejecutar') a.modo = 'ejecutar';
    else if (x === '--validar-local') a.modo = 'local';
    else if (x === '--verificar-spec') a.modo = 'spec';
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
  const spec = fs.readFileSync(SPEC, 'utf8');
  ck('Matriz: cuatro casos originales', CASOS.join() === 'TC-M03-188,TC-M03-189,TC-M03-190,TC-M03-210');
  ck('Cada aserción pertenece a un caso original', ASERCIONES.every(id => CASOS.includes(casoDeId(id))));
  ck('Configuración compartida y QA_AUTORIZADO=NO', fs.existsSync(ENV) && v.QA_AUTORIZADO === 'NO');
  ck('Barrera rechaza ejecución actual', !autorizar(v, { ambiente: 'TEST', autorizacion: '', efectos: [] }).ok);
  ck('Barrera acepta condiciones futuras válidas', autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ambiente: 'TEST', autorizacion: 'REF-DESARROLLO', efectos: ['notificacion-login'] }).ok);
  ck('Barrera rechaza DEV', !autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ambiente: 'DEV', autorizacion: 'REF-DESARROLLO', efectos: ['notificacion-login'] }).ok);
  ck('Variables QA de preparación y tres roles resueltas', ['SETUP', 'PROD', 'ENG', 'VETERINARIO'].every(r => !!v[`QA_${r}_EMAIL`] && !!(v[`QA_${r}_PASSWORD`] || v.QA_COMMON_PASSWORD)) && !!v.QA_SANDBOX_SECRET);
  ck('Prefijo de serial QA disponible (automático si falta)', /-G97-/.test(serialQa(v, '20261017000000')));
  ck('Colección Postman v2.1', /v2\.1\.0/.test(col.info?.schema || '') && col.item?.length >= 4);
  ck('Aserciones API y UI completas', ASERCIONES.every(x => JSON.stringify(col).includes(x) || spec.includes(x)));
  const vars = new Set([...JSON.stringify(col).matchAll(/\{\{([a-z_]+)\}\}/g)].map(x => x[1]));
  ck('Variables Newman resueltas por el ejecutor', [...vars].every(x => ['base_url', 'run_id', 'sandbox_secret', 'token_prod', 'token_eng', 'token_vet', 'id_unidad', 'id_sensor', 'id_activo', 'id_alerta', 'fincas_vet', 'fecha_desde', 'fecha_hasta'].includes(x)));
  const envCypress = new Set([...spec.matchAll(/env\('([A-Z_]+)'\)/g)].map(x => x[1]));
  ck('Variables Cypress resueltas por el ejecutor', [...envCypress].every(x => ['AUTORIZADO_RUN', 'ROLE', 'API_BASE', 'RUN_ID', 'SANDBOX_SECRET', 'ID_UNIDAD', 'ID_SENSOR', 'ID_ACTIVO', 'ID_ALERTA', 'FINCAS_VET', 'NOMBRE_UNIDAD', 'NOMBRE_SENSOR', 'VALOR', 'UNIDAD_MEDIDA', 'EMAIL', 'PASSWORD'].includes(x)));
  ck('Barrera propia de Newman', JSON.stringify(col).includes('BLOQUEO_G97'));
  try { for (const e of [...(col.event || []), ...col.item.flatMap(x => x.event || [])]) new Function((e.script?.exec || []).join('\n')); ck('Sintaxis Postman', true); } catch { ck('Sintaxis Postman', false); }
  ck('Sintaxis ejecutor', spawnSync(process.execPath, ['--check', fileURLToPath(import.meta.url)]).status === 0);
  ck('Sintaxis Cypress', spawnSync(process.execPath, ['--check', SPEC]).status === 0);
  const oc = opcionesCypress({ front: 'https://front.test.example', out: DIR, env: {} });
  ck('Cypress: proyecto raíz y anulaciones en e2e (specPattern al spec, baseUrl del frontend, sin reporter de archivos ni capturas)', oc.project === ROOT && fs.existsSync(path.join(ROOT, 'cypress.config.cjs')) && path.resolve(ROOT, oc.config.e2e.specPattern) === SPEC && oc.config.e2e.baseUrl === 'https://front.test.example' && oc.config.e2e.reporter === 'spec' && oc.config.e2e.screenshotOnRunFailure === false);
  const ov = opcionesCypress({ front: null, out: null, env: { ROLE: 'PROD' }, configFile: path.relative(ROOT, VERIFICACION).split(path.sep).join('/') });
  const proxy = { HTTP_PROXY: 'http://127.0.0.1:9', HTTPS_PROXY: 'http://127.0.0.1:9' };
  ck('--verificar-spec aislado: configuración de loopback (nunca la raíz) y salida bloqueada', aislamientoVerificacion({ opciones: ov, entorno: proxy }).length === 0 && aislamientoVerificacion({ opciones: { ...ov, configFile: undefined }, entorno: proxy }).length > 0 && path.resolve(ROOT, oc.configFile) === VERIFICACION);
  ck('UI-188-01: semáforo por correspondencia con el estado del API y etiquetas reales de la interfaz', spec.includes('estadoDelSensor()') && ['normal', 'advertencia', 'fuera de rango', 'sin señal'].every(x => spec.includes(`'${x}'`)) && !spec.includes(['cy.contains(/(VERDE', '|AMARILLO'].join('')));
  ck('Barrera propia de Cypress y sin respuestas simuladas', spec.includes('BLOQUEO_G97') && !/req\.reply|cy\.stub|cy\.fixture/.test(spec));
  ck('Escenario construido (sin descubrimiento de unidades preexistentes)', !/FROM modulo3\.alertas a JOIN/.test(fs.readFileSync(fileURLToPath(import.meta.url), 'utf8').split('function local')[0]));
  ck('Sin peticiones concurrentes al sandbox en el ejecutor', !/Promise\.all\(\s*\[?['"]PROD/.test(fs.readFileSync(fileURLToPath(import.meta.url), 'utf8')));
  ck('Veredicto: ASSERT con evidencia rechaza; PRE y faltantes bloquean',
    veredictoCasos({ estado: 'CONCLUIDA', rollback: true, aserciones: [{ caso: 'TC-M03-188', tipo: 'ASSERT', id: 'API-188-01', ok: false, evidencia: true }] }).casos['TC-M03-188'] === 'RECHAZADO'
    && veredictoCasos({ estado: 'CONCLUIDA', rollback: true, aserciones: [{ caso: 'TC-M03-188', tipo: 'PRE', id: 'PRE', ok: false }] }).casos['TC-M03-188'] === 'BLOQUEADO');
  ck('Sin RESULTS de preparación', !fs.existsSync(path.join(DIR, 'RESULTADOS')));
  ck('Sin secretos literales', [fileURLToPath(import.meta.url), COLLECTION, SPEC].every(f => ![v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_PROD_PASSWORD, v.QA_ENG_PASSWORD, v.QA_VETERINARIO_PASSWORD, v.QA_SETUP_PASSWORD].filter(x => x?.length > 4).some(x => fs.readFileSync(f, 'utf8').includes(x))));
  const t = spawnSync(process.execPath, ['--test', path.join(DIR, 'validar_local_g97.mjs')], { encoding: 'utf8' });
  ck('Pruebas unitarias locales', t.status === 0);
  try { newmanModulo(); ck('Newman disponible', true); } catch { ck('Newman disponible', false); }
  try { createRequire(path.join(ROOT, 'package.json'))('cypress'); ck('Cypress disponible', true); } catch { ck('Cypress disponible', false); }
  for (const [n, ok] of checks) console.log(`${ok ? 'OK' : 'FALLO'} ${n}`);
  console.log(`G97 local ${checks.filter(x => x[1]).length}/${checks.length}`);
  return checks.every(x => x[1]) ? 0 : 1;
}

async function ejecutar(a) {
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const gate = autorizar(v, a);
  if (!gate.ok) { console.error(`EJECUCIÓN NO AUTORIZADA: ${gate.motivos.join('; ')}`); return 2; }
  if (!['evaluacion', 'reintento'].includes(a.tipo)) { console.error('Indique --tipo evaluacion|reintento'); return 2; }
  const n = version(DIR, a.tipo, a.version), newman = newmanModulo();
  const cypress = createRequire(path.join(ROOT, 'package.json'))('cypress');
  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14);
  const run = `G97-${n === 1 ? 'EVAL' : 'REEVAL'}-V${n}-${stamp}`;
  const base = n === 1 ? path.join(DIR, 'RESULTADOS') : path.join(DIR, `EvaluacionV${n}`, 'RESULTADOS');
  const out = path.join(base, run); fs.mkdirSync(base, { recursive: true }); fs.mkdirSync(out);
  const serial = serialQa(v, stamp);
  const ev = { grupo: GRUPO, rf: 'RF-58', cu: 'CU04', casos: CASOS, version: n, run_id: run, estado: 'EN_CURSO', fase: 'PREFLIGHT', autorizacion: a.autorizacion, dependencias: [], bloqueos: {}, aserciones: [], sandbox: {}, datos: {}, inicio: new Date().toISOString() };
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_PROD_PASSWORD, v.QA_ENG_PASSWORD, v.QA_VETERINARIO_PASSWORD, serial].filter(Boolean);
  const limpiar = x => secretos.reduce((s, y) => s.replaceAll(y, '[REDACTADO]'), String(x)).replace(/eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}/g, '[JWT]');
  const guardar = () => fs.writeFileSync(path.join(out, 'evidencia.json'), limpiar(JSON.stringify(ev, null, 2)));
  const bloquear = (casos, motivo) => { for (const c of casos) (ev.bloqueos[c] ??= []).push(motivo); };
  const tokens = {}; let abierto = false, dispositivoCreado = false;
  // Peticiones SIEMPRE secuenciales: el sandbox comparte una sola sesión de base de datos.
  async function req(m, ruta, { body, token, control = false, runId = run } = {}) {
    const headers = { Accept: 'application/json', 'X-Sandbox-Secret': v.QA_SANDBOX_SECRET };
    if (!control) headers['X-Test-Run-Id'] = runId;
    if (token) headers.Authorization = `Bearer ${token}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const r = await fetchReal(`${gate.api}${ruta}`, { method: m, headers, body: body === undefined ? undefined : JSON.stringify(body), redirect: 'manual', signal: AbortSignal.timeout(30000) });
    const data = await r.json().catch(() => null);
    if (!control && r.headers.get('x-test-run-id') !== runId) throw Error(`Sandbox sin eco: ${m} ${ruta}`);
    return { status: r.status, data };
  }
  function need(r, status, label) { if (r.status !== status) throw Error(`${label}: HTTP ${r.status} ${JSON.stringify(r.data ?? '').slice(0, 300)}`); return r.data; }
  const sql = (query, runId = run) => req('POST', '/test-control/query', { body: { query }, runId });
  async function sondaExterna(sufijo) { const rid = `${run}-${sufijo}`; try { return leerConteo(await sql(consultaTestigoDispositivo(serial), rid)); } finally { await req('DELETE', `/test-control/runs/${rid}`, { control: true }); } }
  try {
    const probe = await req('DELETE', `/test-control/runs/${run}-PREFLIGHT`, { control: true });
    if (probe.status !== 404 || !/Run ID no encontrado/i.test(String(probe.data?.detail ?? ''))) throw Error(`Sandbox no disponible: HTTP ${probe.status}`);
    abierto = true;
    // Un login por actor, dentro del sandbox (Cypress hace luego su propio login de interfaz).
    const ids = {};
    for (const [rol, patron] of [['SETUP', /administrador/i], ['PROD', /productor/i], ['ENG', /ingeniero/i], ['VETERINARIO', /veterinario/i]]) {
      const data = need(await req('POST', '/sesiones/', { body: { correo_electronico: v[`QA_${rol}_EMAIL`], contrasena: v[`QA_${rol}_PASSWORD`] || v.QA_COMMON_PASSWORD } }), 200, `Login ${rol}`);
      if (!data?.token) throw Error(`Login ${rol} sin token`);
      tokens[rol] = data.token; secretos.push(data.token);
      const me = need(await req('GET', '/usuarios/me', { token: data.token }), 200, `Identidad ${rol}`);
      if (!patron.test(me.nombre_rol || '')) throw Error(`Cuenta QA ${rol} con rol inesperado`);
      ids[rol] = me.id_usuario;
    }
    const S = tokens.SETUP;
    const get = async (ruta, etiqueta, token = S) => need(await req('GET', ruta, { token }), 200, etiqueta);
    const fincasDe = async rol => new Set((await get('/configuracion/fincas', `Fincas ${rol}`, tokens[rol])).items?.map(f => Number(f.id_finca)) ?? []);

    // ---- PREPARACIÓN ---------------------------------------------------------
    ev.fase = 'PREPARACION';
    const tipo = (await get('/configuracion/tipos-area?solo_activos=true', 'Tipos de área')).items?.find(x => x.es_activo);
    const tipoDisp = (await get('/configuracion/tipos-dispositivo-iot', 'Tipos de dispositivo')).items?.filter(x => x.categoria === 'SENSOR').sort((x, y) => x.id_tipo_dispositivo - y.id_tipo_dispositivo)[0];
    const rango = (await get('/configuracion/sensores/rangos-calibracion', 'Rangos de calibración')).items?.find(x => x.categoria === 'TEMPERATURA');
    const corporal = (await get('/configuracion/variables-ambientales', 'Variables')).items?.find(x => Number(x.id_variable_ambiental) === 13);
    if (!tipo || !tipoDisp || !rango) throw Error('Catálogos insuficientes (tipo de área, tipo SENSOR o rango TEMPERATURA)');
    if (corporal && !(VALOR_BIOMETRICO >= Number(corporal.valor_fisico_min) && VALOR_BIOMETRICO <= Number(corporal.valor_fisico_max))) throw Error('El valor biométrico del escenario está fuera del rango físico de TEMPERATURA_CORPORAL');
    // Especie apta para un activo INDIVIDUAL sin atributos obligatorios.
    let especie = null;
    for (const e of ((await get('/configuracion/especies?solo_activas=true', 'Especies')).items ?? []).filter(x => x.es_activo).sort((x, y) => x.id_especie - y.id_especie).slice(0, 40)) {
      const m = await get(`/configuracion/metricas?id_especie=${e.id_especie}&solo_activas=true`, `Métricas especie ${e.id_especie}`);
      if (!(m.items ?? []).some(x => x.es_obligatorio && ['INDIVIDUAL', 'AMBOS'].includes(x.aplica_a_tipo_activo))) { especie = e; break; }
    }
    if (!especie) throw Error('Ninguna especie activa admite un activo INDIVIDUAL sin atributos obligatorios');

    // Finca: compartida por los cuatro actores; si no existe, se crea con acceso del Productor y
    // se agrega de forma aditiva al Ingeniero y al Veterinario.
    const vis = {}; for (const rol of ['SETUP', 'PROD', 'ENG', 'VETERINARIO']) vis[rol] = await fincasDe(rol);
    let finca = [...vis.SETUP].find(id => ['PROD', 'ENG', 'VETERINARIO'].every(r => vis[r].has(id)));
    if (finca) ev.datos.finca = { id: finca, origen: 'existente compartida por los cuatro actores (solo se le agrega un área)' };
    else {
      finca = need(await req('POST', '/configuracion/fincas', { token: S, body: { nombre: `QA Monitoreo G Noventa Siete ${stamp}`.replace(/\d/g, d => 'abcdefghij'[Number(d)]), ubicacion: { departamento: 'Huila', municipio: 'Neiva', vereda: 'QA', latitud: 2.9273, longitud: -75.2819 }, tamano_h: 1, id_usuario: ids.PROD } }), 201, 'Crear finca QA').id_finca;
      ev.datos.finca = { id: finca, origen: 'creada en el RUN con acceso del Productor', asignaciones: {} };
      for (const rol of ['ENG', 'VETERINARIO']) {
        // Asignaciones activas reales (lectura con identidad de Administrador: RLS de usuarios_fincas).
        await get('/usuarios/me', 'Identidad de consulta');
        const f = filas(await sql(`SELECT id_finca FROM modulo9.usuarios_fincas WHERE id_usuario = ${Number(ids[rol])} AND es_activo IS TRUE`));
        const plan = f ? planAsignacion([...vis[rol]], f.map(x => Number(x.id_finca)), Number(finca)) : { aplicar: false, motivo: 'asignaciones activas no consultables' };
        if (!plan.aplicar) { const msg = `${rol}: no se asigna la finca del RUN (${plan.motivo}).`; ev.dependencias.push(msg); bloquear(CASOS_POR_ROL[rol], msg); continue; }
        const r = await req('PUT', `/usuarios/${ids[rol]}/fincas`, { token: S, body: { ids_fincas: plan.ids } });
        await get('/usuarios/me', 'Identidad de consulta');
        const despues = filas(await sql(`SELECT id_finca FROM modulo9.usuarios_fincas WHERE id_usuario = ${Number(ids[rol])} AND es_activo IS TRUE`));
        const ok = r.status === 200 && despues && conservaExactamente([...vis[rol]], despues.map(x => Number(x.id_finca)), Number(finca));
        ev.datos.finca.asignaciones[rol] = { previas: [...vis[rol]].length, http: r.status, conservadas_exactamente: !!ok };
        if (!ok) { const msg = `${rol}: la asignación aditiva no quedó exactamente como previas ∪ {finca del RUN} (PUT HTTP ${r.status}).`; ev.dependencias.push(msg); bloquear(CASOS_POR_ROL[rol], msg); }
      }
    }
    const nombreUnidad = `QA G97 ${stamp}`, nombreSensor = `QA G97 ${stamp} BIO`;
    const area = need(await req('POST', '/configuracion/infraestructuras', { token: S, body: { nombre_infraestructura: nombreUnidad, tipo_area: tipo.nombre, superficie: 25, finca_id: finca, descripcion_infraestructura: `QA ${run}`, especie_id: especie.id_especie } }), 201, 'Crear área QA');
    const disp = need(await req('POST', '/configuracion/dispositivos-iot', { token: S, body: { serial, descripcion: `QA G97 ${stamp}`, id_infraestructura: area.id_infraestructura, id_tipo_dispositivo: tipoDisp.id_tipo_dispositivo, es_activo: true } }), 201, 'Registrar dispositivo QA (sin gateway)');
    dispositivoCreado = true;
    const sensor = need(await req('POST', `/configuracion/dispositivos-iot/${disp.id_dispositivo_iot}/sensores`, { token: S, body: { nombre: nombreSensor, categoria: 'TEMPERATURA' } }), 201, 'Registrar sensor biométrico');
    need(await req('POST', `/configuracion/sensores/${sensor.id_sensores}/asociar`, { token: S, body: { id_dispositivo_iot: disp.id_dispositivo_iot, id_infraestructura: area.id_infraestructura, punto_instalacion: 'QA G97' } }), 201, 'Asociar sensor');
    need(await req('POST', `/configuracion/sensores/${sensor.id_sensores}/calibrar`, { token: S, body: { id_dispositivo_iot: disp.id_dispositivo_iot, id_infraestructura: area.id_infraestructura, valor_referencia: Number(((Number(rango.valor_min) + Number(rango.valor_max)) / 2).toFixed(2)), ganancia: 1, offset: 0, fecha_calibracion: new Date(Date.now() - 600000).toISOString(), observaciones: `QA ${run}`, modo_calibracion: 'SENSOR' } }), 201, 'Calibrar sensor');
    const hoy = new Date();
    const activo = need(await req('POST', '/activos-biologicos', { token: S, body: { tipo_activo: 'INDIVIDUAL', id_especie: especie.id_especie, fecha_inicio_ciclo: hoy.toISOString().slice(0, 10), origen_financiero: 'nacimiento', id_infraestructura: area.id_infraestructura, identificador: `QA-G97-${stamp}`, raza: 'QA', sexo: 'Macho', fecha_nacimiento: new Date(hoy.getTime() - 365 * 86400000).toISOString() } }), 201, 'Registrar activo biológico INDIVIDUAL');
    const activos = await get(`/activos-biologicos?id_infraestructura=${area.id_infraestructura}&page_size=100`, 'Activos del área');
    if (activos.total !== 1) throw Error(`El área debe tener exactamente un activo operativo y tiene ${activos.total}`);
    for (const rol of ['PROD', 'ENG', 'VETERINARIO']) {
      const r = await req('GET', `/configuracion/infraestructuras/${area.id_infraestructura}`, { token: tokens[rol] });
      if (r.status !== 200) { const msg = `${rol} sin alcance sobre el área del RUN (HTTP ${r.status}).`; ev.dependencias.push(msg); bloquear(CASOS_POR_ROL[rol], msg); }
    }
    // Aislamiento antes de las lecturas (testigo sin RLS).
    const dentro = leerConteo(await sql(consultaTestigoDispositivo(serial))), fuera = await sondaExterna('SONDA');
    ev.sandbox.aislamiento = { testigo: 'auditoria.logs_dml (INSERT del dispositivo)', dentro, fuera };
    if (dentro !== 1 || fuera !== 0) throw Error(`Aislamiento no demostrado (dentro=${dentro}, fuera=${fuera})`);
    // Lectura biométrica con indicadores técnicos y alerta activa (contratos RF-53 y RF-57).
    const ts = new Date(Date.now() - 30000).toISOString();
    const lectura = need(await req('POST', '/iot/telemetria', { body: { ...cuerpoDispositivo({ idDispositivo: disp.id_dispositivo_iot, idSensor: sensor.id_sensores, serial }), tipo_variable: 'TEMPERATURA_CORPORAL', valor: VALOR_BIOMETRICO, unidad: '°C', timestamp_captura: ts, origen: 'TIEMPO_REAL', estado_conectividad: true, nivel_bateria: 87, calidad_senal_rssi: -71, calidad_senal_snr: 7.5 } }), 201, 'Lectura biométrica');
    if (lectura.estado_calidad !== 'LECTURA_VALIDA') throw Error(`La lectura biométrica no quedó LECTURA_VALIDA (${lectura.estado_calidad})`);
    const vinc = await get(`/iot/vinculaciones?id_telemetria=${lectura.id_telemetria}`, 'Vinculación de la lectura');
    const v1 = (vinc.items ?? [])[0];
    ev.datos.vinculacion = { estado: v1?.estado_vinculacion ?? null, id_activo: v1?.id_activo_biologico ?? null };
    if (v1?.estado_vinculacion !== 'VINCULADA' || Number(v1?.id_activo_biologico) !== Number(activo.id_activo_biologico)) {
      const msg = `La lectura biométrica no quedó VINCULADA al activo del área (RF-61): ${JSON.stringify(ev.datos.vinculacion)}.`;
      ev.dependencias.push(msg); bloquear(['TC-M03-190'], msg);
    }
    const alerta = need(await req('POST', '/iot/alertas', { body: { ...cuerpoDispositivo({ idDispositivo: disp.id_dispositivo_iot, idSensor: sensor.id_sensores, serial }), tipo_variable: 'TEMPERATURA_CORPORAL', valor: VALOR_BIOMETRICO, unidad: '°C', timestamp_evento: new Date().toISOString(), estado_dato: 'LECTURA_VALIDA', severidad_edge: 'MODERADO', origen_evento: 'EDGE', id_telemetria: lectura.id_telemetria, reglas_activadas: [] } }), 201, 'Alerta activa RF-57');
    if (!alerta.id_alerta || alerta.es_duplicado) throw Error('La alerta del escenario no se registró como nueva');
    const fincasVet = [...(await fincasDe('VETERINARIO'))];
    const desde = new Date(Date.parse(ts) - 86400000).toISOString().slice(0, 10), hasta = new Date(Date.parse(ts) + 86400000).toISOString().slice(0, 10);
    ev.datos = { ...ev.datos, id_unidad: area.id_infraestructura, nombre_unidad: nombreUnidad, id_sensor_biometrico: sensor.id_sensores, nombre_sensor: nombreSensor, id_activo_biologico: activo.id_activo_biologico, id_alerta: alerta.id_alerta, id_telemetria: lectura.id_telemetria, especie: especie.id_especie, fecha_desde: desde, fecha_hasta: hasta, origen: 'construido en el RUN con APIs oficiales', limite_contrato: 'La alerta no puede asociarse explícitamente al activo por API; API-190-03 evalúa si el sistema la presenta con su contexto.' };

    // ---- ESCENARIOS: Newman y Cypress ----------------------------------------
    ev.fase = 'ESCENARIOS'; guardar();
    const vars = { base_url: gate.api, run_id: run, sandbox_secret: v.QA_SANDBOX_SECRET, autorizado_run: 'SI', token_prod: tokens.PROD, token_eng: tokens.ENG, token_vet: tokens.VETERINARIO, id_unidad: String(area.id_infraestructura), id_sensor: String(sensor.id_sensores), id_activo: String(activo.id_activo_biologico), id_alerta: String(alerta.id_alerta), fincas_vet: JSON.stringify(fincasVet), fecha_desde: desde, fecha_hasta: hasta };
    const nr = await new Promise(resolve => newman.run({ ignoreRedirects: true,  collection: JSON.parse(fs.readFileSync(COLLECTION, 'utf8')), environment: { values: Object.entries(vars).map(([key, value]) => ({ key, value })) }, reporters: [], silent: true }, (error, summary) => resolve({ error, summary })));
    for (const e of nr.summary?.run?.executions || []) {
      // Caso de la petición: su nombre o, si no lo trae, el de sus propias aserciones.
      const casoPeticion = casoDeTexto(e.item?.name) ?? (e.assertions || []).map(x => casoDeTexto(x.assertion)).find(Boolean) ?? null;
      for (const x of e.assertions || []) {
        const id = (String(x.assertion).match(/\]\[([A-Z]+-\d{3}-\d{2})\]/) || [null, null])[1];
        ev.aserciones.push({ herramienta: 'Newman', caso: casoDeTexto(x.assertion) ?? casoPeticion, tipo: /^PRE/.test(x.assertion) || /\[PRE\]/.test(x.assertion) ? 'PRE' : 'ASSERT', id, nombre: x.assertion, ok: !x.error, evidencia: e.response?.code != null, error: x.error ? limpiar(x.error.message) : undefined });
      }
    }
    for (const f of (nr.summary?.run?.failures || []).filter(f => !/AssertionError/.test(f.error?.name || ''))) {
      const caso = casoDeTexto(f.source?.name); const msg = `AUTOMATIZACION: error de script en «${f.source?.name ?? ''}»: ${limpiar(f.error?.message)}`;
      ev.dependencias.push(msg); bloquear(caso ? [caso] : CASOS, msg);
    }
    if (nr.error) { const msg = `AUTOMATIZACION: Newman — ${limpiar(nr.error.message)}`; ev.dependencias.push(msg); bloquear(CASOS, msg); }
    ev.cypress = [];
    entornoCypress();
    for (const rol of ['PROD', 'ENG', 'VET']) {
      const cuenta = rol === 'VET' ? 'VETERINARIO' : rol;
      const cy = await cypress.run(opcionesCypress({ front: gate.front, out, env: { AUTORIZADO_RUN: 'SI', ROLE: rol, API_BASE: gate.api, RUN_ID: run, SANDBOX_SECRET: v.QA_SANDBOX_SECRET, ID_UNIDAD: area.id_infraestructura, ID_SENSOR: sensor.id_sensores, ID_ACTIVO: activo.id_activo_biologico, ID_ALERTA: alerta.id_alerta, FINCAS_VET: fincasVet, NOMBRE_UNIDAD: nombreUnidad, NOMBRE_SENSOR: nombreSensor, VALOR: String(VALOR_BIOMETRICO), UNIDAD_MEDIDA: '°C', EMAIL: v[`QA_${cuenta}_EMAIL`], PASSWORD: v[`QA_${cuenta}_PASSWORD`] || v.QA_COMMON_PASSWORD } }));
      if (cy?.status === 'failed') { const msg = `AUTOMATIZACION: Cypress (${rol}) no pudo ejecutarse: ${limpiar(cy.message ?? '')}`; ev.dependencias.push(msg); bloquear(CASOS_POR_ROL[cuenta], msg); continue; }
      for (const t of (cy.runs || []).flatMap(r => r.tests || [])) {
        const titulo = Array.isArray(t.title) ? t.title.at(-1) : String(t.title || '');
        const err = String(t.displayError || '');
        const hook = /before all|before each|after all|after each/i.test(err);
        ev.aserciones.push({ herramienta: `Cypress ${rol}`, caso: casoDeTexto(titulo), tipo: hook ? 'PRE' : 'ASSERT', id: (titulo.match(/\]\[([A-Z]+-\d{3}-\d{2})\]/) || [null, null])[1], nombre: titulo, ok: t.state === 'passed', evidencia: t.state === 'failed' && !hook, error: err ? limpiar(err.split(/\r?\n/)[0]) : undefined });
      }
      ev.cypress.push({ rol, total: cy.totalTests, passed: cy.totalPassed, failed: cy.totalFailed, skipped: cy.totalSkipped });
    }
    ev.estado = 'CONCLUIDA';
  } catch (e) { ev.estado = ev.fase === 'ESCENARIOS' ? 'INTERRUMPIDA' : 'ABORTADA_PREFLIGHT'; ev.dependencias.push(limpiar(e.message)); }
  finally {
    try {
      if (abierto) {
        const c = await req('DELETE', `/test-control/runs/${run}`, { control: true });
        const d = await req('DELETE', `/test-control/runs/${run}`, { control: true });
        const resto = dispositivoCreado ? await sondaExterna('POST') : 0;
        ev.sandbox.cierre = c.status; ev.sandbox.sonda_posterior = resto;
        ev.sandbox.rollback = c.status === 200 && d.status === 404 && resto === 0;
        if (dispositivoCreado && resto === null) ev.dependencias.push('Rollback no confirmable: testigo auditoria.logs_dml no consultable.');
      }
    } catch (e) { ev.sandbox.rollback = false; ev.dependencias.push(limpiar(e.message)); }
    ev.veredicto = veredictoCasos({ estado: ev.estado, rollback: !!ev.sandbox.rollback, aserciones: ev.aserciones, bloqueos: ev.bloqueos });
    ev.fin = new Date().toISOString(); guardar();
    const informe = n === 1 ? `${GRUPO}_resultado.md` : `${GRUPO}_reevaluacion_V${n}.md`;
    fs.writeFileSync(path.join(out, informe), limpiar(`# ${GRUPO} — ${n === 1 ? 'EVALUACIÓN V1' : `REEVALUACIÓN V${n}`}\n\n> Borrador técnico generado automáticamente; QA revisa la evidencia antes de emitir el dictamen.\n\nCasos: ${CASOS.join(', ')} · RUN_ID: \`${run}\` · Ambiente: TEST · Estado técnico: ${ev.estado}\n\n| Caso | Resultado propuesto |\n| --- | --- |\n${CASOS.map(c => `| ${c} | ${ev.veredicto.casos[c]} |`).join('\n')}\n| **Grupo** | **${ev.veredicto.grupo}** |\n\nEscenario construido: ${JSON.stringify(ev.datos)}\n\nAserciones: ${JSON.stringify(ev.aserciones)}\n\nBloqueos por caso: ${JSON.stringify(ev.bloqueos)}\n\nDependencias: ${ev.dependencias.join('; ') || 'ninguna'}\n\nSandbox: aislamiento ${JSON.stringify(ev.sandbox.aislamiento || {})}; rollback ${ev.sandbox.rollback ? 'confirmado' : 'NO confirmado'}.\n`));
  }
  console.log(`${GRUPO}: ${ev.estado} — ${out}`); return ev.estado === 'CONCLUIDA' ? 0 : 4;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let code; try { const a = argumentos(process.argv.slice(2)); code = a.modo === 'local' ? local() : a.modo === 'spec' ? await verificarSpec() : await ejecutar(a); } catch (e) { console.error(e.message); code = 2; } process.exitCode = code;
}
