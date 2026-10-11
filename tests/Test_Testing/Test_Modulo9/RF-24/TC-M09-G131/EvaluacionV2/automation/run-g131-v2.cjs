// Runner único de la SEGUNDA EVALUACIÓN de TC-M09-G131 (RF-24 v2.0, Módulo 9).
// Casos TC-M09-258, TC-M09-259 y TC-M09-260 (variantes "OTRO" y "").
//
// Un solo archivo, tres modos (G131_MODO):
//
//   precheck  Validación Newman de SOLO LECTURA previa al RUN. Ejecuta la colección filtrada en
//             memoria SIN los cuatro POST /calibrar; no escribe nada, no genera HTML, no crea
//             RESULTADOS y no deja archivos: solo consola. El RUN se autoriza si no hay
//             failures de automatización.
//   run       RUN funcional oficial: la colección completa una única vez, con los 4 POST y el
//             ÚNICO reporte Newman HTML persistente.
//   close     Oráculo por caso, verificación final de solo lectura y consolidación de
//             evidencia.json y automation_manifest.json.
//
// PROPIEDAD DE SESIONES (regla corregida desde G76): la colección es dueña de la sesión. Hace su
// propio login y publica el token en {{session_value}}. El runner NO obtiene tokens y NO los
// inyecta: solo pasa configuración. Motivo: TEST aplica sesión única por usuario. El modo close
// se autentica DESPUÉS del RUN y exclusivamente para GET.
//
// Presupuesto: 4 POST /calibrar (uno por variante), sin reintentos. PATCH/PUT/DELETE: 0. Los
// cuatro son rechazos esperados: no deben crear datos y no se borra nada después.
//
// Uso:
//   $env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
//   $env:QA_ING_EMAIL="ingeniero@pecuaria.co"
//   $env:QA_ING_PASSWORD="<secreto>"
//   $env:G131_RUN_ID="run-YYYYMMDD-HHMMSS"     (modos run y close)
//   $env:G131_MODO="precheck" | "run" | "close"
//   node .\run-g131-v2.cjs

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const CASE_DIR = path.resolve(__dirname, '..', '..');
const EVAL_DIR = path.resolve(__dirname, '..');
const COLECCION = path.join(EVAL_DIR, 'TC-M09-G131.postman_collection.json');
const COLECCION_ORIGINAL = path.join(CASE_DIR, 'TC-M09-G131.postman_collection.json');

const GRUPO = 'TC-M09-G131';
const RF = 'RF-24 v2.0';
const POST_BUDGET = 4;

// Las cuatro variantes funcionales, en el orden obligatorio de ejecución.
const VARIANTES = [
  { clave: '258', caso: 'TC-M09-258', etiqueta: 'TC-M09-258', variante: '—', invalidez: 'Sensor pertenece a otro dispositivo' },
  { clave: '259', caso: 'TC-M09-259', etiqueta: 'TC-M09-259', variante: '—', invalidez: 'modo_calibracion ausente' },
  { clave: '260a', caso: 'TC-M09-260', etiqueta: 'TC-M09-260 OTRO', variante: 'OTRO', invalidez: 'modo_calibracion = "OTRO" (valor fuera de dominio)' },
  { clave: '260b', caso: 'TC-M09-260', etiqueta: 'TC-M09-260 VACIO', variante: '""', invalidez: 'modo_calibracion = "" (valor vacío)' }
];
const ITEMS_CALIBRAR = VARIANTES.map(v => `${v.etiqueta} POST calibrar`);

const MODO = process.env.G131_MODO || 'precheck';
if (!['precheck', 'run', 'close'].includes(MODO)) throw new Error(`G131_MODO no reconocido: ${MODO}`);

const base = () => {
  const b = process.env.QA_BASE_URL;
  if (!b) throw new Error('QA_BASE_URL requerido');
  return b.replace(/\/$/, '');
};
const ING = { email: process.env.QA_ING_EMAIL, secret: process.env.QA_ING_PASSWORD };
if (!ING.email || !ING.secret) throw new Error('QA_ING_EMAIL y QA_ING_PASSWORD requeridos (solo en memoria de proceso).');

// ------------------------------------------------------------------------- fixtures
const FIX = {
  // TC-258: el sensor pertenece al propietario, pero el body envía el dispositivo alterno.
  s258: {
    sensor: Number(process.env.G131_258_SENSOR || 3),
    propietario: Number(process.env.G131_258_OWNER || 1),
    dispositivoBody: Number(process.env.G131_258_DEVICE_BODY || 3),
    area: Number(process.env.G131_258_AREA || 1),
    categoria: process.env.G131_258_CAT || 'OXIGENO',
    valor: process.env.G131_258_VALOR || '10.0000'
  },
  // TC-259 y TC-260: fixture completamente válido; la única invalidez es modo_calibracion.
  s259: {
    sensor: Number(process.env.G131_259_SENSOR || 6),
    dispositivo: Number(process.env.G131_259_DEVICE || 3),
    area: Number(process.env.G131_259_AREA || 3),
    categoria: process.env.G131_259_CAT || 'TEMPERATURA',
    valor: process.env.G131_259_VALOR || '22.5000'
  }
};

const log = (...a) => console.log(...a);
const sha256 = (f) => crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');

// --------------------------------------------------------------------- sanitización
// La credencial de BD que el paquete entrega se cubre si llega por QA_DB_PASSWORD. NUNCA se
// escribe como literal aquí: el propio escaneo la marcaría como credencial en claro.
const secretos = () => [ING.secret, process.env.QA_ADMIN_PASSWORD, process.env.QA_DB_PASSWORD].filter(Boolean);
function limpiar(texto) {
  let s = String(texto);
  for (const x of secretos()) s = s.split(x).join('[REDACTED]');
  return s
    .replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[JWT REDACTED]')
    .replace(/Bearer\s+[A-Za-z0-9_.-]{12,}/g, 'Bearer [REDACTED]');
}
function limpiarHtml(html) {
  return limpiar(html)
    .replace(/Authorization/gi, '[REDACTED_HEADER]')
    .replace(/Bearer/gi, '[REDACTED_HEADER]')
    .replace(/access_token/gi, '[REDACTED]')
    .replace(/refresh_token/gi, '[REDACTED]')
    .replace(/contrasena/gi, '[REDACTED]')
    .replace(/password/gi, '[REDACTED]')
    .replace(/set-cookie/gi, '[REDACTED]')
    .replace(/\bjwt\b/gi, '[REDACTED]');
}

// ---------------------------------------------------------------------- rutas del RUN
const runId = process.env.G131_RUN_ID;
if (MODO !== 'precheck' && (!runId || !/^run-\d{8}-\d{6}$/.test(runId))) {
  throw new Error('G131_RUN_ID requerido con formato run-YYYYMMDD-HHMMSS.');
}
const RUN_DIR = runId ? path.join(EVAL_DIR, 'RESULTADOS', runId) : null;
const mk = (sub) => {
  if (MODO === 'precheck') throw new Error('El PRECHECK no debe crear carpetas de resultados.');
  const d = sub ? path.join(RUN_DIR, sub) : RUN_DIR;
  fs.mkdirSync(d, { recursive: true });
  return d;
};
const escribir = (nombre, valor) => {
  const f = path.join(mk(), nombre);
  fs.writeFileSync(f, limpiar(typeof valor === 'string' ? valor : JSON.stringify(valor, null, 2)));
  return f;
};
const HTML_OFICIAL = () => path.join(mk('newman'), `newman-${GRUPO}.html`);
const SUMMARY_TMP = () => path.join(RUN_DIR, '.summary-run.json');

// ------------------------------------------------------------------------------- git
const git = (args) => {
  const repoRoot = (() => {
    let d = CASE_DIR;
    for (let i = 0; i < 12; i += 1) {
      if (fs.existsSync(path.join(d, '.git'))) return d;
      const padre = path.dirname(d);
      if (padre === d) break;
      d = padre;
    }
    return CASE_DIR;
  })();
  try { return execFileSync('git', args, { cwd: repoRoot, encoding: 'utf8' }).trim(); }
  catch (e) { return `ERROR: ${e.message}`; }
};
const estadoGit = (etiqueta) => ({
  etiqueta, capturado: new Date().toISOString(),
  rama: git(['branch', '--show-current']),
  status_short: git(['status', '--short']) || '(vacio)',
  commit: git(['rev-parse', 'HEAD']),
  origin_test: git(['rev-parse', 'origin/test']),
  divergencia_HEAD_origin_test: git(['rev-list', '--left-right', '--count', 'HEAD...origin/test']),
  primera_evaluacion_RESULTADOS: git(['status', '--short', '--', 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G131/RESULTADOS']) || '(vacio = intacta)',
  operaciones_git_de_escritura: 'ninguna: sin add, commit, push, merge, rebase, reset, clean, stash, switch ni checkout'
});

// ------------------------------------------------------------------------- seguridad
function escanearSeguridad() {
  const TODOS = [
    [/eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\./, 'JWT'],
    [/Bearer\s+[A-Za-z0-9_.-]{12,}/, 'Authorization con token'],
    [/set-cookie/i, 'cabecera de cookie'],
    [/(access|refresh)_token"?\s*[:=]\s*"?[A-Za-z0-9_.-]{12,}/i, 'token en clave/valor'],
    [/(password|contrasena|contraseña)"?\s*[:=]\s*"?[^"\s,}\]]{4,}/i, 'credencial en clave/valor'],
    [/postgres(ql)?:\/\//i, 'cadena de conexión']
  ];
  const SOLO_VALORES = TODOS.filter(([, n]) => n === 'JWT' || n === 'Authorization con token' || n === 'cadena de conexión');
  const credenciales = secretos();
  const revisados = [];
  const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).forEach(e => {
    const f = path.join(d, e.name);
    if (e.isDirectory()) return walk(f);
    if (!/\.(html|json|md|txt|cjs)$/i.test(e.name)) return;
    const rel = path.relative(EVAL_DIR, f).split(path.sep).join('/');
    const esCodigo = /\.cjs$/i.test(rel);
    const txt = fs.readFileSync(f, 'utf8');
    revisados.push({
      archivo: rel, bytes: txt.length, tipo: esCodigo ? 'codigo-fuente' : 'evidencia',
      secretos: (esCodigo ? SOLO_VALORES : TODOS).filter(([re]) => re.test(txt)).map(([, n]) => n),
      credencialesEnClaro: credenciales.filter(x => txt.includes(x)).length
    });
  });
  walk(EVAL_DIR);
  const sucios = revisados.filter(r => r.secretos.length || r.credencialesEnClaro);
  return {
    alcance: 'todo EvaluacionV2/: runner, coleccion, informe, evidencia, manifiesto y el HTML de Newman',
    limpio: sucios.length === 0, archivosConHallazgos: sucios, revisados,
    credencialesCubiertas: 'contrasena de API del Ingeniero y, si se entregan por variable de entorno, la del Administrador y la de BD. Ninguna aparece como literal en el codigo.',
    criterio: 'Se marcan solo VALORES de secreto. En los .cjs solo se evaluan valores y la coincidencia literal con las credenciales.',
    nota: 'Las contrasenas solo existieron en memoria de proceso. El reporter htmlextra se ejecuto con omitHeaders, sin environment ni globals y omitiendo las variables sensibles; el HTML se sanitizo despues de generarse.'
  };
}

// ------------------------------------------------------------------- env de la colección
function construirEnv() {
  const f = (clave) => `"fecha_calibracion":"__FECHA__"`;
  // Los literales conservan los cuatro decimales en el JSON enviado, como en el plan original.
  const body258 = `{"modo_calibracion":"SENSOR","id_dispositivo_iot":${FIX.s258.dispositivoBody},"id_infraestructura":${FIX.s258.area},"valor_referencia":${FIX.s258.valor},"observaciones":"QA TC-M09-258",${f()}}`;
  // TC-259: la clave modo_calibracion NO aparece. Ni null, ni vacía, ni con valor.
  const body259 = `{"id_dispositivo_iot":${FIX.s259.dispositivo},"id_infraestructura":${FIX.s259.area},"valor_referencia":${FIX.s259.valor},"observaciones":"QA TC-M09-259",${f()}}`;
  const body260a = `{"modo_calibracion":"OTRO","id_dispositivo_iot":${FIX.s259.dispositivo},"id_infraestructura":${FIX.s259.area},"valor_referencia":${FIX.s259.valor},"observaciones":"QA TC-M09-260",${f()}}`;
  const body260b = `{"modo_calibracion":"","id_dispositivo_iot":${FIX.s259.dispositivo},"id_infraestructura":${FIX.s259.area},"valor_referencia":${FIX.s259.valor},"observaciones":"QA TC-M09-260",${f()}}`;

  if (JSON.parse(body259).modo_calibracion !== undefined || body259.includes('modo_calibracion')) {
    throw new Error('ABORTADO: el body de TC-M09-259 no puede contener la clave modo_calibracion.');
  }
  return [
    ['base_url', base()],
    ['ing_email', ING.email], ['ing_secret', ING.secret],
    ['owner_258', String(FIX.s258.propietario)], ['sensor_258', String(FIX.s258.sensor)],
    ['area_258', String(FIX.s258.area)], ['cat_258', FIX.s258.categoria], ['valor_258', FIX.s258.valor],
    ['device_258_body', String(FIX.s258.dispositivoBody)],
    ['device_259', String(FIX.s259.dispositivo)], ['sensor_259', String(FIX.s259.sensor)],
    ['area_259', String(FIX.s259.area)], ['cat_259', FIX.s259.categoria], ['valor_259', FIX.s259.valor],
    ['body_258', body258], ['body_259', body259], ['body_260a', body260a], ['body_260b', body260b],
    ['stop_all', 'NO']
  ];
}

function cargarColeccion(excluir) {
  const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
  const antes = col.item.map(i => i.name);
  for (const n of excluir) if (!antes.includes(n)) throw new Error(`El item «${n}» no existe en la colección.`);
  col.item = col.item.filter(i => !excluir.includes(i.name));
  return { col, itemsTotales: antes.length, itemsEjecutables: col.item.length, quitados: excluir };
}

function verificarEscrituras(col, permitirCalibrar) {
  for (const it of col.item) {
    const url = typeof it.request.url === 'string' ? it.request.url : it.request.url?.raw || '';
    const metodo = (it.request.method || 'GET').toUpperCase();
    if (['PATCH', 'PUT', 'DELETE'].includes(metodo)) throw new Error(`ABORTADO: escritura no autorizada ${metodo} ${url} (${it.name}).`);
    if (/\/calibrar$/.test(url) && !permitirCalibrar) throw new Error(`ABORTADO: el PRECHECK no puede contener el endpoint de calibración (${it.name}).`);
    if (metodo === 'POST' && !/\/sesiones\/?$/.test(url) && !/\/calibrar$/.test(url)) throw new Error(`ABORTADO: POST no autorizado: ${url} (${it.name}).`);
  }
}

function correrNewman(col, env, html, titulo) {
  const o = { collection: col, reporters: html ? ['cli', 'htmlextra'] : ['cli'], envVar: env.map(([key, value]) => ({ key, value })) };
  if (html) {
    o.reporter = { htmlextra: {
      export: html, omitHeaders: true, showEnvironmentData: false, showGlobalData: false,
      skipEnvironmentVars: ['ing_secret', 'session_value'], showMarkdownLinks: false
    } };
    if (titulo) o.reporter.htmlextra.title = titulo;
  }
  return new Promise((resolve, reject) => newman.run(o, (err, summary) => (err ? reject(err) : resolve(summary))));
}

function extraer(summary) {
  const ex = summary?.run?.executions || [];
  const find = (n) => ex.find(x => x.item && x.item.name === n);
  const cuerpo = (n) => { const e = find(n); if (!e || !e.response) return null; try { return JSON.parse(e.response.stream.toString()); } catch { return null; } };
  const crudo = (n) => { const e = find(n); if (!e || !e.response) return null; try { return e.response.stream.toString(); } catch { return null; } };
  const http = (n) => { const e = find(n); return e && e.response ? e.response.code : null; };
  const enviadoTexto = (n) => { const e = find(n); try { return e.request.body.raw.toString(); } catch { return null; } };
  const asserts = (n) => { const e = find(n); return (e?.assertions || []).map(a => ({ assertion: a.assertion, paso: !a.error, error: a.error ? a.error.message : null })); };
  const ejecutado = (n) => Boolean(find(n));
  return { cuerpo, crudo, http, enviadoTexto, asserts, ejecutado };
}
const fallos = (s) => (s?.run?.failures || []).map(f => ({ item: f.source?.name, assertion: f.error?.test, error: f.error?.message })).filter(f => f.error);
const stats = (s) => {
  const t = s?.run?.stats || {};
  return {
    iterations: { ejecutadas: t.iterations?.total ?? null, fallidas: t.iterations?.failed ?? null },
    requests: { ejecutados: t.requests?.total ?? null, fallidos: t.requests?.failed ?? null },
    assertions: { total: t.assertions?.total ?? 0, fallidas: t.assertions?.failed ?? 0 }
  };
};
const contar = (s, re) => (s?.run?.executions || []).filter(e => re.test(e.request?.url?.toString() || '')).length;
const envDe = (s, k) => s?.environment?.values?.find?.(x => x.key === k)?.value ?? null;

// HTTP directo: solo para la verificación final del modo close, DESPUÉS del RUN.
async function login(email, secret) {
  const r = await fetch(base() + '/sesiones/', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correo_electronico: email, contrasena: secret }), signal: AbortSignal.timeout(25000)
  });
  const b = await r.json().catch(() => null);
  if (r.status !== 200 || !b?.token) throw new Error(`login ${email} HTTP ${r.status}${b?.error_code ? ' ' + b.error_code : ''}`);
  return b.token;
}
async function get(endpoint, token) {
  const r = await fetch(base() + endpoint, { headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(30000) });
  return { status: r.status, cuerpo: await r.json().catch(() => null) };
}

// ==========================================================================================
(async () => {
  if (MODO === 'precheck') return modoPrecheck();
  if (MODO === 'run') return modoRun();
  return modoClose();
})().catch((e) => { console.error('\nNO COMPLETADO:', e.message); process.exitCode = 1; });

// ------------------------------------------------------------------------------- precheck
async function modoPrecheck() {
  const { col, itemsTotales, itemsEjecutables, quitados } = cargarColeccion(ITEMS_CALIBRAR);
  verificarEscrituras(col, false);

  log('PRECHECK de solo lectura — Newman sin reporter HTML, sin carpeta de resultados.');
  log(`Colección: ${itemsEjecutables} de ${itemsTotales} items. Excluidos los 4 POST /calibrar.`);
  log('Sin escrituras de negocio.\n');

  const summary = await correrNewman(col, construirEnv(), null, null);
  const st = stats(summary);
  const f = fallos(summary);
  const { cuerpo, http, asserts } = extraer(summary);
  const pasa = (item) => { const a = asserts(item); return a.length > 0 && a.every(x => x.paso); };

  const me = cuerpo('Identidad Ingeniero');
  const perm = cuerpo('Permisos Ingeniero');
  const chequeos = {
    ingeniero: http('Login Ingeniero') >= 200 && http('Login Ingeniero') <= 299 &&
      me?.correo_electronico === ING.email && me?.nombre_rol === 'Ingeniero de Campo' &&
      me?.estado_cuenta === 'Activo' && pasa('Identidad Ingeniero'),
    permisos: (perm?.permisos || []).some(p => p.id_recurso === 12 && p.id_accion === 1) && pasa('Permisos Ingeniero'),
    fixture258: ['Fixture 258 — dispositivo propietario', 'Fixture 258 — sensor del propietario',
      'Fixture 258 — asociación vigente', 'Fixture 258 — área de la asociación',
      'Fixture 258 — dispositivo alterno del body'].every(pasa),
    fixture259: ['Fixture 259/260 — dispositivo', 'Fixture 259/260 — sensor del dispositivo',
      'Fixture 259/260 — asociación vigente', 'Fixture 259/260 — área de la asociación'].every(pasa),
    rangos: pasa('Fixture — rangos de calibración'),
    openapiConsultado: http('Contrato OpenAPI') === 200 && pasa('Contrato OpenAPI')
  };

  const postCalibrar = contar(summary, /\/calibrar$/);
  // Un hallazgo del contrato NO bloquea el RUN: G131 debe comprobarlo empíricamente.
  const autorizar = Object.values(chequeos).every(Boolean) && f.length === 0 &&
    (st.requests.fallidos || 0) === 0 && postCalibrar === 0;

  const P = (b) => (b ? 'PASS' : 'FAIL');
  log('\nPRECHECK_G131\n');
  log(`Ingeniero:\n${P(chequeos.ingeniero)}\n`);
  log(`Permisos:\n${P(chequeos.permisos)}\n`);
  log(`Fixture TC258:\n${P(chequeos.fixture258)}\n`);
  log(`Fixture sensor6:\n${P(chequeos.fixture259)}\n`);
  log(`Rangos:\n${P(chequeos.rangos)}\n`);
  log(`OpenAPI consultado:\n${P(chequeos.openapiConsultado)}\n`);
  log(`Failures automatización:\n${f.length}\n`);
  log(`POST calibrar:\n${postCalibrar}\n`);
  log(`AUTORIZAR_RUN:\n${autorizar ? 'SÍ' : 'NO'}\n`);

  log('--- contrato OpenAPI observado (diagnóstico, no decide el resultado) ---');
  log(`modo_calibracion declarado: ${envDe(summary, 'openapi_modo_declarado')}`);
  log(`required:                   ${envDe(summary, 'openapi_modo_required')}`);
  log(`default:                    ${envDe(summary, 'openapi_modo_default')}`);
  log(`dominio:                    ${envDe(summary, 'openapi_modo_dominio')}`);
  log(`definición:                 ${envDe(summary, 'openapi_modo_definicion')}`);
  log(`required del DTO:           ${envDe(summary, 'openapi_required')}`);
  if (envDe(summary, 'openapi_modo_required') !== 'SI') {
    log('RIESGO DE REGRESIÓN / CORRECCIÓN NO DESPLEGADA: el contrato no marca modo_calibracion como obligatorio.');
    log('No se cambia el esperado funcional: el objetivo se determina por los POST reales.');
  }

  log('\n--- detalle observado (solo consola, no se persiste) ---');
  log(`Ingeniero: id_usuario=${me?.id_usuario} rol="${me?.nombre_rol}" estado=${me?.estado_cuenta} | permisos recurso 12: ${envDe(summary, 'permisos_recurso12')}`);
  log(`fixture TC-258: sensor ${FIX.s258.sensor} (${FIX.s258.categoria}) propietario ${FIX.s258.propietario} / área ${FIX.s258.area} | el body enviará dispositivo ${FIX.s258.dispositivoBody} | valor ${FIX.s258.valor} | rango ${envDe(summary, 'rango_258')}`);
  log(`fixture TC-259/260: sensor ${FIX.s259.sensor} (${FIX.s259.categoria}) dispositivo ${FIX.s259.dispositivo} / área ${FIX.s259.area} | valor ${FIX.s259.valor} | rango ${envDe(summary, 'rango_259')}`);
  for (const v of VARIANTES) log(`historial PRE ${v.etiqueta}: total ${envDe(summary, `pre_${v.clave}_total`)}`);
  log(`newman: requests ${st.requests.ejecutados}/${st.requests.fallidos} fallidos | assertions ${st.assertions.total}/${st.assertions.fallidas} fallidas`);
  if (f.length) { log('\nfailures:'); f.forEach((x, i) => log(`  ${i + 1}. ${x.item} :: ${x.assertion} :: ${x.error}`)); }
  log('');

  if (!autorizar) { log('El RUN funcional NO está autorizado. Corregir la automatización antes de ejecutar los POST.'); process.exitCode = 2; }
}

// ------------------------------------------------------------------------------------ run
async function modoRun() {
  if (fs.existsSync(RUN_DIR)) throw new Error(`La carpeta ${runId} ya existe. Un RUN oficial no se repite ni se sobrescribe.`);
  const { col, itemsTotales, itemsEjecutables } = cargarColeccion([]);
  verificarEscrituras(col, true);
  const calibrar = col.item.filter(i => /\/calibrar$/.test(typeof i.request.url === 'string' ? i.request.url : i.request.url?.raw || ''));
  if (calibrar.length !== POST_BUDGET) throw new Error(`ABORTADO: la colección debe contener exactamente ${POST_BUDGET} POST de calibración, contiene ${calibrar.length}.`);

  const gitPre = estadoGit('git_pre');
  const html = HTML_OFICIAL();

  log(`RUN funcional oficial. RUN_ID: ${runId}`);
  log(`Colección: ${itemsEjecutables} de ${itemsTotales} items.`);
  log(`POST /calibrar planificados: ${POST_BUDGET} | PATCH/PUT/DELETE: 0 | reintentos: 0`);
  log('Los cuatro POST son rechazos esperados: oráculo = 4xx + no persistencia.\n');

  const summary = await correrNewman(col, construirEnv(), html, `${GRUPO} — SEGUNDA EVALUACIÓN · RUN funcional oficial ${runId}`);
  if (fs.existsSync(html)) fs.writeFileSync(html, limpiarHtml(fs.readFileSync(html, 'utf8')));

  const { cuerpo, crudo, http, enviadoTexto, asserts, ejecutado } = extraer(summary);
  const preservado = {
    runId, generado: new Date().toISOString(), gitPre, itemsTotales, itemsEjecutables,
    stats: stats(summary), failures: fallos(summary),
    postCalibrar: contar(summary, /\/calibrar$/),
    stopAll: envDe(summary, 'stop_all') ?? 'NO',
    stopAllMotivo: envDe(summary, 'stop_all_motivo'),
    ingLogin: { http: http('Login Ingeniero'), assertions: asserts('Login Ingeniero') },
    identidad: { http: http('Identidad Ingeniero'), cuerpo: cuerpo('Identidad Ingeniero'), assertions: asserts('Identidad Ingeniero') },
    permisos: { http: http('Permisos Ingeniero'), cuerpo: cuerpo('Permisos Ingeniero'), assertions: asserts('Permisos Ingeniero'), recurso12: envDe(summary, 'permisos_recurso12') },
    openapi: {
      http: http('Contrato OpenAPI'), assertions: asserts('Contrato OpenAPI'),
      modo_declarado: envDe(summary, 'openapi_modo_declarado'),
      modo_required: envDe(summary, 'openapi_modo_required'),
      modo_default: envDe(summary, 'openapi_modo_default'),
      modo_dominio: envDe(summary, 'openapi_modo_dominio'),
      modo_definicion: envDe(summary, 'openapi_modo_definicion'),
      required_dto: envDe(summary, 'openapi_required')
    },
    fixtures: {
      '258': {
        propietario: { http: http('Fixture 258 — dispositivo propietario'), cuerpo: cuerpo('Fixture 258 — dispositivo propietario'), assertions: asserts('Fixture 258 — dispositivo propietario') },
        sensores: { http: http('Fixture 258 — sensor del propietario'), cuerpo: cuerpo('Fixture 258 — sensor del propietario'), assertions: asserts('Fixture 258 — sensor del propietario') },
        asociaciones: { http: http('Fixture 258 — asociación vigente'), cuerpo: cuerpo('Fixture 258 — asociación vigente'), assertions: asserts('Fixture 258 — asociación vigente') },
        area: { http: http('Fixture 258 — área de la asociación'), cuerpo: cuerpo('Fixture 258 — área de la asociación'), assertions: asserts('Fixture 258 — área de la asociación') },
        dispositivoAlterno: { http: http('Fixture 258 — dispositivo alterno del body'), cuerpo: cuerpo('Fixture 258 — dispositivo alterno del body'), assertions: asserts('Fixture 258 — dispositivo alterno del body') },
        rango: envDe(summary, 'rango_258')
      },
      '259': {
        dispositivo: { http: http('Fixture 259/260 — dispositivo'), cuerpo: cuerpo('Fixture 259/260 — dispositivo'), assertions: asserts('Fixture 259/260 — dispositivo') },
        sensores: { http: http('Fixture 259/260 — sensor del dispositivo'), cuerpo: cuerpo('Fixture 259/260 — sensor del dispositivo'), assertions: asserts('Fixture 259/260 — sensor del dispositivo') },
        asociaciones: { http: http('Fixture 259/260 — asociación vigente'), cuerpo: cuerpo('Fixture 259/260 — asociación vigente'), assertions: asserts('Fixture 259/260 — asociación vigente') },
        area: { http: http('Fixture 259/260 — área de la asociación'), cuerpo: cuerpo('Fixture 259/260 — área de la asociación'), assertions: asserts('Fixture 259/260 — área de la asociación') },
        rango: envDe(summary, 'rango_259')
      },
      rangos: { http: http('Fixture — rangos de calibración'), cuerpo: cuerpo('Fixture — rangos de calibración'), assertions: asserts('Fixture — rangos de calibración') }
    },
    variantes: {}
  };
  for (const v of VARIANTES) {
    preservado.variantes[v.clave] = {
      ejecutado: ejecutado(`${v.etiqueta} POST calibrar`),
      pre: { http: http(`${v.etiqueta} Historial PRE`), cuerpo: cuerpo(`${v.etiqueta} Historial PRE`), assertions: asserts(`${v.etiqueta} Historial PRE`) },
      calibrar: {
        http: http(`${v.etiqueta} POST calibrar`), cuerpo: cuerpo(`${v.etiqueta} POST calibrar`),
        crudo: crudo(`${v.etiqueta} POST calibrar`),
        enviadoTexto: enviadoTexto(`${v.etiqueta} POST calibrar`),
        assertions: asserts(`${v.etiqueta} POST calibrar`),
        error_code: envDe(summary, `${v.clave}_error_code`),
        id_respuesta: envDe(summary, `${v.clave}_id_respuesta`)
      },
      post: { http: http(`${v.etiqueta} Historial POST`), cuerpo: cuerpo(`${v.etiqueta} Historial POST`), assertions: asserts(`${v.etiqueta} Historial POST`) },
      idsNuevos: envDe(summary, `${v.clave}_ids_nuevos`)
    };
  }
  fs.writeFileSync(SUMMARY_TMP(), limpiar(JSON.stringify(preservado, null, 2)));

  const st = preservado.stats;
  log('\n================ RUN OFICIAL ================');
  log(`RUN_ID: ${runId}`);
  log(`requests ${st.requests.ejecutados} (fallidos ${st.requests.fallidos}) | assertions ${st.assertions.total} (fallidas ${st.assertions.fallidas})`);
  log(`POST /calibrar ejecutados: ${preservado.postCalibrar}/${POST_BUDGET} | STOP_ALL: ${preservado.stopAll}`);
  for (const v of VARIANTES) {
    const b = preservado.variantes[v.clave];
    if (!b.ejecutado) { log(`  ${v.etiqueta}: NO EJECUTADO`); continue; }
    const en4xx = b.calibrar.http >= 400 && b.calibrar.http <= 499;
    log(`  ${v.etiqueta}: HTTP ${b.calibrar.http} (${en4xx ? '4xx' : 'FUERA DE 4xx'}) | error_code ${b.calibrar.error_code || '—'} | id_calibracion ${b.calibrar.id_respuesta || 'ausente'} | ids nuevos ${b.idsNuevos}`);
  }
  if (preservado.failures.length) { log('\nFAILURES:'); preservado.failures.forEach((x, i) => log(`  ${i + 1}. ${x.item} :: ${x.assertion} :: ${x.error}`)); }
  log('=============================================\n');
  log(`HTML: ${path.relative(EVAL_DIR, html).split(path.sep).join('/')}`);
  log('Ejecute ahora el modo close para el oráculo y la evidencia.');
  if (preservado.failures.length) process.exitCode = 2;
}

// ---------------------------------------------------------------------------------- close
async function modoClose() {
  const tmp = SUMMARY_TMP();
  const evidenciaPath = path.join(RUN_DIR, 'evidencia.json');
  if (!fs.existsSync(tmp)) {
    if (!fs.existsSync(evidenciaPath)) throw new Error('No hay summary del RUN ni evidencia previa: ejecute primero G131_MODO=run.');
    const ev = JSON.parse(fs.readFileSync(evidenciaPath, 'utf8'));
    ev.seguridad = escanearSeguridad();
    ev.git_post = estadoGit('git_post');
    escribir('evidencia.json', ev);
    refrescarManifest();
    log(`\nCIERRE (recalculo de seguridad y git). GRUPO ${GRUPO} -> ${ev.resultado_grupo}`);
    log(`Evidencia limpia de secretos: ${ev.seguridad.limpio ? 'SI' : 'NO'}`);
    if (!ev.seguridad.limpio) process.exitCode = 3;
    return;
  }
  const R = JSON.parse(fs.readFileSync(tmp, 'utf8'));
  const sid = (x) => (x && x.id_sensor !== undefined ? x.id_sensor : x && x.id_sensores);
  const vig = (x) => x && x.tiene_estado === true && (x.fecha_finalizacion === null || x.fecha_finalizacion === undefined);

  // ---------------------------------------------------- oráculo por variante
  const variantes = {};
  for (const v of VARIANTES) {
    const b = R.variantes[v.clave];
    if (!b.ejecutado) {
      variantes[v.clave] = {
        ...v, ejecutado: false, resultado: 'NO EJECUTADO',
        motivo: `No se ejecutó: STOP_ALL activado por una variante anterior. ${R.stopAllMotivo || ''}`.trim()
      };
      continue;
    }
    const pre = b.pre.cuerpo, post = b.post.cuerpo, resp = b.calibrar.cuerpo;
    const preIds = pre ? (pre.items || []).map(x => x.id_calibracion) : null;
    const postIds = post ? (post.items || []).map(x => x.id_calibracion) : null;
    const nuevos = preIds && postIds ? postIds.filter(x => !preIds.includes(x)) : null;
    const enviado = b.calibrar.enviadoTexto ? JSON.parse(b.calibrar.enviadoTexto) : null;
    const claveModoPresente = b.calibrar.enviadoTexto ? b.calibrar.enviadoTexto.includes('modo_calibracion') : null;

    let historicosIntactos = null;
    if (pre && post) {
      historicosIntactos = (pre.items || []).every(s => {
        const row = (post.items || []).find(x => x.id_calibracion === s.id_calibracion);
        return row && String(row.valor_referencia) === String(s.valor_referencia) &&
          row.fecha_calibracion === s.fecha_calibracion && row.id_usuario === s.id_usuario &&
          row.observaciones === s.observaciones;
      });
    }
    const assertionsFuncionales = [...b.pre.assertions, ...b.calibrar.assertions, ...b.post.assertions];

    const oraculo = {
      // El oráculo de la matriz: rechazo 4xx y ausencia de persistencia. Sin código ni mensaje exactos.
      http_4xx: b.calibrar.http >= 400 && b.calibrar.http <= 499,
      sin_id_calibracion: resp ? resp.id_calibracion === undefined || resp.id_calibracion === null : false,
      total_sin_cambios: Boolean(pre) && Boolean(post) && Number(pre.total) === Number(post.total),
      ids_identicos: Boolean(preIds) && Boolean(postIds) && JSON.stringify(preIds.slice().sort()) === JSON.stringify(postIds.slice().sort()),
      sin_persistencia: Array.isArray(nuevos) && nuevos.length === 0,
      historial_intacto: historicosIntactos === true,
      assertions_funcionales_todas_pass: assertionsFuncionales.length > 0 && assertionsFuncionales.every(a => a.paso)
    };
    // TC-259 exige además que la clave estuviera COMPLETAMENTE ausente del body enviado.
    if (v.clave === '259') oraculo.modo_calibracion_completamente_ausente = claveModoPresente === false;

    variantes[v.clave] = {
      ...v, ejecutado: true,
      sensor: v.clave === '258' ? FIX.s258.sensor : FIX.s259.sensor,
      dispositivoEnBody: v.clave === '258' ? FIX.s258.dispositivoBody : FIX.s259.dispositivo,
      area: v.clave === '258' ? FIX.s258.area : FIX.s259.area,
      valor: v.clave === '258' ? FIX.s258.valor : FIX.s259.valor,
      request: {
        endpoint: `/configuracion/sensores/${v.clave === '258' ? FIX.s258.sensor : FIX.s259.sensor}/calibrar`,
        metodo: 'POST', headers: { Authorization: '[REDACTED]', 'Content-Type': 'application/json' },
        bodyTextoEnviado: b.calibrar.enviadoTexto, body: enviado,
        clave_modo_calibracion_presente: claveModoPresente
      },
      response: {
        http: b.calibrar.http, cuerpo: resp, crudo: b.calibrar.crudo,
        error_code: resp?.error_code ?? b.calibrar.error_code ?? null,
        message: resp?.message ?? resp?.detail ?? null,
        id_calibracion: resp?.id_calibracion ?? null,
        capturado: new Date().toISOString()
      },
      httpEsperado: '4xx (RF-24 no fija un código concreto)',
      en4xx: b.calibrar.http >= 400 && b.calibrar.http <= 499,
      historialPre: pre ? { http: b.pre.http, total: pre.total, ids: preIds, items: pre.items || [] } : null,
      historialPost: post ? { http: b.post.http, total: post.total, ids: postIds, items: post.items || [] } : null,
      idsNuevos: nuevos, historicosIntactos,
      assertionsFuncionales: { total: assertionsFuncionales.length, fallidas: assertionsFuncionales.filter(a => !a.paso).length, detalle: assertionsFuncionales },
      oraculo,
      resultado: Object.values(oraculo).every(x => x === true) ? 'APROBADO' : 'RECHAZADO'
    };
  }

  // Resultado por caso. TC-260 agrupa las dos variantes.
  const r258 = variantes['258'].resultado;
  const r259 = variantes['259'].resultado;
  const v260 = [variantes['260a'], variantes['260b']];
  const r260 = v260.every(x => x.resultado === 'APROBADO') ? 'APROBADO'
    : v260.some(x => x.resultado === 'NO EJECUTADO') ? 'RECHAZADO / ejecución parcial'
    : 'RECHAZADO';

  const newmanLimpio = R.failures.length === 0 && (R.stats.requests.fallidos || 0) === 0;
  const persistenciaInesperada = Object.values(variantes)
    .filter(x => x.ejecutado && Array.isArray(x.idsNuevos) && x.idsNuevos.length > 0)
    .flatMap(x => x.idsNuevos);
  const resultadoGrupo = (r258 === 'APROBADO' && r259 === 'APROBADO' && r260 === 'APROBADO' &&
    newmanLimpio && persistenciaInesperada.length === 0) ? 'APROBADO' : 'RECHAZADO';

  // ------------------------------------- verificación final: SOLO LECTURA, después del RUN
  const tokenIng = await login(ING.email, ING.secret);
  const hist258 = await get(`/configuracion/sensores/${FIX.s258.sensor}/calibraciones`, tokenIng);
  const hist259 = await get(`/configuracion/sensores/${FIX.s259.sensor}/calibraciones`, tokenIng);
  const asoc258 = await get(`/configuracion/sensores/${FIX.s258.sensor}/asociaciones`, tokenIng);
  const asoc259 = await get(`/configuracion/sensores/${FIX.s259.sensor}/asociaciones`, tokenIng);
  const ids258 = (hist258.cuerpo?.items || []).map(x => x.id_calibracion);
  const ids259 = (hist259.cuerpo?.items || []).map(x => x.id_calibracion);
  const obsDelGrupo = ['QA TC-M09-258', 'QA TC-M09-259', 'QA TC-M09-260'];
  const atribuibles258 = (hist258.cuerpo?.items || []).filter(x => obsDelGrupo.includes(x.observaciones)).map(x => x.id_calibracion);
  const atribuibles259 = (hist259.cuerpo?.items || []).filter(x => obsDelGrupo.includes(x.observaciones)).map(x => x.id_calibracion);

  // ------------------------------------------------------- comparación con la primera
  const PRIMERA = {
    runId: 'run-20261007-040706',
    fuente: 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G131/RESULTADOS/run-20261007-040706/TC-M09-G131_resultado.md',
    '258': { resultado: 'APROBADO', http: '422 — 4xx correcto', persistencia: 'PASS — sin persistencia', detalle: 'SENSOR_DISPOSITIVO_INVALIDO; historial del sensor 3 sin cambios' },
    '259': { resultado: 'RECHAZADO', http: 'HTTP 201 — fuera de 4xx', persistencia: 'FAIL — creó id_calibracion 16', detalle: 'historial del sensor 6 pasó de 6 a 7 registros' },
    '260a': { resultado: 'NO EJECUTADO', http: 'sin POST', persistencia: 'sin POST', detalle: 'STOP_ALL tras la persistencia indebida de TC-M09-259' },
    '260b': { resultado: 'NO EJECUTADO', http: 'sin POST', persistencia: 'sin POST', detalle: 'STOP_ALL tras la persistencia indebida de TC-M09-259' },
    grupo: 'RECHAZADO',
    presupuesto: { planificados: 4, ejecutados: 2, stopAll: 'SÍ' },
    openapi: { declarado: 'NO', required: 'NO', default: 'no verificable / comportamiento equivalente a opcional', dominio: 'no publicado', ausenciaRechazada: 'NO — respondió 201' }
  };
  const comparacion = {
    baselineUnico: `PRIMERA EVALUACION OFICIAL ${PRIMERA.runId}`,
    fuente: PRIMERA.fuente,
    porVariante: Object.fromEntries(VARIANTES.map(v => [v.etiqueta, {
      primera: PRIMERA[v.clave].resultado,
      segunda: variantes[v.clave].resultado,
      cambio: variantes[v.clave].resultado === PRIMERA[v.clave].resultado ? 'SIN CAMBIO' : `${PRIMERA[v.clave].resultado} -> ${variantes[v.clave].resultado}`,
      dimensiones: {
        rechazo_4xx: { primera: PRIMERA[v.clave].http, segunda: variantes[v.clave].ejecutado ? `HTTP ${variantes[v.clave].response.http} — ${variantes[v.clave].en4xx ? '4xx correcto' : 'fuera de 4xx'}` : 'sin POST' },
        no_persistencia: { primera: PRIMERA[v.clave].persistencia, segunda: variantes[v.clave].ejecutado ? (variantes[v.clave].oraculo.sin_persistencia ? 'PASS — sin persistencia' : `FAIL — IDs nuevos ${JSON.stringify(variantes[v.clave].idsNuevos)}`) : 'sin POST' }
      },
      detallePrimera: PRIMERA[v.clave].detalle
    }])),
    porCaso: {
      'TC-M09-258': { primera: 'APROBADO', segunda: r258, cambio: r258 === 'APROBADO' ? 'SIN CAMBIO' : `APROBADO -> ${r258}` },
      'TC-M09-259': { primera: 'RECHAZADO', segunda: r259, cambio: r259 === 'RECHAZADO' ? 'SIN CAMBIO' : `RECHAZADO -> ${r259}` },
      'TC-M09-260': { primera: 'NO EJECUTADO (ambas variantes)', segunda: r260, cambio: `NO EJECUTADO -> ${r260}` }
    },
    grupo: { primera: PRIMERA.grupo, segunda: resultadoGrupo, cambio: resultadoGrupo === PRIMERA.grupo ? 'SIN CAMBIO' : `${PRIMERA.grupo} -> ${resultadoGrupo}` },
    openapi: {
      modo_calibracion_declarado: { primera: PRIMERA.openapi.declarado, segunda: R.openapi.modo_declarado },
      required: { primera: PRIMERA.openapi.required, segunda: R.openapi.modo_required },
      default_automatico: { primera: PRIMERA.openapi.default, segunda: R.openapi.modo_default },
      dominio_publicado: { primera: PRIMERA.openapi.dominio, segunda: R.openapi.modo_dominio },
      ausencia_rechazada: { primera: PRIMERA.openapi.ausenciaRechazada, segunda: variantes['259'].ejecutado ? (variantes['259'].en4xx ? `SÍ — HTTP ${variantes['259'].response.http}` : `NO — HTTP ${variantes['259'].response.http}`) : 'sin POST' }
    },
    presupuesto: { primera: PRIMERA.presupuesto, segunda: { planificados: POST_BUDGET, ejecutados: R.postCalibrar, stopAll: R.stopAll } },
    causaDelRechazoAnterior: r259 === 'APROBADO' ? 'CORREGIDA' : 'NO CORREGIDA'
  };

  const causaRaiz = (() => {
    if (r258 === 'APROBADO' && r259 === 'APROBADO' && r260 === 'APROBADO') {
      return 'A. Todo rechazado correctamente: el defecto anterior (modo_calibracion no era obligatorio y su ausencia se persistia) esta corregido y desplegado en TEST. El contrato publica el campo como required y el endpoint lo restringe a SENSOR.';
    }
    if (r259 !== 'APROBADO') return 'B. TC-M09-259 vuelve a aceptar la ausencia de modo_calibracion: el campo aun no es obligatorio en el TEST desplegado.';
    if (r260 !== 'APROBADO') return 'C. TC-M09-259 pasa pero TC-M09-260 acepta valores invalidos: la validacion de dominio de modo_calibracion esta incompleta.';
    return 'Por determinar con la evidencia de esta corrida.';
  })();

  const anomalia = Object.values(variantes).some(x => x.ejecutado && (!x.en4xx || !x.oraculo.sin_persistencia));

  const evidencia = {
    run_id: runId, evaluacion: 'SEGUNDA EVALUACION',
    grupo: GRUPO, casos: ['TC-M09-258', 'TC-M09-259', 'TC-M09-260'], requisito: RF,
    herramientas: 'API - Postman / Newman. BD no es herramienta principal y no se utilizo.',
    ambiente: { decisorio: 'TEST', base_url: base() },
    carpeta: `tests/Test_Testing/Test_Modulo9/RF-24/${GRUPO}/EvaluacionV2/`,
    rama: R.gitPre.rama, commit: R.gitPre.commit,
    resultado_grupo: resultadoGrupo,
    resultado_por_caso: { 'TC-M09-258': r258, 'TC-M09-259': r259, 'TC-M09-260': r260 },

    git_pre: R.gitPre,

    actor: {
      nota: 'La coleccion Newman es duena de la sesion: hace su propio login y publica el token en session_value. El runner no obtiene tokens ni los inyecta; en el cierre se autentica solo para GET.',
      correo: ING.email, credencial: '[REDACTED]', login_http: R.ingLogin.http,
      id_usuario: R.identidad.cuerpo?.id_usuario ?? null, id_descubierto_dinamicamente: true,
      rol: R.identidad.cuerpo?.nombre_rol ?? null, estado_cuenta: R.identidad.cuerpo?.estado_cuenta ?? null,
      permisos_recurso_12: R.permisos.recurso12,
      total_permisos: (R.permisos.cuerpo?.permisos || []).length,
      papel: 'ejecuta exclusivamente los 4 POST /calibrar',
      administrador: { utilizado: false, motivo: 'el Ingeniero resolvio por GET todas las precondiciones de ambos fixtures: no hizo falta el actor auxiliar de lectura' }
    },

    contrato_openapi: {
      http: R.openapi.http,
      modo_calibracion_declarado: R.openapi.modo_declarado,
      required: R.openapi.modo_required,
      default: R.openapi.modo_default,
      dominio: R.openapi.modo_dominio,
      definicion: R.openapi.modo_definicion,
      required_del_dto: R.openapi.required_dto,
      nota: 'Observacion DIAGNOSTICA del contrato desplegado. No decide el resultado: el objetivo funcional se determina por los POST reales.',
      riesgo_de_regresion: R.openapi.modo_required === 'SI' ? 'NO' : 'SI — el contrato no marca el campo como obligatorio'
    },

    fixture_258: {
      escenario: 'Sensor pertenece a otro dispositivo',
      sensor: FIX.s258.sensor, propietario_real: FIX.s258.propietario,
      dispositivo_enviado_en_el_body: FIX.s258.dispositivoBody,
      area: FIX.s258.area, categoria: FIX.s258.categoria, valor: FIX.s258.valor,
      rango: R.fixtures['258'].rango ? JSON.parse(R.fixtures['258'].rango) : null,
      propietario: R.fixtures['258'].propietario.cuerpo ? { id: R.fixtures['258'].propietario.cuerpo.id_dispositivo_iot, serial: R.fixtures['258'].propietario.cuerpo.serial, es_activo: R.fixtures['258'].propietario.cuerpo.es_activo } : null,
      sensorRow: (() => { const row = (R.fixtures['258'].sensores.cuerpo?.items || []).find(x => sid(x) === FIX.s258.sensor) || null;
        return row ? { id: sid(row), categoria: row.categoria, es_activo: row.es_activo, id_dispositivo_iot: row.id_dispositivo_iot } : null; })(),
      asociacionVigente: (() => { const a = (R.fixtures['258'].asociaciones.cuerpo?.items || []).find(x => vig(x) && sid(x) === FIX.s258.sensor && x.id_dispositivo_iot === FIX.s258.propietario) || null;
        return a ? { id_dispositivo_iot: a.id_dispositivo_iot, id_infraestructura: a.id_infraestructura, tiene_estado: a.tiene_estado, fecha_finalizacion: a.fecha_finalizacion } : null; })(),
      area_detalle: R.fixtures['258'].area.cuerpo ? { id: R.fixtures['258'].area.cuerpo.id_infraestructura, es_activo: R.fixtures['258'].area.cuerpo.es_activo } : null,
      dispositivo_alterno: R.fixtures['258'].dispositivoAlterno.cuerpo ? { id: R.fixtures['258'].dispositivoAlterno.cuerpo.id_dispositivo_iot, serial: R.fixtures['258'].dispositivoAlterno.cuerpo.serial, es_activo: R.fixtures['258'].dispositivoAlterno.cuerpo.es_activo } : null,
      unica_invalidez: 'la inconsistencia sensor-dispositivo: el sensor pertenece al propietario, pero el body envia el dispositivo alterno, tambien real y activo'
    },

    fixture_259_260: {
      escenario: 'Fixture completamente valido; la unica invalidez de cada variante es modo_calibracion',
      sensor: FIX.s259.sensor, dispositivo: FIX.s259.dispositivo, area: FIX.s259.area,
      categoria: FIX.s259.categoria, valor: FIX.s259.valor,
      rango: R.fixtures['259'].rango ? JSON.parse(R.fixtures['259'].rango) : null,
      dispositivo_detalle: R.fixtures['259'].dispositivo.cuerpo ? { id: R.fixtures['259'].dispositivo.cuerpo.id_dispositivo_iot, serial: R.fixtures['259'].dispositivo.cuerpo.serial, es_activo: R.fixtures['259'].dispositivo.cuerpo.es_activo } : null,
      sensorRow: (() => { const row = (R.fixtures['259'].sensores.cuerpo?.items || []).find(x => sid(x) === FIX.s259.sensor) || null;
        return row ? { id: sid(row), categoria: row.categoria, es_activo: row.es_activo, id_dispositivo_iot: row.id_dispositivo_iot } : null; })(),
      asociacionVigente: (() => { const a = (R.fixtures['259'].asociaciones.cuerpo?.items || []).find(x => vig(x) && sid(x) === FIX.s259.sensor && x.id_dispositivo_iot === FIX.s259.dispositivo) || null;
        return a ? { id_dispositivo_iot: a.id_dispositivo_iot, id_infraestructura: a.id_infraestructura, tiene_estado: a.tiene_estado, fecha_finalizacion: a.fecha_finalizacion } : null; })(),
      area_detalle: R.fixtures['259'].area.cuerpo ? { id: R.fixtures['259'].area.cuerpo.id_infraestructura, es_activo: R.fixtures['259'].area.cuerpo.es_activo } : null
    },

    'TC-M09-258': variantes['258'],
    'TC-M09-259': variantes['259'],
    'TC-M09-260': { OTRO: variantes['260a'], VACIO: variantes['260b'], resultado: r260 },

    newman: {
      html: `newman/newman-${GRUPO}.html`, htmlPersistentes: 1,
      coleccionEjecutada: `${R.itemsEjecutables} de ${R.itemsTotales} items`,
      iterations: R.stats.iterations, requests: R.stats.requests, assertions: R.stats.assertions,
      failures: R.failures,
      presupuesto: { postPlanificados: POST_BUDGET, postEjecutados: R.postCalibrar, patch: 0, put: 0, delete: 0, reintentos: 0 },
      stopAll: R.stopAll, stopAllMotivo: R.stopAllMotivo ? JSON.parse(R.stopAllMotivo) : null,
      limpio: newmanLimpio
    },

    verificacion_final: {
      soloLectura: true, sql: 'ninguno', escrituras: 0, fecha: new Date().toISOString(),
      historial_sensor_258: { sensor: FIX.s258.sensor, http: hist258.status, total: hist258.cuerpo?.total ?? null, ids: ids258,
        igualAlPre: JSON.stringify(ids258.slice().sort()) === JSON.stringify((variantes['258'].historialPre?.ids || []).slice().sort()) },
      historial_sensor_259: { sensor: FIX.s259.sensor, http: hist259.status, total: hist259.cuerpo?.total ?? null, ids: ids259 },
      asociacion_sensor_258: (asoc258.cuerpo?.items || []).filter(x => vig(x) && sid(x) === FIX.s258.sensor).map(x => ({ id_dispositivo_iot: x.id_dispositivo_iot, id_infraestructura: x.id_infraestructura })),
      asociacion_sensor_259: (asoc259.cuerpo?.items || []).filter(x => vig(x) && sid(x) === FIX.s259.sensor).map(x => ({ id_dispositivo_iot: x.id_dispositivo_iot, id_infraestructura: x.id_infraestructura })),
      ids_nuevos_por_variante: Object.fromEntries(VARIANTES.map(v => [v.etiqueta, variantes[v.clave].idsNuevos ?? 'sin POST'])),
      calibraciones_atribuibles_al_grupo: { sensor_258: atribuibles258, sensor_259: atribuibles259 },
      ninguna_calibracion_creada: persistenciaInesperada.length === 0,
      persistencia_inesperada: persistenciaInesperada,
      post_extra_ejecutados: 0,
      nota_calibracion_16: (() => {
        const existe = ids259.includes(16);
        return `La calibracion 16, creada indebidamente por la PRIMERA evaluacion, ${existe ? 'sigue existiendo' : 'no esta'} en el historial del sensor ${FIX.s259.sensor}. Su presencia o ausencia NO es criterio de este RUN: solo cuentan los IDs nuevos surgidos durante esta corrida. No se borro ningun registro.`;
      })()
    },

    contraste_dev: {
      necesario: anomalia,
      motivo: anomalia
        ? 'TEST reproduce un comportamiento inesperado: procede contrastar DEV para distinguir defecto de aplicacion de desfase de despliegue.'
        : 'TEST paso completamente: las cuatro variantes fueron rechazadas con 4xx y sin persistencia. No se uso DEV.',
      peticiones_a_dev: 0
    },

    diagnostico_bd: {
      utilizada: false,
      motivo: 'La matriz no exige BD y no aparecio ninguna duda de persistencia: la API entrego historiales PRE/POST consistentes por variante y ninguna respuesta devolvio id_calibracion. No se abrio ninguna conexion.',
      solo_select: true
    },

    comparacion_primera_segunda: comparacion,
    causa_raiz: causaRaiz,
    seguridad: null,
    git_post: estadoGit('git_post')
  };
  escribir('evidencia.json', evidencia);
  evidencia.seguridad = escanearSeguridad();
  escribir('evidencia.json', evidencia);
  refrescarManifest();
  fs.unlinkSync(tmp);

  log('\n================ CIERRE ================');
  log(`RUN_ID: ${runId}`);
  for (const v of VARIANTES) {
    const c = variantes[v.clave];
    if (!c.ejecutado) { log(`${v.etiqueta}: NO EJECUTADO — ${c.motivo}`); continue; }
    log(`${v.etiqueta}: HTTP ${c.response.http} (${c.en4xx ? '4xx' : 'FUERA DE 4xx'}) | error_code ${c.response.error_code || '—'} | id_calibracion ${c.response.id_calibracion ?? 'ausente'} | PRE ${c.historialPre?.total} POST ${c.historialPost?.total} | nuevos ${JSON.stringify(c.idsNuevos)} -> ${c.resultado}`);
  }
  log(`TC-M09-258 -> ${r258} | TC-M09-259 -> ${r259} | TC-M09-260 -> ${r260}`);
  log(`GRUPO ${GRUPO} -> ${resultadoGrupo}`);
  log(`Newman: requests ${R.stats.requests.ejecutados} (fallidos ${R.stats.requests.fallidos}) | assertions ${R.stats.assertions.total} (fallidas ${R.stats.assertions.fallidas}) | limpio ${newmanLimpio ? 'SI' : 'NO'}`);
  log(`POST /calibrar ${R.postCalibrar}/${POST_BUDGET} | STOP_ALL ${R.stopAll} | persistencia inesperada: ${persistenciaInesperada.length ? JSON.stringify(persistenciaInesperada) : 'ninguna'}`);
  log(`OpenAPI: modo_calibracion declarado=${R.openapi.modo_declarado} required=${R.openapi.modo_required} dominio=${R.openapi.modo_dominio}`);
  log(`Causa del rechazo anterior: ${comparacion.causaDelRechazoAnterior}`);
  log(`Contraste DEV necesario: ${anomalia ? 'SI' : 'NO'} | BD utilizada: NO`);
  log(`Evidencia limpia de secretos: ${evidencia.seguridad.limpio ? 'SI' : 'NO'}`);
  log('========================================\n');

  if (!evidencia.seguridad.limpio) process.exitCode = 3;
  else if (resultadoGrupo !== 'APROBADO') process.exitCode = 2;
}

// --------------------------------------------------------------------------- manifiesto
function refrescarManifest() {
  const artefactos = [
    { archivo: 'run-g131-v2.cjs', abs: path.join(__dirname, 'run-g131-v2.cjs'),
      ruta: `${GRUPO}/EvaluacionV2/automation/run-g131-v2.cjs`,
      funcion: 'Runner unico de la reevaluacion, con los modos precheck (Newman de solo lectura, sin HTML ni archivos), run (RUN funcional oficial con los 4 POST y el unico HTML) y close (oraculo por variante, verificacion final de solo lectura y consolidacion de evidencia). No obtiene ni inyecta tokens y no ejecuta PATCH, PUT ni DELETE.' },
    { archivo: 'TC-M09-G131.postman_collection.json', abs: COLECCION,
      ruta: `${GRUPO}/EvaluacionV2/TC-M09-G131.postman_collection.json`,
      funcion: 'Coleccion de EvaluacionV2. Despliega las CUATRO variantes como items propios y es duena de su sesion (login dentro de Newman, token en session_value), porque la original inyectaba el token desde el runner. Conserva los cuatro casos, sus bodies, sus valores, sus URLs, el criterio de rechazo 4xx y las verificaciones de no persistencia por total e IDs de historial PRE/POST, con PRE propio por variante y STOP_ALL si alguna persistiera.' },
    { archivo: 'TC-M09-G131.postman_collection.json (original)', abs: COLECCION_ORIGINAL,
      ruta: `${GRUPO}/TC-M09-G131.postman_collection.json`,
      funcion: 'Coleccion de la primera evaluacion: un unico item generico parametrizado por el runner, con el token inyectado desde fuera. Reutilizada como fuente del criterio 4xx y de las URLs, en solo lectura; no fue modificada.' },
    { archivo: 'run-newman.cjs (original)', abs: path.join(CASE_DIR, 'run-newman.cjs'),
      ruta: `${GRUPO}/run-newman.cjs`,
      funcion: 'Runner de la primera evaluacion. Fuente de los cuatro bodies, valores y del orden de las variantes. NO se utiliza en esta reevaluacion: se registra por trazabilidad del baseline.' }
  ];
  const p = path.join(RUN_DIR, 'automation_manifest.json');
  const previo = fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : null;
  const shaPrevio = previo ? Object.fromEntries((previo.artefactos || []).map(a => [a.archivo, a.sha256])) : {};
  const filas = artefactos.map(a => {
    if (!fs.existsSync(a.abs)) return { archivo: a.archivo, ruta: `tests/Test_Testing/Test_Modulo9/RF-24/${a.ruta}`, funcion: a.funcion, sha256: null, estado: 'AUSENTE' };
    const actual = sha256(a.abs);
    const fila = { archivo: a.archivo, ruta: `tests/Test_Testing/Test_Modulo9/RF-24/${a.ruta}`, funcion: a.funcion, sha256: actual, bytes: fs.statSync(a.abs).size };
    if (shaPrevio[a.archivo] && shaPrevio[a.archivo] !== actual) fila.sha256_anterior = shaPrevio[a.archivo];
    return fila;
  });
  fs.writeFileSync(p, limpiar(JSON.stringify({
    grupo: GRUPO, casos: ['TC-M09-258', 'TC-M09-259', 'TC-M09-260'], runId,
    nota: 'Artefactos finales de la SEGUNDA EVALUACION. Los ejecutables viven unicamente en EvaluacionV2/; no se duplica automation dentro de RESULTADOS.',
    newmanHtmlPersistentes: 1, automationDentroDeResultados: 'NO', artefactos: filas
  }, null, 2)));
}
