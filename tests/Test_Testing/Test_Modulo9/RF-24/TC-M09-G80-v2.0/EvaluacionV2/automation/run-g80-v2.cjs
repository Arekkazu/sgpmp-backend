// Runner único de la SEGUNDA EVALUACIÓN de TC-M09-G80-v2.0 (RF-24 v2.0, Módulo 9).
// Caso TC-M09-151-v2.0 — una calibración SENSOR exitosa debe quedar registrada en RF-10.
//
// Un solo archivo, tres modos (G80_MODO):
//
//   precheck  Validación Newman previa. Ejecuta la colección filtrada en memoria SIN el POST
//             /calibrar; no escribe nada de negocio, no genera HTML, no crea RESULTADOS y no
//             deja archivos: solo consola. El RUN se autoriza únicamente si failures = 0.
//   run       RUN funcional oficial: la colección completa una única vez, con el ÚNICO POST de
//             calibración y el ÚNICO reporte Newman HTML persistente.
//   close     Oráculo RF-10: recorre TODAS las páginas de GET /auditoria/ en la ventana real,
//             correlaciona por campos estructurados, hace la verificación final de solo
//             lectura y consolida evidencia.json y automation_manifest.json.
//
// PROPIEDAD DE SESIONES (corrección de G76/G77): la colección es dueña de sus sesiones. Hace
// sus propios logins y publica los tokens en {{ing_session}} y {{admin_session}}. El runner NO
// inicia sesión antes de Newman y NO inyecta ningún token: solo pasa configuración. Motivo:
// TEST aplica sesión única por usuario. El modo close sí se autentica, pero DESPUÉS del RUN y
// exclusivamente para GET.
//
// ESTA PRUEBA PERSISTE: el RUN crea exactamente UNA calibración nueva y no se elimina. No hay
// cleanup funcional: la calibración y su evento de auditoría son la evidencia del RUN.
//
// Presupuesto: 1 POST /calibrar, sin reintentos. Ninguna otra escritura. Sin SQL de escritura.
//
// Uso:
//   $env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
//   $env:QA_ING_EMAIL="ingeniero@pecuaria.co"
//   $env:QA_ING_PASSWORD="<secreto>"
//   $env:QA_ADMIN_EMAIL="administador.dev@gmail.com"
//   $env:QA_ADMIN_PASSWORD="<secreto>"
//   $env:G80_RUN_ID="run-YYYYMMDD-HHMMSS"      (modos run y close)
//   $env:G80_MODO="precheck" | "run" | "close"
//   node .\run-g80-v2.cjs

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const CASE_DIR = path.resolve(__dirname, '..', '..');
const EVAL_DIR = path.resolve(__dirname, '..');
const COLECCION = path.join(EVAL_DIR, 'TC-M09-G80-v2.0.postman_collection.json');
const COLECCION_ORIGINAL = path.join(CASE_DIR, 'TC-M09-G80-v2.0.postman_collection.json');

const GRUPO = 'TC-M09-G80-v2.0';
const CASO = 'TC-M09-151-v2.0';
const RF = 'RF-24 v2.0 (integración con RF-10)';
const POST_BUDGET = 1;
const ITEM_CALIBRAR = 'POST calibrar';
// Items que el PRECHECK no puede ejecutar: son POSCONDICIONES del POST de calibración, no
// precondiciones. Dependen del id_calibracion y de la fecha persistida que produce la
// escritura, así que sin ella no tienen nada que verificar. La disponibilidad de
// GET /auditoria/ se comprueba aparte, con una lectura propia del precheck.
const ITEMS_POSCONDICION = ['Historial POST', 'Auditoría RF-10'];

const MODO = process.env.G80_MODO || 'precheck';
if (!['precheck', 'run', 'close'].includes(MODO)) throw new Error(`G80_MODO no reconocido: ${MODO}`);

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

// ------------------------------------------------------------------ fixture del caso
const FIX = {
  sensor: Number(process.env.G80_SENSOR || 6),
  dispositivo: Number(process.env.G80_DEVICE || 3),
  area: Number(process.env.G80_AREA || 3),
  categoria: process.env.G80_CAT || 'TEMPERATURA',
  valor: process.env.G80_VALOR || '22.5000'
};
const OBSERVACIONES = `QA ${CASO}`;
const VENTANA_MS = 60000; // ±1 minuto, construido con la fecha persistida de la calibración.

const log = (...a) => console.log(...a);
const sha256 = (f) => crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
const igualDecimal = (a, b) => Number(a) === Number(b);

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
const runId = process.env.G80_RUN_ID;
if (MODO !== 'precheck' && (!runId || !/^run-\d{8}-\d{6}$/.test(runId))) {
  throw new Error('G80_RUN_ID requerido con formato run-YYYYMMDD-HHMMSS.');
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
  carpeta_historica_TC_M09_G80: git(['status', '--short', '--', 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G80']) || '(vacio = intacta)',
  primera_evaluacion_RESULTADOS: git(['status', '--short', '--', 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G80-v2.0/RESULTADOS']) || '(vacio = intacta)',
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
    criterio: 'Se marcan solo VALORES de secreto: contrasenas en uso, JWT, Authorization con token, cookies, tokens en pares clave-valor y cadenas de conexion. En los .cjs solo se evaluan valores y la coincidencia literal con las credenciales. Los correos de los actores los publica el propio caso.',
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
    ['device_id', String(FIX.dispositivo)], ['sensor_id', String(FIX.sensor)],
    ['area_id', String(FIX.area)], ['categoria', FIX.categoria], ['valor', FIX.valor],
    ['observaciones', OBSERVACIONES],
    ['body_calibracion', body]
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
    if (/\/calibrar/.test(url) && !permitirCalibrar) throw new Error(`ABORTADO: el PRECHECK no puede contener el endpoint de calibración (${it.name}).`);
    if (metodo === 'POST' && !/\/sesiones\/?$/.test(url) && !/\/calibrar/.test(url)) throw new Error(`ABORTADO: POST no autorizado: ${url} (${it.name}).`);
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

// HTTP directo: solo para el oráculo RF-10 y la verificación final, DESPUÉS del RUN.
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

// ------------------------------------------------- correlación RF-10 por campos estructurados
// No se buscan subcadenas: un "6" o un "3" pueden aparecer dentro de una IP o un timestamp.
// Se exige coincidencia en los campos estructurados del detalle del evento.
function evaluarCorrelacion(ev, ctx) {
  const d = ev.detalle || {};
  const fecha = new Date(ev.fecha_evento || ev.fecha || 0).getTime();
  const criterios = {
    usuario: Number(ev.id_usuario) === Number(ctx.ingId) || Number(d.id_usuario) === Number(ctx.ingId),
    fecha_en_ventana: fecha >= ctx.desdeMs && fecha <= ctx.hastaMs,
    sensor: d.id_sensor !== undefined && Number(d.id_sensor) === Number(ctx.sensor),
    dispositivo: d.id_dispositivo_iot !== undefined && Number(d.id_dispositivo_iot) === Number(ctx.dispositivo),
    valor: d.valor_referencia !== undefined && igualDecimal(d.valor_referencia, ctx.valor),
    operacion_de_calibracion: /CALIBRAC/i.test(String(d.operacion || '')) ||
      (ctx.tipoExitosa !== null && Number(ev.tipo_evento) === Number(ctx.tipoExitosa)),
    resultado_exitoso: String(ev.resultado || '').toLowerCase() === 'exitoso'
  };
  // Refuerzo opcional (seccion 35): no se exige si RF-10 no lo expone.
  const refuerzos = {
    id_calibracion: d.id_calibracion !== undefined ? Number(d.id_calibracion) === Number(ctx.idCalibracion) : null,
    infraestructura: d.id_infraestructura !== undefined ? Number(d.id_infraestructura) === Number(ctx.area) : null,
    modo_calibracion: d.modo_calibracion !== undefined ? String(d.modo_calibracion) === 'SENSOR' : null,
    observaciones: d.observaciones !== undefined ? String(d.observaciones) === ctx.observaciones : null,
    integridad_ok: ev.integridad_ok === undefined ? null : ev.integridad_ok === true
  };
  return { criterios, refuerzos, todosLosCriterios: Object.values(criterios).every(Boolean) };
}

// ==========================================================================================
(async () => {
  if (MODO === 'precheck') return modoPrecheck();
  if (MODO === 'run') return modoRun();
  return modoClose();
})().catch((e) => { console.error('\nNO COMPLETADO:', e.message); process.exitCode = 1; });

// ------------------------------------------------------------------------------- precheck
async function modoPrecheck() {
  const { col, itemsTotales, itemsEjecutables, quitados } = cargarColeccion([ITEM_CALIBRAR, ...ITEMS_POSCONDICION]);
  verificarEscrituras(col, false);

  log('PRECHECK de validación previa — Newman sin reporter HTML, sin carpeta de resultados.');
  log(`Colección: ${itemsEjecutables} de ${itemsTotales} items. Excluidos: ${quitados.join(' | ')}`);
  log('Sin POST /calibrar y sin ninguna escritura de negocio.\n');

  const summary = await correrNewman(col, construirEnv(), null, null);
  const st = stats(summary);
  const f = fallos(summary);
  const { cuerpo, http, asserts } = extraer(summary);
  const pasa = (item) => { const a = asserts(item); return a.length > 0 && a.every(x => x.paso); };

  const me = cuerpo('Identidad Ingeniero');
  const meA = cuerpo('Identidad Administrador');
  const perm = cuerpo('Permisos Ingeniero');
  const disp = cuerpo('Fixture dispositivo');
  const sens = cuerpo('Fixture sensores del dispositivo');
  const asoc = cuerpo('Fixture asociación vigente');
  const rangos = cuerpo('Fixture rango de la categoría');
  const cat = cuerpo('Catálogo RF-10 tipos de evento');
  const sid = (x) => (x && x.id_sensor !== undefined ? x.id_sensor : x && x.id_sensores);
  const vig = (x) => x && x.tiene_estado === true && (x.fecha_finalizacion === null || x.fecha_finalizacion === undefined);
  const sensorRow = (sens?.items || []).find(x => sid(x) === FIX.sensor) || null;
  const asocRow = (asoc?.items || []).find(x => vig(x) && sid(x) === FIX.sensor && x.id_dispositivo_iot === FIX.dispositivo) || null;
  const rango = (rangos?.items || []).find(x => x.categoria === FIX.categoria) || null;
  const tiposCalib = JSON.parse(envDe(summary, 'catalogo_calibracion') || '[]');
  const tipoExitosa = envDe(summary, 'tipo_calibracion_exitosa');

  // /auditoria/ disponible: se comprueba con una ventana reciente, sin crear nada.
  const chequeos = {
    ingeniero: http('Login Ingeniero') >= 200 && http('Login Ingeniero') <= 299 &&
      me?.correo_electronico === ACTORES.ing.email && me?.nombre_rol === 'Ingeniero de Campo' &&
      me?.estado_cuenta === 'Activo' && pasa('Identidad Ingeniero'),
    administrador: http('Login Administrador') >= 200 && http('Login Administrador') <= 299 &&
      meA?.nombre_rol === 'Administrador' && pasa('Identidad Administrador'),
    permisos: (perm?.permisos || []).some(p => p.id_recurso === 12 && p.id_accion === 1) && pasa('Permisos Ingeniero'),
    fixture: disp?.id_dispositivo_iot === FIX.dispositivo && disp?.es_activo === true &&
      Boolean(sensorRow) && sensorRow.es_activo === true && sensorRow.categoria === FIX.categoria &&
      sensorRow.id_dispositivo_iot === FIX.dispositivo &&
      Boolean(asocRow) && asocRow.id_infraestructura === FIX.area &&
      pasa('Fixture dispositivo') && pasa('Fixture sensores del dispositivo') && pasa('Fixture asociación vigente'),
    rango: Boolean(rango) && Number(FIX.valor) > Number(rango.valor_min) && Number(FIX.valor) < Number(rango.valor_max) && pasa('Fixture rango de la categoría'),
    auditoriaDisponible: false,
    catalogoConsultado: http('Catálogo RF-10 tipos de evento') === 200 && pasa('Catálogo RF-10 tipos de evento')
  };

  // Comprobación de /auditoria/ con la sesión del Administrador de la propia colección no es
  // posible fuera de Newman sin reautenticar; se usa una lectura propia de solo lectura.
  let auditoriaHttp = null, auditoriaTotal = null;
  try {
    const tok = await login(ACTORES.admin.email, ACTORES.admin.secret);
    const ahora = Date.now();
    const r = await get(`/auditoria/?id_usuario=${me?.id_usuario}&fecha_desde=${new Date(ahora - 300000).toISOString()}&fecha_hasta=${new Date(ahora + 60000).toISOString()}&tamano=50&pagina=1`, tok);
    auditoriaHttp = r.status; auditoriaTotal = r.cuerpo?.total ?? null;
    chequeos.auditoriaDisponible = r.status === 200 || r.status === 206;
  } catch (e) { auditoriaHttp = `ERROR ${e.message}`; }

  const postCalibrar = contar(summary, /\/calibrar/);
  const autorizar = Object.values(chequeos).every(Boolean) && f.length === 0 &&
    (st.requests.fallidos || 0) === 0 && postCalibrar === 0;

  const P = (b) => (b ? 'PASS' : 'FAIL');
  log('\nPRECHECK_G80\n');
  log(`Ingeniero:\n${P(chequeos.ingeniero)}\n`);
  log(`Administrador:\n${P(chequeos.administrador)}\n`);
  log(`Permisos:\n${P(chequeos.permisos)}\n`);
  log(`Fixture:\n${P(chequeos.fixture)}\n`);
  log(`Rango:\n${P(chequeos.rango)}\n`);
  log(`GET /auditoria:\n${chequeos.auditoriaDisponible ? 'DISPONIBLE' : 'NO DISPONIBLE'}\n`);
  log(`Catálogo:\n${chequeos.catalogoConsultado ? 'CONSULTADO' : 'NO CONSULTADO'}\n`);
  log(`Failures:\n${f.length}\n`);
  log(`POST /calibrar:\n${postCalibrar}\n`);
  log(`AUTORIZAR_RUN:\n${autorizar ? 'SÍ' : 'NO'}\n`);

  log('--- detalle observado (solo consola, no se persiste) ---');
  log(`Ingeniero: id_usuario=${me?.id_usuario} rol="${me?.nombre_rol}" estado=${me?.estado_cuenta} | permiso 12/1=${(perm?.permisos || []).some(p => p.id_recurso === 12 && p.id_accion === 1)}`);
  log(`Administrador: ${ACTORES.admin.email} id_usuario=${meA?.id_usuario} rol="${meA?.nombre_rol}"`);
  log(`fixture: dispositivo ${disp?.id_dispositivo_iot} activo=${disp?.es_activo} | sensor ${sid(sensorRow)} ${sensorRow?.categoria} activo=${sensorRow?.es_activo} | asociación vigente área ${asocRow?.id_infraestructura}`);
  log(`rango ${FIX.categoria}: ${rango?.valor_min}–${rango?.valor_max} | valor ${FIX.valor} interior=${Boolean(rango) && Number(FIX.valor) > Number(rango.valor_min) && Number(FIX.valor) < Number(rango.valor_max)}`);
  log(`catálogo RF-10: ${envDe(summary, 'catalogo_total')} tipos | relacionados con calibración: ${tiposCalib.map(x => x.id_tipo_evento + ':' + (x.nombre || x.nombre_evento)).join(', ') || 'ninguno'}`);
  log(`tipo de calibración exitosa en el catálogo: ${tipoExitosa || '(ninguno)'} — evidencia favorable, NO aprueba el caso`);
  log(`GET /auditoria/: HTTP ${auditoriaHttp} | total en ventana reciente ${auditoriaTotal}`);
  log(`historial PRE del sensor ${FIX.sensor}: total ${envDe(summary, 'pre_total')}`);
  log(`newman: requests ${st.requests.ejecutados}/${st.requests.fallidos} fallidos | assertions ${st.assertions.total}/${st.assertions.fallidas} fallidas`);
  if (f.length) { log('\nfailures:'); f.forEach((x, i) => log(`  ${i + 1}. ${x.item} :: ${x.assertion} :: ${x.error}`)); }
  log('');

  if (!autorizar) { log('El RUN funcional NO está autorizado. Corregir antes de ejecutar la calibración.'); process.exitCode = 2; }
}

// ------------------------------------------------------------------------------------ run
async function modoRun() {
  if (fs.existsSync(RUN_DIR)) throw new Error(`La carpeta ${runId} ya existe. Un RUN oficial no se repite ni se sobrescribe.`);
  const { col, itemsTotales, itemsEjecutables } = cargarColeccion([]);
  verificarEscrituras(col, true);
  const calibrar = col.item.filter(i => /\/calibrar/.test(typeof i.request.url === 'string' ? i.request.url : i.request.url?.raw || ''));
  if (calibrar.length !== POST_BUDGET) throw new Error(`ABORTADO: la colección debe contener exactamente ${POST_BUDGET} POST de calibración, contiene ${calibrar.length}.`);

  const gitPre = estadoGit('git_pre');
  const html = HTML_OFICIAL();

  log(`RUN funcional oficial. RUN_ID: ${runId}`);
  log(`Colección: ${itemsEjecutables} de ${itemsTotales} items.`);
  log(`POST /calibrar planificados: ${POST_BUDGET} | reintentos: 0`);
  log('Esta prueba PERSISTE: la calibración creada no se elimina y su auditoría es evidencia.\n');

  const summary = await correrNewman(col, construirEnv(), html, `${GRUPO} — SEGUNDA EVALUACIÓN · RUN funcional oficial ${runId}`);
  if (fs.existsSync(html)) fs.writeFileSync(html, limpiarHtml(fs.readFileSync(html, 'utf8')));

  const { cuerpo, http, enviado, asserts } = extraer(summary);
  const preservado = {
    runId, generado: new Date().toISOString(), gitPre, itemsTotales, itemsEjecutables,
    stats: stats(summary), failures: fallos(summary),
    postCalibrar: contar(summary, /\/calibrar/),
    ingLogin: { http: http('Login Ingeniero'), assertions: asserts('Login Ingeniero') },
    adminLogin: { http: http('Login Administrador'), assertions: asserts('Login Administrador') },
    identidadIng: { http: http('Identidad Ingeniero'), cuerpo: cuerpo('Identidad Ingeniero'), assertions: asserts('Identidad Ingeniero') },
    identidadAdmin: { http: http('Identidad Administrador'), cuerpo: cuerpo('Identidad Administrador'), assertions: asserts('Identidad Administrador') },
    permisos: { http: http('Permisos Ingeniero'), cuerpo: cuerpo('Permisos Ingeniero'), assertions: asserts('Permisos Ingeniero') },
    fixture: {
      dispositivo: { http: http('Fixture dispositivo'), cuerpo: cuerpo('Fixture dispositivo'), assertions: asserts('Fixture dispositivo') },
      sensores: { http: http('Fixture sensores del dispositivo'), cuerpo: cuerpo('Fixture sensores del dispositivo'), assertions: asserts('Fixture sensores del dispositivo') },
      asociaciones: { http: http('Fixture asociación vigente'), cuerpo: cuerpo('Fixture asociación vigente'), assertions: asserts('Fixture asociación vigente') },
      rangos: { http: http('Fixture rango de la categoría'), cuerpo: cuerpo('Fixture rango de la categoría'), assertions: asserts('Fixture rango de la categoría') }
    },
    catalogo: { http: http('Catálogo RF-10 tipos de evento'), cuerpo: cuerpo('Catálogo RF-10 tipos de evento'), assertions: asserts('Catálogo RF-10 tipos de evento'),
      total: envDe(summary, 'catalogo_total'), calibracion: envDe(summary, 'catalogo_calibracion'), tipoExitosa: envDe(summary, 'tipo_calibracion_exitosa') },
    historialPre: { http: http('Historial PRE'), cuerpo: cuerpo('Historial PRE'), assertions: asserts('Historial PRE') },
    calibracion: { http: http('POST calibrar'), cuerpo: cuerpo('POST calibrar'), enviado: enviado('POST calibrar'), assertions: asserts('POST calibrar') },
    historialPost: { http: http('Historial POST'), cuerpo: cuerpo('Historial POST'), assertions: asserts('Historial POST') },
    auditoriaPagina1: { http: http('Auditoría RF-10'), cuerpo: cuerpo('Auditoría RF-10'), assertions: asserts('Auditoría RF-10') },
    tiempos: {
      t_request_before: envDe(summary, 't_request_before'),
      t_response_after: envDe(summary, 't_response_after'),
      fecha_enviada: envDe(summary, 'fecha_calibracion'),
      fecha_persistida: envDe(summary, 'fecha_persistida')
    },
    ids: { ing: envDe(summary, 'ing_id'), admin: envDe(summary, 'admin_id'), calibracion: envDe(summary, 'id_calibracion') },
    ventana: { desde: envDe(summary, 'ventana_desde'), hasta: envDe(summary, 'ventana_hasta') }
  };
  fs.writeFileSync(SUMMARY_TMP(), limpiar(JSON.stringify(preservado, null, 2)));

  const st = preservado.stats;
  log('\n================ RUN OFICIAL ================');
  log(`RUN_ID: ${runId}`);
  log(`requests ${st.requests.ejecutados} (fallidos ${st.requests.fallidos}) | assertions ${st.assertions.total} (fallidas ${st.assertions.fallidas})`);
  log(`POST /calibrar ejecutados: ${preservado.postCalibrar}/${POST_BUDGET} | reintentos: 0`);
  log(`calibración: HTTP ${preservado.calibracion.http} | id_calibracion ${preservado.ids.calibracion} | id_usuario ${preservado.calibracion.cuerpo?.id_usuario}`);
  log(`fecha persistida: ${preservado.tiempos.fecha_persistida}`);
  log(`ventana de auditoría: ${preservado.ventana.desde} → ${preservado.ventana.hasta}`);
  log(`auditoría página 1: HTTP ${preservado.auditoriaPagina1.http} | total ${preservado.auditoriaPagina1.cuerpo?.total}`);
  if (preservado.failures.length) { log('\nFAILURES:'); preservado.failures.forEach((x, i) => log(`  ${i + 1}. ${x.item} :: ${x.assertion} :: ${x.error}`)); }
  log('=============================================\n');
  log(`HTML: ${path.relative(EVAL_DIR, html).split(path.sep).join('/')}`);
  log('Ejecute ahora el modo close para el oráculo RF-10 y la evidencia.');
  if (preservado.failures.length) process.exitCode = 2;
}

// ---------------------------------------------------------------------------------- close
async function modoClose() {
  const tmp = SUMMARY_TMP();
  const evidenciaPath = path.join(RUN_DIR, 'evidencia.json');
  if (!fs.existsSync(tmp)) {
    if (!fs.existsSync(evidenciaPath)) throw new Error('No hay summary del RUN ni evidencia previa: ejecute primero G80_MODO=run.');
    const ev = JSON.parse(fs.readFileSync(evidenciaPath, 'utf8'));
    ev.seguridad = escanearSeguridad();
    ev.git_post = estadoGit('git_post');
    escribir('evidencia.json', ev);
    refrescarManifest();
    log(`\nCIERRE (recalculo de seguridad y git). CASO ${CASO} -> ${ev.resultado_caso}`);
    log(`Evidencia limpia de secretos: ${ev.seguridad.limpio ? 'SI' : 'NO'}`);
    if (!ev.seguridad.limpio) process.exitCode = 3;
    return;
  }
  const R = JSON.parse(fs.readFileSync(tmp, 'utf8'));

  const ingId = Number(R.ids.ing);
  const idCalibracion = Number(R.ids.calibracion);
  const resp = R.calibracion.cuerpo || {};
  const fechaPersistida = R.tiempos.fecha_persistida && R.tiempos.fecha_persistida !== 'undefined'
    ? R.tiempos.fecha_persistida : R.tiempos.t_request_before;
  const central = new Date(fechaPersistida).getTime();
  const desdeMs = central - VENTANA_MS;
  const hastaMs = central + VENTANA_MS;
  const desde = new Date(desdeMs).toISOString();
  const hasta = new Date(hastaMs).toISOString();
  const tipoExitosa = R.catalogo.tipoExitosa ? Number(R.catalogo.tipoExitosa) : null;

  // --------------------------------- oráculo RF-10: todas las páginas, con el Administrador
  const tokenAdmin = await login(ACTORES.admin.email, ACTORES.admin.secret);
  const paginas = [];
  const eventos = [];
  let pagina = 1, total = null, httpAuditoria = null;
  const TAMANO = 50;
  for (;;) {
    const url = `/auditoria/?id_usuario=${ingId}&fecha_desde=${encodeURIComponent(desde)}&fecha_hasta=${encodeURIComponent(hasta)}&tamano=${TAMANO}&pagina=${pagina}`;
    const r = await get(url, tokenAdmin);
    httpAuditoria = r.status;
    if (r.status !== 200 && r.status !== 206) { paginas.push({ pagina, http: r.status, items: 0, error: r.cuerpo }); break; }
    const items = r.cuerpo?.items || [];
    total = r.cuerpo?.total ?? total;
    paginas.push({ pagina, http: r.status, items: items.length, total });
    eventos.push(...items);
    if (items.length === 0 || eventos.length >= Number(total || 0) || pagina > 40) break;
    pagina += 1;
  }

  const ctx = { ingId, sensor: FIX.sensor, dispositivo: FIX.dispositivo, area: FIX.area, valor: FIX.valor, idCalibracion, observaciones: OBSERVACIONES, tipoExitosa, desdeMs, hastaMs };
  const evaluados = eventos.map(ev => ({
    id_evento: ev.id_evento, tipo_evento: ev.tipo_evento, modulo: ev.modulo, categoria: ev.categoria,
    resultado: ev.resultado, fecha_evento: ev.fecha_evento, id_usuario: ev.id_usuario,
    descripcion: ev.descripcion ?? null, integridad_ok: ev.integridad_ok ?? null, integridad: ev.integridad ?? null,
    detalle: ev.detalle ?? null,
    correlacion: evaluarCorrelacion(ev, ctx)
  }));
  const correlacionados = evaluados.filter(e => e.correlacion.todosLosCriterios);
  const eventoCorrelacionado = correlacionados[0] || null;

  // ------------------------------------------------- verificación final: SOLO LECTURA
  const tokenIng = await login(ACTORES.ing.email, ACTORES.ing.secret);
  const histFinal = await get(`/configuracion/sensores/${FIX.sensor}/calibraciones`, tokenIng);
  const filaFinal = (histFinal.cuerpo?.items || []).find(x => x.id_calibracion === idCalibracion) || null;
  const dispFinal = await get(`/configuracion/dispositivos-iot/${FIX.dispositivo}`, tokenIng);
  const asocFinal = await get(`/configuracion/sensores/${FIX.sensor}/asociaciones`, tokenIng);
  const rangosFinal = await get('/configuracion/sensores/rangos-calibracion', tokenIng);
  const rangoFinal = (rangosFinal.cuerpo?.items || []).find(x => x.categoria === FIX.categoria) || null;
  const sid = (x) => (x && x.id_sensor !== undefined ? x.id_sensor : x && x.id_sensores);
  const vig = (x) => x && x.tiene_estado === true && (x.fecha_finalizacion === null || x.fecha_finalizacion === undefined);
  // Reconsulta del evento, para comprobar que sigue recuperable.
  let eventoReconsultado = null;
  if (eventoCorrelacionado && tipoExitosa !== null) {
    const r2 = await get(`/auditoria/?id_usuario=${ingId}&tipo_evento=${tipoExitosa}&fecha_desde=${encodeURIComponent(desde)}&fecha_hasta=${encodeURIComponent(hasta)}&tamano=${TAMANO}&pagina=1`, tokenAdmin);
    const row = (r2.cuerpo?.items || []).find(x => x.id_evento === eventoCorrelacionado.id_evento) || null;
    eventoReconsultado = { http: r2.status, recuperable: Boolean(row), id_evento: row?.id_evento ?? null, integridad_ok: row?.integridad_ok ?? null };
  }

  // ------------------------------------------------------------------------- oráculo
  const newmanLimpio = R.failures.length === 0 && (R.stats.requests.fallidos || 0) === 0;
  const oraculo = {
    ingeniero_autenticado: R.identidadIng.cuerpo?.correo_electronico === ACTORES.ing.email && R.identidadIng.cuerpo?.nombre_rol === 'Ingeniero de Campo',
    fixture_valido: R.fixture.dispositivo.cuerpo?.es_activo === true,
    calibracion_creada: R.calibracion.http >= 200 && R.calibracion.http <= 299,
    id_calibracion_real: Number.isInteger(idCalibracion) && idCalibracion > 0,
    calibracion_persistida: Boolean(filaFinal),
    administrador_consulta_rf10: httpAuditoria === 200 || httpAuditoria === 206,
    existe_evento_calibracion_exitosa: Boolean(eventoCorrelacionado),
    evento_en_ventana: Boolean(eventoCorrelacionado?.correlacion.criterios.fecha_en_ventana),
    usuario_correcto: Boolean(eventoCorrelacionado?.correlacion.criterios.usuario),
    sensor_correcto: Boolean(eventoCorrelacionado?.correlacion.criterios.sensor),
    dispositivo_correcto: Boolean(eventoCorrelacionado?.correlacion.criterios.dispositivo),
    valor_correcto: Boolean(eventoCorrelacionado?.correlacion.criterios.valor),
    newman_sin_failures: newmanLimpio
  };
  const resultado = Object.values(oraculo).every(Boolean) ? 'APROBADO' : 'RECHAZADO';

  // ---------------------------------------------------------- comparación primera vs segunda
  const PRIMERA = {
    runId: 'run-20261007-085020',
    fuente: 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G80-v2.0/RESULTADOS/run-20261007-085020/TC-M09-G80-v2.0_resultado.md',
    postCalibracion: 'PASS — HTTP 201', persistencia: 'PASS', auditoriaHttp: 'HTTP 200',
    eventoExitoso: 'NO', usuario: 'NO', sensor: 'NO', dispositivo: 'NO', valor: 'NO',
    caso: 'RECHAZADO', grupo: 'RECHAZADO',
    idCalibracion: 15,
    eventosEnVentana: ['LOGIN_EXITOSO (tipo 3)', 'CONSULTA_PERFIL_PROPIO (tipo 19)'],
    catalogo: 'solo CALIBRACION_RECHAZADA (tipo 29); no existia tipo para calibracion exitosa'
  };
  const comparacion = {
    baselineUnico: `PRIMERA EVALUACION OFICIAL ${PRIMERA.runId}`,
    fuente: PRIMERA.fuente,
    porDimension: {
      'POST calibración': { primera: PRIMERA.postCalibracion, segunda: `${oraculo.calibracion_creada ? 'PASS' : 'FAIL'} — HTTP ${R.calibracion.http}`, cambio: 'SIN CAMBIO' },
      'Persistencia': { primera: PRIMERA.persistencia, segunda: oraculo.calibracion_persistida ? 'PASS' : 'FAIL', cambio: oraculo.calibracion_persistida ? 'SIN CAMBIO' : 'PASS -> FAIL' },
      'GET /auditoria/': { primera: PRIMERA.auditoriaHttp, segunda: `HTTP ${httpAuditoria}`, cambio: 'SIN CAMBIO' },
      'Evento de calibración exitosa': { primera: PRIMERA.eventoExitoso, segunda: oraculo.existe_evento_calibracion_exitosa ? 'SÍ' : 'NO', cambio: oraculo.existe_evento_calibracion_exitosa ? 'NO -> SÍ' : 'SIN CAMBIO' },
      'Usuario correlacionado': { primera: PRIMERA.usuario, segunda: oraculo.usuario_correcto ? 'SÍ' : 'NO', cambio: oraculo.usuario_correcto ? 'NO -> SÍ' : 'SIN CAMBIO' },
      'Sensor correlacionado': { primera: PRIMERA.sensor, segunda: oraculo.sensor_correcto ? 'SÍ' : 'NO', cambio: oraculo.sensor_correcto ? 'NO -> SÍ' : 'SIN CAMBIO' },
      'Dispositivo correlacionado': { primera: PRIMERA.dispositivo, segunda: oraculo.dispositivo_correcto ? 'SÍ' : 'NO', cambio: oraculo.dispositivo_correcto ? 'NO -> SÍ' : 'SIN CAMBIO' },
      'Valor correlacionado': { primera: PRIMERA.valor, segunda: oraculo.valor_correcto ? 'SÍ' : 'NO', cambio: oraculo.valor_correcto ? 'NO -> SÍ' : 'SIN CAMBIO' },
      'Caso': { primera: PRIMERA.caso, segunda: resultado, cambio: resultado === PRIMERA.caso ? 'SIN CAMBIO' : `${PRIMERA.caso} -> ${resultado}` },
      'Grupo': { primera: PRIMERA.grupo, segunda: resultado, cambio: resultado === PRIMERA.grupo ? 'SIN CAMBIO' : `${PRIMERA.grupo} -> ${resultado}` }
    },
    catalogo: { primera: PRIMERA.catalogo, segunda: `${R.catalogo.total} tipos; relacionados con calibracion: ${R.catalogo.calibracion}` },
    causaDelRechazoAnterior: oraculo.existe_evento_calibracion_exitosa ? 'CORREGIDA' : 'NO CORREGIDA'
  };

  const causaRaiz = oraculo.existe_evento_calibracion_exitosa
    ? 'D. TEST API contiene el evento correcto: el defecto anterior (ausencia de la integracion RF-24 -> RF-10 para el camino exitoso) esta corregido y desplegado en TEST.'
    : 'A determinar con la evidencia de esta corrida: API no muestra el evento correlacionado. Sin acceso BD autorizado no puede distinguirse entre generacion no ejecutada y problema de consulta.';

  const evidencia = {
    run_id: runId, evaluacion: 'SEGUNDA EVALUACION',
    grupo: GRUPO, caso: CASO, requisito: RF,
    herramientas: 'Newman (API - Postman) + verificacion BD cuando hay acceso autorizado',
    ambiente: { decisorio: 'TEST', base_url: base() },
    carpeta: `tests/Test_Testing/Test_Modulo9/RF-24/${GRUPO}/EvaluacionV2/`,
    rama: R.gitPre.rama, commit: R.gitPre.commit,
    resultado_caso: resultado, resultado_grupo: resultado,

    git_pre: R.gitPre,

    actores: {
      nota: 'La coleccion Newman es duena de sus sesiones: hace sus propios logins y publica los tokens en ing_session y admin_session. El runner no inicia sesion antes de Newman ni inyecta ningun token; en el cierre se autentica solo para GET.',
      ingeniero: {
        correo: ACTORES.ing.email, credencial: '[REDACTED]',
        login_http: R.ingLogin.http,
        id_usuario: R.identidadIng.cuerpo?.id_usuario ?? null,
        rol: R.identidadIng.cuerpo?.nombre_rol ?? null,
        estado_cuenta: R.identidadIng.cuerpo?.estado_cuenta ?? null,
        id_descubierto_dinamicamente: true,
        permiso_registrar_calibraciones: (R.permisos.cuerpo?.permisos || []).some(p => p.id_recurso === 12 && p.id_accion === 1),
        total_permisos: (R.permisos.cuerpo?.permisos || []).length,
        papel: 'ejecuta el unico POST de calibracion'
      },
      administrador: {
        correo: ACTORES.admin.email, credencial: '[REDACTED]',
        login_http: R.adminLogin.http,
        id_usuario: R.identidadAdmin.cuerpo?.id_usuario ?? null,
        rol: R.identidadAdmin.cuerpo?.nombre_rol ?? null,
        alternativo_necesario: 'NO',
        papel: 'consulta el historial RF-10 y el catalogo de tipos de evento; no ejecuta la calibracion'
      }
    },

    fixture: {
      sensor: (() => { const row = (R.fixture.sensores.cuerpo?.items || []).find(x => sid(x) === FIX.sensor) || null;
        return row ? { id: sid(row), nombre: row.nombre, categoria: row.categoria, es_activo: row.es_activo, id_dispositivo_iot: row.id_dispositivo_iot } : null; })(),
      dispositivo: R.fixture.dispositivo.cuerpo ? { id: R.fixture.dispositivo.cuerpo.id_dispositivo_iot, serial: R.fixture.dispositivo.cuerpo.serial, es_activo: R.fixture.dispositivo.cuerpo.es_activo } : null,
      asociacionVigente: (() => { const a = (R.fixture.asociaciones.cuerpo?.items || []).find(x => vig(x) && sid(x) === FIX.sensor && x.id_dispositivo_iot === FIX.dispositivo) || null;
        return a ? { id_dispositivo_iot: a.id_dispositivo_iot, id_infraestructura: a.id_infraestructura, tiene_estado: a.tiene_estado, fecha_finalizacion: a.fecha_finalizacion } : null; })(),
      categoria: FIX.categoria,
      rango: (() => { const r = (R.fixture.rangos.cuerpo?.items || []).find(x => x.categoria === FIX.categoria) || null;
        return r ? { categoria: FIX.categoria, min: String(r.valor_min), max: String(r.valor_max) } : null; })(),
      valorEnviado: FIX.valor,
      valorEstrictamenteInterior: (() => { const r = (R.fixture.rangos.cuerpo?.items || []).find(x => x.categoria === FIX.categoria) || null;
        return Boolean(r) && Number(FIX.valor) > Number(r.valor_min) && Number(FIX.valor) < Number(r.valor_max); })(),
      observaciones: OBSERVACIONES,
      fixtureOriginalReutilizado: FIX.sensor === 6 && FIX.dispositivo === 3 && FIX.area === 3 && FIX.valor === '22.5000',
      cambiosFrenteAlOriginal: 'ninguno'
    },

    catalogo_rf10: {
      http: R.catalogo.http,
      total: R.catalogo.total,
      tipos_de_calibracion: R.catalogo.calibracion ? JSON.parse(R.catalogo.calibracion) : null,
      tipo_de_calibracion_exitosa: tipoExitosa,
      nota: 'La existencia de un tipo para calibracion exitosa es evidencia favorable, pero NO aprueba el caso: el oraculo es el evento correlacionado en GET /auditoria/.'
    },

    historial_pre: R.historialPre.cuerpo ? { http: R.historialPre.http, total: R.historialPre.cuerpo.total, ids: (R.historialPre.cuerpo.items || []).map(x => x.id_calibracion), items: R.historialPre.cuerpo.items || [] } : null,

    calibracion: {
      endpoint: `/configuracion/sensores/${FIX.sensor}/calibrar`,
      metodo: 'POST', actor: 'Ingeniero de Campo',
      request: { headers: { Authorization: '[REDACTED]', 'Content-Type': 'application/json' }, body: R.calibracion.enviado },
      t_request_before: R.tiempos.t_request_before,
      t_response_after: R.tiempos.t_response_after,
      http: R.calibracion.http,
      response: resp,
      id_calibracion: idCalibracion,
      id_usuario: resp.id_usuario ?? null,
      id_sensor: resp.id_sensor ?? null,
      id_dispositivo_iot: resp.id_dispositivo_iot ?? null,
      valor_referencia: resp.valor_referencia ?? null,
      fecha_calibracion_enviada: R.tiempos.fecha_enviada,
      fecha_calibracion_persistida: R.tiempos.fecha_persistida,
      observaciones: resp.observaciones ?? null,
      modo_calibracion: resp.modo_calibracion ?? null,
      assertions: R.calibracion.assertions,
      reintentos: 0,
      nota: 'Unico POST funcional del RUN. La calibracion PERSISTE a proposito: no se elimina ni se compensa.'
    },

    historial_post: R.historialPost.cuerpo ? {
      http: R.historialPost.http, total: R.historialPost.cuerpo.total,
      ids: (R.historialPost.cuerpo.items || []).map(x => x.id_calibracion),
      items: R.historialPost.cuerpo.items || [],
      filaDeLaCalibracion: (R.historialPost.cuerpo.items || []).find(x => x.id_calibracion === idCalibracion) || null,
      correlacionPor: 'id_calibracion devuelto, no por total+1 (tolera concurrencia)'
    } : null,

    ventana_de_correlacion: {
      base: R.tiempos.fecha_persistida && R.tiempos.fecha_persistida !== 'undefined' ? 'fecha_calibracion persistida' : 't_request_before',
      central: fechaPersistida, margen: '±1 minuto', fecha_desde: desde, fecha_hasta: hasta
    },

    consulta_rf10: {
      actor: 'Administrador', endpoint: `/auditoria/?id_usuario=${ingId}&fecha_desde=...&fecha_hasta=...&tamano=${TAMANO}&pagina=N`,
      http: httpAuditoria, total: total, tamano_pagina: TAMANO,
      paginas_recorridas: paginas, eventos_recuperados: eventos.length,
      pagina1_en_la_coleccion: { http: R.auditoriaPagina1.http, total: R.auditoriaPagina1.cuerpo?.total ?? null },
      nota: 'Se recorrieron todas las paginas necesarias: no se concluye ausencia mirando solo la primera.'
    },

    eventos_recuperados: evaluados,

    evento_correlacionado: eventoCorrelacionado,

    criterios_de_correlacion: {
      metodo: 'campos ESTRUCTURADOS del evento; no se buscan subcadenas',
      por_que: 'un "6" o un "3" pueden aparecer dentro de una IP o de un timestamp y producir un falso positivo, como se documento en la primera evaluacion',
      obligatorios: ['usuario (id_usuario del evento o del detalle)', 'fecha_evento dentro de la ventana', 'detalle.id_sensor', 'detalle.id_dispositivo_iot', 'detalle.valor_referencia', 'operacion de calibracion (detalle.operacion o tipo_evento del catalogo)', 'resultado exitoso'],
      refuerzos_no_exigidos: ['detalle.id_calibracion', 'detalle.id_infraestructura', 'detalle.modo_calibracion', 'detalle.observaciones', 'integridad_ok'],
      candidatos_que_cumplen_todo: correlacionados.length
    },

    verificacion_final: {
      soloLectura: true, sql: 'ninguno', escrituras: 0, fecha: new Date().toISOString(),
      calibracion_sigue_existiendo: Boolean(filaFinal),
      fila_recuperada_por_id: filaFinal,
      datos_coinciden: Boolean(filaFinal) && Number(filaFinal.id_sensor) === FIX.sensor &&
        Number(filaFinal.id_dispositivo_iot) === FIX.dispositivo && igualDecimal(filaFinal.valor_referencia, FIX.valor) &&
        Number(filaFinal.id_usuario) === ingId && filaFinal.observaciones === OBSERVACIONES,
      historial_final: { http: histFinal.status, total: histFinal.cuerpo?.total ?? null, ids: (histFinal.cuerpo?.items || []).map(x => x.id_calibracion) },
      dispositivo_sigue_activo: dispFinal.cuerpo?.es_activo === true,
      asociacion_vigente: (asocFinal.cuerpo?.items || []).filter(x => vig(x) && sid(x) === FIX.sensor).map(x => ({ id_dispositivo_iot: x.id_dispositivo_iot, id_infraestructura: x.id_infraestructura })),
      rango_sin_cambios: Boolean(rangoFinal) && Number(FIX.valor) > Number(rangoFinal.valor_min) && Number(FIX.valor) < Number(rangoFinal.valor_max),
      rango_final: rangoFinal ? { categoria: FIX.categoria, min: String(rangoFinal.valor_min), max: String(rangoFinal.valor_max) } : null,
      evento_reconsultado: eventoReconsultado,
      post_extra_ejecutados: 0,
      calibracion_eliminada: false,
      nota: 'No hay cleanup: la calibracion creada y su evento son evidencia del RUN y se conservan.'
    },

    verificacion_bd: {
      acceso_disponible: false,
      estado: 'NO DISPONIBLE',
      motivo: 'No hay cliente de base de datos ni host de TEST declarado en este entorno (sin psql, sin driver pg y sin POSTGRES_HOST en la configuracion): no existe acceso SQL autorizado de solo lectura.',
      calibracion_funcional: 'NO DISPONIBLE',
      auditoria_interna_m09: 'NO DISPONIBLE',
      rf10: 'NO DISPONIBLE',
      solo_select: true,
      nota: 'El oraculo principal del caso es GET /auditoria/ y pudo ejecutarse completo, de modo que la ausencia de acceso SQL no bloquea el caso. No se invento ningun dato de base.'
    },

    newman: {
      html: `newman/newman-${GRUPO}.html`, htmlPersistentes: 1,
      coleccionEjecutada: `${R.itemsEjecutables} de ${R.itemsTotales} items`,
      iterations: R.stats.iterations, requests: R.stats.requests, assertions: R.stats.assertions,
      failures: R.failures,
      presupuesto: { postCalibrarPlanificados: POST_BUDGET, postCalibrarEjecutados: R.postCalibrar, reintentos: 0 },
      stopAll: 'NO', limpio: newmanLimpio
    },

    oraculo: oraculo,

    comparacion_primera_segunda: comparacion,

    causa_raiz: causaRaiz,

    contraste_dev: {
      necesario: !oraculo.existe_evento_calibracion_exitosa,
      motivo: oraculo.existe_evento_calibracion_exitosa
        ? 'TEST produce el evento correlacionado: no hay motivo de contraste por desfase de despliegue.'
        : 'TEST no produce el evento esperado: procede contrastar DEV si es tecnicamente posible.',
      peticiones_a_dev: 0
    },

    seguridad: null,
    git_post: estadoGit('git_post')
  };
  escribir('evidencia.json', evidencia);
  evidencia.seguridad = escanearSeguridad();
  escribir('evidencia.json', evidencia);
  refrescarManifest();
  fs.unlinkSync(tmp);

  log('\n================ CIERRE — ORÁCULO RF-10 ================');
  log(`RUN_ID: ${runId}`);
  log(`calibración: HTTP ${R.calibracion.http} | id_calibracion ${idCalibracion} | id_usuario ${resp.id_usuario} | persistida ${filaFinal ? 'SI' : 'NO'}`);
  log(`ventana: ${desde} → ${hasta}`);
  log(`GET /auditoria/: HTTP ${httpAuditoria} | total ${total} | páginas recorridas ${paginas.length} | eventos ${eventos.length}`);
  log(`tipo de calibración exitosa en el catálogo: ${tipoExitosa ?? '(ninguno)'}`);
  log(`eventos que cumplen TODOS los criterios estructurados: ${correlacionados.length}`);
  if (eventoCorrelacionado) {
    log(`  evento correlacionado: id_evento ${eventoCorrelacionado.id_evento} | tipo ${eventoCorrelacionado.tipo_evento} | ${eventoCorrelacionado.modulo} | ${eventoCorrelacionado.resultado} | ${eventoCorrelacionado.fecha_evento}`);
    log(`  criterios: ${JSON.stringify(eventoCorrelacionado.correlacion.criterios)}`);
    log(`  refuerzos: ${JSON.stringify(eventoCorrelacionado.correlacion.refuerzos)}`);
  }
  log(`VERIFICACIÓN BD: NO DISPONIBLE`);
  log(`Newman: requests ${R.stats.requests.ejecutados} (fallidos ${R.stats.requests.fallidos}) | assertions ${R.stats.assertions.total} (fallidas ${R.stats.assertions.fallidas}) | limpio ${newmanLimpio ? 'SI' : 'NO'}`);
  log(`CASO ${CASO} -> ${resultado}`);
  log(`GRUPO ${GRUPO} -> ${resultado}`);
  log(`Causa del rechazo anterior: ${comparacion.causaDelRechazoAnterior}`);
  log(`Evidencia limpia de secretos: ${evidencia.seguridad.limpio ? 'SI' : 'NO'}`);
  log('========================================================\n');

  if (!evidencia.seguridad.limpio) process.exitCode = 3;
  else if (resultado !== 'APROBADO') process.exitCode = 2;
}

// --------------------------------------------------------------------------- manifiesto
function refrescarManifest() {
  const artefactos = [
    { archivo: 'run-g80-v2.cjs', abs: path.join(__dirname, 'run-g80-v2.cjs'),
      ruta: `${GRUPO}/EvaluacionV2/automation/run-g80-v2.cjs`,
      funcion: 'Runner unico de la reevaluacion, con los modos precheck (Newman de validacion previa, sin HTML ni archivos), run (RUN funcional oficial con el unico POST de calibracion y el unico HTML) y close (oraculo RF-10 con paginacion completa y correlacion estructurada, verificacion final de solo lectura y consolidacion de evidencia). No inyecta tokens a Newman y no ejecuta ninguna escritura fuera del POST autorizado.' },
    { archivo: 'TC-M09-G80-v2.0.postman_collection.json', abs: COLECCION,
      ruta: `${GRUPO}/EvaluacionV2/TC-M09-G80-v2.0.postman_collection.json`,
      funcion: 'Copia de la coleccion funcional para EvaluacionV2. Cambios de infraestructura: los 2 GET de fixture leen con ing_session porque el Administrador perdio alcance, y se anade un GET del catalogo RF-10 que solo registra. El oraculo funcional (1 POST /calibrar, fixture, valores y criterio de auditoria) es el de la primera evaluacion.' },
    { archivo: 'TC-M09-G80-v2.0.postman_collection.json (original)', abs: COLECCION_ORIGINAL,
      ruta: `${GRUPO}/TC-M09-G80-v2.0.postman_collection.json`,
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
    grupo: GRUPO, caso: CASO, runId,
    nota: 'Artefactos finales de la SEGUNDA EVALUACION. Los ejecutables viven unicamente en EvaluacionV2/; no se copia automation dentro de RESULTADOS.',
    newmanHtmlPersistentes: 1, automationDentroDeResultados: 'NO', artefactos: filas
  }, null, 2)));
}
