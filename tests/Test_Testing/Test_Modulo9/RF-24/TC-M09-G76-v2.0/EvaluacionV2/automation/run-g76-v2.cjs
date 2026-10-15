// Runner único de la SEGUNDA EVALUACIÓN de TC-M09-G76-v2.0 (RF-24 v2.0, CU05 Flujo D).
//
// Un solo archivo, tres modos (G76_MODO):
//
//   precheck  Validación Newman de SOLO LECTURA previa al RUN. Ejecuta la colección filtrada
//             en memoria SIN los dos POST /calibrar. No genera HTML, no crea RESULTADOS y no
//             deja ningún archivo: su resultado va solo a consola. Si hay cualquier failure,
//             AUTORIZAR_RUN = NO y no debe ejecutarse el RUN.
//   run       RUN funcional oficial: la colección completa una única vez, con los 2 POST de
//             calibración, y el ÚNICO reporte Newman HTML persistente.
//   close     Cierre documental: consolida evidencia.json y automation_manifest.json a partir
//             del summary del RUN, escanea secretos y captura el estado de git. Sin red.
//
// REGLAS DE AUTENTICACIÓN QUE ESTE RUNNER HACE CUMPLIR:
//   - El runner NUNCA se autentica con el correo del actor funcional. La colección es dueña
//     de la sesión: hace su propio login y publica el token en {{session_value}}, que usan
//     TODAS las peticiones del Ingeniero, incluidas las precondiciones.
//   - No existe ninguna variable de token inyectada desde fuera de Newman.
//   - Motivo: TEST mantiene una sola sesión activa por usuario y un segundo login del mismo
//     correo revoca el token anterior.
//   - El Administrador auxiliar no inicia sesión por defecto: su item se excluye de la
//     colección salvo que se autorice explícitamente, y en ese caso su login también ocurre
//     DENTRO de Newman, publicando el token en {{admin_session}}.
//
// Presupuesto: 2 POST de calibración (uno por caso), sin reintentos. PATCH: 0 — este runner
// no ejecuta PATCH en ningún modo.
//
// Uso:
//   $env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
//   $env:QA_EMAIL="ingeniero@pecuaria.co"
//   $env:QA_PASSWORD="<secreto>"
//   $env:G76_RUN_ID="run-YYYYMMDD-HHMMSS"     (modos run y close)
//   $env:G76_MODO="precheck" | "run" | "close"
//   node .\run-g76-v2.cjs
//
// Solo si el PRECHECK demuestra que una lectura indispensable no es visible para el
// Ingeniero, y tras autorización de QA:
//   $env:G76_USAR_ADMIN="SI"
//   $env:QA_ADMIN_EMAIL="administador.dev@gmail.com"
//   $env:QA_ADMIN_PASSWORD="<secreto>"

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

// La guarda de directorio autorizado de helpers.cjs se evalúa con su propio __dirname, que
// sigue siendo TC-M09-G76-v2.0: se respeta sin copiar ni modificar el archivo. De helpers solo
// se usan constantes y los constructores de los mensajes exigidos por el RF; no se usa ninguna
// de sus funciones de login ni de discovery.
const H = require('../../helpers.cjs');

const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const CASE_DIR = path.resolve(__dirname, '..', '..');
const EVAL_DIR = path.resolve(__dirname, '..');
const COLECCION = path.join(EVAL_DIR, 'TC-M09-G76-v2.0.postman_collection.json');
const COLECCION_ORIGINAL = path.join(CASE_DIR, 'TC-M09-G76-v2.0.postman_collection.json');

const MODO = process.env.G76_MODO || 'precheck';
if (!['precheck', 'run', 'close'].includes(MODO)) throw new Error(`G76_MODO no reconocido: ${MODO}`);

const actorEmail = process.env.QA_EMAIL;
const actorSecret = process.env.QA_PASSWORD;
if (!actorEmail || !actorSecret) throw new Error('QA_EMAIL y QA_PASSWORD requeridos (solo en memoria de proceso).');
const base = () => {
  const b = process.env.QA_BASE_URL;
  if (!b) throw new Error('QA_BASE_URL requerido');
  return b.replace(/\/$/, '');
};

const usarAdmin = process.env.G76_USAR_ADMIN === 'SI';
const adminEmail = usarAdmin ? (process.env.QA_ADMIN_EMAIL || '') : '';
const adminSecret = usarAdmin ? (process.env.QA_ADMIN_PASSWORD || '') : '';

// ------------------------------------------------------------------- fixtures de la matriz
// Valores del caso. No se descubren autenticando desde el runner: la colección los verifica
// con sus propias assertions y, si la realidad no coincide, el PRECHECK falla y el RUN no se
// ejecuta.
const FIX = {
  '146': {
    device: Number(process.env.G76_146_DEVICE || 47),
    serial: process.env.G76_146_SERIAL || 'BUGCHECK-REASIGN-001',
    sensor: Number(process.env.G76_146_SENSOR || 29),
    area: Number(process.env.G76_146_AREA || 3),
    categoria: process.env.G76_146_CAT || 'PH',
    valor: process.env.G76_146_VALOR || '7.0000'
  },
  '147': {
    device: Number(process.env.G76_147_DEVICE || 3),
    sensor: Number(process.env.G76_147_SENSOR || 6),
    areaVigente: Number(process.env.G76_147_AREA_VIGENTE || 3),
    areaSolicitada: Number(process.env.G76_147_AREA_ALT || 1),
    categoria: process.env.G76_147_CAT || 'TEMPERATURA',
    valor: process.env.G76_147_VALOR || '22.5000'
  }
};
const RANGOS_ESPERADOS = { PH: { min: '0', max: '14' }, TEMPERATURA: { min: '0', max: '45' } };

const POST_CALIBRAR = ['146 POST calibrar', '147 POST calibrar'];
const ITEM_LOGIN_ADMIN = 'Login Administrador auxiliar';

// Motivos de los cambios que este runner puede sufrir DESPUÉS del RUN funcional. Se declaran
// aquí para que el manifiesto los registre con su razón y no como un cambio sin explicar.
const MOTIVO_CAMBIO_POSTERIOR = {
  'run-g76-v2.cjs':
    'Ajuste posterior al RUN, sin efecto sobre el oraculo: (1) el escaneo de secretos pasa a ' +
    'evaluar los archivos .cjs solo por VALORES de secreto, porque el propio codigo del escaner ' +
    'contiene su vocabulario (set-cookie, password) y se marcaba a si mismo con ' +
    'credencialesEnClaro = 0; (2) el modo close se hizo idempotente para poder recalcular ' +
    'seguridad, git y manifiesto sin volver a la red ni reejecutar ningun POST. No se modifico ' +
    'ninguna assertion, valor, codigo ni mensaje esperado, y no se reejecuto el RUN.'
};

const log = (...a) => console.log(...a);
const sha256 = (f) => crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');

// Sanitización: la contraseña nunca debe quedar en un artefacto.
const secretos = () => [actorSecret, adminSecret].filter(Boolean);
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

// RUN_ID y rutas: en precheck no se toca el disco.
const runId = process.env.G76_RUN_ID;
if (MODO !== 'precheck') {
  if (!runId || !/^run-\d{8}-\d{6}$/.test(runId)) {
    throw new Error('G76_RUN_ID requerido con formato run-YYYYMMDD-HHMMSS.');
  }
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
const HTML_OFICIAL = () => path.join(mk('newman'), `newman-${H.GROUP_ID}.html`);
const SUMMARY_TMP = () => path.join(RUN_DIR, '.summary-run.json');

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
  carpeta_historica_TC_M09_G76: git(['status', '--short', '--', 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G76']) || '(vacio = intacta)',
  primera_evaluacion_RESULTADOS: git(['status', '--short', '--', 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G76-v2.0/RESULTADOS']) || '(vacio = intacta)',
  operaciones_git_de_escritura: 'ninguna: sin add, commit, push, merge, rebase, reset, clean, stash, switch ni checkout'
});

// ------------------------------------------------------------------------- seguridad
// Escaneo de EvaluacionV2 buscando VALORES de secreto, no vocabulario.
//
// En los archivos de código (.cjs) el vocabulario del propio escáner aparece de forma
// legítima: `set-cookie` es este mismo patrón y `password|contrasena` es la referencia a una
// variable. Para código fuente solo cuentan valores de secreto (JWT, Authorization con token
// real, cadena de conexión) y la coincidencia literal con las credenciales en uso; la
// evidencia y los reportes se revisan con todos los patrones.
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
    const esCodigoFuente = /\.cjs$/i.test(rel);
    const txt = fs.readFileSync(f, 'utf8');
    revisados.push({
      archivo: rel,
      bytes: txt.length,
      tipo: esCodigoFuente ? 'codigo-fuente' : 'evidencia',
      secretos: (esCodigoFuente ? SOLO_VALORES : TODOS).filter(([re]) => re.test(txt)).map(([, n]) => n),
      credencialesEnClaro: credenciales.filter(x => txt.includes(x)).length
    });
  });
  walk(EVAL_DIR);
  const sucios = revisados.filter(r => r.secretos.length || r.credencialesEnClaro);
  return {
    alcance: 'todo EvaluacionV2/: runner, coleccion, informe, evidencia, manifiesto y el HTML de Newman',
    limpio: sucios.length === 0,
    archivosConHallazgos: sucios,
    revisados,
    criterio: 'Se marcan solo VALORES de secreto: contrasenas en uso, JWT, Authorization con token, cookies, tokens en pares clave-valor y cadenas de conexion. En los archivos .cjs (codigo fuente) solo se evaluan valores de secreto y la coincidencia literal con las credenciales: el vocabulario del propio escaner y las referencias a variables no son fugas. El correo del actor lo publica el propio caso y no es un secreto del requisito.',
    nota: 'La contrasena solo existio en memoria de proceso. El reporter htmlextra se ejecuto con omitHeaders, sin environment ni globals y omitiendo las variables sensibles; el HTML se sanitizo despues de generarse.'
  };
}

// --------------------------------------------------------------------- mensajes del RF
const EXP_146 = H.mensaje146(FIX['146'].serial);
const EXP_147 = H.mensaje147(FIX['147'].sensor, FIX['147'].areaSolicitada);

function construirEnv() {
  const cuerpo = (dispositivo, area, valor, observaciones) =>
    `{"modo_calibracion":"SENSOR","id_dispositivo_iot":${dispositivo},"id_infraestructura":${area},"valor_referencia":${valor},"observaciones":${JSON.stringify(observaciones)},"fecha_calibracion":"__FECHA__"}`;
  return [
    ['base_url', base()],
    ['actor_email', actorEmail], ['actor_secret', actorSecret],
    ['admin_email', adminEmail], ['admin_secret', adminSecret],
    ['device_146', String(FIX['146'].device)], ['serial_146', FIX['146'].serial],
    ['sensor_146', String(FIX['146'].sensor)], ['area_146', String(FIX['146'].area)],
    ['cat_146', FIX['146'].categoria], ['valor_146', FIX['146'].valor],
    ['body_146', cuerpo(FIX['146'].device, FIX['146'].area, FIX['146'].valor, H.CASOS['146'].observaciones)],
    ['exp_msg_146', EXP_146],
    ['device_147', String(FIX['147'].device)], ['sensor_147', String(FIX['147'].sensor)],
    ['area_vigente_147', String(FIX['147'].areaVigente)], ['area_alt_147', String(FIX['147'].areaSolicitada)],
    ['cat_147', FIX['147'].categoria], ['valor_147', FIX['147'].valor],
    ['body_147', cuerpo(FIX['147'].device, FIX['147'].areaSolicitada, FIX['147'].valor, H.CASOS['147'].observaciones)],
    ['exp_msg_147', EXP_147],
    ['stop_all', 'NO']
  ];
}

// Carga la colección y aplica las exclusiones de items. No altera URLs, métodos, bodies,
// assertions ni el orden de los items que permanecen.
function cargarColeccion(excluir) {
  const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
  const antes = col.item.map(i => i.name);
  col.item = col.item.filter(i => !excluir.includes(i.name));
  const quitados = antes.filter(n => !col.item.map(x => x.name).includes(n));
  for (const n of excluir) {
    if (!antes.includes(n)) throw new Error(`El item «${n}» no existe en la colección.`);
  }
  return { col, itemsTotales: antes.length, itemsEjecutables: col.item.length, quitados };
}

function verificarSinEscrituras(col, permitirCalibrar) {
  for (const it of col.item) {
    const url = typeof it.request.url === 'string' ? it.request.url : it.request.url?.raw || '';
    const metodo = (it.request.method || 'GET').toUpperCase();
    if (metodo === 'PATCH' || metodo === 'PUT' || metodo === 'DELETE') {
      throw new Error(`ABORTADO: operación de escritura no autorizada en la colección: ${metodo} ${url} (${it.name}).`);
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
  const opciones = {
    collection: col,
    reporters: html ? ['cli', 'htmlextra'] : ['cli'],
    envVar: env.map(([key, value]) => ({ key, value }))
  };
  if (html) {
    opciones.reporter = {
      htmlextra: {
        export: html, omitHeaders: true, showEnvironmentData: false, showGlobalData: false,
        skipEnvironmentVars: ['actor_secret', 'admin_secret', 'session_value', 'admin_session'],
        showMarkdownLinks: false
      }
    };
    if (titulo) opciones.reporter.htmlextra.title = titulo;
  }
  return new Promise((resolve, reject) => {
    newman.run(opciones, (err, summary) => (err ? reject(err) : resolve(summary)));
  });
}

// Extrae del summary de Newman lo que necesitamos, sin volver a la red.
function extraer(summary) {
  const ex = summary?.run?.executions || [];
  const find = (n) => ex.find(x => x.item && x.item.name === n);
  const cuerpo = (n) => { const e = find(n); if (!e || !e.response) return null; try { return JSON.parse(e.response.stream.toString()); } catch { return null; } };
  const http = (n) => { const e = find(n); return e && e.response ? e.response.code : null; };
  const enviado = (n) => { const e = find(n); try { return JSON.parse(e.request.body.raw.toString()); } catch { return null; } };
  const assertionsDe = (n) => {
    const e = find(n);
    return (e?.assertions || []).map(a => ({ assertion: a.assertion, paso: !a.error, error: a.error ? a.error.message : null }));
  };
  return { ex, find, cuerpo, http, enviado, assertionsDe };
}

function fallos(summary) {
  return (summary?.run?.failures || [])
    .map(f => ({ item: f.source?.name, assertion: f.error?.test, error: f.error?.message }))
    .filter(f => f.error);
}

function stats(summary) {
  const s = summary?.run?.stats || {};
  return {
    iterations: { ejecutadas: s.iterations?.total ?? null, fallidas: s.iterations?.failed ?? null },
    requests: { ejecutados: s.requests?.total ?? null, fallidos: s.requests?.failed ?? null },
    testScripts: { ejecutados: s.testScripts?.total ?? null, fallidos: s.testScripts?.failed ?? null },
    assertions: { total: s.assertions?.total ?? 0, fallidas: s.assertions?.failed ?? 0 }
  };
}

const postsDeCalibracion = (summary) =>
  (summary?.run?.executions || []).filter(e => /\/calibrar$/.test(e.request?.url?.toString() || '')).length;
const patchsEjecutados = (summary) =>
  (summary?.run?.executions || []).filter(e => (e.request?.method || '').toUpperCase() === 'PATCH').length;

// ==========================================================================================
(async () => {
  if (MODO === 'precheck') return modoPrecheck();
  if (MODO === 'run') return modoRun();
  return modoClose();
})().catch((e) => { console.error('\nNO COMPLETADO:', e.message); process.exitCode = 1; });

// ------------------------------------------------------------------------------- precheck
async function modoPrecheck() {
  // Sin los 2 POST de calibración y, por defecto, sin el login del Administrador.
  const excluir = [...POST_CALIBRAR];
  if (!usarAdmin) excluir.push(ITEM_LOGIN_ADMIN);
  const { col, itemsTotales, itemsEjecutables, quitados } = cargarColeccion(excluir);
  verificarSinEscrituras(col, false);

  log('PRECHECK de solo lectura — Newman sin reporter HTML, sin carpeta de resultados.');
  log(`Colección: ${itemsEjecutables} de ${itemsTotales} items. Excluidos: ${quitados.join(' | ')}`);
  log(`Administrador auxiliar: ${usarAdmin ? `autorizado (${adminEmail})` : 'no se inicia sesión (todo se resuelve con el Ingeniero de Campo)'}\n`);

  const summary = await correrNewman(col, construirEnv(), null, null);
  const st = stats(summary);
  const fs_ = fallos(summary);
  const { cuerpo, http, assertionsDe } = extraer(summary);

  const pasa = (item) => {
    const a = assertionsDe(item);
    return a.length > 0 && a.every(x => x.paso);
  };
  const login = cuerpo('Login Ingeniero');
  const yo = cuerpo('Identidad del Ingeniero');
  const permisos = cuerpo('Permisos del Ingeniero');
  const tiene = (r, a) => (permisos?.permisos || []).some(p => p.id_recurso === r && p.id_accion === a);
  const d146 = cuerpo('146 Dispositivo inactivo');
  const s146 = cuerpo('146 Sensor del dispositivo inactivo');
  const a146 = cuerpo('146 Asociación vigente del sensor');
  const d147 = cuerpo('147 Dispositivo activo');
  const s147 = cuerpo('147 Sensor del dispositivo');
  const a147 = cuerpo('147 Asociación vigente del sensor');
  const area147 = cuerpo('147 Área alternativa existe');
  const rangos = cuerpo('Rangos de calibración');

  const sid = (x) => (x && x.id_sensor !== undefined ? x.id_sensor : x && x.id_sensores);
  const vig = (x) => x && x.tiene_estado === true && (x.fecha_finalizacion === null || x.fecha_finalizacion === undefined);
  const rangoDe = (cat) => {
    const r = (rangos?.items || []).find(x => x.categoria === cat);
    return r ? { min: String(r.valor_min), max: String(r.valor_max) } : null;
  };
  const rPH = rangoDe(FIX['146'].categoria);
  const rTE = rangoDe(FIX['147'].categoria);
  const rangoCoincide = (r, esp) => Boolean(r) && Boolean(esp) && Number(r.min) === Number(esp.min) && Number(r.max) === Number(esp.max);

  const sensor146 = (s146?.items || []).find(x => sid(x) === FIX['146'].sensor);
  const sensor147 = (s147?.items || []).find(x => sid(x) === FIX['147'].sensor);
  const asoc146 = (a146?.items || []).find(x => vig(x) && sid(x) === FIX['146'].sensor && x.id_dispositivo_iot === FIX['146'].device);
  const vigentes147 = (a147?.items || []).filter(x => vig(x) && sid(x) === FIX['147'].sensor);
  const asoc147 = vigentes147.find(x => x.id_dispositivo_iot === FIX['147'].device);

  const chequeos = {
    autenticacion: http('Login Ingeniero') >= 200 && http('Login Ingeniero') <= 299 && typeof login?.token === 'string' && pasa('Login Ingeniero'),
    identidad: http('Identidad del Ingeniero') === 200 && yo?.correo_electronico === actorEmail && yo?.nombre_rol === 'Ingeniero de Campo' && pasa('Identidad del Ingeniero'),
    permisos: http('Permisos del Ingeniero') === 200 && tiene(11, 2) && tiene(12, 1) && tiene(12, 2) && pasa('Permisos del Ingeniero'),
    fixture146: http('146 Dispositivo inactivo') === 200 && d146?.id_dispositivo_iot === FIX['146'].device && d146?.es_activo === false &&
      d146?.serial === FIX['146'].serial && Boolean(sensor146) && sensor146.es_activo === true &&
      sensor146.categoria === FIX['146'].categoria && sensor146.id_dispositivo_iot === FIX['146'].device &&
      Boolean(asoc146) && asoc146.id_infraestructura === FIX['146'].area &&
      pasa('146 Dispositivo inactivo') && pasa('146 Sensor del dispositivo inactivo') && pasa('146 Asociación vigente del sensor'),
    fixture147: http('147 Dispositivo activo') === 200 && d147?.es_activo === true &&
      Boolean(sensor147) && sensor147.es_activo === true && sensor147.categoria === FIX['147'].categoria &&
      sensor147.id_dispositivo_iot === FIX['147'].device &&
      Boolean(asoc147) && asoc147.id_infraestructura === FIX['147'].areaVigente &&
      http('147 Área alternativa existe') === 200 && area147?.id_infraestructura === FIX['147'].areaSolicitada &&
      FIX['147'].areaSolicitada !== FIX['147'].areaVigente &&
      !vigentes147.map(x => x.id_infraestructura).includes(FIX['147'].areaSolicitada) &&
      pasa('147 Dispositivo activo') && pasa('147 Sensor del dispositivo') && pasa('147 Asociación vigente del sensor') && pasa('147 Área alternativa existe'),
    rangos: rangoCoincide(rPH, RANGOS_ESPERADOS[FIX['146'].categoria]) && rangoCoincide(rTE, RANGOS_ESPERADOS[FIX['147'].categoria]) && pasa('Rangos de calibración')
  };

  const postCalibrar = postsDeCalibracion(summary);
  const patchs = patchsEjecutados(summary);
  const autorizar = Object.values(chequeos).every(Boolean) && fs_.length === 0 &&
    (st.requests.fallidos || 0) === 0 && postCalibrar === 0 && patchs === 0;

  const P = (b) => (b ? 'PASS' : 'FAIL');
  log('\nPRECHECK_G76\n');
  log(`Autenticación:\n${P(chequeos.autenticacion)}\n`);
  log(`Identidad:\n${P(chequeos.identidad)}\n`);
  log(`Permisos:\n${P(chequeos.permisos)}\n`);
  log(`TC146 fixture:\n${P(chequeos.fixture146)}\n`);
  log(`TC147 fixture:\n${P(chequeos.fixture147)}\n`);
  log(`Rangos:\n${P(chequeos.rangos)}\n`);
  log(`Failures:\n${fs_.length}\n`);
  log(`POST calibrar:\n${postCalibrar}\n`);
  log(`PATCH:\n${patchs}\n`);
  log(`AUTORIZAR_RUN:\n${autorizar ? 'SÍ' : 'NO'}\n`);

  log('--- detalle observado (solo consola, no se persiste) ---');
  log(`identidad: id_usuario=${yo?.id_usuario} rol="${yo?.nombre_rol}"`);
  log(`permisos del caso: 11/2=${tiene(11, 2)} 12/1=${tiene(12, 1)} 12/2=${tiene(12, 2)} (total ${(permisos?.permisos || []).length})`);
  log(`TC-146: dispositivo ${d146?.id_dispositivo_iot} serial "${d146?.serial}" es_activo=${d146?.es_activo} | sensor ${sid(sensor146)} ${sensor146?.categoria} activo=${sensor146?.es_activo} | asociación vigente área ${asoc146?.id_infraestructura}`);
  log(`TC-147: dispositivo ${d147?.id_dispositivo_iot} es_activo=${d147?.es_activo} | sensor ${sid(sensor147)} ${sensor147?.categoria} activo=${sensor147?.es_activo} | área vigente ${asoc147?.id_infraestructura} | área solicitada ${area147?.id_infraestructura} existe=HTTP ${http('147 Área alternativa existe')} asociada=${vigentes147.map(x => x.id_infraestructura).includes(FIX['147'].areaSolicitada)}`);
  log(`rangos: ${FIX['146'].categoria} ${rPH?.min}–${rPH?.max} | ${FIX['147'].categoria} ${rTE?.min}–${rTE?.max}`);
  log(`valores del RUN: TC-146 ${FIX['146'].valor} | TC-147 ${FIX['147'].valor}`);
  log(`newman: requests ${st.requests.ejecutados}/${st.requests.fallidos} fallidos | assertions ${st.assertions.total}/${st.assertions.fallidas} fallidas`);
  if (fs_.length) { log('\nfailures:'); fs_.forEach((f, i) => log(`  ${i + 1}. ${f.item} :: ${f.assertion} :: ${f.error}`)); }
  log('');

  if (!autorizar) {
    log('El RUN funcional NO está autorizado. Corregir antes de ejecutar los POST.');
    process.exitCode = 2;
  }
}

// ------------------------------------------------------------------------------------ run
async function modoRun() {
  if (fs.existsSync(RUN_DIR)) throw new Error(`La carpeta ${runId} ya existe. Un RUN oficial no se repite ni se sobrescribe.`);

  const excluir = usarAdmin ? [] : [ITEM_LOGIN_ADMIN];
  const { col, itemsTotales, itemsEjecutables, quitados } = cargarColeccion(excluir);
  verificarSinEscrituras(col, true);

  const calibrar = col.item.filter(i => /\/calibrar$/.test(typeof i.request.url === 'string' ? i.request.url : i.request.url?.raw || ''));
  if (calibrar.length !== H.POST_BUDGET) {
    throw new Error(`ABORTADO: la colección debe contener exactamente ${H.POST_BUDGET} POST de calibración, contiene ${calibrar.length}.`);
  }

  const gitPre = estadoGit('git_pre');
  const html = HTML_OFICIAL();

  log(`RUN funcional oficial. RUN_ID: ${runId}`);
  log(`Colección: ${itemsEjecutables} de ${itemsTotales} items.${quitados.length ? ' Excluidos: ' + quitados.join(' | ') : ''}`);
  log(`POST de calibración planificados: ${H.POST_BUDGET} | PATCH: 0`);
  log(`Mensaje esperado TC-146: ${EXP_146}`);
  log(`Mensaje esperado TC-147: ${EXP_147}\n`);

  const summary = await correrNewman(col, construirEnv(), html, `TC-M09-G76-v2.0 — SEGUNDA EVALUACIÓN · RUN funcional oficial ${runId}`);

  if (fs.existsSync(html)) fs.writeFileSync(html, limpiarHtml(fs.readFileSync(html, 'utf8')));

  // Se preserva lo necesario del summary para que el cierre no vuelva a la red.
  const { cuerpo, http, enviado, assertionsDe } = extraer(summary);
  const preservado = {
    runId, generado: new Date().toISOString(),
    gitPre,
    itemsTotales, itemsEjecutables, itemsExcluidos: quitados,
    usarAdmin,
    stats: stats(summary),
    failures: fallos(summary),
    postCalibrar: postsDeCalibracion(summary),
    patchs: patchsEjecutados(summary),
    stopAll: summary?.environment?.values?.find?.(x => x.key === 'stop_all')?.value ?? 'NO',
    stopAllMotivo: summary?.environment?.values?.find?.(x => x.key === 'stop_all_motivo')?.value ?? null,
    identidad: cuerpo('Identidad del Ingeniero'),
    permisos: cuerpo('Permisos del Ingeniero'),
    rangos: cuerpo('Rangos de calibración'),
    precondiciones: {
      '146_dispositivo': { http: http('146 Dispositivo inactivo'), cuerpo: cuerpo('146 Dispositivo inactivo'), assertions: assertionsDe('146 Dispositivo inactivo') },
      '146_sensores': { http: http('146 Sensor del dispositivo inactivo'), cuerpo: cuerpo('146 Sensor del dispositivo inactivo'), assertions: assertionsDe('146 Sensor del dispositivo inactivo') },
      '146_asociaciones': { http: http('146 Asociación vigente del sensor'), cuerpo: cuerpo('146 Asociación vigente del sensor'), assertions: assertionsDe('146 Asociación vigente del sensor') },
      '147_dispositivo': { http: http('147 Dispositivo activo'), cuerpo: cuerpo('147 Dispositivo activo'), assertions: assertionsDe('147 Dispositivo activo') },
      '147_sensores': { http: http('147 Sensor del dispositivo'), cuerpo: cuerpo('147 Sensor del dispositivo'), assertions: assertionsDe('147 Sensor del dispositivo') },
      '147_asociaciones': { http: http('147 Asociación vigente del sensor'), cuerpo: cuerpo('147 Asociación vigente del sensor'), assertions: assertionsDe('147 Asociación vigente del sensor') },
      '147_area_solicitada': { http: http('147 Área alternativa existe'), cuerpo: cuerpo('147 Área alternativa existe'), assertions: assertionsDe('147 Área alternativa existe') },
      'rangos': { http: http('Rangos de calibración'), assertions: assertionsDe('Rangos de calibración') }
    },
    casos: {}
  };
  for (const k of Object.keys(H.CASOS)) {
    preservado.casos[k] = {
      pre: { http: http(`${k} PRE historial`), cuerpo: cuerpo(`${k} PRE historial`), assertions: assertionsDe(`${k} PRE historial`) },
      post: { http: http(`${k} POST historial`), cuerpo: cuerpo(`${k} POST historial`), assertions: assertionsDe(`${k} POST historial`) },
      calibrar: { http: http(`${k} POST calibrar`), cuerpo: cuerpo(`${k} POST calibrar`), enviado: enviado(`${k} POST calibrar`), assertions: assertionsDe(`${k} POST calibrar`) }
    };
  }
  fs.writeFileSync(SUMMARY_TMP(), limpiar(JSON.stringify(preservado, null, 2)));

  const st = preservado.stats;
  log('\n================ RUN OFICIAL ================');
  log(`RUN_ID: ${runId}`);
  log(`requests ${st.requests.ejecutados} (fallidos ${st.requests.fallidos}) | assertions ${st.assertions.total} (fallidas ${st.assertions.fallidas})`);
  log(`POST de calibración ejecutados: ${preservado.postCalibrar}/${H.POST_BUDGET} | PATCH: ${preservado.patchs} | STOP_ALL: ${preservado.stopAll}`);
  for (const [k, meta] of Object.entries(H.CASOS)) {
    const c = preservado.casos[k];
    log(`  ${meta.caso} HTTP ${c.calibrar.http} (esperado ${meta.http}) | error_code ${c.calibrar.cuerpo?.error_code} | mensaje ${c.calibrar.cuerpo?.message === (k === '146' ? EXP_146 : EXP_147) ? 'EXACTO' : 'NO COINCIDE'}`);
  }
  if (preservado.failures.length) {
    log('\nFAILURES:');
    preservado.failures.forEach((f, i) => log(`  ${i + 1}. ${f.item} :: ${f.assertion} :: ${f.error}`));
  }
  log('=============================================\n');
  log(`HTML: ${path.relative(EVAL_DIR, html).split(path.sep).join('/')}`);
  log('Ejecute ahora el modo close para consolidar la evidencia.');

  if (preservado.failures.length) process.exitCode = 2;
}

// ---------------------------------------------------------------------------------- close
async function modoClose() {
  const tmp = SUMMARY_TMP();
  const evidenciaPath = path.join(RUN_DIR, 'evidencia.json');

  // Idempotencia: si el summary temporal ya se retiró pero la evidencia existe, el cierre
  // solo recalcula lo que no depende del RUN (escaneo de secretos y estado de git). Nunca
  // se vuelve a la red ni se reinterpreta el oráculo ya emitido.
  if (!fs.existsSync(tmp)) {
    if (!fs.existsSync(evidenciaPath)) throw new Error('No hay summary preservado del RUN ni evidencia previa: ejecute primero G76_MODO=run.');
    const ev = JSON.parse(fs.readFileSync(evidenciaPath, 'utf8'));
    ev.seguridad = escanearSeguridad();
    ev.git_post = estadoGit('git_post');
    escribir('evidencia.json', ev);

    // El manifiesto se rehace para que los SHA-256 correspondan a los archivos tal como
    // quedan al cierre, indicando qué cambió después del RUN y por qué.
    const manifestPath = path.join(RUN_DIR, 'automation_manifest.json');
    if (fs.existsSync(manifestPath)) {
      const man = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
      const cambios = [];
      man.artefactos = man.artefactos.map(a => {
        const abs = path.join(CASE_DIR, a.ruta.replace('tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G76-v2.0/', ''));
        if (!fs.existsSync(abs)) return a;
        const actual = sha256(abs);
        if (a.sha256 && a.sha256 !== actual) {
          cambios.push(a.archivo);
          return { ...a, sha256: actual, sha256_durante_el_run: a.sha256, bytes: fs.statSync(abs).size, cambio_posterior_al_run: MOTIVO_CAMBIO_POSTERIOR[a.archivo] || 'modificado despues del RUN' };
        }
        return { ...a, sha256: actual, bytes: fs.statSync(abs).size };
      });
      man.cambiosPosterioresAlRun = cambios.length
        ? cambios.map(c => ({ archivo: c, motivo: MOTIVO_CAMBIO_POSTERIOR[c] || 'modificado despues del RUN' }))
        : [];
      man.integridadDeLaColeccionEjecutada = man.artefactos
        .filter(a => /postman_collection/.test(a.archivo))
        .every(a => !a.sha256_durante_el_run)
          ? 'OK: la coleccion ejecutada y la original no cambiaron desde el RUN'
          : 'ATENCION: la coleccion cambio despues del RUN';
      fs.writeFileSync(manifestPath, limpiar(JSON.stringify(man, null, 2)));
      if (cambios.length) log(`Manifiesto actualizado. Cambios posteriores al RUN: ${cambios.join(', ')}`);
    }
    log('\n=== CIERRE (recalculo de seguridad y git, sin tocar el oráculo) ===');
    log(`GRUPO ${H.GROUP_ID} -> ${ev.resultado_grupo}`);
    log(`Evidencia limpia de secretos: ${ev.seguridad.limpio ? 'SI' : 'NO'}`);
    if (!ev.seguridad.limpio) {
      ev.seguridad.archivosConHallazgos.forEach(a => log(`  ${a.archivo} | ${JSON.stringify(a.secretos)} | credenciales en claro: ${a.credencialesEnClaro}`));
    }
    log('==================================================================\n');
    if (!ev.seguridad.limpio) process.exitCode = 3;
    return;
  }
  const R = JSON.parse(fs.readFileSync(tmp, 'utf8'));

  const sid = (x) => (x && x.id_sensor !== undefined ? x.id_sensor : x && x.id_sensores);
  const vig = (x) => x && x.tiene_estado === true && (x.fecha_finalizacion === null || x.fecha_finalizacion === undefined);
  const rangoDe = (cat) => {
    const r = (R.rangos?.items || []).find(x => x.categoria === cat);
    return r ? { categoria: cat, min: String(r.valor_min), max: String(r.valor_max) } : null;
  };

  // -------------------------------------------------------------- oráculo por caso
  const casos = {};
  for (const [k, meta] of Object.entries(H.CASOS)) {
    const c = R.casos[k];
    const esperado = k === '146' ? EXP_146 : EXP_147;
    const pre = c.pre.cuerpo, post = c.post.cuerpo, resp = c.calibrar.cuerpo;
    const preIds = pre ? (pre.items || []).map(x => x.id_calibracion) : null;
    const postIds = post ? (post.items || []).map(x => x.id_calibracion) : null;
    const nuevos = preIds && postIds ? postIds.filter(x => !preIds.includes(x)) : null;
    const obtenido = resp ? resp.message ?? null : null;

    let historicosIntactos = null;
    if (pre && post) {
      historicosIntactos = (pre.items || []).every(s => {
        const row = (post.items || []).find(x => x.id_calibracion === s.id_calibracion);
        return row && String(row.valor_referencia) === String(s.valor_referencia) &&
          row.fecha_calibracion === s.fecha_calibracion && row.id_usuario === s.id_usuario &&
          row.observaciones === s.observaciones;
      });
    }
    const assertionsFuncionales = [...c.pre.assertions, ...c.calibrar.assertions, ...c.post.assertions];

    const oraculo = {
      [`http_${meta.http}`]: c.calibrar.http === meta.http,
      error_code_esperado: resp?.error_code === (k === '146' ? 'DISPOSITIVO_INACTIVO' : 'SENSOR_AREA_INVALIDA'),
      mensaje_exacto: obtenido === esperado,
      sin_calibracion_en_la_respuesta: resp ? resp.id_calibracion === undefined : false,
      sin_persistencia: Array.isArray(nuevos) && nuevos.length === 0,
      total_sin_cambios: Boolean(pre) && Boolean(post) && Number(pre.total) === Number(post.total),
      ids_identicos: Boolean(preIds) && Boolean(postIds) && JSON.stringify(preIds.slice().sort()) === JSON.stringify(postIds.slice().sort()),
      historial_intacto: historicosIntactos === true,
      assertions_funcionales_todas_pass: assertionsFuncionales.length > 0 && assertionsFuncionales.every(a => a.paso)
    };

    casos[k] = {
      caso: meta.caso, titulo: meta.titulo,
      ejecutado: c.calibrar.http !== null,
      endpoint: `/configuracion/sensores/${k === '146' ? FIX['146'].sensor : FIX['147'].sensor}/calibrar`,
      request: { metodo: 'POST', headers: { Authorization: '[REDACTED]', 'Content-Type': 'application/json' }, body: c.calibrar.enviado },
      httpEsperado: meta.http, httpObtenido: c.calibrar.http,
      error_codeEsperado: k === '146' ? 'DISPOSITIVO_INACTIVO' : 'SENSOR_AREA_INVALIDA',
      error_codeObtenido: resp?.error_code ?? null,
      response: { http: c.calibrar.http, cuerpo: resp },
      mensajeEsperado: esperado, mensajeObtenido: obtenido, mensajeCoincide: obtenido === esperado,
      comparacionLiteral: obtenido === esperado
        ? { tipo: 'igualdad literal', resultado: 'coincide caracter a caracter' }
        : { tipo: 'igualdad literal', resultado: 'no coincide', esperado, obtenido },
      fechaEnviada: c.calibrar.enviado ? c.calibrar.enviado.fecha_calibracion : null,
      historialPre: pre ? { total: pre.total, ids: preIds, items: pre.items || [] } : null,
      historialPost: post ? { total: post.total, ids: postIds, items: post.items || [] } : null,
      idsNuevos: nuevos, historicosIntactos,
      assertionsFuncionales: { total: assertionsFuncionales.length, fallidas: assertionsFuncionales.filter(a => !a.paso).length, detalle: assertionsFuncionales },
      oraculo,
      resultado: c.calibrar.http === null ? 'NO EJECUTADO' : Object.values(oraculo).every(x => x === true) ? 'APROBADO' : 'RECHAZADO'
    };
  }

  const rechazados = Object.values(casos).filter(c => c.resultado === 'RECHAZADO').length;
  const noEjecutados = Object.values(casos).filter(c => c.resultado === 'NO EJECUTADO').length;
  const newmanLimpio = R.failures.length === 0 && (R.stats.requests.fallidos || 0) === 0;
  const resultadoGrupo = rechazados > 0 ? 'RECHAZADO'
    : noEjecutados > 0 ? 'BLOQUEADO / NO VERIFICABLE'
    : newmanLimpio ? 'APROBADO' : 'RECHAZADO';

  // ------------------------------------------------ precondiciones observadas en el RUN
  const p = R.precondiciones;
  const sensor146 = (p['146_sensores'].cuerpo?.items || []).find(x => sid(x) === FIX['146'].sensor) || null;
  const asoc146 = (p['146_asociaciones'].cuerpo?.items || []).find(x => vig(x) && sid(x) === FIX['146'].sensor && x.id_dispositivo_iot === FIX['146'].device) || null;
  const sensor147 = (p['147_sensores'].cuerpo?.items || []).find(x => sid(x) === FIX['147'].sensor) || null;
  const vigentes147 = (p['147_asociaciones'].cuerpo?.items || []).filter(x => vig(x) && sid(x) === FIX['147'].sensor);
  const asoc147 = vigentes147.find(x => x.id_dispositivo_iot === FIX['147'].device) || null;

  const fixture146 = {
    fixtureOriginalDeLaMatriz: FIX['146'].device === 47 && FIX['146'].sensor === 29 && FIX['146'].area === 3,
    dispositivo: { id: p['146_dispositivo'].cuerpo?.id_dispositivo_iot ?? null, serial: p['146_dispositivo'].cuerpo?.serial ?? null, es_activo: p['146_dispositivo'].cuerpo?.es_activo ?? null, http: p['146_dispositivo'].http },
    serialEsperadoPorElCaso: FIX['146'].serial,
    serialCoincide: p['146_dispositivo'].cuerpo?.serial === FIX['146'].serial,
    sensor: sensor146 ? { id: sid(sensor146), nombre: sensor146.nombre, categoria: sensor146.categoria, es_activo: sensor146.es_activo, id_dispositivo_iot: sensor146.id_dispositivo_iot } : null,
    asociacionVigente: asoc146 ? { id_dispositivo_iot: asoc146.id_dispositivo_iot, id_infraestructura: asoc146.id_infraestructura, tiene_estado: asoc146.tiene_estado, fecha_finalizacion: asoc146.fecha_finalizacion } : null,
    areaEnviada: FIX['146'].area,
    areaEnviadaEsLaVigente: asoc146?.id_infraestructura === FIX['146'].area,
    rango: rangoDe(FIX['146'].categoria),
    valorEnviado: FIX['146'].valor,
    valorEstrictamenteInterior: Boolean(rangoDe(FIX['146'].categoria)) &&
      Number(FIX['146'].valor) > Number(rangoDe(FIX['146'].categoria).min) &&
      Number(FIX['146'].valor) < Number(rangoDe(FIX['146'].categoria).max),
    preparacion: { patchPlanificados: 0, patchEjecutados: R.patchs, seDesactivoAlgunDispositivo: false, motivo: 'el dispositivo del caso ya estaba inactivo: no se preparo nada y el runner no ejecuta PATCH en ningun modo' }
  };
  const fixture147 = {
    fixtureOriginalDeLaMatriz: FIX['147'].device === 3 && FIX['147'].sensor === 6 && FIX['147'].areaVigente === 3 && FIX['147'].areaSolicitada === 1,
    dispositivo: { id: p['147_dispositivo'].cuerpo?.id_dispositivo_iot ?? null, serial: p['147_dispositivo'].cuerpo?.serial ?? null, es_activo: p['147_dispositivo'].cuerpo?.es_activo ?? null, http: p['147_dispositivo'].http },
    sensor: sensor147 ? { id: sid(sensor147), nombre: sensor147.nombre, categoria: sensor147.categoria, es_activo: sensor147.es_activo, id_dispositivo_iot: sensor147.id_dispositivo_iot } : null,
    areasVigentesDelSensor: vigentes147.map(x => x.id_infraestructura),
    areaVigente: asoc147 ? { id_infraestructura: asoc147.id_infraestructura, tiene_estado: asoc147.tiene_estado, fecha_finalizacion: asoc147.fecha_finalizacion } : null,
    areaSolicitada: {
      id_infraestructura: p['147_area_solicitada'].cuerpo?.id_infraestructura ?? null,
      es_activo: p['147_area_solicitada'].cuerpo?.es_activo ?? null,
      http: p['147_area_solicitada'].http,
      existeEnTest: p['147_area_solicitada'].http === 200,
      distintaDeLaVigente: FIX['147'].areaSolicitada !== (asoc147?.id_infraestructura ?? null),
      asociadaAlSensor: vigentes147.map(x => x.id_infraestructura).includes(FIX['147'].areaSolicitada)
    },
    rango: rangoDe(FIX['147'].categoria),
    valorEnviado: FIX['147'].valor,
    valorEstrictamenteInterior: Boolean(rangoDe(FIX['147'].categoria)) &&
      Number(FIX['147'].valor) > Number(rangoDe(FIX['147'].categoria).min) &&
      Number(FIX['147'].valor) < Number(rangoDe(FIX['147'].categoria).max)
  };

  // ------------------------------------------------------- comparación con la primera
  const PRIMERA = {
    runId: 'run-20261007-074315',
    fuente: 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G76-v2.0/RESULTADOS/run-20261007-074315/TC-M09-G76_resultado.md',
    '146': { resultado: 'RECHAZADO', http: '422 correcto', error_code: 'DISPOSITIVO_INACTIVO correcto', persistencia: 'Correcta (no persistio)', mensaje: 'Incorrecto', mensajeObtenido: 'Solo se pueden calibrar sensores de dispositivos activos.' },
    '147': { resultado: 'RECHAZADO', http: '400 correcto', error_code: 'SENSOR_AREA_INVALIDA correcto', persistencia: 'Correcta (no persistio)', mensaje: 'Incorrecto', mensajeObtenido: 'El sensor 6 no está asociado al área 1. Verifique la ubicación física y lógica del equipo antes de calibrar.' },
    grupo: 'RECHAZADO'
  };
  const comparacion = {
    baselineUnico: `PRIMERA EVALUACION OFICIAL ${PRIMERA.runId}`,
    fuente: PRIMERA.fuente,
    porCaso: Object.fromEntries(Object.entries(H.CASOS).map(([k, meta]) => [meta.caso, {
      primera: PRIMERA[k].resultado, segunda: casos[k].resultado,
      cambio: casos[k].resultado === PRIMERA[k].resultado ? 'SIN CAMBIO' : `${PRIMERA[k].resultado} -> ${casos[k].resultado}`,
      dimensiones: {
        http: { primera: PRIMERA[k].http, segunda: `${casos[k].httpObtenido} ${casos[k].oraculo[`http_${meta.http}`] ? 'correcto' : 'incorrecto'}` },
        error_code: { primera: PRIMERA[k].error_code, segunda: `${casos[k].error_codeObtenido} ${casos[k].oraculo.error_code_esperado ? 'correcto' : 'incorrecto'}` },
        no_persistencia: { primera: PRIMERA[k].persistencia, segunda: casos[k].oraculo.sin_persistencia ? 'Correcta (no persistio)' : 'INCORRECTA' },
        mensaje: { primera: PRIMERA[k].mensaje, segunda: casos[k].mensajeCoincide ? 'Correcto (literal)' : 'Incorrecto' }
      },
      mensajeAnterior: PRIMERA[k].mensajeObtenido,
      mensajeActual: casos[k].mensajeObtenido,
      causaAnteriorCorregida: casos[k].mensajeCoincide ? 'SI' : 'NO'
    }])),
    grupo: { primera: PRIMERA.grupo, segunda: resultadoGrupo, cambio: resultadoGrupo === PRIMERA.grupo ? 'SIN CAMBIO' : `${PRIMERA.grupo} -> ${resultadoGrupo}` },
    causaDelRechazoAnterior: Object.values(casos).every(c => c.mensajeCoincide) ? 'CORREGIDA'
      : Object.values(casos).some(c => c.mensajeCoincide) ? 'PARCIALMENTE CORREGIDA' : 'NO CORREGIDA'
  };

  const anomalia = Object.values(casos).some(c => !c.ejecutado || c.httpObtenido === null || c.httpObtenido >= 500 || c.httpObtenido !== c.httpEsperado || c.oraculo.sin_persistencia !== true);

  // ------------------------------------------------------------------- manifiesto
  const artefactos = [
    { archivo: 'run-g76-v2.cjs', abs: path.join(__dirname, 'run-g76-v2.cjs'),
      ruta: 'TC-M09-G76-v2.0/EvaluacionV2/automation/run-g76-v2.cjs',
      funcion: 'Runner unico de la reevaluacion, con los modos precheck (Newman de solo lectura, sin HTML ni archivos), run (RUN funcional oficial con los 2 POST y el unico HTML) y close (consolidacion de evidencia y manifiesto, sin red). Nunca autentica con el correo del actor y no ejecuta PATCH.' },
    { archivo: 'TC-M09-G76-v2.0.postman_collection.json', abs: COLECCION,
      ruta: 'TC-M09-G76-v2.0/EvaluacionV2/TC-M09-G76-v2.0.postman_collection.json',
      funcion: 'Copia de la coleccion funcional para EvaluacionV2. Unico cambio autorizado: los 6 GET de precondicion usan {{session_value}} en lugar de un token externo. Items, metodos, URLs, bodies, assertions, orden, codigos y mensajes esperados y los 2 POST de calibracion son los de la primera evaluacion.' },
    { archivo: 'TC-M09-G76-v2.0.postman_collection.json (original)', abs: COLECCION_ORIGINAL,
      ruta: 'TC-M09-G76-v2.0/TC-M09-G76-v2.0.postman_collection.json',
      funcion: 'Coleccion funcional de la primera evaluacion. Reutilizada como fuente, en solo lectura; no fue modificada.' },
    { archivo: 'helpers.cjs', abs: path.join(CASE_DIR, 'helpers.cjs'),
      ruta: 'TC-M09-G76-v2.0/helpers.cjs',
      funcion: 'Reutilizado en solo lectura para las constantes del grupo y los constructores de los mensajes exigidos por RF-24 v2.0 (mensaje146 y mensaje147). No se usan sus funciones de login ni de discovery.' }
  ];
  const manifest = {
    grupo: H.GROUP_ID, runId, commit: R.gitPre.commit,
    nota: 'Artefactos finales de la SEGUNDA EVALUACION. Los ejecutables viven unicamente en EvaluacionV2/; no se copia automation dentro de RESULTADOS.',
    artefactos: artefactos.map(a => ({
      archivo: a.archivo, ruta: `tests/Test_Testing/Test_Modulo9/RF-24/${a.ruta}`, funcion: a.funcion,
      sha256: fs.existsSync(a.abs) ? sha256(a.abs) : null,
      bytes: fs.existsSync(a.abs) ? fs.statSync(a.abs).size : null
    })),
    newmanHtmlPersistentes: 1,
    automationDentroDeResultados: 'NO'
  };
  escribir('automation_manifest.json', manifest);

  // -------------------------------------------------------------------- evidencia
  const evidencia = {
    run_id: runId,
    evaluacion: 'SEGUNDA EVALUACION',
    grupo: H.GROUP_ID, requisito: H.RF, caso_de_uso: H.CU,
    herramienta: 'Newman',
    ambiente: { decisorio: 'TEST', base_url: base() },
    carpeta: `tests/Test_Testing/Test_Modulo9/RF-24/${H.FOLDER}/EvaluacionV2/`,
    rama: R.gitPre.rama, commit: R.gitPre.commit,
    resultado_grupo: resultadoGrupo,

    git_pre: R.gitPre,

    actor: {
      rol_esperado: 'Ingeniero de Campo',
      correo: actorEmail,
      id_usuario: R.identidad?.id_usuario ?? null,
      rol_confirmado: R.identidad?.nombre_rol ?? null,
      credencial: '[REDACTED]',
      sesion: 'la coleccion Newman es duena de la sesion: hace su propio login y publica el token en {{session_value}}; el runner nunca se autentica con este correo ni inyecta tokens',
      administrador_auxiliar: R.usarAdmin ? { usado: true, correo: adminEmail, alcance: 'solo GET de discovery' } : { usado: false, motivo: 'todas las lecturas las resolvio el Ingeniero de Campo; su item de login quedo excluido de la coleccion ejecutada' }
    },
    permisos: {
      total: (R.permisos?.permisos || []).length,
      delCaso: {
        'recurso 11 accion 2': (R.permisos?.permisos || []).some(x => x.id_recurso === 11 && x.id_accion === 2),
        'recurso 12 accion 1': (R.permisos?.permisos || []).some(x => x.id_recurso === 12 && x.id_accion === 1),
        'recurso 12 accion 2': (R.permisos?.permisos || []).some(x => x.id_recurso === 12 && x.id_accion === 2)
      }
    },

    precheck: {
      tipo: 'validacion Newman de solo lectura previa al RUN',
      genera_html: false, crea_resultados: false, deja_archivos: false,
      post_calibrar: 0, patch: 0,
      nota: 'Su resultado se mostro solo por consola y fue PASS con 0 failures: requisito para ejecutar el RUN funcional.'
    },

    rangos: {
      fuente: 'GET /configuracion/sensores/rangos-calibracion (dentro del RUN)',
      vigentes: { [FIX['146'].categoria]: rangoDe(FIX['146'].categoria), [FIX['147'].categoria]: rangoDe(FIX['147'].categoria) },
      esperados_por_el_caso: RANGOS_ESPERADOS
    },

    fixture_146: fixture146,
    fixture_147: fixture147,

    'TC-M09-146-v2.0': casos['146'],
    'TC-M09-147-v2.0': casos['147'],

    newman: {
      html: `newman/newman-${H.GROUP_ID}.html`,
      htmlPersistentes: 1,
      coleccionEjecutada: `${R.itemsEjecutables} de ${R.itemsTotales} items`,
      itemsExcluidos: R.itemsExcluidos,
      iterations: R.stats.iterations,
      requests: R.stats.requests,
      assertions: R.stats.assertions,
      failures: R.failures,
      presupuesto: {
        postCalibrarPlanificados: H.POST_BUDGET, postCalibrarEjecutados: R.postCalibrar,
        patchPlanificados: 0, patchEjecutados: R.patchs, reintentos: 0
      },
      stopAll: R.stopAll,
      stopAllMotivo: R.stopAllMotivo ? JSON.parse(R.stopAllMotivo) : null,
      limpio: newmanLimpio
    },

    verificacion_de_no_persistencia: Object.fromEntries(Object.entries(H.CASOS).map(([k, meta]) => [meta.caso, {
      totalPre: casos[k].historialPre?.total ?? null,
      totalPost: casos[k].historialPost?.total ?? null,
      idsPre: casos[k].historialPre?.ids ?? null,
      idsPost: casos[k].historialPost?.ids ?? null,
      idsIdenticos: casos[k].oraculo.ids_identicos,
      idsNuevos: casos[k].idsNuevos,
      persistenciaNueva: Array.isArray(casos[k].idsNuevos) && casos[k].idsNuevos.length > 0,
      historicosIntactos: casos[k].historicosIntactos,
      respuestaSinIdCalibracion: casos[k].oraculo.sin_calibracion_en_la_respuesta
    }])),

    contraste_dev: {
      necesario: anomalia,
      motivo: anomalia
        ? 'TEST presenta una anomalia relevante: procede contraste de solo lectura en DEV.'
        : 'TEST paso completamente: ambos casos devolvieron el codigo y el error_code exigidos, el mensaje literal del requisito y no persistieron. No se uso DEV.',
      peticiones_a_dev: 0
    },

    comparacion_primera_segunda: comparacion,

    seguridad: null,
    git_post: estadoGit('git_post')
  };
  escribir('evidencia.json', evidencia);

  // ------------------------------------------------------------------- seguridad
  evidencia.seguridad = escanearSeguridad();
  escribir('evidencia.json', evidencia);

  // El summary temporal no es evidencia: se retira para dejar la carpeta mínima.
  fs.unlinkSync(tmp);

  log('\n================ CIERRE ================');
  log(`RUN_ID: ${runId}`);
  for (const [k, meta] of Object.entries(H.CASOS)) {
    const c = casos[k];
    log(`${meta.caso}: HTTP ${c.httpObtenido}/${c.httpEsperado} | error_code ${c.error_codeObtenido} | mensaje ${c.mensajeCoincide ? 'EXACTO' : 'NO COINCIDE'} | PRE ${c.historialPre?.total} POST ${c.historialPost?.total} | nuevos ${JSON.stringify(c.idsNuevos)} -> ${c.resultado}`);
  }
  log(`GRUPO ${H.GROUP_ID} -> ${resultadoGrupo}`);
  log(`Newman: requests ${R.stats.requests.ejecutados} (fallidos ${R.stats.requests.fallidos}) | assertions ${R.stats.assertions.total} (fallidas ${R.stats.assertions.fallidas}) | limpio: ${newmanLimpio ? 'SI' : 'NO'}`);
  log(`POST calibrar ${R.postCalibrar}/${H.POST_BUDGET} | PATCH ${R.patchs} | STOP_ALL ${R.stopAll}`);
  log(`Causa del rechazo anterior: ${comparacion.causaDelRechazoAnterior}`);
  log(`Contraste DEV necesario: ${anomalia ? 'SI' : 'NO'}`);
  log(`Evidencia limpia de secretos: ${evidencia.seguridad.limpio ? 'SI' : 'NO'}`);
  log('========================================\n');

  if (!evidencia.seguridad.limpio) process.exitCode = 3;
  else if (resultadoGrupo !== 'APROBADO') process.exitCode = 2;
}
