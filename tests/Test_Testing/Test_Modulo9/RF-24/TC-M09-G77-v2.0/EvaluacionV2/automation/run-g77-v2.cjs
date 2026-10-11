// Runner único de la SEGUNDA EVALUACIÓN de TC-M09-G77-v2.0 (RF-24 v2.0, CU05 Flujo D).
// Caso TC-M09-148-v2.0 — subescenarios Productor y Contador (roles NO autorizados).
//
// Un solo archivo, tres modos (G77_MODO):
//
//   precheck  Validación Newman previa al RUN. Ejecuta la colección filtrada en memoria SIN
//             los dos POST /calibrar; no toca /gestionar, no activa ni desactiva cuentas, no
//             genera HTML, no crea RESULTADOS y no deja archivos: solo consola. El RUN se
//             autoriza únicamente si failures = 0.
//   run       RUN funcional oficial: la colección completa una única vez, con los 2 POST de
//             calibración, y el ÚNICO reporte Newman HTML persistente.
//   close     Verificación final de solo lectura (estados de cuenta, fixture, historial y
//             rango) y consolidación de evidencia.json y automation_manifest.json.
//
// REGLA DE SESIONES QUE ESTE RUNNER HACE CUMPLIR (corrección aprendida en G76):
//   La colección es dueña de TODAS las sesiones. Hace sus propios logins y publica los tokens
//   en ing_session, admin_session, productor_session y contador_session. El runner NO inicia
//   sesión antes de Newman y NO inyecta ningún token: solo pasa configuración (correos,
//   secretos, ids del fixture, body y mensaje esperado). Motivo: TEST aplica sesión única por
//   usuario y un nuevo login del mismo correo revoca el token anterior.
//   El modo close sí se autentica, pero DESPUÉS del RUN y solo para GET de verificación.
//
// Presupuesto: 2 POST /calibrar (uno por rol), sin reintentos. Ninguna escritura más: este
// runner no ejecuta PATCH y solo permite POST /usuarios/{id}/gestionar si una cuenta estuviera
// inactiva, lo que se decide con el estado capturado por la colección.
//
// Uso:
//   $env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
//   $env:QA_ADMIN_EMAIL="administador.dev@gmail.com"
//   $env:QA_ADMIN_PASSWORD="<secreto>"
//   $env:QA_PRODUCTOR_EMAIL="m2m.nuevo@ejemplo.com"
//   $env:QA_PRODUCTOR_PASSWORD="<secreto>"
//   $env:QA_CONTADOR_EMAIL="contador@pecuaria.co"
//   $env:QA_CONTADOR_PASSWORD="<secreto>"
//   $env:QA_ING_EMAIL="ingeniero@pecuaria.co"
//   $env:QA_ING_PASSWORD="<secreto>"
//   $env:G77_RUN_ID="run-YYYYMMDD-HHMMSS"      (modos run y close)
//   $env:G77_MODO="precheck" | "run" | "close"
//   node .\run-g77-v2.cjs

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const CASE_DIR = path.resolve(__dirname, '..', '..');
const EVAL_DIR = path.resolve(__dirname, '..');
const COLECCION = path.join(EVAL_DIR, 'TC-M09-G77-v2.0.postman_collection.json');
const COLECCION_ORIGINAL = path.join(CASE_DIR, 'TC-M09-G77-v2.0.postman_collection.json');

const GRUPO = 'TC-M09-G77-v2.0';
const CASO = 'TC-M09-148-v2.0';
const RF = 'RF-24 v2.0';
const CU = 'CU05 — Gestionar Dispositivos IoT, Flujo D · Seguridad OWASP API5';
const POST_BUDGET = 2;

const MODO = process.env.G77_MODO || 'precheck';
if (!['precheck', 'run', 'close'].includes(MODO)) throw new Error(`G77_MODO no reconocido: ${MODO}`);

const base = () => {
  const b = process.env.QA_BASE_URL;
  if (!b) throw new Error('QA_BASE_URL requerido');
  return b.replace(/\/$/, '');
};

const ACTORES = {
  ing: { email: process.env.QA_ING_EMAIL, secret: process.env.QA_ING_PASSWORD },
  admin: { email: process.env.QA_ADMIN_EMAIL, secret: process.env.QA_ADMIN_PASSWORD },
  productor: { email: process.env.QA_PRODUCTOR_EMAIL, secret: process.env.QA_PRODUCTOR_PASSWORD },
  contador: { email: process.env.QA_CONTADOR_EMAIL, secret: process.env.QA_CONTADOR_PASSWORD }
};
for (const [k, v] of Object.entries(ACTORES)) {
  if (!v.email || !v.secret) throw new Error(`Faltan credenciales de ${k} (solo en memoria de proceso).`);
}

// ------------------------------------------------------------------ fixture del caso
const FIX = {
  sensor: Number(process.env.G77_SENSOR || 6),
  dispositivo: Number(process.env.G77_DEVICE || 3),
  area: Number(process.env.G77_AREA || 3),
  categoria: process.env.G77_CAT || 'TEMPERATURA',
  valor: process.env.G77_VALOR || '22.5000',
  rangoEsperado: { min: '0', max: '45' }
};
const OBSERVACIONES = `QA ${CASO}`;
const EXP_MSG_403 = 'Acceso denegado: La calibración de sensores es una función crítica restringida exclusivamente al Ingeniero de Campo o al Administrador.';

const ITEMS_CALIBRAR = ['productor POST calibrar', 'contador POST calibrar'];

const log = (...a) => console.log(...a);
const sha256 = (f) => crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');

// --------------------------------------------------------------------- sanitización
const secretos = () => Object.values(ACTORES).map(a => a.secret).filter(Boolean);
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
const runId = process.env.G77_RUN_ID;
if (MODO !== 'precheck' && (!runId || !/^run-\d{8}-\d{6}$/.test(runId))) {
  throw new Error('G77_RUN_ID requerido con formato run-YYYYMMDD-HHMMSS.');
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
  diff_stat: git(['diff', '--stat']) || '(vacio)',
  commit: git(['rev-parse', 'HEAD']),
  origin_test: git(['rev-parse', 'origin/test']),
  divergencia_HEAD_origin_test: git(['rev-list', '--left-right', '--count', 'HEAD...origin/test']),
  carpeta_historica_TC_M09_G77: git(['status', '--short', '--', 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G77']) || '(vacio = intacta)',
  primera_evaluacion_RESULTADOS: git(['status', '--short', '--', 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G77-v2.0/RESULTADOS']) || '(vacio = intacta)',
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
  // En los .cjs el vocabulario del propio escáner aparece de forma legítima: para código
  // fuente solo cuentan VALORES de secreto y la coincidencia literal con las credenciales.
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
    limpio: sucios.length === 0,
    archivosConHallazgos: sucios, revisados,
    criterio: 'Se marcan solo VALORES de secreto: contrasenas en uso, JWT, Authorization con token, cookies, tokens en pares clave-valor y cadenas de conexion. En los .cjs solo se evaluan valores y la coincidencia literal con las credenciales. Los correos de los actores los publica el propio caso y no son secretos del requisito.',
    nota: 'Las contrasenas solo existieron en memoria de proceso. El reporter htmlextra se ejecuto con omitHeaders, sin environment ni globals y omitiendo las variables sensibles; el HTML se sanitizo despues de generarse.'
  };
}

// ------------------------------------------------------------------- env de la colección
function construirEnv() {
  const body = `{"modo_calibracion":"SENSOR","id_dispositivo_iot":${FIX.dispositivo},"id_infraestructura":${FIX.area},"valor_referencia":${FIX.valor},"observaciones":${JSON.stringify(OBSERVACIONES)},"fecha_calibracion":"__FECHA__"}`;
  return [
    ['base_url', base()],
    ['ing_email', ACTORES.ing.email], ['ing_secret', ACTORES.ing.secret],
    ['admin_email', ACTORES.admin.email], ['admin_secret', ACTORES.admin.secret],
    ['productor_email', ACTORES.productor.email], ['productor_secret', ACTORES.productor.secret],
    ['contador_email', ACTORES.contador.email], ['contador_secret', ACTORES.contador.secret],
    ['device_id', String(FIX.dispositivo)], ['sensor_id', String(FIX.sensor)],
    ['area_id', String(FIX.area)], ['categoria', FIX.categoria], ['valor', FIX.valor],
    ['body_calibracion', body],
    ['exp_msg_403', EXP_MSG_403],
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

// Guarda de escrituras: nada fuera de los 2 POST de calibración autorizados.
function verificarEscrituras(col, permitirCalibrar) {
  for (const it of col.item) {
    const url = typeof it.request.url === 'string' ? it.request.url : it.request.url?.raw || '';
    const metodo = (it.request.method || 'GET').toUpperCase();
    if (['PATCH', 'PUT', 'DELETE'].includes(metodo)) {
      throw new Error(`ABORTADO: escritura no autorizada ${metodo} ${url} (${it.name}).`);
    }
    if (/\/gestionar/.test(url)) {
      throw new Error(`ABORTADO: la colección no debe gestionar cuentas en esta corrida (${it.name}); ambas cuentas deben estar Activo.`);
    }
    if (/\/calibrar$/.test(url) && !permitirCalibrar) {
      throw new Error(`ABORTADO: el PRECHECK no puede contener el endpoint de calibración (${it.name}).`);
    }
    if (metodo === 'POST' && !/\/sesiones\/?$/.test(url) && !/\/calibrar$/.test(url)) {
      throw new Error(`ABORTADO: POST no autorizado: ${url} (${it.name}).`);
    }
  }
}

function correrNewman(col, env, html, titulo) {
  const o = {
    collection: col,
    reporters: html ? ['cli', 'htmlextra'] : ['cli'],
    envVar: env.map(([key, value]) => ({ key, value }))
  };
  if (html) {
    o.reporter = {
      htmlextra: {
        export: html, omitHeaders: true, showEnvironmentData: false, showGlobalData: false,
        skipEnvironmentVars: ['ing_secret', 'admin_secret', 'productor_secret', 'contador_secret',
          'ing_session', 'admin_session', 'productor_session', 'contador_session'],
        showMarkdownLinks: false
      }
    };
    if (titulo) o.reporter.htmlextra.title = titulo;
  }
  return new Promise((resolve, reject) => {
    newman.run(o, (err, summary) => (err ? reject(err) : resolve(summary)));
  });
}

function extraer(summary) {
  const ex = summary?.run?.executions || [];
  const find = (n) => ex.find(x => x.item && x.item.name === n);
  const cuerpo = (n) => { const e = find(n); if (!e || !e.response) return null; try { return JSON.parse(e.response.stream.toString()); } catch { return null; } };
  const http = (n) => { const e = find(n); return e && e.response ? e.response.code : null; };
  const enviado = (n) => { const e = find(n); try { return JSON.parse(e.request.body.raw.toString()); } catch { return null; } };
  const asserts = (n) => {
    const e = find(n);
    return (e?.assertions || []).map(a => ({ assertion: a.assertion, paso: !a.error, error: a.error ? a.error.message : null }));
  };
  return { ex, cuerpo, http, enviado, asserts };
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
const patchs = (s) => (s?.run?.executions || []).filter(e => (e.request?.method || '').toUpperCase() === 'PATCH').length;
const envDe = (s, k) => s?.environment?.values?.find?.(x => x.key === k)?.value ?? null;

// HTTP directo, solo para la verificación final del modo close (después del RUN).
async function login(email, secret) {
  const r = await fetch(base() + '/sesiones/', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correo_electronico: email, contrasena: secret }),
    signal: AbortSignal.timeout(25000)
  });
  const b = await r.json().catch(() => null);
  if (r.status !== 200 || !b?.token) throw new Error(`login ${email} HTTP ${r.status}${b?.error_code ? ' ' + b.error_code : ''}`);
  return b.token;
}
async function get(endpoint, token) {
  const r = await fetch(base() + endpoint, { headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(25000) });
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

  log('PRECHECK de validación previa — Newman sin reporter HTML, sin carpeta de resultados.');
  log(`Colección: ${itemsEjecutables} de ${itemsTotales} items. Excluidos: ${quitados.join(' | ')}`);
  log('Sin /calibrar, sin /gestionar, sin PATCH: no se activa ni se desactiva ninguna cuenta.\n');

  const summary = await correrNewman(col, construirEnv(), null, null);
  const st = stats(summary);
  const f = fallos(summary);
  const { cuerpo, http, asserts } = extraer(summary);

  const pasa = (item) => { const a = asserts(item); return a.length > 0 && a.every(x => x.paso); };
  const adminLogin = http('Login Administrador auxiliar');
  const prodLoc = cuerpo('Localizar Productor (Administrador)');
  const contLoc = cuerpo('Localizar Contador (Administrador)');
  const buscar = (c, correo) => ((c?.items || c?.usuarios || []).find(x => (x.correo_electronico || x.correo) === correo) || null);
  const uProd = buscar(prodLoc, ACTORES.productor.email);
  const uCont = buscar(contLoc, ACTORES.contador.email);
  const estado = (u) => (u ? (u.estado_cuenta || u.estado || '') : '');

  const disp = cuerpo('Fixture — dispositivo activo');
  const sens = cuerpo('Fixture — sensor del dispositivo');
  const asoc = cuerpo('Fixture — asociación vigente');
  const rangos = cuerpo('Fixture — rango de la categoría');
  const sid = (x) => (x && x.id_sensor !== undefined ? x.id_sensor : x && x.id_sensores);
  const vig = (x) => x && x.tiene_estado === true && (x.fecha_finalizacion === null || x.fecha_finalizacion === undefined);
  const sensorRow = (sens?.items || []).find(x => sid(x) === FIX.sensor) || null;
  const asocRow = (asoc?.items || []).find(x => vig(x) && sid(x) === FIX.sensor && x.id_dispositivo_iot === FIX.dispositivo) || null;
  const rango = (rangos?.items || []).find(x => x.categoria === FIX.categoria) || null;

  const meProd = cuerpo('productor Identidad');
  const meCont = cuerpo('contador Identidad');

  const chequeos = {
    admin: adminLogin >= 200 && adminLogin <= 299 && pasa('Login Administrador auxiliar'),
    productorLocalizado: Boolean(uProd) && (uProd.nombre_rol || uProd.rol) === 'Productor' && pasa('Localizar Productor (Administrador)'),
    contadorLocalizado: Boolean(uCont) && (uCont.nombre_rol || uCont.rol) === 'Contador' && pasa('Localizar Contador (Administrador)'),
    estadosCapturados: Boolean(estado(uProd)) && Boolean(estado(uCont)),
    fixture: disp?.id_dispositivo_iot === FIX.dispositivo && disp?.es_activo === true &&
      Boolean(sensorRow) && sensorRow.es_activo === true && sensorRow.categoria === FIX.categoria &&
      sensorRow.id_dispositivo_iot === FIX.dispositivo &&
      Boolean(asocRow) && asocRow.id_infraestructura === FIX.area &&
      pasa('Fixture — dispositivo activo') && pasa('Fixture — sensor del dispositivo') && pasa('Fixture — asociación vigente'),
    rango: Boolean(rango) && Number(rango.valor_min) === Number(FIX.rangoEsperado.min) &&
      Number(rango.valor_max) === Number(FIX.rangoEsperado.max) &&
      Number(FIX.valor) > Number(rango.valor_min) && Number(FIX.valor) < Number(rango.valor_max) &&
      pasa('Fixture — rango de la categoría')
  };

  const postCalibrar = contar(summary, /\/calibrar$/);
  const postGestionar = contar(summary, /\/gestionar/);
  const nPatch = patchs(summary);
  const autorizar = Object.values(chequeos).every(Boolean) && f.length === 0 &&
    (st.requests.fallidos || 0) === 0 && postCalibrar === 0 && postGestionar === 0 && nPatch === 0;

  const P = (b) => (b ? 'PASS' : 'FAIL');
  log('\nPRECHECK_G77\n');
  log(`Admin:\n${P(chequeos.admin)}\n`);
  log(`Productor localizado:\n${P(chequeos.productorLocalizado)}\n`);
  log(`Contador localizado:\n${P(chequeos.contadorLocalizado)}\n`);
  log(`Estados capturados:\n${P(chequeos.estadosCapturados)}\n`);
  log(`Fixture:\n${P(chequeos.fixture)}\n`);
  log(`Rango:\n${P(chequeos.rango)}\n`);
  log(`Failures:\n${f.length}\n`);
  log(`POST /calibrar:\n${postCalibrar}\n`);
  log(`POST /usuarios/*/gestionar:\n${postGestionar}\n`);
  log(`PATCH:\n${nPatch}\n`);
  log(`AUTORIZAR_RUN:\n${autorizar ? 'SÍ' : 'NO'}\n`);

  log('--- detalle observado (solo consola, no se persiste) ---');
  log(`admin efectivo: ${ACTORES.admin.email} | login HTTP ${adminLogin}`);
  log(`Productor: id_usuario=${uProd?.id_usuario} rol=${uProd?.nombre_rol || uProd?.rol} estado_original=${estado(uProd)} | requiere_setup=${estado(uProd) === 'Activo' ? 'NO' : 'SI'}`);
  log(`Contador:  id_usuario=${uCont?.id_usuario} rol=${uCont?.nombre_rol || uCont?.rol} estado_original=${estado(uCont)} | requiere_setup=${estado(uCont) === 'Activo' ? 'NO' : 'SI'}`);
  log(`identidad Productor: ${meProd ? `${meProd.correo_electronico} rol=${meProd.nombre_rol} estado=${meProd.estado_cuenta}` : 'no obtenida'}`);
  log(`identidad Contador:  ${meCont ? `${meCont.correo_electronico} rol=${meCont.nombre_rol} estado=${meCont.estado_cuenta}` : 'no obtenida'}`);
  log(`permisos recurso 12: Productor=${envDe(summary, 'productor_acciones_recurso12')} | Contador=${envDe(summary, 'contador_acciones_recurso12')}`);
  log(`fixture: dispositivo ${disp?.id_dispositivo_iot} activo=${disp?.es_activo} | sensor ${sid(sensorRow)} ${sensorRow?.categoria} activo=${sensorRow?.es_activo} | asociación vigente área ${asocRow?.id_infraestructura}`);
  log(`rango ${FIX.categoria}: ${rango?.valor_min}–${rango?.valor_max} | valor del caso ${FIX.valor} interior=${Boolean(rango) && Number(FIX.valor) > Number(rango.valor_min) && Number(FIX.valor) < Number(rango.valor_max)}`);
  log(`historial PRE leído por el Ingeniero de discovery: total ${envDe(summary, 'pre_productor_total')}`);
  log(`newman: requests ${st.requests.ejecutados}/${st.requests.fallidos} fallidos | assertions ${st.assertions.total}/${st.assertions.fallidas} fallidas`);
  if (f.length) { log('\nfailures:'); f.forEach((x, i) => log(`  ${i + 1}. ${x.item} :: ${x.assertion} :: ${x.error}`)); }
  log('');

  if (!autorizar) { log('El RUN funcional NO está autorizado. Corregir antes de ejecutar los POST.'); process.exitCode = 2; }
}

// ------------------------------------------------------------------------------------ run
async function modoRun() {
  if (fs.existsSync(RUN_DIR)) throw new Error(`La carpeta ${runId} ya existe. Un RUN oficial no se repite ni se sobrescribe.`);
  const { col, itemsTotales, itemsEjecutables } = cargarColeccion([]);
  verificarEscrituras(col, true);

  const calibrar = col.item.filter(i => /\/calibrar$/.test(typeof i.request.url === 'string' ? i.request.url : i.request.url?.raw || ''));
  if (calibrar.length !== POST_BUDGET) {
    throw new Error(`ABORTADO: la colección debe contener exactamente ${POST_BUDGET} POST de calibración, contiene ${calibrar.length}.`);
  }

  const gitPre = estadoGit('git_pre');
  const html = HTML_OFICIAL();

  log(`RUN funcional oficial. RUN_ID: ${runId}`);
  log(`Colección: ${itemsEjecutables} de ${itemsTotales} items.`);
  log(`POST /calibrar planificados: ${POST_BUDGET} | /gestionar: 0 | PATCH: 0`);
  log(`Mensaje esperado (ambos roles): ${EXP_MSG_403}\n`);

  const summary = await correrNewman(col, construirEnv(), html, `${GRUPO} — SEGUNDA EVALUACIÓN · RUN funcional oficial ${runId}`);
  if (fs.existsSync(html)) fs.writeFileSync(html, limpiarHtml(fs.readFileSync(html, 'utf8')));

  const { cuerpo, http, enviado, asserts } = extraer(summary);
  const bloqueActor = (pref) => ({
    login: { http: http(`${pref} Login`), assertions: asserts(`${pref} Login`) },
    identidad: { http: http(`${pref} Identidad`), cuerpo: cuerpo(`${pref} Identidad`), assertions: asserts(`${pref} Identidad`) },
    permisos: { http: http(`${pref} Permisos`), cuerpo: cuerpo(`${pref} Permisos`), assertions: asserts(`${pref} Permisos`) },
    pre: { http: http(`${pref} PRE historial`), cuerpo: cuerpo(`${pref} PRE historial`), assertions: asserts(`${pref} PRE historial`) },
    calibrar: { http: http(`${pref} POST calibrar`), cuerpo: cuerpo(`${pref} POST calibrar`), enviado: enviado(`${pref} POST calibrar`), assertions: asserts(`${pref} POST calibrar`) },
    post: { http: http(`${pref} POST historial`), cuerpo: cuerpo(`${pref} POST historial`), assertions: asserts(`${pref} POST historial`) }
  });

  const preservado = {
    runId, generado: new Date().toISOString(), gitPre, itemsTotales, itemsEjecutables,
    stats: stats(summary), failures: fallos(summary),
    postCalibrar: contar(summary, /\/calibrar$/),
    postGestionar: contar(summary, /\/gestionar/),
    patchs: patchs(summary),
    stopAll: envDe(summary, 'stop_all') ?? 'NO',
    stopAllMotivo: envDe(summary, 'stop_all_motivo'),
    adminLogin: { http: http('Login Administrador auxiliar'), assertions: asserts('Login Administrador auxiliar') },
    ingLogin: { http: http('Login Ingeniero (discovery)'), assertions: asserts('Login Ingeniero (discovery)') },
    localizacion: {
      productor: { http: http('Localizar Productor (Administrador)'), cuerpo: cuerpo('Localizar Productor (Administrador)'), assertions: asserts('Localizar Productor (Administrador)') },
      contador: { http: http('Localizar Contador (Administrador)'), cuerpo: cuerpo('Localizar Contador (Administrador)'), assertions: asserts('Localizar Contador (Administrador)') }
    },
    estadosOriginales: {
      productor: envDe(summary, 'productor_estado_original'),
      contador: envDe(summary, 'contador_estado_original')
    },
    ids: { productor: envDe(summary, 'productor_id'), contador: envDe(summary, 'contador_id') },
    permisosRecurso12: {
      productor: envDe(summary, 'productor_acciones_recurso12'),
      contador: envDe(summary, 'contador_acciones_recurso12')
    },
    fixture: {
      dispositivo: { http: http('Fixture — dispositivo activo'), cuerpo: cuerpo('Fixture — dispositivo activo'), assertions: asserts('Fixture — dispositivo activo') },
      sensores: { http: http('Fixture — sensor del dispositivo'), cuerpo: cuerpo('Fixture — sensor del dispositivo'), assertions: asserts('Fixture — sensor del dispositivo') },
      asociaciones: { http: http('Fixture — asociación vigente'), cuerpo: cuerpo('Fixture — asociación vigente'), assertions: asserts('Fixture — asociación vigente') },
      rangos: { http: http('Fixture — rango de la categoría'), cuerpo: cuerpo('Fixture — rango de la categoría'), assertions: asserts('Fixture — rango de la categoría') }
    },
    productor: bloqueActor('productor'),
    contador: bloqueActor('contador')
  };
  fs.writeFileSync(SUMMARY_TMP(), limpiar(JSON.stringify(preservado, null, 2)));

  const st = preservado.stats;
  log('\n================ RUN OFICIAL ================');
  log(`RUN_ID: ${runId}`);
  log(`requests ${st.requests.ejecutados} (fallidos ${st.requests.fallidos}) | assertions ${st.assertions.total} (fallidas ${st.assertions.fallidas})`);
  log(`POST /calibrar ejecutados: ${preservado.postCalibrar}/${POST_BUDGET} | /gestionar: ${preservado.postGestionar} | PATCH: ${preservado.patchs} | STOP_ALL: ${preservado.stopAll}`);
  for (const rol of ['productor', 'contador']) {
    const c = preservado[rol].calibrar;
    log(`  ${rol}: HTTP ${c.http} | error_code ${c.cuerpo?.error_code} | mensaje ${c.cuerpo?.message === EXP_MSG_403 ? 'EXACTO' : 'NO COINCIDE'}`);
  }
  if (preservado.failures.length) {
    log('\nFAILURES:');
    preservado.failures.forEach((x, i) => log(`  ${i + 1}. ${x.item} :: ${x.assertion} :: ${x.error}`));
  }
  log('=============================================\n');
  log(`HTML: ${path.relative(EVAL_DIR, html).split(path.sep).join('/')}`);
  log('Ejecute ahora el modo close para la verificación final y la evidencia.');
  if (preservado.failures.length) process.exitCode = 2;
}

// ---------------------------------------------------------------------------------- close
async function modoClose() {
  const tmp = SUMMARY_TMP();
  const evidenciaPath = path.join(RUN_DIR, 'evidencia.json');

  // Idempotencia: si el summary ya se retiró, solo se recalcula lo que no depende del RUN.
  if (!fs.existsSync(tmp)) {
    if (!fs.existsSync(evidenciaPath)) throw new Error('No hay summary del RUN ni evidencia previa: ejecute primero G77_MODO=run.');
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
  const buscar = (c, correo) => ((c?.items || c?.usuarios || []).find(x => (x.correo_electronico || x.correo) === correo) || null);

  // --------------------------------------------- verificación final: SOLO LECTURA
  // Se autentica DESPUÉS del RUN, nunca antes, y solo para GET.
  const tokenAdmin = await login(ACTORES.admin.email, ACTORES.admin.secret);
  const detProd = await get(`/usuarios/${R.ids.productor}/detalle`, tokenAdmin);
  const detCont = await get(`/usuarios/${R.ids.contador}/detalle`, tokenAdmin);
  const tokenIng = await login(ACTORES.ing.email, ACTORES.ing.secret);
  const dispFinal = await get(`/configuracion/dispositivos-iot/${FIX.dispositivo}`, tokenIng);
  const asocFinal = await get(`/configuracion/sensores/${FIX.sensor}/asociaciones`, tokenIng);
  const histFinal = await get(`/configuracion/sensores/${FIX.sensor}/calibraciones`, tokenIng);
  const rangosFinal = await get('/configuracion/sensores/rangos-calibracion', tokenIng);
  const rangoFinal = (rangosFinal.cuerpo?.items || []).find(x => x.categoria === FIX.categoria) || null;
  const idsFinales = (histFinal.cuerpo?.items || []).map(x => x.id_calibracion);
  const estadoFinal = (d) => d.cuerpo?.estado_cuenta ?? d.cuerpo?.estado ?? null;

  // ----------------------------------------------------------- oráculo por subescenario
  const casos = {};
  for (const [rol, etiqueta, rolEsperado, correo] of [
    ['productor', 'Productor', 'Productor', ACTORES.productor.email],
    ['contador', 'Contador', 'Contador', ACTORES.contador.email]
  ]) {
    const b = R[rol];
    const pre = b.pre.cuerpo, post = b.post.cuerpo, resp = b.calibrar.cuerpo, ident = b.identidad.cuerpo;
    const preIds = pre ? (pre.items || []).map(x => x.id_calibracion) : null;
    const postIds = post ? (post.items || []).map(x => x.id_calibracion) : null;
    const nuevos = preIds && postIds ? postIds.filter(x => !preIds.includes(x)) : null;
    const actorId = Number(R.ids[rol]);
    const atribuibles = post ? (post.items || []).filter(x => (nuevos || []).includes(x.id_calibracion) && x.id_usuario === actorId).map(x => x.id_calibracion) : null;
    const obtenido = resp ? resp.message ?? null : null;
    const estadoOriginal = R.estadosOriginales[rol];
    const final = rol === 'productor' ? estadoFinal(detProd) : estadoFinal(detCont);

    let historicosIntactos = null;
    if (pre && post) {
      historicosIntactos = (pre.items || []).every(s => {
        const row = (post.items || []).find(x => x.id_calibracion === s.id_calibracion);
        return row && String(row.valor_referencia) === String(s.valor_referencia) &&
          row.fecha_calibracion === s.fecha_calibracion && row.id_usuario === s.id_usuario &&
          row.observaciones === s.observaciones;
      });
    }
    const assertionsFuncionales = [...b.login.assertions, ...b.identidad.assertions, ...b.permisos.assertions,
      ...b.pre.assertions, ...b.calibrar.assertions, ...b.post.assertions];

    const oraculo = {
      cuenta_activa_al_ejecutar: ident?.estado_cuenta === 'Activo',
      identidad_confirmada: ident?.correo_electronico === correo && ident?.nombre_rol === rolEsperado,
      http_403: b.calibrar.http === 403,
      mensaje_exacto: obtenido === EXP_MSG_403,
      sin_id_calibracion: resp ? resp.id_calibracion === undefined : false,
      sin_persistencia: Array.isArray(nuevos) && nuevos.length === 0,
      sin_calibracion_atribuible_al_actor: Array.isArray(atribuibles) && atribuibles.length === 0,
      total_sin_cambios: Boolean(pre) && Boolean(post) && Number(pre.total) === Number(post.total),
      ids_identicos: Boolean(preIds) && Boolean(postIds) && JSON.stringify(preIds.slice().sort()) === JSON.stringify(postIds.slice().sort()),
      historial_intacto: historicosIntactos === true,
      estado_final_igual_al_original: String(final) === String(estadoOriginal),
      assertions_funcionales_todas_pass: assertionsFuncionales.length > 0 && assertionsFuncionales.every(a => a.paso)
    };

    casos[rol] = {
      subescenario: etiqueta,
      usuario: correo,
      id_usuario: actorId,
      estado_original: estadoOriginal,
      setup: {
        requerido: estadoOriginal === 'Activo' ? 'NO' : 'SI',
        ejecutado: 'NO',
        http: null,
        estado_post_setup: null,
        nota: estadoOriginal === 'Activo'
          ? 'NO APLICABA: la cuenta ya estaba Activo, no se ejecuto POST /usuarios/{id}/gestionar'
          : 'la cuenta no estaba Activo: la corrida se habria detenido antes del POST para autorizacion de QA'
      },
      identidad: { http: b.identidad.http, correo: ident?.correo_electronico ?? null, id_usuario: ident?.id_usuario ?? null, rol: ident?.nombre_rol ?? null, estado_cuenta: ident?.estado_cuenta ?? null },
      permisos: {
        total: (b.permisos.cuerpo?.permisos || []).length,
        acciones_recurso_12: R.permisosRecurso12[rol],
        permiso_de_creacion_inesperado: (b.permisos.cuerpo?.permisos || []).some(p => p.id_recurso === 12 && p.id_accion === 1),
        nota: 'contexto RBAC observado; no se convierte en requisito nuevo del caso'
      },
      actorDeLecturaDelHistorial: 'Ingeniero de Campo (discovery, solo GET): el propio actor no puede leer el historial y el Administrador tampoco tiene alcance sobre el sensor del fixture',
      historialPre: pre ? { total: pre.total, ids: preIds, items: pre.items || [] } : null,
      request: { endpoint: `/configuracion/sensores/${FIX.sensor}/calibrar`, metodo: 'POST', headers: { Authorization: '[REDACTED]', 'Content-Type': 'application/json' }, body: b.calibrar.enviado },
      response: { http: b.calibrar.http, cuerpo: resp, error_code: resp?.error_code ?? null, id_calibracion: resp?.id_calibracion ?? null, capturado: new Date().toISOString() },
      httpEsperado: 403,
      mensajeEsperado: EXP_MSG_403,
      mensajeObtenido: obtenido,
      mensajeCoincide: obtenido === EXP_MSG_403,
      comparacionLiteral: obtenido === EXP_MSG_403
        ? { tipo: 'igualdad literal', resultado: 'coincide caracter a caracter' }
        : { tipo: 'igualdad literal', resultado: 'no coincide', esperado: EXP_MSG_403, obtenido },
      historialPost: post ? { total: post.total, ids: postIds, items: post.items || [] } : null,
      idsNuevos: nuevos,
      idsAtribuiblesAlActor: atribuibles,
      historicosIntactos,
      restauracion: {
        requerida: estadoOriginal === 'Activo' ? 'NO APLICABA' : 'SI',
        ejecutada: 'NO',
        estado_original: estadoOriginal,
        estado_final: final,
        coincide: String(final) === String(estadoOriginal),
        pendiente: false,
        nota: estadoOriginal === 'Activo' ? 'NO APLICABA: la cuenta nunca fue modificada' : null
      },
      assertionsFuncionales: { total: assertionsFuncionales.length, fallidas: assertionsFuncionales.filter(a => !a.paso).length, detalle: assertionsFuncionales },
      oraculo,
      resultado: b.calibrar.http === null ? 'BLOQUEADO'
        : Object.values(oraculo).every(x => x === true) ? 'APROBADO' : 'RECHAZADO'
    };
  }

  const newmanLimpio = R.failures.length === 0 && (R.stats.requests.fallidos || 0) === 0;
  const restauracionPendiente = Object.values(casos).some(c => c.restauracion.pendiente);
  const rechazados = Object.values(casos).filter(c => c.resultado === 'RECHAZADO').length;
  const bloqueados = Object.values(casos).filter(c => c.resultado === 'BLOQUEADO').length;
  const resultadoGrupo = bloqueados > 0 ? 'BLOQUEADO'
    : rechazados > 0 ? 'RECHAZADO'
    : (newmanLimpio && !restauracionPendiente) ? 'APROBADO' : 'RECHAZADO';

  // ------------------------------------------------------- comparación con la primera
  const PRIMERA = {
    runId: 'run-20261007-080541',
    fuente: 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G77-v2.0/RESULTADOS/run-20261007-080541/TC-M09-G77_resultado.md',
    mensajeObtenido: 'Acceso denegado. Su rol no tiene permisos para realizar esta operación.',
    productor: { resultado: 'RECHAZADO', http: '403 correcto', persistencia: 'Correcta', mensaje: 'Incorrecto' },
    contador: { resultado: 'RECHAZADO', http: '403 correcto', persistencia: 'Correcta', mensaje: 'Incorrecto' },
    grupo: 'RECHAZADO'
  };
  const comparacion = {
    baselineUnico: `PRIMERA EVALUACION OFICIAL ${PRIMERA.runId}`,
    fuente: PRIMERA.fuente,
    porSubescenario: Object.fromEntries(['productor', 'contador'].map(rol => [casos[rol].subescenario, {
      primera: PRIMERA[rol].resultado,
      segunda: casos[rol].resultado,
      cambio: casos[rol].resultado === PRIMERA[rol].resultado ? 'SIN CAMBIO' : `${PRIMERA[rol].resultado} -> ${casos[rol].resultado}`,
      dimensiones: {
        http: { primera: PRIMERA[rol].http, segunda: `${casos[rol].response.http} ${casos[rol].oraculo.http_403 ? 'correcto' : 'incorrecto'}` },
        no_persistencia: { primera: PRIMERA[rol].persistencia, segunda: casos[rol].oraculo.sin_persistencia ? 'Correcta' : 'INCORRECTA' },
        mensaje: { primera: PRIMERA[rol].mensaje, segunda: casos[rol].mensajeCoincide ? 'Correcto (literal)' : 'Incorrecto' }
      },
      mensajeAntes: PRIMERA.mensajeObtenido,
      mensajeAhora: casos[rol].mensajeObtenido,
      mensajeEsperado: EXP_MSG_403,
      causaAnteriorCorregida: casos[rol].mensajeCoincide ? 'SI' : 'NO'
    }])),
    grupo: { primera: PRIMERA.grupo, segunda: resultadoGrupo, cambio: resultadoGrupo === PRIMERA.grupo ? 'SIN CAMBIO' : `${PRIMERA.grupo} -> ${resultadoGrupo}` },
    causaDelRechazoAnterior: Object.values(casos).every(c => c.mensajeCoincide) ? 'CORREGIDA'
      : Object.values(casos).some(c => c.mensajeCoincide) ? 'PARCIALMENTE CORREGIDA' : 'NO CORREGIDA'
  };

  const mensajeAnteriorPersiste = Object.values(casos).some(c => c.mensajeObtenido === PRIMERA.mensajeObtenido);
  const anomalia = Object.values(casos).some(c => c.response.http === null || c.response.http >= 500 || !c.oraculo.http_403 || !c.oraculo.sin_persistencia);

  const adminLoc = buscar(R.localizacion.productor.cuerpo, ACTORES.productor.email);

  const evidencia = {
    run_id: runId, evaluacion: 'SEGUNDA EVALUACION',
    grupo: GRUPO, caso: CASO, requisito: RF, caso_de_uso: CU,
    herramienta: 'Newman',
    ambiente: { decisorio: 'TEST', base_url: base() },
    carpeta: `tests/Test_Testing/Test_Modulo9/RF-24/${GRUPO}/EvaluacionV2/`,
    rama: R.gitPre.rama, commit: R.gitPre.commit,
    resultado_caso: resultadoGrupo, resultado_grupo: resultadoGrupo,

    git_pre: R.gitPre,

    actores: {
      nota: 'La coleccion Newman es duena de todas las sesiones: hace sus propios logins y publica los tokens en ing_session, admin_session, productor_session y contador_session. El runner no inicia sesion antes de Newman ni inyecta ningun token.',
      administrador_de_setup: {
        correo: ACTORES.admin.email,
        login_http: R.adminLogin.http,
        rol_esperado: 'Administrador',
        credencial: '[REDACTED]',
        uso: 'localizar a los actores, capturar su estado de cuenta original y consultar estados en la verificacion final. No ejecuto ningun POST /calibrar ni /gestionar.',
        alternativo_necesario: 'NO'
      },
      ingeniero_de_discovery: {
        correo: ACTORES.ing.email,
        login_http: R.ingLogin.http,
        credencial: '[REDACTED]',
        uso: 'solo GET: fixture (dispositivo, sensores, asociacion, rango) e historial PRE/POST del sensor del caso. No es actor negativo y no ejecuto ningun POST /calibrar.',
        motivo: 'el Productor recibe 404 y el Contador 403 en el historial, y el Administrador no tiene alcance sobre el dispositivo 3 ni el sensor 6 en el estado actual de TEST: el Ingeniero es el unico actor que obtiene un PRE confiable.'
      }
    },

    localizacion_de_actores: {
      productor: { http: R.localizacion.productor.http, id_usuario: R.ids.productor, estado_original: R.estadosOriginales.productor, encontrado: Boolean(adminLoc) },
      contador: { http: R.localizacion.contador.http, id_usuario: R.ids.contador, estado_original: R.estadosOriginales.contador },
      nota: 'Localizados dentro de Newman con admin_session. Los ids de la primera evaluacion (35 y 5) son referencia; los valores vigentes son los obtenidos por API.'
    },

    estados_originales: R.estadosOriginales,

    setup: {
      productor: casos.productor.setup,
      contador: casos.contador.setup,
      post_gestionar_ejecutados: R.postGestionar,
      patch_ejecutados: R.patchs
    },

    fixture: {
      sensor: (() => {
        const row = (R.fixture.sensores.cuerpo?.items || []).find(x => sid(x) === FIX.sensor) || null;
        return row ? { id: sid(row), nombre: row.nombre, categoria: row.categoria, es_activo: row.es_activo, id_dispositivo_iot: row.id_dispositivo_iot } : null;
      })(),
      dispositivo: R.fixture.dispositivo.cuerpo ? { id: R.fixture.dispositivo.cuerpo.id_dispositivo_iot, serial: R.fixture.dispositivo.cuerpo.serial, es_activo: R.fixture.dispositivo.cuerpo.es_activo } : null,
      asociacionVigente: (() => {
        const a = (R.fixture.asociaciones.cuerpo?.items || []).find(x => vig(x) && sid(x) === FIX.sensor && x.id_dispositivo_iot === FIX.dispositivo) || null;
        return a ? { id_dispositivo_iot: a.id_dispositivo_iot, id_infraestructura: a.id_infraestructura, tiene_estado: a.tiene_estado, fecha_finalizacion: a.fecha_finalizacion } : null;
      })(),
      categoria: FIX.categoria,
      rango: (() => {
        const r = (R.fixture.rangos.cuerpo?.items || []).find(x => x.categoria === FIX.categoria) || null;
        return r ? { categoria: FIX.categoria, min: String(r.valor_min), max: String(r.valor_max) } : null;
      })(),
      valorEnviado: FIX.valor,
      valorEstrictamenteInterior: (() => {
        const r = (R.fixture.rangos.cuerpo?.items || []).find(x => x.categoria === FIX.categoria) || null;
        return Boolean(r) && Number(FIX.valor) > Number(r.valor_min) && Number(FIX.valor) < Number(r.valor_max);
      })(),
      observaciones: OBSERVACIONES,
      nota: 'Fixture oficial del caso reutilizado. El request es funcionalmente valido: la unica causa intencional de rechazo es el ROL no autorizado.'
    },

    Productor: casos.productor,
    Contador: casos.contador,

    restauracion: {
      productor: casos.productor.restauracion,
      contador: casos.contador.restauracion,
      pendiente: restauracionPendiente,
      post_restauracion_ejecutados: 0,
      nota: 'Ninguna cuenta fue modificada: ambas estaban Activo, de modo que no hubo activacion temporal ni restauracion que ejecutar.'
    },

    newman: {
      html: `newman/newman-${GRUPO}.html`,
      htmlPersistentes: 1,
      coleccionEjecutada: `${R.itemsEjecutables} de ${R.itemsTotales} items`,
      iterations: R.stats.iterations,
      requests: R.stats.requests,
      assertions: R.stats.assertions,
      failures: R.failures,
      presupuesto: {
        postCalibrarPlanificados: POST_BUDGET, postCalibrarEjecutados: R.postCalibrar,
        postSetupEjecutados: R.postGestionar, postRestauracionEjecutados: 0,
        patchEjecutados: R.patchs, reintentos: 0
      },
      stopAll: R.stopAll,
      stopAllMotivo: R.stopAllMotivo ? JSON.parse(R.stopAllMotivo) : null,
      limpio: newmanLimpio
    },

    verificacion_final: {
      soloLectura: true, sqlEjecutado: 'ninguno', escriturasEnLaVerificacion: 0,
      fecha: new Date().toISOString(),
      nota: 'Autenticacion posterior al RUN, exclusivamente para GET de verificacion.',
      productor: { estado_original: R.estadosOriginales.productor, estado_final: estadoFinal(detProd), coincide: String(estadoFinal(detProd)) === String(R.estadosOriginales.productor), http: detProd.status },
      contador: { estado_original: R.estadosOriginales.contador, estado_final: estadoFinal(detCont), coincide: String(estadoFinal(detCont)) === String(R.estadosOriginales.contador), http: detCont.status },
      dispositivo: { id: FIX.dispositivo, http: dispFinal.status, es_activo: dispFinal.cuerpo?.es_activo ?? null, sigueActivo: dispFinal.cuerpo?.es_activo === true },
      asociacionVigente: (() => {
        const vigentes = (asocFinal.cuerpo?.items || []).filter(x => vig(x) && sid(x) === FIX.sensor).map(x => ({ id_dispositivo_iot: x.id_dispositivo_iot, id_infraestructura: x.id_infraestructura }));
        return { vigentes, sigueAsociadoAlArea: vigentes.some(x => x.id_infraestructura === FIX.area && x.id_dispositivo_iot === FIX.dispositivo) };
      })(),
      historialFinal: { total: histFinal.cuerpo?.total ?? null, ids: idsFinales },
      rango: rangoFinal ? { categoria: FIX.categoria, min: String(rangoFinal.valor_min), max: String(rangoFinal.valor_max), sinCambios: Number(rangoFinal.valor_min) === Number(FIX.rangoEsperado.min) && Number(rangoFinal.valor_max) === Number(FIX.rangoEsperado.max) } : null,
      calibracionesAtribuiblesAlProductor: (histFinal.cuerpo?.items || []).filter(x => x.id_usuario === Number(R.ids.productor)).map(x => x.id_calibracion),
      calibracionesAtribuiblesAlContador: (histFinal.cuerpo?.items || []).filter(x => x.id_usuario === Number(R.ids.contador)).map(x => x.id_calibracion),
      calibracionesConLasObservacionesDelCaso: (histFinal.cuerpo?.items || []).filter(x => x.observaciones === OBSERVACIONES).map(x => x.id_calibracion)
    },

    contraste_dev: {
      necesario: anomalia || mensajeAnteriorPersiste,
      motivo: anomalia
        ? 'TEST presenta una anomalia relevante: procede contraste de solo lectura en DEV.'
        : mensajeAnteriorPersiste
          ? 'TEST conserva el mensaje generico de la primera evaluacion: procede contrastar DEV para distinguir defecto de aplicacion de desfase de despliegue.'
          : 'TEST paso completamente: ambos roles devolvieron 403 con el mensaje literal del requisito y sin persistencia. No se uso DEV.',
      peticiones_a_dev: 0
    },

    comparacion_primera_segunda: comparacion,
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
  for (const rol of ['productor', 'contador']) {
    const c = casos[rol];
    log(`${c.subescenario}: id ${c.id_usuario} | estado ${c.estado_original} | HTTP ${c.response.http}/${c.httpEsperado} | error_code ${c.response.error_code} | mensaje ${c.mensajeCoincide ? 'EXACTO' : 'NO COINCIDE'} | PRE ${c.historialPre?.total} POST ${c.historialPost?.total} | nuevos ${JSON.stringify(c.idsNuevos)} -> ${c.resultado}`);
  }
  log(`CASO ${CASO} -> ${resultadoGrupo}`);
  log(`GRUPO ${GRUPO} -> ${resultadoGrupo}`);
  log(`Newman: requests ${R.stats.requests.ejecutados} (fallidos ${R.stats.requests.fallidos}) | assertions ${R.stats.assertions.total} (fallidas ${R.stats.assertions.fallidas}) | limpio ${newmanLimpio ? 'SI' : 'NO'}`);
  log(`POST /calibrar ${R.postCalibrar}/${POST_BUDGET} | setup ${R.postGestionar} | restauracion 0 | PATCH ${R.patchs} | STOP_ALL ${R.stopAll}`);
  log(`Restauracion pendiente: ${restauracionPendiente ? 'SI' : 'NO'}`);
  log(`Causa del rechazo anterior: ${comparacion.causaDelRechazoAnterior}`);
  log(`Contraste DEV necesario: ${evidencia.contraste_dev.necesario ? 'SI' : 'NO'}`);
  log(`Evidencia limpia de secretos: ${evidencia.seguridad.limpio ? 'SI' : 'NO'}`);
  log('========================================\n');

  if (!evidencia.seguridad.limpio) process.exitCode = 3;
  else if (resultadoGrupo !== 'APROBADO') process.exitCode = 2;
}

// --------------------------------------------------------------------------- manifiesto
function refrescarManifest() {
  const artefactos = [
    { archivo: 'run-g77-v2.cjs', abs: path.join(__dirname, 'run-g77-v2.cjs'),
      ruta: `${GRUPO}/EvaluacionV2/automation/run-g77-v2.cjs`,
      funcion: 'Runner unico de la reevaluacion, con los modos precheck (Newman de validacion previa, sin HTML ni archivos), run (RUN funcional oficial con los 2 POST y el unico HTML) y close (verificacion final de solo lectura y consolidacion de evidencia). No inyecta tokens a Newman y no ejecuta PATCH ni /gestionar.' },
    { archivo: 'TC-M09-G77-v2.0.postman_collection.json', abs: COLECCION,
      ruta: `${GRUPO}/EvaluacionV2/TC-M09-G77-v2.0.postman_collection.json`,
      funcion: 'Copia de la coleccion funcional para EvaluacionV2. Cambios de infraestructura: los 3 GET de fixture leen con ing_session porque el Administrador perdio alcance, y la localizacion de actores y la captura de estados originales se hacen dentro de Newman con admin_session. El oraculo funcional (2 POST /calibrar, HTTP 403, mensaje exacto, assertions) es el de la primera evaluacion.' },
    { archivo: 'TC-M09-G77-v2.0.postman_collection.json (original)', abs: COLECCION_ORIGINAL,
      ruta: `${GRUPO}/TC-M09-G77-v2.0.postman_collection.json`,
      funcion: 'Coleccion funcional de la primera evaluacion. Reutilizada como fuente, en solo lectura; no fue modificada.' },
    { archivo: 'helpers.cjs (original)', abs: path.join(CASE_DIR, 'helpers.cjs'),
      ruta: `${GRUPO}/helpers.cjs`,
      funcion: 'Helpers de la primera evaluacion. NO se utilizan en esta reevaluacion: el runner unico no los requiere. Se registran por trazabilidad del baseline.' }
  ];
  const previoPath = path.join(RUN_DIR, 'automation_manifest.json');
  const previo = fs.existsSync(previoPath) ? JSON.parse(fs.readFileSync(previoPath, 'utf8')) : null;
  const shaPrevio = previo ? Object.fromEntries((previo.artefactos || []).map(a => [a.archivo, a.sha256])) : {};
  const filas = artefactos.map(a => {
    if (!fs.existsSync(a.abs)) return { archivo: a.archivo, ruta: `tests/Test_Testing/Test_Modulo9/RF-24/${a.ruta}`, funcion: a.funcion, sha256: null, estado: 'AUSENTE' };
    const actual = sha256(a.abs);
    const fila = { archivo: a.archivo, ruta: `tests/Test_Testing/Test_Modulo9/RF-24/${a.ruta}`, funcion: a.funcion, sha256: actual, bytes: fs.statSync(a.abs).size };
    if (shaPrevio[a.archivo] && shaPrevio[a.archivo] !== actual) fila.sha256_anterior = shaPrevio[a.archivo];
    return fila;
  });
  fs.writeFileSync(previoPath, limpiar(JSON.stringify({
    grupo: GRUPO, caso: CASO, runId,
    nota: 'Artefactos finales de la SEGUNDA EVALUACION. Los ejecutables viven unicamente en EvaluacionV2/; no se duplica automation dentro de RESULTADOS.',
    newmanHtmlPersistentes: 1,
    automationDentroDeResultados: 'NO',
    artefactos: filas
  }, null, 2)));
}
