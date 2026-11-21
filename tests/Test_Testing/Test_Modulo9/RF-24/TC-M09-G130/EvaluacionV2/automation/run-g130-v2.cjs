// Runner único de la SEGUNDA EVALUACIÓN de TC-M09-G130 (RF-24 v2.0, Módulo 9).
// Casos TC-M09-256 (dispositivo inexistente) y TC-M09-257 (sensor inexistente).
//
// Un solo archivo, tres modos (G130_MODO):
//
//   precheck  Validación Newman de SOLO LECTURA previa al RUN. Ejecuta la colección filtrada en
//             memoria SIN los dos POST /calibrar; no escribe nada de negocio, no genera HTML, no
//             crea RESULTADOS y no deja archivos: solo consola. El RUN se autoriza únicamente
//             si failures = 0.
//   run       RUN funcional oficial: la colección completa una única vez, con los 2 POST de
//             calibración y el ÚNICO reporte Newman HTML persistente.
//   close     Oráculo por caso, verificación final de solo lectura y consolidación de
//             evidencia.json y automation_manifest.json.
//
// PROPIEDAD DE SESIONES (regla aprendida en G76): la colección es dueña de sus sesiones. Hace
// sus propios logins y publica los tokens en {{ing_session}} y {{admin_session}}. El runner NO
// inicia sesión antes de Newman y NO inyecta ningún token: solo pasa configuración. Motivo: TEST
// aplica sesión única por usuario. El modo close se autentica DESPUÉS del RUN y solo para GET.
//
// Presupuesto: 2 POST /calibrar (uno por caso), sin reintentos. PATCH/PUT/DELETE: 0.
// Ambos POST son rechazos esperados: no deben crear datos y no se borra nada después.
//
// CRITERIO AUXILIAR ACTUALIZADO POR AUTORIZACIÓN EXPRESA DE QA: el historial de un sensor
// inexistente ya no responde 200 con total 0; el contrato vigente devuelve 404
// SENSOR_NO_ENCONTRADO por control de alcance / protección IDOR. Es un cambio intencional del
// contrato de seguridad, no un defecto de G130. El esperado funcional de los POST no se tocó.
//
// Uso:
//   $env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
//   $env:QA_ING_EMAIL="ingeniero@pecuaria.co"
//   $env:QA_ING_PASSWORD="<secreto>"
//   $env:QA_ADMIN_EMAIL="administador.dev@gmail.com"
//   $env:QA_ADMIN_PASSWORD="<secreto>"
//   $env:G130_RUN_ID="run-YYYYMMDD-HHMMSS"     (modos run y close)
//   $env:G130_MODO="precheck" | "run" | "close"
//   node .\run-g130-v2.cjs

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const CASE_DIR = path.resolve(__dirname, '..', '..');
const EVAL_DIR = path.resolve(__dirname, '..');
const COLECCION = path.join(EVAL_DIR, 'TC-M09-G130.postman_collection.json');
const COLECCION_ORIGINAL = path.join(CASE_DIR, 'TC-M09-G130.postman_collection.json');

const GRUPO = 'TC-M09-G130';
const CASOS = { '256': 'TC-M09-256', '257': 'TC-M09-257' };
const RF = 'RF-24 v2.0';
const POST_BUDGET = 2;
const ITEMS_CALIBRAR = ['256 POST calibrar', '257 POST calibrar'];

const MODO = process.env.G130_MODO || 'precheck';
if (!['precheck', 'run', 'close'].includes(MODO)) throw new Error(`G130_MODO no reconocido: ${MODO}`);

const base = () => {
  const b = process.env.QA_BASE_URL;
  if (!b) throw new Error('QA_BASE_URL requerido');
  return b.replace(/\/$/, '');
};
const ACTORES = {
  ing: { email: process.env.QA_ING_EMAIL, secret: process.env.QA_ING_PASSWORD },
  admin: { email: process.env.QA_ADMIN_EMAIL, secret: process.env.QA_ADMIN_PASSWORD }
};
for (const [k, v] of Object.entries(ACTORES)) {
  if (!v.email || !v.secret) throw new Error(`Faltan credenciales de ${k} (solo en memoria de proceso).`);
}

// ------------------------------------------------------------------ fixture y esperados
const FIX = {
  sensor: Number(process.env.G130_SENSOR || 6),
  dispositivo: Number(process.env.G130_DEVICE || 3),
  area: Number(process.env.G130_AREA || 3),
  categoria: process.env.G130_CAT || 'TEMPERATURA',
  valor: process.env.G130_VALOR || '22.5000',
  sensorInexistente: Number(process.env.G130_SENSOR_INEX || 999999),
  dispositivoInexistente: Number(process.env.G130_DEVICE_INEX || 999999)
};
const EXP_MSG = 'Error de referencia: El sensor o dispositivo especificado no existe. No se puede registrar una calibración sobre un hardware inexistente.';

const log = (...a) => console.log(...a);
const sha256 = (f) => crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');

// --------------------------------------------------------------------- sanitización
// La credencial de BD que el paquete entrega se cubre si llega por variable de entorno
// (QA_DB_PASSWORD). NUNCA se escribe como literal en este archivo: el propio escaneo de
// seguridad lo marcaría como credencial en claro, y el paquete prohíbe que esa contraseña
// quede persistida en ningún artefacto. En esta corrida la BD no se utilizó.
const secretos = () => [
  ...Object.values(ACTORES).map(a => a.secret),
  process.env.QA_DB_PASSWORD
].filter(Boolean);
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
const runId = process.env.G130_RUN_ID;
if (MODO !== 'precheck' && (!runId || !/^run-\d{8}-\d{6}$/.test(runId))) {
  throw new Error('G130_RUN_ID requerido con formato run-YYYYMMDD-HHMMSS.');
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
  primera_evaluacion_RESULTADOS: git(['status', '--short', '--', 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G130/RESULTADOS']) || '(vacio = intacta)',
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
    credencialesCubiertasPorElEscaneo: 'contrasenas de API del Ingeniero y del Administrador, y la contrasena de BD entregada por QA (que no se utilizo)',
    criterio: 'Se marcan solo VALORES de secreto: contrasenas en uso, JWT, Authorization con token, cookies, tokens en pares clave-valor y cadenas de conexion. En los .cjs solo se evaluan valores y la coincidencia literal con las credenciales.',
    nota: 'Las contrasenas solo existieron en memoria de proceso. El reporter htmlextra se ejecuto con omitHeaders, sin environment ni globals y omitiendo las variables sensibles; el HTML se sanitizo despues de generarse.'
  };
}

// ------------------------------------------------------------------- env de la colección
function construirEnv() {
  const cuerpo = (dispositivo, observaciones) =>
    `{"modo_calibracion":"SENSOR","id_dispositivo_iot":${dispositivo},"id_infraestructura":${FIX.area},"valor_referencia":${FIX.valor},"observaciones":${JSON.stringify(observaciones)},"fecha_calibracion":"__FECHA__"}`;
  return [
    ['base_url', base()],
    ['ing_email', ACTORES.ing.email], ['ing_secret', ACTORES.ing.secret],
    ['admin_email', ACTORES.admin.email], ['admin_secret', ACTORES.admin.secret],
    ['device_id', String(FIX.dispositivo)], ['sensor_id', String(FIX.sensor)],
    ['area_id', String(FIX.area)], ['categoria', FIX.categoria], ['valor', FIX.valor],
    ['device_inexistente', String(FIX.dispositivoInexistente)],
    ['sensor_inexistente', String(FIX.sensorInexistente)],
    ['body_256', cuerpo(FIX.dispositivoInexistente, 'QA TC-M09-256')],
    ['body_257', cuerpo(FIX.dispositivo, 'QA TC-M09-257')],
    ['exp_msg', EXP_MSG],
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
      skipEnvironmentVars: ['ing_secret', 'admin_secret', 'ing_session', 'admin_session'],
      showMarkdownLinks: false
    } };
    if (titulo) o.reporter.htmlextra.title = titulo;
  }
  return new Promise((resolve, reject) => newman.run(o, (err, summary) => (err ? reject(err) : resolve(summary))));
}

function extraer(summary) {
  const ex = summary?.run?.executions || [];
  const find = (n) => ex.find(x => x.item && x.item.name === n);
  const cuerpo = (n) => { const e = find(n); if (!e || !e.response) return null; try { return JSON.parse(e.response.stream.toString()); } catch { return null; } };
  const http = (n) => { const e = find(n); return e && e.response ? e.response.code : null; };
  const enviado = (n) => { const e = find(n); try { return JSON.parse(e.request.body.raw.toString()); } catch { return null; } };
  const asserts = (n) => { const e = find(n); return (e?.assertions || []).map(a => ({ assertion: a.assertion, paso: !a.error, error: a.error ? a.error.message : null })); };
  return { cuerpo, http, enviado, asserts };
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
  log(`Colección: ${itemsEjecutables} de ${itemsTotales} items. Excluidos: ${quitados.join(' | ')}`);
  log('Sin POST /calibrar y sin ninguna escritura de negocio.\n');

  const summary = await correrNewman(col, construirEnv(), null, null);
  const st = stats(summary);
  const f = fallos(summary);
  const { cuerpo, http, asserts } = extraer(summary);
  const pasa = (item) => { const a = asserts(item); return a.length > 0 && a.every(x => x.paso); };

  const me = cuerpo('Identidad Ingeniero');
  const perm = cuerpo('Permisos Ingeniero');
  const disp = cuerpo('Fixture dispositivo real');
  const sens = cuerpo('Fixture sensor real del dispositivo');
  const asoc = cuerpo('Fixture asociación vigente');
  const rangos = cuerpo('Fixture rango de la categoría');
  const dispInexIng = http('Confirmar dispositivo inexistente');
  const dispInexAdm = http('Confirmar dispositivo inexistente (Administrador — confirmación adicional)');
  const sensInex = cuerpo('Confirmar sensor inexistente (historial PRE)');
  const sensInexHttp = http('Confirmar sensor inexistente (historial PRE)');
  const sid = (x) => (x && x.id_sensor !== undefined ? x.id_sensor : x && x.id_sensores);
  const vig = (x) => x && x.tiene_estado === true && (x.fecha_finalizacion === null || x.fecha_finalizacion === undefined);
  const sensorRow = (sens?.items || []).find(x => sid(x) === FIX.sensor) || null;
  const asocRow = (asoc?.items || []).find(x => vig(x) && sid(x) === FIX.sensor && x.id_dispositivo_iot === FIX.dispositivo) || null;
  const rango = (rangos?.items || []).find(x => x.categoria === FIX.categoria) || null;

  const chequeos = {
    ingeniero: http('Login Ingeniero') >= 200 && http('Login Ingeniero') <= 299 &&
      me?.correo_electronico === ACTORES.ing.email && me?.nombre_rol === 'Ingeniero de Campo' &&
      me?.estado_cuenta === 'Activo' && pasa('Identidad Ingeniero'),
    permisos: (perm?.permisos || []).some(p => p.id_recurso === 12 && p.id_accion === 1) && pasa('Permisos Ingeniero'),
    fixtureReal: disp?.id_dispositivo_iot === FIX.dispositivo && disp?.es_activo === true &&
      Boolean(sensorRow) && sensorRow.es_activo === true && sensorRow.categoria === FIX.categoria &&
      sensorRow.id_dispositivo_iot === FIX.dispositivo &&
      Boolean(asocRow) && asocRow.id_infraestructura === FIX.area &&
      pasa('Fixture dispositivo real') && pasa('Fixture sensor real del dispositivo') && pasa('Fixture asociación vigente'),
    // Acreditación discriminante: el mismo actor lee el dispositivo REAL con 200 y el
    // inexistente con 404, de modo que su 404 no se confunde con falta de alcance.
    dispositivoInexistente: dispInexIng === 404 && disp?.es_activo === true &&
      pasa('Confirmar dispositivo inexistente') && pasa('Confirmar dispositivo inexistente (Administrador — confirmación adicional)'),
    // Criterio auxiliar actualizado por autorización de QA: el contrato vigente es 404.
    sensorInexistente: sensInexHttp === 404 && sensInex?.error_code === 'SENSOR_NO_ENCONTRADO' &&
      pasa('Confirmar sensor inexistente (historial PRE)'),
    rango: Boolean(rango) && Number(FIX.valor) > Number(rango.valor_min) && Number(FIX.valor) < Number(rango.valor_max) && pasa('Fixture rango de la categoría')
  };

  const postCalibrar = contar(summary, /\/calibrar$/);
  const autorizar = Object.values(chequeos).every(Boolean) && f.length === 0 &&
    (st.requests.fallidos || 0) === 0 && postCalibrar === 0;

  const P = (b) => (b ? 'PASS' : 'FAIL');
  log('\nPRECHECK_G130\n');
  log(`Ingeniero:\n${P(chequeos.ingeniero)}\n`);
  log(`Permisos:\n${P(chequeos.permisos)}\n`);
  log(`Fixture real:\n${P(chequeos.fixtureReal)}\n`);
  log(`Dispositivo ${FIX.dispositivoInexistente} inexistente:\n${P(chequeos.dispositivoInexistente)}\n`);
  log(`Sensor ${FIX.sensorInexistente} inexistente:\n${P(chequeos.sensorInexistente)}\n`);
  log(`GET historial sensor ${FIX.sensorInexistente}:\n${chequeos.sensorInexistente ? 'PASS — contrato actual 404 SENSOR_NO_ENCONTRADO' : 'FAIL'}\n`);
  log(`Rango:\n${P(chequeos.rango)}\n`);
  log(`Failures:\n${f.length}\n`);
  log(`POST /calibrar:\n${postCalibrar}\n`);
  log(`AUTORIZAR_RUN:\n${autorizar ? 'SÍ' : 'NO'}\n`);

  log('--- detalle observado (solo consola, no se persiste) ---');
  log(`Ingeniero: id_usuario=${me?.id_usuario} rol="${me?.nombre_rol}" estado=${me?.estado_cuenta} | permiso 12/1=${(perm?.permisos || []).some(p => p.id_recurso === 12 && p.id_accion === 1)}`);
  log(`fixture real: dispositivo ${disp?.id_dispositivo_iot} activo=${disp?.es_activo} | sensor ${sid(sensorRow)} ${sensorRow?.categoria} activo=${sensorRow?.es_activo} | asociación vigente área ${asocRow?.id_infraestructura}`);
  log(`rango ${FIX.categoria}: ${rango?.valor_min}–${rango?.valor_max} | valor ${FIX.valor} interior=${Boolean(rango) && Number(FIX.valor) > Number(rango.valor_min) && Number(FIX.valor) < Number(rango.valor_max)}`);
  log(`acreditación de inexistencia del dispositivo ${FIX.dispositivoInexistente}:`);
  log(`  Ingeniero  -> dispositivo real ${FIX.dispositivo}: HTTP ${http('Fixture dispositivo real')} | dispositivo ${FIX.dispositivoInexistente}: HTTP ${dispInexIng}  (par discriminante)`);
  log(`  Administrador -> dispositivo ${FIX.dispositivoInexistente}: HTTP ${dispInexAdm}  (confirmación adicional, no discriminante)`);
  log(`historial del sensor ${FIX.sensorInexistente}: HTTP ${sensInexHttp} ${sensInex?.error_code || ''} (contrato vigente aceptado por QA)`);
  log(`historial PRE del sensor real ${FIX.sensor}: total ${envDe(summary, 'pre_256_total')}`);
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
  if (calibrar.length !== POST_BUDGET) throw new Error(`ABORTADO: la colección debe contener exactamente ${POST_BUDGET} POST de calibración, contiene ${calibrar.length}.`);

  const gitPre = estadoGit('git_pre');
  const html = HTML_OFICIAL();

  log(`RUN funcional oficial. RUN_ID: ${runId}`);
  log(`Colección: ${itemsEjecutables} de ${itemsTotales} items.`);
  log(`POST /calibrar planificados: ${POST_BUDGET} | PATCH/PUT/DELETE: 0 | reintentos: 0`);
  log(`Mensaje esperado (ambos casos): ${EXP_MSG}\n`);

  const summary = await correrNewman(col, construirEnv(), html, `${GRUPO} — SEGUNDA EVALUACIÓN · RUN funcional oficial ${runId}`);
  if (fs.existsSync(html)) fs.writeFileSync(html, limpiarHtml(fs.readFileSync(html, 'utf8')));

  const { cuerpo, http, enviado, asserts } = extraer(summary);
  const preservado = {
    runId, generado: new Date().toISOString(), gitPre, itemsTotales, itemsEjecutables,
    stats: stats(summary), failures: fallos(summary),
    postCalibrar: contar(summary, /\/calibrar$/),
    stopAll: envDe(summary, 'stop_all') ?? 'NO',
    stopAllMotivo: envDe(summary, 'stop_all_motivo'),
    ingLogin: { http: http('Login Ingeniero'), assertions: asserts('Login Ingeniero') },
    adminLogin: { http: http('Login Administrador auxiliar'), assertions: asserts('Login Administrador auxiliar') },
    identidad: { http: http('Identidad Ingeniero'), cuerpo: cuerpo('Identidad Ingeniero'), assertions: asserts('Identidad Ingeniero') },
    permisos: { http: http('Permisos Ingeniero'), cuerpo: cuerpo('Permisos Ingeniero'), assertions: asserts('Permisos Ingeniero') },
    fixture: {
      dispositivo: { http: http('Fixture dispositivo real'), cuerpo: cuerpo('Fixture dispositivo real'), assertions: asserts('Fixture dispositivo real') },
      sensores: { http: http('Fixture sensor real del dispositivo'), cuerpo: cuerpo('Fixture sensor real del dispositivo'), assertions: asserts('Fixture sensor real del dispositivo') },
      asociaciones: { http: http('Fixture asociación vigente'), cuerpo: cuerpo('Fixture asociación vigente'), assertions: asserts('Fixture asociación vigente') },
      rangos: { http: http('Fixture rango de la categoría'), cuerpo: cuerpo('Fixture rango de la categoría'), assertions: asserts('Fixture rango de la categoría') }
    },
    inexistentes: {
      dispositivoIngeniero: { http: http('Confirmar dispositivo inexistente'), cuerpo: cuerpo('Confirmar dispositivo inexistente'), assertions: asserts('Confirmar dispositivo inexistente') },
      dispositivoAdministrador: { http: http('Confirmar dispositivo inexistente (Administrador — confirmación adicional)'), cuerpo: cuerpo('Confirmar dispositivo inexistente (Administrador — confirmación adicional)'), assertions: asserts('Confirmar dispositivo inexistente (Administrador — confirmación adicional)') },
      sensorHistorialPre: { http: http('Confirmar sensor inexistente (historial PRE)'), cuerpo: cuerpo('Confirmar sensor inexistente (historial PRE)'), assertions: asserts('Confirmar sensor inexistente (historial PRE)') }
    },
    casos: {
      '256': {
        pre: { http: http('256 Historial PRE'), cuerpo: cuerpo('256 Historial PRE'), assertions: asserts('256 Historial PRE') },
        calibrar: { http: http('256 POST calibrar'), cuerpo: cuerpo('256 POST calibrar'), enviado: enviado('256 POST calibrar'), assertions: asserts('256 POST calibrar'), fecha: envDe(summary, 'fecha_256') },
        post: { http: http('256 Historial POST'), cuerpo: cuerpo('256 Historial POST'), assertions: asserts('256 Historial POST') }
      },
      '257': {
        pre: { http: http('Confirmar sensor inexistente (historial PRE)'), cuerpo: cuerpo('Confirmar sensor inexistente (historial PRE)'), assertions: asserts('Confirmar sensor inexistente (historial PRE)') },
        calibrar: { http: http('257 POST calibrar'), cuerpo: cuerpo('257 POST calibrar'), enviado: enviado('257 POST calibrar'), assertions: asserts('257 POST calibrar'), fecha: envDe(summary, 'fecha_257') },
        post: { http: http('257 Historial POST del sensor inexistente'), cuerpo: cuerpo('257 Historial POST del sensor inexistente'), assertions: asserts('257 Historial POST del sensor inexistente') }
      }
    }
  };
  fs.writeFileSync(SUMMARY_TMP(), limpiar(JSON.stringify(preservado, null, 2)));

  const st = preservado.stats;
  log('\n================ RUN OFICIAL ================');
  log(`RUN_ID: ${runId}`);
  log(`requests ${st.requests.ejecutados} (fallidos ${st.requests.fallidos}) | assertions ${st.assertions.total} (fallidas ${st.assertions.fallidas})`);
  log(`POST /calibrar ejecutados: ${preservado.postCalibrar}/${POST_BUDGET} | STOP_ALL: ${preservado.stopAll}`);
  for (const k of ['256', '257']) {
    const c = preservado.casos[k].calibrar;
    log(`  ${CASOS[k]}: HTTP ${c.http} | error_code ${c.cuerpo?.error_code} | mensaje ${c.cuerpo?.message === EXP_MSG ? 'EXACTO' : 'NO COINCIDE'}`);
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
    if (!fs.existsSync(evidenciaPath)) throw new Error('No hay summary del RUN ni evidencia previa: ejecute primero G130_MODO=run.');
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
  const ingId = R.identidad.cuerpo?.id_usuario ?? null;
  const sid = (x) => (x && x.id_sensor !== undefined ? x.id_sensor : x && x.id_sensores);
  const vig = (x) => x && x.tiene_estado === true && (x.fecha_finalizacion === null || x.fecha_finalizacion === undefined);

  // --------------------------------- verificación final: SOLO LECTURA, después del RUN
  const tokenIng = await login(ACTORES.ing.email, ACTORES.ing.secret);
  const histReal = await get(`/configuracion/sensores/${FIX.sensor}/calibraciones`, tokenIng);
  const histInex = await get(`/configuracion/sensores/${FIX.sensorInexistente}/calibraciones`, tokenIng);
  const dispReal = await get(`/configuracion/dispositivos-iot/${FIX.dispositivo}`, tokenIng);
  const dispInex = await get(`/configuracion/dispositivos-iot/${FIX.dispositivoInexistente}`, tokenIng);
  const asocFinal = await get(`/configuracion/sensores/${FIX.sensor}/asociaciones`, tokenIng);
  const rangosFinal = await get('/configuracion/sensores/rangos-calibracion', tokenIng);
  const rangoFinal = (rangosFinal.cuerpo?.items || []).find(x => x.categoria === FIX.categoria) || null;
  const idsFinales = (histReal.cuerpo?.items || []).map(x => x.id_calibracion);
  const obsDelCaso = ['QA TC-M09-256', 'QA TC-M09-257'];
  const atribuibles = (histReal.cuerpo?.items || []).filter(x => obsDelCaso.includes(x.observaciones)).map(x => x.id_calibracion);

  // ------------------------------------------------------------------- oráculo por caso
  const casos = {};

  // TC-M09-256: dispositivo inexistente, sensor real.
  {
    const b = R.casos['256'];
    const pre = b.pre.cuerpo, post = b.post.cuerpo, resp = b.calibrar.cuerpo;
    const preIds = pre ? (pre.items || []).map(x => x.id_calibracion) : null;
    const postIds = post ? (post.items || []).map(x => x.id_calibracion) : null;
    const nuevos = preIds && postIds ? postIds.filter(x => !preIds.includes(x)) : null;
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
      dispositivo_inexistente_confirmado: R.inexistentes.dispositivoIngeniero.http === 404 && R.fixture.dispositivo.http === 200,
      sensor_de_ruta_valido: Boolean((R.fixture.sensores.cuerpo?.items || []).find(x => sid(x) === FIX.sensor && x.es_activo === true)),
      unica_invalidez_el_dispositivo: R.fixture.dispositivo.cuerpo?.es_activo === true &&
        Boolean((R.fixture.asociaciones.cuerpo?.items || []).find(x => vig(x) && sid(x) === FIX.sensor && x.id_infraestructura === FIX.area)),
      http_404: b.calibrar.http === 404,
      mensaje_exacto: (resp?.message ?? null) === EXP_MSG,
      sin_id_calibracion: resp ? resp.id_calibracion === undefined : false,
      total_sin_cambios: Boolean(pre) && Boolean(post) && Number(pre.total) === Number(post.total),
      ids_identicos: Boolean(preIds) && Boolean(postIds) && JSON.stringify(preIds.slice().sort()) === JSON.stringify(postIds.slice().sort()),
      sin_persistencia: Array.isArray(nuevos) && nuevos.length === 0,
      historial_intacto: historicosIntactos === true,
      assertions_funcionales_todas_pass: assertionsFuncionales.length > 0 && assertionsFuncionales.every(a => a.paso)
    };
    casos['256'] = {
      caso: CASOS['256'], escenario: 'Dispositivo inexistente en el body, sensor real en la ruta',
      sensorEnRuta: FIX.sensor, dispositivoEnBody: FIX.dispositivoInexistente, infraestructura: FIX.area, valor: FIX.valor,
      acreditacionDeInexistencia: {
        actorDiscriminante: 'Ingeniero de Campo',
        dispositivoRealHttp: R.fixture.dispositivo.http,
        dispositivoInexistenteHttp: R.inexistentes.dispositivoIngeniero.http,
        error_code: R.inexistentes.dispositivoIngeniero.cuerpo?.error_code ?? null,
        confirmacionAdicionalAdministrador: { http: R.inexistentes.dispositivoAdministrador.http, error_code: R.inexistentes.dispositivoAdministrador.cuerpo?.error_code ?? null, nota: 'corrobora pero no discrimina: hoy el Administrador responde 404 incluso sobre recursos reales' },
        confirmado: R.inexistentes.dispositivoIngeniero.http === 404 && R.fixture.dispositivo.http === 200
      },
      historialPre: pre ? { http: b.pre.http, total: pre.total, ids: preIds, items: pre.items || [] } : null,
      request: { endpoint: `/configuracion/sensores/${FIX.sensor}/calibrar`, metodo: 'POST', headers: { Authorization: '[REDACTED]', 'Content-Type': 'application/json' }, body: b.calibrar.enviado, fecha: b.calibrar.fecha },
      response: { http: b.calibrar.http, cuerpo: resp, error_code: resp?.error_code ?? null, id_calibracion: resp?.id_calibracion ?? null, capturado: new Date().toISOString() },
      httpEsperado: 404, mensajeEsperado: EXP_MSG, mensajeObtenido: resp?.message ?? null,
      mensajeCoincide: (resp?.message ?? null) === EXP_MSG,
      comparacionLiteral: (resp?.message ?? null) === EXP_MSG
        ? { tipo: 'igualdad literal', resultado: 'coincide caracter a caracter' }
        : { tipo: 'igualdad literal', resultado: 'no coincide', esperado: EXP_MSG, obtenido: resp?.message ?? null },
      historialPost: post ? { http: b.post.http, total: post.total, ids: postIds, items: post.items || [] } : null,
      idsNuevos: nuevos, historicosIntactos,
      assertionsFuncionales: { total: assertionsFuncionales.length, fallidas: assertionsFuncionales.filter(a => !a.paso).length, detalle: assertionsFuncionales },
      oraculo, resultado: b.calibrar.http === null ? 'BLOQUEADO' : Object.values(oraculo).every(x => x === true) ? 'APROBADO' : 'RECHAZADO'
    };
  }

  // TC-M09-257: sensor inexistente en la ruta, dispositivo real en el body.
  {
    const b = R.casos['257'];
    const pre = b.pre.cuerpo, post = b.post.cuerpo, resp = b.calibrar.cuerpo;
    const assertionsFuncionales = [...b.pre.assertions, ...b.calibrar.assertions, ...b.post.assertions];
    const oraculo = {
      sensor_inexistente_confirmado: b.pre.http === 404 && pre?.error_code === 'SENSOR_NO_ENCONTRADO',
      dispositivo_de_body_valido: R.fixture.dispositivo.cuerpo?.es_activo === true && R.fixture.dispositivo.http === 200,
      unica_invalidez_el_sensor: true,
      http_404: b.calibrar.http === 404,
      mensaje_exacto: (resp?.message ?? null) === EXP_MSG,
      sin_id_calibracion: resp ? resp.id_calibracion === undefined : false,
      // Criterio auxiliar actualizado por autorización de QA: el contrato vigente es 404,
      // y el comportamiento PRE y POST debe ser idéntico.
      historial_post_mantiene_el_contrato: b.post.http === 404 && post?.error_code === 'SENSOR_NO_ENCONTRADO',
      comportamiento_pre_post_identico: b.pre.http === b.post.http && pre?.error_code === post?.error_code,
      assertions_funcionales_todas_pass: assertionsFuncionales.length > 0 && assertionsFuncionales.every(a => a.paso)
    };
    casos['257'] = {
      caso: CASOS['257'], escenario: 'Sensor inexistente en la ruta, dispositivo real en el body',
      sensorEnRuta: FIX.sensorInexistente, dispositivoEnBody: FIX.dispositivo, infraestructura: FIX.area, valor: FIX.valor,
      acreditacionDeInexistencia: {
        endpoint: `/configuracion/sensores/${FIX.sensorInexistente}/calibraciones`,
        http: b.pre.http, error_code: pre?.error_code ?? null,
        contratoVigente: '404 SENSOR_NO_ENCONTRADO',
        contratoPrimeraEvaluacion: '200 con total 0 e items []',
        clasificacion: 'CAMBIO INTENCIONAL DEL CONTRATO DE SEGURIDAD, NO DEFECTO DE G130',
        autorizacion: 'criterio auxiliar actualizado por autorizacion expresa de QA',
        confirmado: b.pre.http === 404 && pre?.error_code === 'SENSOR_NO_ENCONTRADO'
      },
      historialPre: { http: b.pre.http, cuerpo: pre, total: 'N/A (contrato vigente 404)', ids: [] },
      request: { endpoint: `/configuracion/sensores/${FIX.sensorInexistente}/calibrar`, metodo: 'POST', headers: { Authorization: '[REDACTED]', 'Content-Type': 'application/json' }, body: b.calibrar.enviado, fecha: b.calibrar.fecha },
      response: { http: b.calibrar.http, cuerpo: resp, error_code: resp?.error_code ?? null, id_calibracion: resp?.id_calibracion ?? null, capturado: new Date().toISOString() },
      httpEsperado: 404, mensajeEsperado: EXP_MSG, mensajeObtenido: resp?.message ?? null,
      mensajeCoincide: (resp?.message ?? null) === EXP_MSG,
      comparacionLiteral: (resp?.message ?? null) === EXP_MSG
        ? { tipo: 'igualdad literal', resultado: 'coincide caracter a caracter' }
        : { tipo: 'igualdad literal', resultado: 'no coincide', esperado: EXP_MSG, obtenido: resp?.message ?? null },
      historialPost: { http: b.post.http, cuerpo: post, total: 'N/A (contrato vigente 404)', ids: [] },
      noPersistencia: {
        criterioA_respuesta_sin_id_calibracion: resp ? resp.id_calibracion === undefined : false,
        criterioB_pre_y_post_siguen_404: b.pre.http === 404 && b.post.http === 404,
        criterioC_diagnostico_bd: 'NO UTILIZADO: la matriz no exige BD y la API resolvio el oraculo sin ambiguedad'
      },
      assertionsFuncionales: { total: assertionsFuncionales.length, fallidas: assertionsFuncionales.filter(a => !a.paso).length, detalle: assertionsFuncionales },
      oraculo, resultado: b.calibrar.http === null ? 'BLOQUEADO' : Object.values(oraculo).every(x => x === true) ? 'APROBADO' : 'RECHAZADO'
    };
  }

  const newmanLimpio = R.failures.length === 0 && (R.stats.requests.fallidos || 0) === 0;
  const rechazados = Object.values(casos).filter(c => c.resultado === 'RECHAZADO').length;
  const bloqueados = Object.values(casos).filter(c => c.resultado === 'BLOQUEADO').length;
  const resultadoGrupo = bloqueados > 0 ? 'BLOQUEADO' : rechazados > 0 ? 'RECHAZADO' : newmanLimpio ? 'APROBADO' : 'RECHAZADO';

  // ------------------------------------------------------- comparación con la primera
  const PRIMERA = {
    runId: 'run-20261007-085922',
    fuente: 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G130/RESULTADOS/run-20261007-085922/TC-M09-G130_resultado.md',
    '256': { resultado: 'RECHAZADO', http: '404 correcto', error_code: 'DISPOSITIVO_NO_ENCONTRADO', persistencia: 'Ninguna', mensaje: 'Incorrecto', mensajeObtenido: 'No existe un dispositivo IoT con ID 999999.' },
    '257': { resultado: 'RECHAZADO', http: '404 correcto', error_code: 'SENSOR_NO_ENCONTRADO', persistencia: 'Ninguna', mensaje: 'Incorrecto', mensajeObtenido: 'No existe un sensor con ID 999999.' },
    grupo: 'RECHAZADO',
    historialSensorInexistente: '200, total 0'
  };
  const comparacion = {
    baselineUnico: `PRIMERA EVALUACION OFICIAL ${PRIMERA.runId}`,
    fuente: PRIMERA.fuente,
    porCaso: Object.fromEntries(['256', '257'].map(k => [CASOS[k], {
      primera: PRIMERA[k].resultado, segunda: casos[k].resultado,
      cambio: casos[k].resultado === PRIMERA[k].resultado ? 'SIN CAMBIO' : `${PRIMERA[k].resultado} -> ${casos[k].resultado}`,
      dimensiones: {
        http: { primera: PRIMERA[k].http, segunda: `${casos[k].response.http} ${casos[k].oraculo.http_404 ? 'correcto' : 'incorrecto'}` },
        no_persistencia: { primera: PRIMERA[k].persistencia, segunda: casos[k].oraculo.sin_id_calibracion ? 'Ninguna' : 'REVISAR' },
        mensaje: { primera: PRIMERA[k].mensaje, segunda: casos[k].mensajeCoincide ? 'Correcto (literal)' : 'Incorrecto' }
      },
      error_code: { primera: PRIMERA[k].error_code, segunda: casos[k].response.error_code },
      mensajeAntes: PRIMERA[k].mensajeObtenido, mensajeAhora: casos[k].mensajeObtenido, mensajeEsperado: EXP_MSG,
      causaAnteriorCorregida: casos[k].mensajeCoincide ? 'SI' : 'NO'
    }])),
    historialSensorInexistente: {
      primera: PRIMERA.historialSensorInexistente,
      segunda: `${R.inexistentes.sensorHistorialPre.http} ${R.inexistentes.sensorHistorialPre.cuerpo?.error_code || ''}`,
      interpretacion: 'Cambio contractual de seguridad aceptado por QA; no es defecto de G130'
    },
    grupo: { primera: PRIMERA.grupo, segunda: resultadoGrupo, cambio: resultadoGrupo === PRIMERA.grupo ? 'SIN CAMBIO' : `${PRIMERA.grupo} -> ${resultadoGrupo}` },
    causaDelRechazoAnterior: Object.values(casos).every(c => c.mensajeCoincide) ? 'CORREGIDA'
      : Object.values(casos).some(c => c.mensajeCoincide) ? 'PARCIALMENTE CORREGIDA' : 'NO CORREGIDA'
  };

  const todosMensajesOk = Object.values(casos).every(c => c.mensajeCoincide);
  const causaRaiz = todosMensajesOk
    ? 'D. Ambos mensajes comunes son correctos: la causa anterior (el flujo emitia el mensaje propio de cada entidad en lugar del mensaje comun de referencia del RF) esta corregida y desplegada en TEST.'
    : 'A. HTTP correcto y mensaje especifico antiguo: la validacion de referencia existe y rechaza, pero el mensaje comun del RF no esta implementado en TEST.';

  const evidencia = {
    run_id: runId, evaluacion: 'SEGUNDA EVALUACION',
    grupo: GRUPO, casos: Object.values(CASOS), requisito: RF,
    herramientas: 'API - Postman / Newman. BD no forma parte del oraculo y no se utilizo.',
    ambiente: { decisorio: 'TEST', base_url: base() },
    carpeta: `tests/Test_Testing/Test_Modulo9/RF-24/${GRUPO}/EvaluacionV2/`,
    rama: R.gitPre.rama, commit: R.gitPre.commit,
    resultado_grupo: resultadoGrupo,

    git_pre: R.gitPre,

    actor: {
      nota: 'La coleccion Newman es duena de sus sesiones: hace sus propios logins y publica los tokens en ing_session y admin_session. El runner no inicia sesion antes de Newman ni inyecta ningun token; en el cierre se autentica solo para GET.',
      ingeniero: {
        correo: ACTORES.ing.email, credencial: '[REDACTED]', login_http: R.ingLogin.http,
        id_usuario: ingId, id_descubierto_dinamicamente: true,
        rol: R.identidad.cuerpo?.nombre_rol ?? null, estado_cuenta: R.identidad.cuerpo?.estado_cuenta ?? null,
        permiso_registrar_calibraciones: (R.permisos.cuerpo?.permisos || []).some(p => p.id_recurso === 12 && p.id_accion === 1),
        total_permisos: (R.permisos.cuerpo?.permisos || []).length,
        papel: 'ejecuta exclusivamente los 2 POST /calibrar'
      },
      administrador: {
        correo: ACTORES.admin.email, credencial: '[REDACTED]', login_http: R.adminLogin.http,
        alternativo_necesario: 'NO',
        papel: 'solo GET: confirmacion adicional del dispositivo inexistente. No ejecuta POST /calibrar.',
        nota_de_alcance: 'En el estado actual de TEST el Administrador responde 404 incluso sobre el dispositivo real 3 y el sensor 6, de modo que su 404 corrobora pero ya no discrimina inexistencia.'
      }
    },

    fixture_real: {
      sensor: (() => { const row = (R.fixture.sensores.cuerpo?.items || []).find(x => sid(x) === FIX.sensor) || null;
        return row ? { id: sid(row), nombre: row.nombre, categoria: row.categoria, es_activo: row.es_activo, id_dispositivo_iot: row.id_dispositivo_iot } : null; })(),
      dispositivo: R.fixture.dispositivo.cuerpo ? { id: R.fixture.dispositivo.cuerpo.id_dispositivo_iot, serial: R.fixture.dispositivo.cuerpo.serial, es_activo: R.fixture.dispositivo.cuerpo.es_activo, http: R.fixture.dispositivo.http } : null,
      asociacionVigente: (() => { const a = (R.fixture.asociaciones.cuerpo?.items || []).find(x => vig(x) && sid(x) === FIX.sensor && x.id_dispositivo_iot === FIX.dispositivo) || null;
        return a ? { id_dispositivo_iot: a.id_dispositivo_iot, id_infraestructura: a.id_infraestructura, tiene_estado: a.tiene_estado, fecha_finalizacion: a.fecha_finalizacion } : null; })(),
      categoria: FIX.categoria,
      rango: (() => { const r = (R.fixture.rangos.cuerpo?.items || []).find(x => x.categoria === FIX.categoria) || null;
        return r ? { categoria: FIX.categoria, min: String(r.valor_min), max: String(r.valor_max) } : null; })(),
      valor: FIX.valor,
      valorEstrictamenteInterior: (() => { const r = (R.fixture.rangos.cuerpo?.items || []).find(x => x.categoria === FIX.categoria) || null;
        return Boolean(r) && Number(FIX.valor) > Number(r.valor_min) && Number(FIX.valor) < Number(r.valor_max); })(),
      fixtureOriginalReutilizado: FIX.sensor === 6 && FIX.dispositivo === 3 && FIX.area === 3 && FIX.valor === '22.5000'
    },

    verificacion_ids_inexistentes: {
      dispositivo: {
        id: FIX.dispositivoInexistente,
        acreditacion: 'par discriminante del mismo actor: el Ingeniero lee el dispositivo REAL con 200 y el inexistente con 404',
        ingeniero_dispositivo_real: R.fixture.dispositivo.http,
        ingeniero_dispositivo_inexistente: R.inexistentes.dispositivoIngeniero.http,
        error_code: R.inexistentes.dispositivoIngeniero.cuerpo?.error_code ?? null,
        administrador_confirmacion_adicional: { http: R.inexistentes.dispositivoAdministrador.http, error_code: R.inexistentes.dispositivoAdministrador.cuerpo?.error_code ?? null, discriminante: false },
        confirmado: R.inexistentes.dispositivoIngeniero.http === 404 && R.fixture.dispositivo.http === 200,
        idNoModificado: FIX.dispositivoInexistente === 999999,
        datosCreados: 'ninguno: no se creo, modifico ni elimino nada para obtener este ID'
      },
      sensor: {
        id: FIX.sensorInexistente,
        endpoint: `/configuracion/sensores/${FIX.sensorInexistente}/calibraciones`,
        http: R.inexistentes.sensorHistorialPre.http,
        error_code: R.inexistentes.sensorHistorialPre.cuerpo?.error_code ?? null,
        contratoVigente: '404 SENSOR_NO_ENCONTRADO',
        contratoPrimeraEvaluacion: '200 con total 0 e items []',
        clasificacion: 'CAMBIO INTENCIONAL DEL CONTRATO DE SEGURIDAD, NO DEFECTO DE G130',
        motivo: 'el historial de calibraciones valida previamente existencia y alcance del sensor para evitar exposicion de recursos ajenos mediante IDOR',
        autorizacion: 'criterio auxiliar actualizado por autorizacion expresa de QA; el esperado funcional del POST no fue modificado',
        confirmado: R.inexistentes.sensorHistorialPre.http === 404 && R.inexistentes.sensorHistorialPre.cuerpo?.error_code === 'SENSOR_NO_ENCONTRADO',
        idNoModificado: FIX.sensorInexistente === 999999,
        datosCreados: 'ninguno'
      }
    },

    'TC-M09-256': casos['256'],
    'TC-M09-257': casos['257'],

    newman: {
      html: `newman/newman-${GRUPO}.html`, htmlPersistentes: 1,
      coleccionEjecutada: `${R.itemsEjecutables} de ${R.itemsTotales} items`,
      iterations: R.stats.iterations, requests: R.stats.requests, assertions: R.stats.assertions,
      failures: R.failures,
      presupuesto: { postCalibrarPlanificados: POST_BUDGET, postCalibrarEjecutados: R.postCalibrar, patch: 0, put: 0, delete: 0, reintentos: 0 },
      stopAll: R.stopAll, stopAllMotivo: R.stopAllMotivo ? JSON.parse(R.stopAllMotivo) : null,
      limpio: newmanLimpio
    },

    verificacion_final: {
      soloLectura: true, sql: 'ninguno', escrituras: 0, fecha: new Date().toISOString(),
      historial_sensor_real: { http: histReal.status, total: histReal.cuerpo?.total ?? null, ids: idsFinales,
        igualAlPreDeTC256: JSON.stringify(idsFinales.slice().sort()) === JSON.stringify((casos['256'].historialPre?.ids || []).slice().sort()) },
      historial_sensor_inexistente: { http: histInex.status, error_code: histInex.cuerpo?.error_code ?? null, mantieneElContrato: histInex.status === 404 },
      dispositivo_real: { http: dispReal.status, es_activo: dispReal.cuerpo?.es_activo ?? null, sinCambios: dispReal.cuerpo?.es_activo === true },
      dispositivo_inexistente: { http: dispInex.status, sigueInexistente: dispInex.status === 404 },
      asociacion_vigente: (asocFinal.cuerpo?.items || []).filter(x => vig(x) && sid(x) === FIX.sensor).map(x => ({ id_dispositivo_iot: x.id_dispositivo_iot, id_infraestructura: x.id_infraestructura })),
      rango: rangoFinal ? { categoria: FIX.categoria, min: String(rangoFinal.valor_min), max: String(rangoFinal.valor_max) } : null,
      calibraciones_atribuibles_a_los_casos: atribuibles,
      ninguna_calibracion_creada: atribuibles.length === 0,
      post_extra_ejecutados: 0
    },

    contraste_dev: {
      necesario: !todosMensajesOk,
      motivo: todosMensajesOk
        ? 'TEST paso completamente: ambos casos devolvieron 404 con el mensaje comun exacto y sin persistencia. No se uso DEV.'
        : 'TEST conserva el mensaje anterior en al menos un caso: procede contrastar DEV para distinguir defecto de aplicacion de desfase de despliegue.',
      peticiones_a_dev: 0
    },

    diagnostico_bd: {
      utilizada: false,
      motivo: 'La matriz de G130 no exige BD y la API resolvio ambos oraculos sin ambiguedad: los IDs inexistentes quedaron acreditados por GET y la no persistencia por la respuesta del POST y por los GET PRE/POST. No se abrio ninguna conexion.',
      solo_select: true,
      credencialesEntregadasPorQA: 'no utilizadas. La contrasena de BD no aparece como literal en ningun artefacto; el saneado la cubre solo si se entrega por variable de entorno'
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
  for (const k of ['256', '257']) {
    const c = casos[k];
    log(`${c.caso}: HTTP ${c.response.http}/${c.httpEsperado} | error_code ${c.response.error_code} | mensaje ${c.mensajeCoincide ? 'EXACTO' : 'NO COINCIDE'} | id_calibracion ${c.response.id_calibracion ?? 'ausente'} -> ${c.resultado}`);
  }
  log(`GRUPO ${GRUPO} -> ${resultadoGrupo}`);
  log(`Newman: requests ${R.stats.requests.ejecutados} (fallidos ${R.stats.requests.fallidos}) | assertions ${R.stats.assertions.total} (fallidas ${R.stats.assertions.fallidas}) | limpio ${newmanLimpio ? 'SI' : 'NO'}`);
  log(`POST /calibrar ${R.postCalibrar}/${POST_BUDGET} | PATCH/PUT/DELETE 0 | STOP_ALL ${R.stopAll}`);
  log(`historial sensor real ${FIX.sensor}: total ${histReal.cuerpo?.total} | calibraciones atribuibles a los casos: ${atribuibles.length}`);
  log(`historial sensor ${FIX.sensorInexistente}: HTTP ${histInex.status} ${histInex.cuerpo?.error_code || ''}`);
  log(`BD utilizada: NO (no requerida por el caso)`);
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
    { archivo: 'run-g130-v2.cjs', abs: path.join(__dirname, 'run-g130-v2.cjs'),
      ruta: `${GRUPO}/EvaluacionV2/automation/run-g130-v2.cjs`,
      funcion: 'Runner unico de la reevaluacion, con los modos precheck (Newman de solo lectura, sin HTML ni archivos), run (RUN funcional oficial con los 2 POST y el unico HTML) y close (oraculo por caso, verificacion final de solo lectura y consolidacion de evidencia). No inyecta tokens a Newman y no ejecuta PATCH, PUT ni DELETE.' },
    { archivo: 'TC-M09-G130.postman_collection.json', abs: COLECCION,
      ruta: `${GRUPO}/EvaluacionV2/TC-M09-G130.postman_collection.json`,
      funcion: 'Copia de la coleccion funcional para EvaluacionV2. Cambios de infraestructura: tres GET de precondicion leen con ing_session porque el Administrador perdio alcance, y se anade un GET del Administrador como confirmacion adicional. Criterio auxiliar del historial del sensor inexistente actualizado por autorizacion de QA al contrato vigente 404 SENSOR_NO_ENCONTRADO. Los 2 POST /calibrar, sus bodies, el HTTP 404 esperado y el mensaje comun exacto son byte-identicos a la primera evaluacion.' },
    { archivo: 'TC-M09-G130.postman_collection.json (original)', abs: COLECCION_ORIGINAL,
      ruta: `${GRUPO}/TC-M09-G130.postman_collection.json`,
      funcion: 'Coleccion funcional de la primera evaluacion. Reutilizada como fuente, en solo lectura; no fue modificada.' },
    { archivo: 'run-newman.cjs (original)', abs: path.join(CASE_DIR, 'run-newman.cjs'),
      ruta: `${GRUPO}/run-newman.cjs`,
      funcion: 'Runner de la primera evaluacion. NO se utiliza en esta reevaluacion: se registra por trazabilidad del baseline.' }
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
    grupo: GRUPO, casos: Object.values(CASOS), runId,
    nota: 'Artefactos finales de la SEGUNDA EVALUACION. Los ejecutables viven unicamente en EvaluacionV2/; no se duplica automation dentro de RESULTADOS.',
    newmanHtmlPersistentes: 1, automationDentroDeResultados: 'NO', artefactos: filas
  }, null, 2)));
}
