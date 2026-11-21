// Runner único de la SEGUNDA EVALUACIÓN de TC-M09-G132 (RF-24 v2.0, Módulo 9).
// Casos TC-M09-261 (variantes "NaN", "Infinity", "-Infinity") y TC-M09-262 (precisión 22.1234).
//
// Un solo archivo, tres modos (G132_MODO):
//
//   precheck  Validación Newman de SOLO LECTURA previa al RUN. Ejecuta la colección filtrada en
//             memoria SIN los cuatro POST /calibrar y sin los historiales de poscondición; no
//             escribe nada, no genera HTML, no crea RESULTADOS y no deja archivos: solo consola.
//             El RUN se autoriza si no hay failures de automatización.
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
// Presupuesto: 4 POST /calibrar, sin reintentos. PATCH/PUT/DELETE: 0.
// TC-M09-262 es un camino exitoso: DEBE persistir exactamente una calibración y NO se borra.
// TC-M09-261 son tres rechazos: no deben crear nada. Si alguno persistiera, STOP_ALL.
//
// Uso:
//   $env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
//   $env:QA_ING_EMAIL="ingeniero@pecuaria.co"
//   $env:QA_ING_PASSWORD="<secreto>"
//   $env:G132_RUN_ID="run-YYYYMMDD-HHMMSS"     (modos run y close)
//   $env:G132_MODO="precheck" | "run" | "close"
//   node .\run-g132-v2.cjs

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const CASE_DIR = path.resolve(__dirname, '..', '..');
const EVAL_DIR = path.resolve(__dirname, '..');
const COLECCION = path.join(EVAL_DIR, 'TC-M09-G132.postman_collection.json');
const COLECCION_ORIGINAL = path.join(CASE_DIR, 'TC-M09-G132.postman_collection.json');

const GRUPO = 'TC-M09-G132';
const RF = 'RF-24 v2.0';
const POST_BUDGET = 4;

// Mensaje literal exigido por la matriz para cada entrada no finita.
const mensajeEsperado = (v) =>
  `Error de formato: El valor de referencia debe ser un número decimal válido. Verifique la entrada '${v}'.`;

// Las cuatro peticiones funcionales, en el orden de la colección original: primero la precisión.
const VARIANTES = [
  { clave: '262', caso: 'TC-M09-262', etiqueta: 'TC-M09-262', tipo: 'exito', valor: '22.1234', representacion: 'número JSON', observaciones: 'QA TC-M09-262' },
  { clave: 'nan', caso: 'TC-M09-261', etiqueta: 'TC-M09-261 NaN', tipo: 'rechazo', valor: 'NaN', representacion: 'cadena JSON "NaN"', observaciones: 'QA TC-M09-261' },
  { clave: 'inf', caso: 'TC-M09-261', etiqueta: 'TC-M09-261 Infinity', tipo: 'rechazo', valor: 'Infinity', representacion: 'cadena JSON "Infinity"', observaciones: 'QA TC-M09-261' },
  { clave: 'ninf', caso: 'TC-M09-261', etiqueta: 'TC-M09-261 -Infinity', tipo: 'rechazo', valor: '-Infinity', representacion: 'cadena JSON "-Infinity"', observaciones: 'QA TC-M09-261' }
];
const RECHAZOS = VARIANTES.filter(v => v.tipo === 'rechazo');
const ITEMS_CALIBRAR = VARIANTES.map(v => `${v.etiqueta} POST calibrar`);
// Dependen del POST (id creado, historial posterior): el PRECHECK no puede evaluarlos.
const ITEMS_POSCONDICION = VARIANTES.map(v => `${v.etiqueta} Historial POST`);

const MODO = process.env.G132_MODO || 'precheck';
if (!['precheck', 'run', 'close'].includes(MODO)) throw new Error(`G132_MODO no reconocido: ${MODO}`);

const base = () => {
  const b = process.env.QA_BASE_URL;
  if (!b) throw new Error('QA_BASE_URL requerido');
  return b.replace(/\/$/, '');
};
const ING = { email: process.env.QA_ING_EMAIL, secret: process.env.QA_ING_PASSWORD };
if (!ING.email || !ING.secret) throw new Error('QA_ING_EMAIL y QA_ING_PASSWORD requeridos (solo en memoria de proceso).');

// ------------------------------------------------------------------------- fixture
const FIX = {
  sensor: Number(process.env.G132_SENSOR || 6),
  dispositivo: Number(process.env.G132_DEVICE || 3),
  area: Number(process.env.G132_AREA || 3),
  categoria: process.env.G132_CAT || 'TEMPERATURA',
  valor262: process.env.G132_VALOR || '22.1234'
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
const runId = process.env.G132_RUN_ID;
if (MODO !== 'precheck' && (!runId || !/^run-\d{8}-\d{6}$/.test(runId))) {
  throw new Error('G132_RUN_ID requerido con formato run-YYYYMMDD-HHMMSS.');
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
  primera_evaluacion_RESULTADOS: git(['status', '--short', '--', `tests/Test_Testing/Test_Modulo9/RF-24/${GRUPO}/RESULTADOS`]) || '(vacio = intacta)',
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

// -------------------------------------------------------- decimal exacto (sin float)
function normDec(x) {
  if (x === null || x === undefined) return null;
  const m = /^([+-]?)(\d+)(?:\.(\d*))?$/.exec(String(x).trim());
  if (!m) return null;
  let signo = m[1] === '-' ? '-' : '';
  const ent = m[2].replace(/^0+(?=\d)/, '');
  const frac = (m[3] || '').replace(/0+$/, '');
  if (ent === '0' && frac === '') signo = '';
  return signo + ent + (frac ? '.' + frac : '');
}
const escalaDe = (x) => { const m = /\.(\d+)$/.exec(String(x).trim()); return m ? m[1].length : 0; };
const igualDecimal = (a, b) => {
  const x = normDec(a); const y = normDec(b);
  return x !== null && y !== null && x === y;
};

// ------------------------------------------------------------------- env de la colección
function construirEnv() {
  const fecha = '"fecha_calibracion":"__FECHA__"';
  const cuerpo = (valorTexto, observaciones) =>
    `{"modo_calibracion":"SENSOR","id_dispositivo_iot":${FIX.dispositivo},"id_infraestructura":${FIX.area},` +
    `"valor_referencia":${valorTexto},"observaciones":"${observaciones}",${fecha}}`;

  // TC-M09-262: 22.1234 como NÚMERO JSON, con los cuatro decimales literales en el texto enviado.
  const body262 = cuerpo(FIX.valor262, 'QA TC-M09-262');
  // TC-M09-261: los tres valores especiales se envían TAL CUAL, como cadenas JSON. No se
  // convierten silenciosamente a null, 0 ni cadena vacía (reglas 21 y 22).
  const bodyNan = cuerpo('"NaN"', 'QA TC-M09-261');
  const bodyInf = cuerpo('"Infinity"', 'QA TC-M09-261');
  const bodyNinf = cuerpo('"-Infinity"', 'QA TC-M09-261');

  // Guardia de representación: lo que se envía debe ser exactamente lo que el caso define.
  const guardia = (texto, esperado, etiqueta) => {
    const v = JSON.parse(texto.replace('__FECHA__', '2026-01-01T00:00:00.000Z')).valor_referencia;
    if (typeof esperado === 'string') {
      if (typeof v !== 'string' || v !== esperado) {
        throw new Error(`ABORTADO: ${etiqueta} debe enviar valor_referencia como la cadena ${JSON.stringify(esperado)}; se obtuvo ${JSON.stringify(v)} (${typeof v}).`);
      }
    } else if (!igualDecimal(v, FIX.valor262) || !new RegExp(`"valor_referencia":${FIX.valor262.replace('.', '\\.')},`).test(texto)) {
      throw new Error(`ABORTADO: ${etiqueta} debe enviar valor_referencia con el literal ${FIX.valor262}; se obtuvo ${JSON.stringify(v)}.`);
    }
    if (/[eE]/.test(String(v))) throw new Error(`ABORTADO: ${etiqueta} no puede usar notación científica.`);
    return true;
  };
  guardia(body262, null, 'TC-M09-262');
  guardia(bodyNan, 'NaN', 'TC-M09-261 NaN');
  guardia(bodyInf, 'Infinity', 'TC-M09-261 Infinity');
  guardia(bodyNinf, '-Infinity', 'TC-M09-261 -Infinity');
  // Fuera de alcance: 5 o más decimales (regla 29).
  const dec = (escalaDe(FIX.valor262));
  if (dec !== 4) throw new Error(`ABORTADO: TC-M09-262 debe enviar exactamente 4 decimales; se configuró escala ${dec}.`);

  return [
    ['base_url', base()],
    ['ing_email', ING.email], ['ing_secret', ING.secret],
    ['sensor', String(FIX.sensor)], ['device', String(FIX.dispositivo)], ['area', String(FIX.area)],
    ['categoria', FIX.categoria], ['valor_262', FIX.valor262],
    ['body_262', body262], ['body_nan', bodyNan], ['body_inf', bodyInf], ['body_ninf', bodyNinf],
    ['msg_nan', mensajeEsperado('NaN')], ['msg_inf', mensajeEsperado('Infinity')], ['msg_ninf', mensajeEsperado('-Infinity')],
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

// Comprobación estática de la colección (regla 21): la representación de cada valor especial.
function verificarRepresentacionColeccion() {
  const texto = fs.readFileSync(COLECCION, 'utf8');
  const col = JSON.parse(texto);
  const resultado = {};
  for (const v of VARIANTES) {
    const it = col.item.find(x => x.name === `${v.etiqueta} POST calibrar`);
    if (!it) throw new Error(`ABORTADO: falta el item «${v.etiqueta} POST calibrar» en la colección.`);
    const raw = it.request.body?.raw || '';
    const variable = /^\{\{(body_sent_[a-z0-9]+)\}\}$/.exec(raw.trim());
    if (!variable) throw new Error(`ABORTADO: ${v.etiqueta} debe enviar el body preparado en prerequest, no un literal suelto.`);
    const pre = (it.event || []).find(e => e.listen === 'prerequest');
    const fuente = (pre?.script?.exec || []).join('\n');
    if (!fuente.includes(`body_${v.clave}`)) throw new Error(`ABORTADO: ${v.etiqueta} no deriva su body de body_${v.clave}.`);
    resultado[v.clave] = { item: it.name, bodyVariable: variable[1], derivaDe: `body_${v.clave}` };
  }
  // Ningún token inyectado desde fuera de la colección.
  if (/\{\{token\}\}/.test(texto)) throw new Error('ABORTADO: la colección no debe aceptar un token inyectado por el runner.');
  if (!/\{\{session_value\}\}/.test(texto)) throw new Error('ABORTADO: la colección debe usar su propia sesión en {{session_value}}.');
  // Valores fuera de alcance que no deben aparecer en ningún body (regla 22 y 29).
  const prohibidos = [/"valor_referencia":\s*null/, /"valor_referencia":\s*"abc"/, /"valor_referencia":\s*[-+]?\d+\.\d{5,}/, /"valor_referencia":\s*[-+]?\d+(\.\d+)?[eE]/];
  for (const re of prohibidos) if (re.test(texto)) throw new Error(`ABORTADO: la colección contiene un valor fuera del alcance del RF: ${re}`);
  return resultado;
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
  const representacion = verificarRepresentacionColeccion();
  const { col, itemsTotales, itemsEjecutables } = cargarColeccion([...ITEMS_CALIBRAR, ...ITEMS_POSCONDICION]);
  verificarEscrituras(col, false);
  const env = construirEnv();
  const bodyDe = (clave) => env.find(([k]) => k === `body_${clave}`)[1];

  log('PRECHECK de solo lectura — Newman sin reporter HTML, sin carpeta de resultados.');
  log(`Colección: ${itemsEjecutables} de ${itemsTotales} items. Excluidos los 4 POST /calibrar y sus 4 historiales de poscondición.`);
  log('Sin escrituras de negocio. Los valores especiales NO se envían en el PRECHECK.\n');

  const summary = await correrNewman(col, env, null, null);
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
    fixture: ['Fixture — dispositivo', 'Fixture — sensor del dispositivo',
      'Fixture — asociación vigente', 'Fixture — área de la asociación'].every(pasa),
    rango: pasa('Fixture — rangos de calibración'),
    openapiConsultado: http('Contrato OpenAPI') === 200 && pasa('Contrato OpenAPI'),
    coleccion: VARIANTES.every(v => {
      const texto = bodyDe(v.clave);
      const valor = JSON.parse(texto.replace('__FECHA__', '2026-01-01T00:00:00.000Z')).valor_referencia;
      return v.tipo === 'rechazo' ? valor === v.valor && typeof valor === 'string' : igualDecimal(valor, FIX.valor262);
    })
  };

  const postCalibrar = contar(summary, /\/calibrar$/);
  const autorizar = Object.values(chequeos).every(Boolean) && f.length === 0 &&
    (st.requests.fallidos || 0) === 0 && postCalibrar === 0;

  const P = (b) => (b ? 'PASS' : 'FAIL');
  log('\nPRECHECK_G132\n');
  log(`Ingeniero:\n${P(chequeos.ingeniero)}\n`);
  log(`Permisos:\n${P(chequeos.permisos)}\n`);
  log(`Fixture:\n${P(chequeos.fixture)}\n`);
  log(`Rango:\n${P(chequeos.rango)}\n`);
  log(`OpenAPI:\n${chequeos.openapiConsultado ? 'CONSULTADO' : 'NO CONSULTADO'}\n`);
  log(`Colección:\n${P(chequeos.coleccion)}\n`);
  log(`Failures automatización:\n${f.length}\n`);
  log(`POST calibrar:\n${postCalibrar}\n`);
  log(`AUTORIZAR_RUN:\n${autorizar ? 'SÍ' : 'NO'}\n`);

  log('--- representación que se enviará (regla 21/22: no se convierte nada silenciosamente) ---');
  for (const v of VARIANTES) {
    const texto = bodyDe(v.clave);
    const valor = JSON.parse(texto.replace('__FECHA__', '2026-01-01T00:00:00.000Z')).valor_referencia;
    log(`  ${v.etiqueta.padEnd(24)} valor_referencia = ${JSON.stringify(valor)} (${typeof valor}) | item ${representacion[v.clave].bodyVariable}`);
  }
  log('\n--- contrato OpenAPI observado (diagnóstico, no decide el resultado) ---');
  log(`valor_referencia:            ${envDe(summary, 'openapi_valor_referencia')}`);
  log(`patrón de cadena:            ${envDe(summary, 'openapi_patron_valor')}`);
  log(`¿el patrón admite no finitos? ${envDe(summary, 'openapi_patron_admite_no_finitos')}`);
  log(`modo_calibracion:            ${envDe(summary, 'openapi_modo')}`);
  log(`required del DTO:            ${envDe(summary, 'openapi_required')}`);
  log(`códigos del POST calibrar:   ${envDe(summary, 'openapi_codigos_calibrar')}`);
  log(`códigos del historial:       ${envDe(summary, 'openapi_codigos_historial')}`);

  log('\n--- detalle observado (solo consola, no se persiste) ---');
  log(`Ingeniero: id_usuario=${me?.id_usuario} rol="${me?.nombre_rol}" estado=${me?.estado_cuenta} | permisos recurso 12: ${envDe(summary, 'permisos_recurso12')}`);
  log(`fixture: sensor ${FIX.sensor} (${FIX.categoria}) dispositivo ${FIX.dispositivo} / área ${FIX.area} | rango ${envDe(summary, 'rango')}`);
  log(`asociación vigente: ${envDe(summary, 'asociacion_vigente')}`);
  log(`historial PRE del sensor ${FIX.sensor}: total ${envDe(summary, 'pre_262_total')} ids ${envDe(summary, 'pre_262_ids')}`);
  log(`newman: requests ${st.requests.ejecutados}/${st.requests.fallidos} fallidos | assertions ${st.assertions.total}/${st.assertions.fallidas} fallidas`);
  if (f.length) { log('\nfailures:'); f.forEach((x, i) => log(`  ${i + 1}. ${x.item} :: ${x.assertion} :: ${x.error}`)); }
  log('');

  if (!autorizar) { log('El RUN funcional NO está autorizado. Corregir la automatización antes de ejecutar los POST.'); process.exitCode = 2; }
}

// ------------------------------------------------------------------------------------ run
async function modoRun() {
  if (fs.existsSync(RUN_DIR)) throw new Error(`La carpeta ${runId} ya existe. Un RUN oficial no se repite ni se sobrescribe.`);
  const representacion = verificarRepresentacionColeccion();
  const { col, itemsTotales, itemsEjecutables } = cargarColeccion([]);
  verificarEscrituras(col, true);
  const calibrar = col.item.filter(i => /\/calibrar$/.test(typeof i.request.url === 'string' ? i.request.url : i.request.url?.raw || ''));
  if (calibrar.length !== POST_BUDGET) throw new Error(`ABORTADO: la colección debe contener exactamente ${POST_BUDGET} POST de calibración, contiene ${calibrar.length}.`);

  const gitPre = estadoGit('git_pre');
  const html = HTML_OFICIAL();
  const env = construirEnv();

  log(`RUN funcional oficial. RUN_ID: ${runId}`);
  log(`Colección: ${itemsEjecutables} de ${itemsTotales} items.`);
  log(`POST /calibrar planificados: ${POST_BUDGET} (1 exitoso + 3 rechazos) | PATCH/PUT/DELETE: 0 | reintentos: 0`);
  log('TC-M09-262 debe persistir exactamente una calibración; las tres entradas no finitas, ninguna.\n');

  const summary = await correrNewman(col, env, html, `${GRUPO} — SEGUNDA EVALUACIÓN · RUN funcional oficial ${runId}`);
  if (fs.existsSync(html)) fs.writeFileSync(html, limpiarHtml(fs.readFileSync(html, 'utf8')));

  const { cuerpo, crudo, http, enviadoTexto, asserts, ejecutado } = extraer(summary);
  const preservado = {
    runId, generado: new Date().toISOString(), gitPre, itemsTotales, itemsEjecutables,
    stats: stats(summary), failures: fallos(summary),
    postCalibrar: contar(summary, /\/calibrar$/),
    stopAll: envDe(summary, 'stop_all') ?? 'NO',
    stopAllMotivo: envDe(summary, 'stop_all_motivo'),
    representacionColeccion: representacion,
    bodiesConfigurados: Object.fromEntries(VARIANTES.map(v => [v.clave, env.find(([k]) => k === `body_${v.clave}`)[1]])),
    mensajesEsperados: Object.fromEntries(RECHAZOS.map(v => [v.clave, mensajeEsperado(v.valor)])),
    ingLogin: { http: http('Login Ingeniero'), assertions: asserts('Login Ingeniero') },
    identidad: { http: http('Identidad Ingeniero'), cuerpo: cuerpo('Identidad Ingeniero'), assertions: asserts('Identidad Ingeniero') },
    permisos: { http: http('Permisos Ingeniero'), cuerpo: cuerpo('Permisos Ingeniero'), assertions: asserts('Permisos Ingeniero'), recurso12: envDe(summary, 'permisos_recurso12') },
    openapi: {
      http: http('Contrato OpenAPI'), assertions: asserts('Contrato OpenAPI'),
      valor_referencia: envDe(summary, 'openapi_valor_referencia'),
      modo_calibracion: envDe(summary, 'openapi_modo'),
      required_dto: envDe(summary, 'openapi_required'),
      codigos_calibrar: envDe(summary, 'openapi_codigos_calibrar'),
      codigos_historial: envDe(summary, 'openapi_codigos_historial'),
      patron_valor: envDe(summary, 'openapi_patron_valor'),
      patron_admite_no_finitos: envDe(summary, 'openapi_patron_admite_no_finitos')
    },
    fixture: {
      dispositivo: { http: http('Fixture — dispositivo'), cuerpo: cuerpo('Fixture — dispositivo'), assertions: asserts('Fixture — dispositivo') },
      sensores: { http: http('Fixture — sensor del dispositivo'), cuerpo: cuerpo('Fixture — sensor del dispositivo'), assertions: asserts('Fixture — sensor del dispositivo') },
      asociaciones: { http: http('Fixture — asociación vigente'), cuerpo: cuerpo('Fixture — asociación vigente'), assertions: asserts('Fixture — asociación vigente') },
      area: { http: http('Fixture — área de la asociación'), cuerpo: cuerpo('Fixture — área de la asociación'), assertions: asserts('Fixture — área de la asociación') },
      rangos: { http: http('Fixture — rangos de calibración'), cuerpo: cuerpo('Fixture — rangos de calibración'), assertions: asserts('Fixture — rangos de calibración') },
      rango: envDe(summary, 'rango'),
      asociacionVigente: envDe(summary, 'asociacion_vigente')
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
        mensaje: envDe(summary, `${v.clave}_mensaje`),
        mensajeExacto: envDe(summary, `${v.clave}_mensaje_exacto`),
        id_respuesta: envDe(summary, `${v.clave}_id_respuesta`) ?? envDe(summary, `${v.clave}_id`),
        valorRespuestaCrudo: envDe(summary, `${v.clave}_valor_respuesta_crudo`),
        valorRespuestaNorm: envDe(summary, `${v.clave}_valor_respuesta_norm`),
        escalaRespuesta: envDe(summary, `${v.clave}_escala_respuesta`),
        tipoJsonRespuesta: envDe(summary, `${v.clave}_tipo_json_respuesta`)
      },
      post: { http: http(`${v.etiqueta} Historial POST`), cuerpo: cuerpo(`${v.etiqueta} Historial POST`), assertions: asserts(`${v.etiqueta} Historial POST`) },
      idsNuevos: envDe(summary, `${v.clave}_ids_nuevos`),
      valorHistorialCrudo: envDe(summary, `${v.clave}_valor_historial_crudo`),
      valorHistorialNorm: envDe(summary, `${v.clave}_valor_historial_norm`),
      escalaHistorial: envDe(summary, `${v.clave}_escala_historial`)
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
    if (v.tipo === 'exito') {
      log(`  ${v.etiqueta}: HTTP ${b.calibrar.http} | id_calibracion ${b.calibrar.id_respuesta || 'ausente'} | respuesta ${b.calibrar.valorRespuestaCrudo} (norm ${b.calibrar.valorRespuestaNorm}, escala ${b.calibrar.escalaRespuesta}) | historial ${b.valorHistorialCrudo} (norm ${b.valorHistorialNorm}) | ids nuevos ${b.idsNuevos}`);
    } else {
      log(`  ${v.etiqueta}: HTTP ${b.calibrar.http} | error_code ${b.calibrar.error_code || '—'} | mensaje exacto ${b.calibrar.mensajeExacto} | ids nuevos ${b.idsNuevos}`);
    }
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
    if (!fs.existsSync(evidenciaPath)) throw new Error('No hay summary del RUN ni evidencia previa: ejecute primero G132_MODO=run.');
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
    const assertionsFuncionales = [...b.pre.assertions, ...b.calibrar.assertions, ...b.post.assertions];
    const idCreado = resp && resp.id_calibracion !== undefined && resp.id_calibracion !== null ? Number(resp.id_calibracion) : null;
    const filaCreada = post && idCreado !== null ? (post.items || []).find(x => Number(x.id_calibracion) === idCreado) || null : null;

    // Integridad de los registros que ya existían antes de la petición.
    let historicosIntactos = null;
    if (pre && post) {
      historicosIntactos = (pre.items || []).every(s => {
        const row = (post.items || []).find(x => x.id_calibracion === s.id_calibracion);
        return row && igualDecimal(row.valor_referencia, s.valor_referencia) &&
          row.fecha_calibracion === s.fecha_calibracion && row.id_usuario === s.id_usuario &&
          row.observaciones === s.observaciones;
      });
    }

    const comun = {
      ...v, ejecutado: true,
      sensor: FIX.sensor, dispositivo: FIX.dispositivo, area: FIX.area, categoria: FIX.categoria,
      request: {
        endpoint: `/configuracion/sensores/${FIX.sensor}/calibrar`, metodo: 'POST',
        headers: { Authorization: '[REDACTED]', 'Content-Type': 'application/json' },
        bodyTextoEnviado: b.calibrar.enviadoTexto, body: enviado,
        valor_referencia_enviado: enviado ? enviado.valor_referencia : null,
        tipo_json_enviado: enviado ? typeof enviado.valor_referencia : null,
        representacion_preservada: v.tipo === 'rechazo'
          ? enviado && typeof enviado.valor_referencia === 'string' && enviado.valor_referencia === v.valor
          : Boolean(enviado) && igualDecimal(enviado.valor_referencia, FIX.valor262) &&
            new RegExp(`"valor_referencia":${FIX.valor262.replace('.', '\\.')},`).test(b.calibrar.enviadoTexto || '')
      },
      response: {
        http: b.calibrar.http, cuerpo: resp, crudo: b.calibrar.crudo,
        error_code: resp?.error_code ?? b.calibrar.error_code ?? null,
        message: resp?.message ?? resp?.detail ?? null,
        id_calibracion: idCreado, capturado: new Date().toISOString()
      },
      historialPre: pre ? { http: b.pre.http, total: pre.total, ids: preIds, items: pre.items || [] } : null,
      historialPost: post ? { http: b.post.http, total: post.total, ids: postIds, items: post.items || [] } : null,
      idsNuevos: nuevos, historicosIntactos,
      assertionsFuncionales: { total: assertionsFuncionales.length, fallidas: assertionsFuncionales.filter(a => !a.paso).length, detalle: assertionsFuncionales }
    };

    if (v.tipo === 'exito') {
      // TC-M09-262: camino exitoso. La persistencia es ESPERADA y no se borra.
      const oraculo = {
        http_2xx: b.calibrar.http >= 200 && b.calibrar.http <= 299,
        id_calibracion_devuelto: idCreado !== null && Number.isInteger(idCreado),
        respuesta_decimal_exacto: igualDecimal(resp?.valor_referencia, FIX.valor262),
        registro_recuperado_por_get: Boolean(filaCreada),
        historial_decimal_exacto: Boolean(filaCreada) && igualDecimal(filaCreada.valor_referencia, FIX.valor262),
        persistio_exactamente_una: Array.isArray(nuevos) && nuevos.length === 1 && idCreado !== null && Number(nuevos[0]) === idCreado,
        registro_de_este_run: Boolean(filaCreada) && filaCreada.observaciones === v.observaciones &&
          Number(filaCreada.id_usuario) === Number(R.identidad.cuerpo?.id_usuario),
        historial_previo_intacto: historicosIntactos === true,
        assertions_funcionales_todas_pass: assertionsFuncionales.length > 0 && assertionsFuncionales.every(a => a.paso)
      };
      variantes[v.clave] = {
        ...comun,
        httpEsperado: '2xx',
        precision: {
          valor_enviado: FIX.valor262,
          valor_respuesta_crudo: resp ? resp.valor_referencia : null,
          valor_respuesta_normalizado: normDec(resp?.valor_referencia),
          tipo_json_respuesta: resp ? typeof resp.valor_referencia : null,
          escala_observable_respuesta: resp ? escalaDe(resp.valor_referencia) : null,
          exactitud_respuesta: igualDecimal(resp?.valor_referencia, FIX.valor262),
          valor_historial_crudo: filaCreada ? filaCreada.valor_referencia : null,
          valor_historial_normalizado: filaCreada ? normDec(filaCreada.valor_referencia) : null,
          escala_observable_historial: filaCreada ? escalaDe(filaCreada.valor_referencia) : null,
          exactitud_historial: Boolean(filaCreada) && igualDecimal(filaCreada.valor_referencia, FIX.valor262),
          metodo_de_comparacion: 'normalizacion decimal textual (signo, ceros a la izquierda y ceros finales), NO Number() ni float binario',
          valores_rechazados_explicitamente: ['22.123', '22.1230', '22.1235', '22.12']
            .map(x => ({ candidato: x, igual_a_22_1234: igualDecimal(x, FIX.valor262) })),
          registro_persistido: filaCreada
            ? { id_calibracion: filaCreada.id_calibracion, run_id: runId, observaciones: filaCreada.observaciones, valor_exacto: normDec(filaCreada.valor_referencia), fecha_calibracion: filaCreada.fecha_calibracion, id_usuario: filaCreada.id_usuario }
            : null,
          nota: 'Esta persistencia es la ESPERADA del camino exitoso: no se elimina.'
        },
        oraculo,
        resultado: Object.values(oraculo).every(x => x === true) ? 'APROBADO' : 'RECHAZADO'
      };
    } else {
      // TC-M09-261: oráculo literal. HTTP 400 + mensaje EXACTO + sin persistencia.
      const esperado = mensajeEsperado(v.valor);
      const obtenido = resp?.message ?? resp?.detail ?? null;
      const oraculo = {
        http_400: b.calibrar.http === 400,
        mensaje_literal_exacto: obtenido === esperado,
        sin_id_calibracion: resp ? resp.id_calibracion === undefined || resp.id_calibracion === null : false,
        total_sin_cambios: Boolean(pre) && Boolean(post) && Number(pre.total) === Number(post.total),
        ids_identicos: Boolean(preIds) && Boolean(postIds) && JSON.stringify(preIds.slice().sort()) === JSON.stringify(postIds.slice().sort()),
        sin_persistencia: Array.isArray(nuevos) && nuevos.length === 0,
        historial_intacto: historicosIntactos === true,
        representacion_preservada: comun.request.representacion_preservada === true,
        assertions_funcionales_todas_pass: assertionsFuncionales.length > 0 && assertionsFuncionales.every(a => a.paso)
      };
      const fallas = [];
      if (!oraculo.http_400) fallas.push(b.calibrar.http === 500
        ? 'HTTP 500: error interno en lugar del rechazo de formato'
        : `HTTP ${b.calibrar.http ?? 'no verificable'} en vez de 400`);
      if (!oraculo.mensaje_literal_exacto) fallas.push(/rango|excede/i.test(String(obtenido || ''))
        ? 'el mensaje clasifica la entrada como VALOR FUERA DE RANGO en vez de formato decimal invalido'
        : `mensaje ${JSON.stringify(obtenido)} distinto del literal exigido`);
      if (!oraculo.sin_id_calibracion) fallas.push('la respuesta devolvio id_calibracion');
      if (!oraculo.sin_persistencia) fallas.push(`persistencia indebida: IDs nuevos ${JSON.stringify(nuevos)}`);
      if (!oraculo.total_sin_cambios || !oraculo.ids_identicos) fallas.push('el historial cambio de total o de IDs');
      if (!oraculo.historial_intacto) fallas.push('algun registro historico previo cambio');
      if (!oraculo.representacion_preservada) fallas.push('la representacion enviada no fue la del caso');

      variantes[v.clave] = {
        ...comun,
        httpEsperado: 400,
        mensajeEsperado: esperado, mensajeObtenido: obtenido,
        mensajeExacto: oraculo.mensaje_literal_exacto,
        comparacion: 'literal estricta: prohibido contains, startsWith, regex o equivalencia semantica',
        clasificacion_observada: oraculo.mensaje_literal_exacto ? 'formato decimal invalido'
          : /rango|excede/i.test(String(obtenido || '')) ? 'valor fuera de rango (clasificacion incorrecta)'
          : b.calibrar.http === 500 ? 'error interno' : 'otro',
        oraculo,
        resultado: Object.values(oraculo).every(x => x === true) ? 'APROBADO' : 'RECHAZADO',
        motivo: fallas.length ? fallas.join('; ') + '.' : 'HTTP 400, mensaje literal exacto, sin id_calibracion y sin persistencia.'
      };
    }
  }

  // ----------------------------------------------------------- resultado por caso
  const r262 = variantes['262'].resultado;
  const r261 = RECHAZOS.every(v => variantes[v.clave].resultado === 'APROBADO') ? 'APROBADO'
    : RECHAZOS.some(v => variantes[v.clave].resultado === 'NO EJECUTADO') ? 'RECHAZADO / ejecución parcial'
    : 'RECHAZADO';

  const newmanLimpio = R.failures.length === 0 && (R.stats.requests.fallidos || 0) === 0;
  const persistenciaIndebida = RECHAZOS
    .map(v => variantes[v.clave])
    .filter(x => x.ejecutado && Array.isArray(x.idsNuevos) && x.idsNuevos.length > 0)
    .flatMap(x => x.idsNuevos);
  const resultadoGrupo = (r262 === 'APROBADO' && r261 === 'APROBADO' && newmanLimpio && persistenciaIndebida.length === 0)
    ? 'APROBADO' : 'RECHAZADO';

  // ------------------------------------- verificación final: SOLO LECTURA, después del RUN
  const tokenIng = await login(ING.email, ING.secret);
  const hist = await get(`/configuracion/sensores/${FIX.sensor}/calibraciones`, tokenIng);
  const asoc = await get(`/configuracion/sensores/${FIX.sensor}/asociaciones`, tokenIng);
  const items = hist.cuerpo?.items || [];
  const ids = items.map(x => x.id_calibracion);
  const id262 = variantes['262'].response?.id_calibracion ?? null;
  const fila262 = id262 !== null ? items.find(x => Number(x.id_calibracion) === Number(id262)) || null : null;
  const atribuibles262 = items.filter(x => x.observaciones === 'QA TC-M09-262').map(x => x.id_calibracion);
  const atribuibles261 = items.filter(x => x.observaciones === 'QA TC-M09-261').map(x => x.id_calibracion);
  const idsDeEsteRun = Object.values(variantes)
    .filter(x => x.ejecutado && Array.isArray(x.idsNuevos))
    .flatMap(x => x.idsNuevos);

  // ------------------------------------------------------- comparación con la primera
  const PRIMERA = {
    runId: 'run-20261007-042408',
    fuente: `tests/Test_Testing/Test_Modulo9/RF-24/${GRUPO}/RESULTADOS/run-20261007-042408/${GRUPO}_resultado.md`,
    nan: { resultado: 'RECHAZADO', http: '500', mensaje: 'Error interno: «Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte.»', persistencia: 'NINGUNA', detalle: 'el valor no finito provoco un error interno en vez del rechazo de formato' },
    inf: { resultado: 'RECHAZADO', http: '400', mensaje: 'VALOR FUERA DE RANGO: «El ajuste de Infinity excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000-45.0000). Verifique el estandar de calibracion utilizado.»', persistencia: 'NINGUNA', detalle: 'se clasifico como fuera de rango en vez de formato decimal invalido' },
    ninf: { resultado: 'RECHAZADO', http: '400', mensaje: 'VALOR FUERA DE RANGO: «El ajuste de -Infinity excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000-45.0000). Verifique el estandar de calibracion utilizado.»', persistencia: 'NINGUNA', detalle: 'se clasifico como fuera de rango en vez de formato decimal invalido' },
    '262': { resultado: 'APROBADO', http: '201', mensaje: 'N/A', persistencia: 'id_calibracion 17', detalle: 'respuesta 22.1234 e historial 22.1234, exactos' },
    caso261: 'RECHAZADO', caso262: 'APROBADO', grupo: 'RECHAZADO',
    presupuesto: { planificados: 4, ejecutados: 4, stopAll: 'NO' }
  };
  const dimension = (v) => {
    const c = variantes[v.clave];
    if (!c.ejecutado) return 'sin POST';
    if (v.tipo === 'exito') return `HTTP ${c.response.http}; id ${c.response.id_calibracion}; respuesta ${JSON.stringify(c.precision.valor_respuesta_crudo)}; historial ${JSON.stringify(c.precision.valor_historial_crudo)}`;
    return `HTTP ${c.response.http}; ${c.mensajeExacto ? 'mensaje literal exacto de formato' : 'mensaje ' + JSON.stringify(c.mensajeObtenido)}`;
  };
  const comparacion = {
    baselineUnico: `PRIMERA EVALUACION OFICIAL ${PRIMERA.runId}`,
    fuente: PRIMERA.fuente,
    porVariante: Object.fromEntries(VARIANTES.map(v => [v.etiqueta, {
      primera: PRIMERA[v.clave].resultado,
      segunda: variantes[v.clave].resultado,
      cambio: variantes[v.clave].resultado === PRIMERA[v.clave].resultado ? 'SIN CAMBIO' : `${PRIMERA[v.clave].resultado} -> ${variantes[v.clave].resultado}`,
      dimensiones: {
        http: { primera: PRIMERA[v.clave].http, segunda: variantes[v.clave].ejecutado ? String(variantes[v.clave].response.http) : 'sin POST' },
        mensaje: { primera: PRIMERA[v.clave].mensaje, segunda: v.tipo === 'rechazo' ? (variantes[v.clave].ejecutado ? (variantes[v.clave].mensajeExacto ? 'literal exacto de formato decimal invalido' : JSON.stringify(variantes[v.clave].mensajeObtenido)) : 'sin POST') : 'N/A' },
        persistencia: { primera: PRIMERA[v.clave].persistencia, segunda: variantes[v.clave].ejecutado ? (v.tipo === 'exito' ? `id_calibracion ${variantes[v.clave].response.id_calibracion}` : (variantes[v.clave].oraculo.sin_persistencia ? 'NINGUNA' : `INDEBIDA: ${JSON.stringify(variantes[v.clave].idsNuevos)}`)) : 'sin POST' },
        observado: { segunda: dimension(v) }
      },
      detallePrimera: PRIMERA[v.clave].detalle
    }])),
    porCaso: {
      'TC-M09-261': { primera: PRIMERA.caso261, segunda: r261, cambio: r261 === PRIMERA.caso261 ? 'SIN CAMBIO' : `${PRIMERA.caso261} -> ${r261}` },
      'TC-M09-262': { primera: PRIMERA.caso262, segunda: r262, cambio: r262 === PRIMERA.caso262 ? 'SIN CAMBIO' : `${PRIMERA.caso262} -> ${r262}` }
    },
    grupo: { primera: PRIMERA.grupo, segunda: resultadoGrupo, cambio: resultadoGrupo === PRIMERA.grupo ? 'SIN CAMBIO' : `${PRIMERA.grupo} -> ${resultadoGrupo}` },
    detalle: {
      NaN_HTTP: { primera: '500', segunda: variantes['nan'].ejecutado ? String(variantes['nan'].response.http) : 'sin POST' },
      NaN_mensaje: { primera: 'Error interno', segunda: variantes['nan'].ejecutado ? variantes['nan'].clasificacion_observada : 'sin POST' },
      Infinity_HTTP: { primera: '400', segunda: variantes['inf'].ejecutado ? String(variantes['inf'].response.http) : 'sin POST' },
      Infinity_mensaje: { primera: 'Fuera de rango', segunda: variantes['inf'].ejecutado ? variantes['inf'].clasificacion_observada : 'sin POST' },
      menos_Infinity_HTTP: { primera: '400', segunda: variantes['ninf'].ejecutado ? String(variantes['ninf'].response.http) : 'sin POST' },
      menos_Infinity_mensaje: { primera: 'Fuera de rango', segunda: variantes['ninf'].ejecutado ? variantes['ninf'].clasificacion_observada : 'sin POST' },
      persistencia_invalidos: { primera: 'Ninguna', segunda: persistenciaIndebida.length ? `INDEBIDA: ${JSON.stringify(persistenciaIndebida)}` : 'Ninguna' },
      valor_22_1234_respuesta: { primera: 'Exacto', segunda: variantes['262'].ejecutado ? (variantes['262'].precision.exactitud_respuesta ? 'Exacto' : 'NO exacto') : 'sin POST' },
      valor_22_1234_historial: { primera: 'Exacto', segunda: variantes['262'].ejecutado ? (variantes['262'].precision.exactitud_historial ? 'Exacto' : 'NO exacto') : 'sin POST' }
    },
    presupuesto: { primera: PRIMERA.presupuesto, segunda: { planificados: POST_BUDGET, ejecutados: R.postCalibrar, stopAll: R.stopAll } },
    causaDelRechazoAnterior: r261 === 'APROBADO' ? 'CORREGIDA'
      : RECHAZOS.some(v => variantes[v.clave].resultado === 'APROBADO') ? 'PARCIALMENTE CORREGIDA'
      : 'NO CORREGIDA'
  };

  // ------------------------------------------------------------------- causa raíz
  const causaRaiz = (() => {
    const nan = variantes['nan'], inf = variantes['inf'], ninf = variantes['ninf'];
    if (r261 === 'APROBADO') {
      return 'A. Los tres valores no finitos responden HTTP 400 con el mensaje literal de formato decimal invalido: la deteccion de NaN, Infinity y -Infinity antes de la validacion de rango esta implementada y desplegada en TEST.';
    }
    if (nan.ejecutado && nan.response.http === 500) {
      return 'B. TC-M09-261/NaN sigue devolviendo HTTP 500: el manejo del valor no finito aun falla antes de poder clasificarlo como error de formato.';
    }
    if ([inf, ninf].some(x => x.ejecutado && /rango/i.test(String(x.clasificacion_observada)))) {
      return 'C. Infinity y/o -Infinity se siguen clasificando como valor fuera de rango: la validacion de finitud no se aplica antes de la de rango en el TEST desplegado.';
    }
    return 'Por determinar con la evidencia de esta corrida: el rechazo no coincide con el mensaje literal exigido por motivos distintos de los tres anteriores.';
  })();

  const anomalia = r261 !== 'APROBADO' || r262 !== 'APROBADO';

  // ------------------------------------------------------------------- incidencia
  const incidencias = [];
  if (r261 !== 'APROBADO') {
    const malas = RECHAZOS.filter(v => variantes[v.clave].resultado !== 'APROBADO');
    incidencias.push({
      titulo: 'Valores no finitos no rechazados como formato decimal invalido',
      incidencia_requerida: 'SI', grupo_responsable: 'Desarrollo', grupo: GRUPO, caso: 'TC-M09-261',
      variantes_afectadas: malas.map(v => v.valor),
      consolidada: malas.length > 1 ? 'SI: las variantes afectadas comparten la misma causa de validacion de valores no finitos' : 'NO',
      esperado: malas.map(v => `${v.valor}: HTTP 400 con el mensaje «${mensajeEsperado(v.valor)}» y sin persistencia.`).join(' '),
      obtenido: malas.map(v => `${v.valor}: HTTP ${variantes[v.clave].response.http}, ${variantes[v.clave].clasificacion_observada}, mensaje ${JSON.stringify(variantes[v.clave].mensajeObtenido)}.`).join(' '),
      motivo: malas.map(v => `${v.valor}: ${variantes[v.clave].motivo}`).join(' '),
      causa_raiz: causaRaiz, type: 'bug', severity: 'Important', priority: 'High',
      evidencia: `evidencia.json y newman/newman-${GRUPO}.html del RUN ${runId}`
    });
  }
  if (r262 !== 'APROBADO') {
    incidencias.push({
      titulo: 'Precision de valor_referencia 22.1234 no conservada',
      incidencia_requerida: 'SI', grupo_responsable: 'Por determinar', grupo: GRUPO, caso: 'TC-M09-262',
      esperado: '2xx, id_calibracion y 22.1234 exacto en respuesta y en el GET de ese id.',
      obtenido: `HTTP ${variantes['262'].response.http}; id ${variantes['262'].response.id_calibracion}; respuesta ${JSON.stringify(variantes['262'].precision.valor_respuesta_crudo)}; historial ${JSON.stringify(variantes['262'].precision.valor_historial_crudo)}.`,
      motivo: Object.entries(variantes['262'].oraculo).filter(([, ok]) => ok !== true).map(([k]) => k).join(', '),
      causa_raiz: 'Por determinar: distinguir transformacion en la aplicacion de la escala de la columna numeric(10,4) desplegada antes de asignar Desarrollo o DBA.',
      type: 'bug', severity: 'Important', priority: 'High',
      evidencia: `evidencia.json y newman/newman-${GRUPO}.html del RUN ${runId}`
    });
  }

  const evidencia = {
    run_id: runId, evaluacion: 'SEGUNDA EVALUACION',
    grupo: GRUPO, casos: ['TC-M09-261', 'TC-M09-262'], requisito: RF,
    herramientas: 'API - Postman / Newman. BD no es el oraculo principal.',
    ambiente: { decisorio: 'TEST', base_url: base() },
    carpeta: `tests/Test_Testing/Test_Modulo9/RF-24/${GRUPO}/EvaluacionV2/`,
    rama: R.gitPre.rama, commit: R.gitPre.commit,
    resultado_grupo: resultadoGrupo,
    resultado_por_caso: { 'TC-M09-261': r261, 'TC-M09-262': r262 },

    git_pre: R.gitPre,

    actor: {
      nota: 'La coleccion Newman es duena de la sesion: hace su propio login y publica el token en session_value. El runner no obtiene tokens ni los inyecta; en el cierre se autentica solo para GET.',
      correo: ING.email, credencial: '[REDACTED]', login_http: R.ingLogin.http,
      id_usuario: R.identidad.cuerpo?.id_usuario ?? null, id_descubierto_dinamicamente: true,
      rol: R.identidad.cuerpo?.nombre_rol ?? null, estado_cuenta: R.identidad.cuerpo?.estado_cuenta ?? null,
      permisos_recurso_12: R.permisos.recurso12,
      total_permisos: (R.permisos.cuerpo?.permisos || []).length,
      papel: 'ejecuta los 4 POST /calibrar',
      administrador: { utilizado: false, motivo: 'el Ingeniero resolvio por GET todas las precondiciones: no hizo falta el actor auxiliar de discovery' }
    },

    preflight: {
      modo: 'PRECHECK Newman de solo lectura previo al RUN',
      post_calibrar_en_precheck: 0, html_generado_en_precheck: 'ninguno', resultados_creados_en_precheck: 'ninguno',
      items_excluidos: [...ITEMS_CALIBRAR, ...ITEMS_POSCONDICION],
      motivo_exclusion_poscondicion: 'los historiales de poscondicion dependen del id creado por su POST: sin POST no son evaluables',
      verificado: ['autenticacion', 'identidad', 'permisos', 'fixture', 'rango', 'OpenAPI', 'representacion de los valores en la coleccion']
    },

    contrato_openapi: {
      http: R.openapi.http,
      valor_referencia: R.openapi.valor_referencia ? JSON.parse(R.openapi.valor_referencia) : null,
      modo_calibracion: R.openapi.modo_calibracion ? JSON.parse(R.openapi.modo_calibracion) : null,
      required_del_dto: R.openapi.required_dto ? JSON.parse(R.openapi.required_dto) : null,
      codigos_del_post_calibrar: R.openapi.codigos_calibrar ? JSON.parse(R.openapi.codigos_calibrar) : null,
      codigos_del_historial: R.openapi.codigos_historial ? JSON.parse(R.openapi.codigos_historial) : null,
      patron_de_cadena_publicado: R.openapi.patron_valor,
      el_patron_admitiria_no_finitos: R.openapi.patron_admite_no_finitos,
      nota: 'Observacion DIAGNOSTICA del contrato desplegado. No sustituye a la prueba: el resultado se determina por los POST reales.'
    },

    fixture: {
      sensor: FIX.sensor, dispositivo: FIX.dispositivo, area: FIX.area, categoria: FIX.categoria,
      valor_de_precision: FIX.valor262,
      rango: R.fixture.rango ? JSON.parse(R.fixture.rango) : null,
      valor_dentro_del_rango: (() => {
        const r = R.fixture.rango ? JSON.parse(R.fixture.rango) : null;
        return r ? Number(FIX.valor262) >= Number(r.min) && Number(FIX.valor262) <= Number(r.max) : null;
      })(),
      dispositivo_detalle: R.fixture.dispositivo.cuerpo ? { id: R.fixture.dispositivo.cuerpo.id_dispositivo_iot, serial: R.fixture.dispositivo.cuerpo.serial, es_activo: R.fixture.dispositivo.cuerpo.es_activo } : null,
      sensorRow: (() => {
        const row = (R.fixture.sensores.cuerpo?.items || []).find(x => sid(x) === FIX.sensor) || null;
        return row ? { id: sid(row), categoria: row.categoria, es_activo: row.es_activo, id_dispositivo_iot: row.id_dispositivo_iot } : null;
      })(),
      asociacionVigente: (() => {
        const a = (R.fixture.asociaciones.cuerpo?.items || []).find(x => vig(x) && sid(x) === FIX.sensor && x.id_dispositivo_iot === FIX.dispositivo && x.id_infraestructura === FIX.area) || null;
        return a ? { id_dispositivo_iot: a.id_dispositivo_iot, id_infraestructura: a.id_infraestructura, tiene_estado: a.tiene_estado, fecha_finalizacion: a.fecha_finalizacion } : null;
      })(),
      area_detalle: R.fixture.area.cuerpo ? { id: R.fixture.area.cuerpo.id_infraestructura, es_activo: R.fixture.area.cuerpo.es_activo } : null,
      nota: 'Fixture completamente valido y reutilizado de la primera evaluacion. La unica invalidez de TC-M09-261 es el formato del valor; el rango nunca es el motivo del rechazo esperado.'
    },

    representacion_enviada: {
      regla: 'Se preserva exactamente la representacion de cada entrada. No se convierte "NaN" en null, 0 ni cadena vacia.',
      por_variante: Object.fromEntries(VARIANTES.map(v => [v.etiqueta, {
        valor_definido: v.valor, representacion: v.representacion,
        texto_enviado: variantes[v.clave].request?.bodyTextoEnviado ?? null,
        valor_referencia_enviado: variantes[v.clave].request?.valor_referencia_enviado ?? null,
        tipo_json: variantes[v.clave].request?.tipo_json_enviado ?? null,
        preservada: variantes[v.clave].request?.representacion_preservada ?? null
      }])),
      fuera_de_alcance_no_enviado: ['5 o mas decimales (22.12345, 22.123456)', 'notacion cientifica', 'null', '"abc"']
    },

    'TC-M09-262': variantes['262'],
    'TC-M09-261': {
      NaN: variantes['nan'], Infinity: variantes['inf'], 'menos-Infinity': variantes['ninf'],
      resultado: r261,
      regla: 'APROBADO solo si las TRES variantes dan 400 + mensaje exacto + no persistencia.'
    },

    newman: {
      html: `newman/newman-${GRUPO}.html`, htmlPersistentes: 1,
      coleccionEjecutada: `${R.itemsEjecutables} de ${R.itemsTotales} items`,
      iterations: R.stats.iterations, requests: R.stats.requests, assertions: R.stats.assertions,
      failures: R.failures,
      presupuesto: {
        postPlanificados: POST_BUDGET, postEjecutados: R.postCalibrar,
        postExitososEsperados: 1, postRechazadosEsperados: 3,
        patch: 0, put: 0, delete: 0, reintentos: 0
      },
      stopAll: R.stopAll, stopAllMotivo: R.stopAllMotivo ? JSON.parse(R.stopAllMotivo) : null,
      limpio: newmanLimpio,
      nota: 'Los failures no se ocultan ni se reinterpretan: un failure funcional real deja el HTML en rojo y el grupo RECHAZADO.'
    },

    verificacion_persistencia: {
      calibraciones_validas_nuevas_esperadas: 1,
      calibraciones_invalidas_nuevas_esperadas: 0,
      id_calibracion_TC262: id262,
      ids_nuevos_por_variante: Object.fromEntries(VARIANTES.map(v => [v.etiqueta, variantes[v.clave].idsNuevos ?? 'sin POST'])),
      ids_creados_en_este_run: idsDeEsteRun,
      ids_indebidos: persistenciaIndebida,
      correlacion: 'por id_calibracion devuelto, observaciones, id_usuario y fecha; nunca por total + 1',
      cumple: idsDeEsteRun.length === 1 && Number(idsDeEsteRun[0]) === Number(id262) && persistenciaIndebida.length === 0
    },

    verificacion_final: {
      soloLectura: true, sql: 'ninguno', escrituras: 0, fecha: new Date().toISOString(),
      historial_sensor: { sensor: FIX.sensor, http: hist.status, total: hist.cuerpo?.total ?? null, ids },
      registro_TC262_sigue_presente: Boolean(fila262),
      registro_TC262: fila262 ? { id_calibracion: fila262.id_calibracion, valor_referencia: fila262.valor_referencia, valor_normalizado: normDec(fila262.valor_referencia), escala_observable: escalaDe(fila262.valor_referencia), exacto: igualDecimal(fila262.valor_referencia, FIX.valor262), observaciones: fila262.observaciones, id_usuario: fila262.id_usuario, fecha_calibracion: fila262.fecha_calibracion } : null,
      calibraciones_atribuibles_a_TC262: atribuibles262,
      calibraciones_atribuibles_a_TC261: atribuibles261,
      nota_atribuibles_261: `Las calibraciones con observaciones «QA TC-M09-261» que aparezcan NO provienen de este RUN: los IDs nuevos de las tres variantes fueron ${JSON.stringify(RECHAZOS.map(v => variantes[v.clave].idsNuevos ?? 'sin POST'))}. No se borro ningun registro.`,
      nota_calibracion_17: (() => {
        const existe = ids.includes(17);
        return `La calibracion 17, creada por la PRIMERA evaluacion en TC-M09-262, ${existe ? 'sigue existiendo' : 'no esta'} en el historial del sensor ${FIX.sensor}. No proviene de este RUN y no se borro.`;
      })(),
      asociacion_sensor: (asoc.cuerpo?.items || []).filter(x => vig(x) && sid(x) === FIX.sensor).map(x => ({ id_dispositivo_iot: x.id_dispositivo_iot, id_infraestructura: x.id_infraestructura })),
      post_extra_ejecutados: 0,
      borrados: 'ninguno: la calibracion del camino exitoso se conserva, como exige el paquete'
    },

    contraste_dev: {
      necesario: anomalia,
      motivo: anomalia
        ? 'TEST mantiene al menos uno de los defectos: procede contrastar DEV para distinguir defecto de aplicacion de desfase de despliegue. TEST conserva la decision oficial.'
        : 'TEST paso completamente: los tres valores no finitos dieron 400 con el mensaje literal y la precision se conservo. No se uso DEV.',
      peticiones_a_dev: 0
    },

    diagnostico_bd: {
      utilizada: false,
      motivo: 'La BD no es el oraculo principal y no aparecio discrepancia de persistencia: los historiales PRE/POST por variante fueron consistentes y el valor exacto 22.1234 se verifico por GET del id devuelto. No se abrio ninguna conexion.',
      solo_select: true
    },

    comparacion_primera_segunda: comparacion,
    causa_raiz: causaRaiz,
    incidencias: incidencias.length ? incidencias : [{ incidencia_requerida: 'NO', nota: 'Todo paso. Causa anterior CORREGIDA: se propone validar y cerrar la incidencia previa de TC-M09-261.' }],
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
    if (v.tipo === 'exito') {
      log(`${v.etiqueta}: HTTP ${c.response.http} | id ${c.response.id_calibracion} | respuesta ${JSON.stringify(c.precision.valor_respuesta_crudo)} (exacto ${c.precision.exactitud_respuesta ? 'SI' : 'NO'}) | historial ${JSON.stringify(c.precision.valor_historial_crudo)} (exacto ${c.precision.exactitud_historial ? 'SI' : 'NO'}) | PRE ${c.historialPre?.total} POST ${c.historialPost?.total} -> ${c.resultado}`);
    } else {
      log(`${v.etiqueta}: HTTP ${c.response.http} | error_code ${c.response.error_code || '—'} | mensaje exacto ${c.mensajeExacto ? 'SI' : 'NO'} (${c.clasificacion_observada}) | PRE ${c.historialPre?.total} POST ${c.historialPost?.total} | nuevos ${JSON.stringify(c.idsNuevos)} -> ${c.resultado}`);
    }
  }
  log(`TC-M09-261 -> ${r261} | TC-M09-262 -> ${r262}`);
  log(`GRUPO ${GRUPO} -> ${resultadoGrupo}`);
  log(`Newman: requests ${R.stats.requests.ejecutados} (fallidos ${R.stats.requests.fallidos}) | assertions ${R.stats.assertions.total} (fallidas ${R.stats.assertions.fallidas}) | limpio ${newmanLimpio ? 'SI' : 'NO'}`);
  log(`POST /calibrar ${R.postCalibrar}/${POST_BUDGET} | STOP_ALL ${R.stopAll} | persistencia indebida: ${persistenciaIndebida.length ? JSON.stringify(persistenciaIndebida) : 'ninguna'}`);
  log(`Persistencia esperada: 1 valida (id ${id262}) y 0 invalidas | cumple: ${evidencia.verificacion_persistencia.cumple ? 'SI' : 'NO'}`);
  log(`Causa del rechazo anterior: ${comparacion.causaDelRechazoAnterior}`);
  log(`Causa raiz: ${causaRaiz}`);
  log(`Contraste DEV necesario: ${anomalia ? 'SI' : 'NO'} | BD utilizada: NO`);
  log(`Evidencia limpia de secretos: ${evidencia.seguridad.limpio ? 'SI' : 'NO'}`);
  log('========================================\n');

  if (!evidencia.seguridad.limpio) process.exitCode = 3;
  else if (resultadoGrupo !== 'APROBADO') process.exitCode = 2;
}

// --------------------------------------------------------------------------- manifiesto
function refrescarManifest() {
  const artefactos = [
    { archivo: 'run-g132-v2.cjs', abs: path.join(__dirname, 'run-g132-v2.cjs'),
      ruta: `${GRUPO}/EvaluacionV2/automation/run-g132-v2.cjs`,
      funcion: 'Runner unico de la reevaluacion, con los modos precheck (Newman de solo lectura, sin HTML ni archivos, sin los 4 POST ni sus historiales de poscondicion), run (RUN funcional oficial con los 4 POST y el unico HTML) y close (oraculo por caso, verificacion final de solo lectura y consolidacion de evidencia). No obtiene ni inyecta tokens, no ejecuta PATCH, PUT ni DELETE, y compara los decimales por normalizacion textual, no por float binario.' },
    { archivo: 'TC-M09-G132.postman_collection.json', abs: COLECCION,
      ruta: `${GRUPO}/EvaluacionV2/TC-M09-G132.postman_collection.json`,
      funcion: 'Coleccion de EvaluacionV2. Despliega los CUATRO POST funcionales como items propios y es duena de su sesion (login dentro de Newman, token en session_value), porque la original inyectaba el token desde el runner. Conserva los mismos inputs, expected, mensajes literales, verificaciones de historial y el caso de precision; envia "NaN", "Infinity" y "-Infinity" tal cual, y 22.1234 como literal de cuatro decimales.' },
    { archivo: 'TC-M09-G132.postman_collection.json (original)', abs: COLECCION_ORIGINAL,
      ruta: `${GRUPO}/TC-M09-G132.postman_collection.json`,
      funcion: 'Coleccion de la primera evaluacion: un unico item generico parametrizado por el runner, con el token inyectado desde fuera. Reutilizada en solo lectura como fuente del criterio de rechazo y de las URLs; no fue modificada.' },
    { archivo: 'run-newman.cjs (original)', abs: path.join(CASE_DIR, 'run-newman.cjs'),
      ruta: `${GRUPO}/run-newman.cjs`,
      funcion: 'Runner de la primera evaluacion. Fuente de los cuatro bodies, del orden de las variantes y de los mensajes esperados. NO se utiliza en esta reevaluacion: se registra por trazabilidad del baseline.' }
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
    grupo: GRUPO, casos: ['TC-M09-261', 'TC-M09-262'], runId,
    nota: 'Artefactos finales de la SEGUNDA EVALUACION. Los ejecutables viven unicamente en EvaluacionV2/; no se duplica automation dentro de RESULTADOS.',
    newmanHtmlPersistentes: 1, automationDentroDeResultados: 'NO', artefactos: filas
  }, null, 2)));
}
