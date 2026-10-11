// Runner único de la SEGUNDA EVALUACIÓN de TC-M09-G138 (RF-24 v2.0, Módulo 9, CU05 Flujo F).
// Casos TC-M09-278, TC-M09-279, TC-M09-280 y TC-M09-281: las cuatro precondiciones NEGATIVAS
// del área para la calibración VISION. Los cuatro deben responder HTTP 422 con el mensaje
// literal del contrato —construido con el ID REAL de cada área— y no publicar línea base.
//
// Un solo archivo, tres modos (G138_MODO):
//
//   precheck  Validación Newman de SOLO LECTURA previa al RUN: solo los items de lectura. No
//             crea especies, áreas ni cámaras, no envía ningún POST de calibración, no genera
//             HTML, no crea RESULTADOS y no deja archivos: solo consola. Incluye el
//             descubrimiento dinámico de la finca compartida, la especie AVES y el tipo de área.
//   run       RUN funcional oficial: la colección completa una única vez, con el setup del
//             fixture, los 4 POST funcionales, la restauración y el ÚNICO HTML persistente.
//   close     Oráculo por caso, verificación final de solo lectura, red de seguridad de la
//             restauración y consolidación de evidencia.json y automation_manifest.json.
//
// PROPIEDAD DE SESIONES (regla corregida desde G76): la colección es dueña de las sesiones. Hace
// sus propios logins del Ingeniero y del Administrador y publica los tokens en
// {{engineer_session}} y {{admin_session}}. El runner NO obtiene tokens y NO los inyecta en
// Newman: solo pasa configuración. Motivo: TEST aplica sesión única por usuario.
//
// FIXTURE: cuatro áreas DISTINTAS, cada una con UNA sola precondición inválida aislada.
//   A2 (TC-278)  AVES + MODELO_AVES  + CERO cámaras asociadas
//   A3 (TC-279)  AVES + MODELO_AVES  + exactamente UNA cámara asociada, INACTIVA
//   A4 (TC-280)  especie de paradigma INDIVIDUAL (MODELO_ESPECIES_GRANDES) + cámara ACTIVA
//   A5 (TC-281)  especie AVES presente + tipo_modelo_asignado NULL + cámara ACTIVA
// Todo se crea y se revierte con endpoints oficiales; no se usa SQL para preparar nada.
//
// G138 NO carga observaciones: los rechazos ocurren antes del cálculo de línea base, así que
// POST /iot/telemetria/vision se ejecuta 0 veces.
//
// Presupuesto: 4 POST /calibraciones-vision, sin reintentos. Las escrituras de setup y de
// restauración se cuentan por separado.
//
// Uso:
//   $env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
//   $env:QA_ING_EMAIL="ingeniero@pecuaria.co";      $env:QA_ING_PASSWORD="<secreto>"
//   $env:QA_ADM_EMAIL="administador.dev@gmail.com"; $env:QA_ADM_PASSWORD="<secreto>"
//   $env:G138_RUN_ID="run-YYYYMMDD-HHMMSS"     (modos run y close)
//   $env:G138_MODO="precheck" | "run" | "close"
//   node .\run-g138-v2.cjs

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const CASE_DIR = path.resolve(__dirname, '..', '..');
const EVAL_DIR = path.resolve(__dirname, '..');
const COLECCION = path.join(EVAL_DIR, 'TC-M09-G138.postman_collection.json');
const COLECCION_ORIGINAL = path.join(CASE_DIR, 'TC-M09-G138.postman_collection.json');

const GRUPO = 'TC-M09-G138';
const RF = 'RF-24 v2.0';
const CU = 'CU05 — Gestionar Dispositivos IoT, Flujo F (precondiciones VISION)';
const CASOS = ['TC-M09-278', 'TC-M09-279', 'TC-M09-280', 'TC-M09-281'];
const POST_VISION_BUDGET = 4;
const BASELINE_RUN = 'run-20261007-101353';

// Mensaje contractual exigido por la matriz. __AREA__ se sustituye por el ID REAL de cada área.
const MSG_BASE = 'Calibración por visión no disponible: El área __AREA__ no cuenta con ' +
  'observaciones de cámara aptas o no tiene un modelo poblacional asignado. Verifique las ' +
  'cámaras (RF-21/22) y la configuración del área (RF-20).';

const POBLACIONALES = ['MODELO_AVES', 'MODELO_PORCINOS', 'MODELO_ACUICULTURA'];
const INDIVIDUALES = ['MODELO_ESPECIES_MEDIANAS', 'MODELO_ESPECIES_GRANDES'];

// Los cuatro casos, con su área y la única precondición que cada uno aísla.
const VARIANTES = [
  { caso: 'TC-M09-278', clave: 'a2', area: 'A2', invalidez: 'El área no tiene ninguna cámara asociada',
    perfil: 'AVES + MODELO_AVES (POBLACIONAL), 0 cámaras asociadas' },
  { caso: 'TC-M09-279', clave: 'a3', area: 'A3', invalidez: 'La única cámara asociada está inactiva',
    perfil: 'AVES + MODELO_AVES (POBLACIONAL), exactamente 1 cámara asociada e inactiva' },
  { caso: 'TC-M09-280', clave: 'a4', area: 'A4', invalidez: 'El modelo asignado es de paradigma INDIVIDUAL',
    perfil: 'especie MODELO_ESPECIES_GRANDES (INDIVIDUAL) + cámara activa' },
  { caso: 'TC-M09-281', clave: 'a5', area: 'A5', invalidez: 'El área no tiene tipo_modelo_asignado (null)',
    perfil: 'especie AVES presente + tipo_modelo_asignado null + cámara activa' }
];

// Items de SOLO LECTURA: los únicos que ejecuta el PRECHECK.
const ITEMS_PRECHECK = [
  'Login Ingeniero', 'Login Administrador', 'Contrato OpenAPI VISION',
  'Identidad Ingeniero', 'Identidad Administrador', 'Permisos Ingeniero', 'Permisos Administrador',
  'Fixture — especie AVES del catálogo', 'Fixture — tipo de área del catálogo',
  'Fixture — finca compartida', 'Fixture — finca compartida vista por el Ingeniero',
  'Fixture — inventario previo de áreas y cámaras'
];

const MODO = process.env.G138_MODO || 'precheck';
if (!['precheck', 'run', 'close'].includes(MODO)) throw new Error(`G138_MODO no reconocido: ${MODO}`);

const base = () => {
  const b = process.env.QA_BASE_URL;
  if (!b) throw new Error('QA_BASE_URL requerido');
  return b.replace(/\/$/, '');
};
const ING = { email: process.env.QA_ING_EMAIL, secret: process.env.QA_ING_PASSWORD };
const ADM = { email: process.env.QA_ADM_EMAIL, secret: process.env.QA_ADM_PASSWORD };
for (const [n, a] of [['ING', ING], ['ADM', ADM]]) {
  if (!a.email || !a.secret) throw new Error(`QA_${n}_EMAIL y QA_${n}_PASSWORD requeridos (solo en memoria de proceso).`);
}

const log = (...a) => console.log(...a);
const sha256 = (f) => crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');

const runId = process.env.G138_RUN_ID;
if (MODO !== 'precheck' && (!runId || !/^run-\d{8}-\d{6}$/.test(runId))) {
  throw new Error('G138_RUN_ID requerido con formato run-YYYYMMDD-HHMMSS.');
}
const SUFIJO = runId ? runId.replace('run-', '') : null;
// Seriales de las tres cámaras del fixture. Por contrato el serial es el access_key de la
// ingesta M03, así que se tratan como secreto aunque G138 no ejecute telemetría.
const SERIALES = SUFIJO
  ? { a3: `QA-M09-G138-A3-${SUFIJO}`, a4: `QA-M09-G138-A4-${SUFIJO}`, a5: `QA-M09-G138-A5-${SUFIJO}` }
  : {};

// --------------------------------------------------------------------- sanitización
// Las credenciales llegan por variable de entorno y NUNCA como literal en este archivo.
const secretos = () => [ING.secret, ADM.secret, process.env.QA_DB_PASSWORD, ...Object.values(SERIALES)].filter(Boolean);
function limpiar(texto) {
  let s = String(texto);
  for (const x of secretos()) s = s.split(x).join('[REDACTED]');
  return s
    .replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[JWT REDACTED]')
    .replace(/Bearer\s+[A-Za-z0-9_.-]{12,}/g, 'Bearer [REDACTED]')
    // Los seriales de camara de los fixtures de QA son access_key por contrato. Se redactan por
    // PATRON, no solo los de este RUN: el inventario de dispositivos devuelve tambien los de
    // corridas hermanas, y esos no deben quedar persistidos.
    .replace(/QA-M09-G1\d{2}-(?:CAM|A\d)-\d{8}-\d{6}/g, '[SERIAL REDACTED]');
}
function limpiarHtml(html) {
  return limpiar(html)
    .replace(/Authorization/gi, '[REDACTED_HEADER]')
    .replace(/Bearer/gi, '[REDACTED_HEADER]')
    .replace(/access_key/gi, '[REDACTED]')
    .replace(/access_token/gi, '[REDACTED]')
    .replace(/refresh_token/gi, '[REDACTED]')
    .replace(/contrasena/gi, '[REDACTED]')
    .replace(/password/gi, '[REDACTED]')
    .replace(/set-cookie/gi, '[REDACTED]')
    .replace(/\bjwt\b/gi, '[REDACTED]');
}

// ---------------------------------------------------------------------- rutas del RUN
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
    [/access_key"\s*:\s*"[A-Za-z0-9_.-]{6,}"/i, 'access_key con valor literal'],
    [/(password|contrasena|contraseña)"?\s*[:=]\s*"?[^"\s,}\]]{4,}/i, 'credencial en clave/valor'],
    [/postgres(ql)?:\/\//i, 'cadena de conexión'],
    [/QA-M09-G138-A\d-\d{8}-\d{6}/, 'serial completo de una cámara del fixture']
  ];
  const SOLO_VALORES = TODOS.filter(([, n]) =>
    n === 'JWT' || n === 'Authorization con token' || n === 'cadena de conexión' ||
    n === 'serial completo de una cámara del fixture');
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
    credencialesCubiertas: ('contrasenas de API del Ingeniero y del Administrador, los seriales de las ' +
      'tres camaras del fixture (que por contrato funcionan como access_key) y, si se entrega por ' +
      'variable de entorno, la de BD. Ninguna aparece como literal en el codigo.'),
    criterio: ('Se marcan solo VALORES de secreto. En los .cjs solo se evaluan valores, el patron del ' +
      'serial completo y la coincidencia literal con las credenciales.'),
    nota: ('Las contrasenas y los seriales solo existieron en memoria de proceso. El reporter htmlextra ' +
      'se ejecuto con omitHeaders, sin environment ni globals y omitiendo las variables sensibles; el ' +
      'HTML se sanitizo despues de generarse. En la evidencia los seriales aparecen redactados.')
  };
}

// ---------------------------------------------------------------- HTTP directo (lectura)
async function login(email, secret) {
  const r = await fetch(base() + '/sesiones/', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correo_electronico: email, contrasena: secret }), signal: AbortSignal.timeout(30000)
  });
  const b = await r.json().catch(() => null);
  if (r.status !== 200 || !b?.token) throw new Error(`login ${email} HTTP ${r.status}${b?.error_code ? ' ' + b.error_code : ''}`);
  return b.token;
}
async function get(endpoint, token) {
  const r = await fetch(base() + endpoint, {
    headers: token ? { Authorization: `Bearer ${token}` } : {}, signal: AbortSignal.timeout(45000)
  });
  return { status: r.status, cuerpo: await r.json().catch(() => null) };
}
async function escribirApi(metodo, endpoint, token, cuerpo) {
  const r = await fetch(base() + endpoint, {
    method: metodo,
    headers: { Authorization: `Bearer ${token}`, ...(cuerpo ? { 'Content-Type': 'application/json' } : {}) },
    body: cuerpo ? JSON.stringify(cuerpo) : undefined, signal: AbortSignal.timeout(45000)
  });
  return { status: r.status, cuerpo: await r.json().catch(() => null) };
}

// ------------------------------------------------- descubrimiento dinámico del fixture
// Nada se hardcodea: la finca se elige entre las que VEN LOS DOS actores autorizados, la especie
// AVES y el tipo de área salen del catálogo real, y se registra por qué no sirve ningún área
// preexistente de TEST para cada uno de los cuatro perfiles.
async function descubrir() {
  const tIng = await login(ING.email, ING.secret);
  const tAdm = await login(ADM.email, ADM.secret);

  const fincasIng = (await get('/configuracion/fincas', tIng)).cuerpo?.items || [];
  const fincasAdm = (await get('/configuracion/fincas', tAdm)).cuerpo?.items || [];
  const idsIng = fincasIng.map(f => f.id_finca);
  const idsAdm = fincasAdm.map(f => f.id_finca);
  const compartidas = fincasIng.filter(f => idsAdm.includes(f.id_finca) && f.es_activo === true);

  const especies = (await get('/configuracion/especies?solo_activas=true', tIng)).cuerpo?.items || [];
  const aves = especies.filter(x => String(x.tipo_modelo) === 'MODELO_AVES' && x.es_activo === true)
    .sort((a, b) => a.id_especie - b.id_especie);
  const individuales = especies.filter(x => INDIVIDUALES.includes(String(x.tipo_modelo)) && x.es_activo === true);

  const tipos = (await get('/configuracion/tipos-area', tAdm)).cuerpo;
  const listaTipos = (Array.isArray(tipos) ? tipos : (tipos?.items || [])).filter(x => x && x.es_activo === true);
  const tipoPreferido = process.env.G138_TIPO_AREA || 'Galpón';
  const tipo = listaTipos.find(x => String(x.nombre) === tipoPreferido) || listaTipos[0] || null;

  const dispositivos = (await get('/configuracion/dispositivos-iot', tIng)).cuerpo?.items || [];
  const camaras = dispositivos.filter(x => String(x.categoria) === 'CAMARA');
  const porId = Object.fromEntries(especies.map(x => [x.id_especie, x]));
  const areas = [];
  for (const f of fincasIng) {
    const r = await get(`/configuracion/infraestructuras?finca_id=${f.id_finca}`, tIng);
    (r.cuerpo?.items || []).forEach(x => areas.push({ ...x, id_finca: f.id_finca }));
  }
  const camsDe = (a) => camaras.filter(c => Number(c.id_infraestructura) === Number(a.id_infraestructura));
  const esAves = (a) => porId[a.especie_id] && String(porId[a.especie_id].tipo_modelo) === 'MODELO_AVES';
  const act = areas.filter(a => a.es_activo === true);

  // Línea base de cada área preexistente que encajaría: el §19 prefiere áreas sin línea base.
  const conLinea = [];
  for (const a of act) {
    if (!esAves(a) || !POBLACIONALES.includes(String(a.tipo_modelo_asignado))) continue;
    const r = await get(`/configuracion/calibraciones-vision/linea-base?area_id=${a.id_infraestructura}`, tIng);
    conLinea.push({ area_id: a.id_infraestructura, linea_base: r.status === 200 ? r.cuerpo.id_calibracion_vision : null, http: r.status });
  }

  const preexistentes = {
    A2_aves_poblacional_sin_camara: act.filter(a => esAves(a) && POBLACIONALES.includes(String(a.tipo_modelo_asignado)) && camsDe(a).length === 0).map(a => a.id_infraestructura),
    A3_aves_poblacional_una_camara_inactiva: act.filter(a => esAves(a) && POBLACIONALES.includes(String(a.tipo_modelo_asignado)) && camsDe(a).length === 1 && camsDe(a)[0].es_activo === false).map(a => a.id_infraestructura),
    A4_individual_con_camara_activa: act.filter(a => INDIVIDUALES.includes(String(a.tipo_modelo_asignado)) && camsDe(a).some(c => c.es_activo === true)).map(a => a.id_infraestructura),
    A5_aves_modelo_null_con_camara_activa: act.filter(a => esAves(a) && (a.tipo_modelo_asignado === null || a.tipo_modelo_asignado === undefined) && camsDe(a).some(c => c.es_activo === true)).map(a => a.id_infraestructura)
  };

  return {
    estrategia: ('cuatro areas NUEVAS y distintas, una por caso, creadas en el RUN con endpoints ' +
      'oficiales dentro de una finca que ya ven los dos actores autorizados. Cada una aisla UNA ' +
      'sola precondicion invalida y todas se revierten por desactivacion oficial.'),
    fincas_del_ingeniero: idsIng, fincas_del_administrador: idsAdm,
    fincas_compartidas: compartidas.map(f => ({ id_finca: f.id_finca, nombre: f.nombre })),
    especie_aves: aves[0] ? { id_especie: aves[0].id_especie, nombre: aves[0].nombre, tipo_modelo: aves[0].tipo_modelo } : null,
    especies_aves_activas: aves.map(x => x.id_especie),
    especies_individual_activas: individuales.map(x => ({ id_especie: x.id_especie, tipo_modelo: x.tipo_modelo })),
    tipo_area_elegido: tipo ? { id_tipo_area: tipo.id_tipo_area, nombre: tipo.nombre } : null,
    tipos_area_activos: listaTipos.map(x => x.nombre),
    camaras_en_test: camaras.map(c => ({ id: c.id_dispositivo_iot, area: c.id_infraestructura, activa: c.es_activo })),
    areas_visibles: areas.length,
    candidatos_preexistentes: preexistentes,
    lineas_base_de_candidatos: conLinea,
    motivo_de_no_reutilizar: ('A2, A4 y A5 no tienen ningun candidato preexistente: ninguna area ' +
      'activa junta especie AVES con cero camaras, ninguna tiene modelo de paradigma INDIVIDUAL con ' +
      'camara activa (el catalogo no tenia ni una especie INDIVIDUAL activa) y ninguna junta especie ' +
      'AVES con tipo_modelo_asignado nulo y camara activa. Para A3 si habia candidatos, pero todos ' +
      'tienen ya una linea base vigente, y el paquete prefiere areas sin linea base previa para poder ' +
      'demostrar literalmente que no se registra ninguna.'),
    elegida: aves[0] && tipo && compartidas[0]
      ? { finca_id: compartidas[0].id_finca, finca_nombre: compartidas[0].nombre,
          especie_aves: aves[0].id_especie, especie_aves_nombre: aves[0].nombre, tipo_area: tipo.nombre }
      : null,
    criterio: ('finca activa visible a los DOS actores, especie AVES activa del catalogo y tipo de ' +
      'area activo. La especie de paradigma INDIVIDUAL se registra en el setup porque el catalogo de ' +
      'TEST no tiene ninguna activa y el area solo admite un modelo que coincida con el de su especie.')
  };
}

// ------------------------------------------------------------------- env de la colección
function construirEnv(fixture) {
  // Ventana válida: fin > inicio, ambos en el pasado. Ninguna invalidez adicional.
  const ahora = Date.now();
  const inicio = new Date(ahora - 3600000).toISOString();   // 1 h antes
  const fin = new Date(ahora - 120000).toISOString();       // 2 min antes
  if (new Date(fin) <= new Date(inicio)) throw new Error('ABORTADO: la ventana debe cumplir fin > inicio.');
  if (new Date(fin).getTime() > ahora) throw new Error('ABORTADO: la ventana no puede terminar en el futuro.');

  // El nombre de la especie solo admite letras y espacios, como el de la finca: el sufijo único
  // del RUN se transcribe dígito a letra.
  const letras = String(SUFIJO || '').replace(/\D/g, '').split('').map(d => 'abcdefghij'[Number(d)]).join('');
  const bodyEspecie = JSON.stringify({
    nombre: `Especie QA Grandes ${letras}`,
    descripcion: `Especie de paradigma INDIVIDUAL para el fixture de ${GRUPO} (${runId})`,
    densidad_maxima_por_especie: 2,
    tipo_modelo: 'MODELO_ESPECIES_GRANDES'
  });
  const bodyAreaBase = JSON.stringify({
    nombre_infraestructura: null,      // lo fija la colección por caso
    tipo_area: fixture.tipo_area,
    superficie: 150,
    finca_id: null,                    // lo fija la colección
    descripcion_infraestructura: null, // lo fija la colección
    especie_id: null,                  // lo fija la colección
    tipo_modelo_asignado: null         // lo fija la colección
  });
  const bodyCamaraBase = JSON.stringify({
    serial: null,                      // lo fija la colección
    descripcion: null,                 // lo fija la colección
    id_infraestructura: null,          // lo fija la colección
    id_tipo_dispositivo: Number(process.env.G138_TIPO_CAMARA || 5),   // CAMARA_VISION
    es_activo: true,                   // lo fija la colección por caso
    resolucion: '1920x1080',
    fps: Number(process.env.G138_FPS || 30),
    area_cobertura_m2: 40
  });

  return {
    env: [
      ['base_url', base()],
      ['ing_email', ING.email], ['ing_secret', ING.secret],
      ['adm_email', ADM.email], ['adm_secret', ADM.secret],
      ['finca_id', String(fixture.finca_id)],
      ['especie_aves', String(fixture.especie_aves)],
      ['area_tipo', String(fixture.tipo_area)],
      ['run_sufijo', String(SUFIJO)],
      ['msg_base', MSG_BASE],
      ['window_inicio', inicio], ['window_fin', fin],
      ['auditoria_desde', new Date(ahora - 600000).toISOString()],
      ['serial_a3', SERIALES.a3], ['serial_a4', SERIALES.a4], ['serial_a5', SERIALES.a5],
      ['body_especie', bodyEspecie], ['body_area_base', bodyAreaBase], ['body_camara_base', bodyCamaraBase],
      ['stop_all', 'NO']
    ],
    ventana: { inicio, fin, criterio: 'fin > inicio, ambos en el pasado; sin invalidez adicional' },
    nombres: { especie: JSON.parse(bodyEspecie).nombre }
  };
}

function cargarColeccion(soloEstos) {
  const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
  const antes = col.item.map(i => i.name);
  if (soloEstos) {
    for (const n of soloEstos) if (!antes.includes(n)) throw new Error(`El item «${n}» no existe en la colección.`);
    col.item = col.item.filter(i => soloEstos.includes(i.name));
  }
  return { col, itemsTotales: antes.length, itemsEjecutables: col.item.length };
}

function verificarEscrituras(col, permitirEscrituras) {
  for (const it of col.item) {
    const url = typeof it.request.url === 'string' ? it.request.url : it.request.url?.raw || '';
    const metodo = (it.request.method || 'GET').toUpperCase();
    if (/\/telemetria\/vision$/.test(url)) {
      throw new Error(`ABORTADO: G138 no debe cargar observaciones M03 (${it.name}).`);
    }
    if (!permitirEscrituras) {
      if (metodo !== 'GET' && !/\/sesiones\/?$/.test(url)) {
        throw new Error(`ABORTADO: el PRECHECK solo admite GET y el login de las sesiones: ${metodo} ${url} (${it.name}).`);
      }
      continue;
    }
    if (metodo === 'DELETE' || metodo === 'PUT') throw new Error(`ABORTADO: escritura no autorizada ${metodo} ${url} (${it.name}).`);
    const permitido =
      (metodo === 'POST' && (/\/sesiones\/?$/.test(url) || /\/calibraciones-vision$/.test(url) ||
        /\/configuracion\/especies$/.test(url) || /\/configuracion\/infraestructuras$/.test(url) ||
        /\/configuracion\/dispositivos-iot$/.test(url))) ||
      (metodo === 'PATCH' && /\/desactivar$/.test(url)) ||
      metodo === 'GET';
    if (!permitido) throw new Error(`ABORTADO: escritura fuera del setup autorizado: ${metodo} ${url} (${it.name}).`);
  }
}

function correrNewman(col, env, html, titulo) {
  const o = { collection: col, reporters: html ? ['cli', 'htmlextra'] : ['cli'], envVar: env.map(([key, value]) => ({ key, value })) };
  if (html) {
    o.reporter = { htmlextra: {
      export: html, omitHeaders: true, showEnvironmentData: false, showGlobalData: false,
      skipEnvironmentVars: ['ing_secret', 'adm_secret', 'engineer_session', 'admin_session',
        'serial_a3', 'serial_a4', 'serial_a5', 'body_camara_base',
        'body_camara_a3', 'body_camara_a4', 'body_camara_a5'],
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
  const enviadoTexto = (n) => { const e = find(n); try { return e.request.body.raw.toString(); } catch { return null; } };
  const asserts = (n) => { const e = find(n); return (e?.assertions || []).map(a => ({ assertion: a.assertion, paso: !a.error, error: a.error ? a.error.message : null })); };
  const ejecutado = (n) => Boolean(find(n));
  return { cuerpo, http, enviadoTexto, asserts, ejecutado };
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
const contar = (s, re, metodo) => (s?.run?.executions || []).filter(e =>
  re.test(e.request?.url?.toString() || '') && (!metodo || String(e.request?.method) === metodo)).length;
const envDe = (s, k) => s?.environment?.values?.find?.(x => x.key === k)?.value ?? null;
const J = (v, d = null) => { try { return v === null || v === undefined ? d : JSON.parse(v); } catch { return d; } };

// ==========================================================================================
(async () => {
  if (MODO === 'precheck') return modoPrecheck();
  if (MODO === 'run') return modoRun();
  return modoClose();
})().catch((e) => { console.error('\nNO COMPLETADO:', e.message); process.exitCode = 1; });

// ------------------------------------------------------------------------------- precheck
async function modoPrecheck() {
  log('PRECHECK de solo lectura — Newman sin reporter HTML, sin carpeta de resultados.');
  log('No se crea ninguna especie, área ni cámara y no se envía ningún POST de calibración.\n');

  const descubrimiento = await descubrir();
  log('--- descubrimiento dinámico (el fixture se CREA en el RUN) ---');
  log(`estrategia: ${descubrimiento.estrategia}`);
  log(`fincas del Ingeniero: ${JSON.stringify(descubrimiento.fincas_del_ingeniero)}`);
  log(`fincas del Administrador: ${JSON.stringify(descubrimiento.fincas_del_administrador)}`);
  log(`fincas compartidas y activas: ${JSON.stringify(descubrimiento.fincas_compartidas)}`);
  log(`especie AVES elegida: ${JSON.stringify(descubrimiento.especie_aves)} (de ${descubrimiento.especies_aves_activas.length} activas)`);
  log(`especies de paradigma INDIVIDUAL activas: ${JSON.stringify(descubrimiento.especies_individual_activas)}`);
  log(`tipo de área elegido: ${JSON.stringify(descubrimiento.tipo_area_elegido)}`);
  log(`cámaras preexistentes en TEST: ${JSON.stringify(descubrimiento.camaras_en_test)}`);
  log(`candidatos preexistentes por caso: ${JSON.stringify(descubrimiento.candidatos_preexistentes)}`);
  log(`línea base de los candidatos de A3: ${JSON.stringify(descubrimiento.lineas_base_de_candidatos)}`);
  log(`por qué no se reutilizan: ${descubrimiento.motivo_de_no_reutilizar}`);
  if (!descubrimiento.elegida) {
    log('\nBLOQUEADO POR PRECONDICIÓN DE DATOS: falta finca compartida, especie AVES activa o tipo de área.');
    process.exitCode = 2;
    return;
  }
  const fixture = descubrimiento.elegida;

  const { col, itemsTotales, itemsEjecutables } = cargarColeccion(ITEMS_PRECHECK);
  verificarEscrituras(col, false);
  const { env, ventana } = construirEnv(fixture);
  log(`\nColección: ${itemsEjecutables} de ${itemsTotales} items (solo lectura).\n`);

  const summary = await correrNewman(col, env, null, null);
  const st = stats(summary);
  const f = fallos(summary);
  const { cuerpo, asserts } = extraer(summary);
  const pasa = (item) => { const a = asserts(item); return a.length > 0 && a.every(x => x.paso); };

  const chequeos = {
    visionEndpoint: envDe(summary, 'oa_post_vision') === 'PRESENTE',
    historialEndpoint: envDe(summary, 'oa_get_vision') === 'PRESENTE',
    lineaBaseEndpoint: envDe(summary, 'oa_get_linea_base') === 'PRESENTE',
    contrato: pasa('Contrato OpenAPI VISION'),
    ingeniero: pasa('Identidad Ingeniero') && pasa('Permisos Ingeniero'),
    administrador: pasa('Identidad Administrador'),
    especie: pasa('Fixture — especie AVES del catálogo'),
    tipoArea: pasa('Fixture — tipo de área del catálogo'),
    finca: pasa('Fixture — finca compartida') && pasa('Fixture — finca compartida vista por el Ingeniero')
  };
  const postFuncionales = contar(summary, /\/calibraciones-vision$/, 'POST');
  const postTelemetria = contar(summary, /\/telemetria\/vision$/, 'POST');
  const autorizar = Object.values(chequeos).every(Boolean) && f.length === 0 &&
    (st.requests.fallidos || 0) === 0 && postFuncionales === 0 && postTelemetria === 0;

  const P = (b) => (b ? 'PASS' : 'FAIL');
  log('\nPRECHECK_G138\n');
  log(`POST calibraciones-vision:\n${envDe(summary, 'oa_post_vision')}\n`);
  log(`GET historial:\n${envDe(summary, 'oa_get_vision')}\n`);
  log(`GET línea-base:\n${envDe(summary, 'oa_get_linea_base')}\n`);
  log(`Contrato (body y dominio VISION):\n${P(chequeos.contrato)}\n`);
  log(`Ingeniero:\n${P(chequeos.ingeniero)}\n`);
  log(`Administrador:\n${P(chequeos.administrador)}\n`);
  log(`Especie AVES del catálogo:\n${P(chequeos.especie)}\n`);
  log(`Tipo de área:\n${P(chequeos.tipoArea)}\n`);
  log(`Finca compartida:\n${P(chequeos.finca)} (${envDe(summary, 'compuerta_fixture')})\n`);
  log(`Failures automatización:\n${f.length}\n`);
  log(`POST VISION funcionales:\n${postFuncionales}\n`);
  log(`POST telemetria/vision:\n${postTelemetria}\n`);
  log(`AUTORIZAR_RUN:\n${autorizar ? 'SÍ' : 'NO'}\n`);

  log('--- contrato VISION observado ---');
  log(`CalibrarVisionDTO: ${envDe(summary, 'oa_dto_vision')}`);
  log(`modo_calibracion: ${envDe(summary, 'oa_modo_dominio')} | códigos del POST: ${envDe(summary, 'oa_codigos_post')}`);
  log('\n--- actores y fixture (solo consola, no se persiste) ---');
  const me = cuerpo('Identidad Ingeniero'); const ma = cuerpo('Identidad Administrador');
  log(`Ingeniero id ${me?.id_usuario} rol "${me?.nombre_rol}" estado ${me?.estado_cuenta} | permisos recurso 12 ${envDe(summary, 'perm_ing')}`);
  log(`Administrador id ${ma?.id_usuario} rol "${ma?.nombre_rol}" estado ${ma?.estado_cuenta} | permisos recurso 12 ${envDe(summary, 'perm_adm')}`);
  log(`finca del fixture: ${fixture.finca_id} «${envDe(summary, 'finca_nombre')}» | visible admin ${envDe(summary, 'finca_visible_admin')} | visible ingeniero ${envDe(summary, 'finca_visible_ingeniero')}`);
  log(`especie AVES: ${fixture.especie_aves} «${envDe(summary, 'especie_aves_nombre')}» modelo ${envDe(summary, 'especie_aves_modelo')}`);
  log(`especies INDIVIDUAL existentes: ${envDe(summary, 'especies_individual_existentes')} -> el setup registrará una`);
  log(`cámaras en TEST antes del setup: ${envDe(summary, 'inventario_camaras_total')}`);
  log(`ventana planificada: ${ventana.inicio} → ${ventana.fin} (${ventana.criterio})`);
  log(`newman: requests ${st.requests.ejecutados}/${st.requests.fallidos} fallidos | assertions ${st.assertions.total}/${st.assertions.fallidas} fallidas`);
  if (f.length) { log('\nfailures:'); f.forEach((x, i) => log(`  ${i + 1}. ${x.item} :: ${x.assertion} :: ${x.error}`)); }
  log('');
  if (!autorizar) { log('El RUN funcional NO está autorizado. Corregir antes de ejecutar los POST.'); process.exitCode = 2; }
  else log(`Ejecute el RUN: creará la especie INDIVIDUAL, las 4 áreas y 3 cámaras en la finca ${fixture.finca_id}.`);
}

// ------------------------------------------------------------------------------------ run
async function modoRun() {
  if (fs.existsSync(RUN_DIR)) throw new Error(`La carpeta ${runId} ya existe. Un RUN oficial no se repite ni se sobrescribe.`);
  const descubrimiento = await descubrir();
  if (!descubrimiento.elegida) throw new Error('BLOQUEADO POR PRECONDICIÓN DE DATOS: falta finca compartida, especie AVES o tipo de área.');
  const fixture = descubrimiento.elegida;

  const { col, itemsTotales, itemsEjecutables } = cargarColeccion(null);
  verificarEscrituras(col, true);
  const calibrar = col.item.filter(i => String(i.request.method) === 'POST' &&
    /\/calibraciones-vision$/.test(typeof i.request.url === 'string' ? i.request.url : i.request.url?.raw || ''));
  if (calibrar.length !== POST_VISION_BUDGET) {
    throw new Error(`ABORTADO: la colección debe contener exactamente ${POST_VISION_BUDGET} POST de calibración VISION, contiene ${calibrar.length}.`);
  }

  const gitPre = estadoGit('git_pre');
  const html = HTML_OFICIAL();
  const { env, ventana, nombres } = construirEnv(fixture);

  log(`RUN funcional oficial. RUN_ID: ${runId}`);
  log(`Colección: ${itemsEjecutables} de ${itemsTotales} items.`);
  log(`Fixture: finca ${fixture.finca_id} «${fixture.finca_nombre}» · especie AVES ${fixture.especie_aves} · tipo ${fixture.tipo_area}`);
  log(`  se crean: 1 especie INDIVIDUAL «${nombres.especie}», 4 áreas (A2..A5) y 3 cámaras (A3 inactiva, A4 y A5 activas).`);
  log(`POST VISION planificados: ${POST_VISION_BUDGET} | POST telemetría: 0 | reintentos: 0 | DELETE: 0\n`);

  const summary = await correrNewman(col, env, html, `${GRUPO} — SEGUNDA EVALUACIÓN · RUN funcional oficial ${runId}`);
  if (fs.existsSync(html)) fs.writeFileSync(html, limpiarHtml(fs.readFileSync(html, 'utf8')));

  const { cuerpo, http, enviadoTexto, asserts, ejecutado } = extraer(summary);
  const bloque = (nombre) => ({ ejecutado: ejecutado(nombre), http: http(nombre), cuerpo: cuerpo(nombre), assertions: asserts(nombre) });

  const preservado = {
    runId, generado: new Date().toISOString(), gitPre, itemsTotales, itemsEjecutables,
    stats: stats(summary), failures: fallos(summary),
    descubrimiento, fixtureElegido: fixture, ventana, nombres,
    stopAll: envDe(summary, 'stop_all') ?? 'NO',
    stopAllMotivo: envDe(summary, 'stop_all_motivo'),
    presupuesto: {
      postCalibracionVision: contar(summary, /\/calibraciones-vision$/, 'POST'),
      postTelemetriaVision: contar(summary, /\/telemetria\/vision$/, 'POST'),
      postEspecies: contar(summary, /\/configuracion\/especies$/, 'POST'),
      postInfraestructuras: contar(summary, /\/configuracion\/infraestructuras$/, 'POST'),
      postDispositivos: contar(summary, /\/configuracion\/dispositivos-iot$/, 'POST'),
      patchDesactivar: contar(summary, /\/desactivar$/, 'PATCH'),
      put: 0, delete: 0, reintentos: 0
    },
    contrato: {
      post_vision: envDe(summary, 'oa_post_vision'), get_vision: envDe(summary, 'oa_get_vision'),
      get_linea_base: envDe(summary, 'oa_get_linea_base'),
      dto_vision: J(envDe(summary, 'oa_dto_vision')), modo_dominio: J(envDe(summary, 'oa_modo_dominio')),
      codigos_post: J(envDe(summary, 'oa_codigos_post')),
      item: bloque('Contrato OpenAPI VISION')
    },
    actores: {
      ingeniero: { login: bloque('Login Ingeniero').http, identidad: bloque('Identidad Ingeniero'), permisos_recurso12: J(envDe(summary, 'perm_ing')), id: envDe(summary, 'ing_id') },
      administrador: { login: bloque('Login Administrador').http, identidad: bloque('Identidad Administrador'), permisos_recurso12: J(envDe(summary, 'perm_adm')), id: envDe(summary, 'adm_id') }
    },
    catalogo: {
      especie_aves: { id: envDe(summary, 'especie_aves'), nombre: envDe(summary, 'especie_aves_nombre'), modelo: envDe(summary, 'especie_aves_modelo'), item: bloque('Fixture — especie AVES del catálogo') },
      especies_individual_previas: J(envDe(summary, 'especies_individual_existentes')),
      tipo_area: { nombre: envDe(summary, 'area_tipo'), id: envDe(summary, 'area_tipo_id'), item: bloque('Fixture — tipo de área del catálogo') },
      finca: { id: envDe(summary, 'finca_id'), nombre: envDe(summary, 'finca_nombre'), visible_admin: envDe(summary, 'finca_visible_admin'), visible_ingeniero: envDe(summary, 'finca_visible_ingeniero'), compuerta: envDe(summary, 'compuerta_fixture') },
      inventario_camaras_previo: J(envDe(summary, 'inventario_camaras')), inventario_camaras_total: envDe(summary, 'inventario_camaras_total')
    },
    setup: {
      especie: { ...bloque('SETUP — crear especie de paradigma INDIVIDUAL'), id: envDe(summary, 'especie_grandes'), nombre: envDe(summary, 'especie_grandes_nombre'), creada: envDe(summary, 'especie_grandes_creada') },
      areas: Object.fromEntries(VARIANTES.map(v => [v.clave, {
        ...bloque(`SETUP — crear área ${v.area} (${v.caso})`),
        verificada: bloque(`SETUP — área ${v.area} verificada por el Ingeniero`),
        id: envDe(summary, `${v.clave}_id`), nombre: envDe(summary, `${v.clave}_nombre`),
        modelo: envDe(summary, `${v.clave}_modelo`), especie: envDe(summary, `${v.clave}_especie`),
        activa: envDe(summary, `${v.clave}_activa`), tipo: envDe(summary, `${v.clave}_tipo_real`),
        detalle: J(envDe(summary, `${v.clave}_detalle`))
      }])),
      camaras: Object.fromEntries(['a3', 'a4', 'a5'].map(k => [k, {
        ...bloque(k === 'a3' ? 'SETUP — registrar cámara INACTIVA en A3' : `SETUP — registrar cámara ACTIVA en ${k.toUpperCase()}`),
        id: envDe(summary, `cam_${k}`), activa: envDe(summary, `cam_${k}_activa`),
        serial_redactado: envDe(summary, `cam_${k}_serial_red`)
      }])),
      inventario: { ...bloque('SETUP — inventario de cámaras por área del fixture'),
        a2: J(envDe(summary, 'cams_a2')), a3: J(envDe(summary, 'cams_a3')),
        a4: J(envDe(summary, 'cams_a4')), a5: J(envDe(summary, 'cams_a5')) }
    },
    casos: Object.fromEntries(VARIANTES.map(v => [v.clave, {
      pre_linea_base: { ...bloque(`PRE ${v.caso} — línea base del área`), http: envDe(summary, `lb_pre_${v.clave}_http`), cuerpo: J(envDe(summary, `lb_pre_${v.clave}`)), id: envDe(summary, `lb_pre_${v.clave}_id`) },
      pre_historial: { ...bloque(`PRE ${v.caso} — historial VISION del área`), total: envDe(summary, `hist_pre_${v.clave}_total`), ids: J(envDe(summary, `hist_pre_${v.clave}_ids`)) },
      post: { ...bloque(`${v.caso} POST calibrar VISION`), enviado: enviadoTexto(`${v.caso} POST calibrar VISION`),
        error_code: envDe(summary, `${v.clave}_error_code`), mensaje: envDe(summary, `${v.clave}_mensaje`),
        mensaje_esperado: envDe(summary, `msg_esperado_${v.clave}`), mensaje_exacto: envDe(summary, `${v.clave}_mensaje_exacto`),
        respuesta: J(envDe(summary, `${v.clave}_respuesta`)) },
      post_linea_base: { ...bloque(`${v.caso} — línea base después del rechazo`), http: envDe(summary, `lb_post_${v.clave}_http`), cuerpo: J(envDe(summary, `lb_post_${v.clave}`)), id: envDe(summary, `lb_post_${v.clave}_id`) },
      post_historial: { ...bloque(`${v.caso} — historial VISION después del rechazo`), total: envDe(summary, `hist_post_${v.clave}_total`), ids: J(envDe(summary, `hist_post_${v.clave}_ids`)), nuevos: J(envDe(summary, `hist_post_${v.clave}_nuevos`)), exitosas: J(envDe(summary, `hist_post_${v.clave}_exitosas`), []) }
    }])),
    auditoria: { ...bloque('Auditoría RF-10 de los rechazos (evidencia complementaria)'),
      rechazos: J(envDe(summary, 'auditoria_rechazos'), []), exitosos: J(envDe(summary, 'auditoria_exitosos'), []) },
    restauracion: {
      camaras: {
        a3: { ...bloque('RESTAURACIÓN — la cámara de A3 sigue inactiva (sin escritura)'),
          final: envDe(summary, 'cam_a3_final'), sin_cambio_de_estado: envDe(summary, 'cam_a3_sin_cambio_de_estado') },
        a4: { ...bloque('RESTAURACIÓN — desactivar la cámara de A4'), final: envDe(summary, 'cam_a4_final') },
        a5: { ...bloque('RESTAURACIÓN — desactivar la cámara de A5'), final: envDe(summary, 'cam_a5_final') }
      },
      areas: Object.fromEntries(VARIANTES.map(v => [v.clave, { ...bloque(`RESTAURACIÓN — desactivar el área ${v.area}`), final: envDe(summary, `${v.clave}_final_activa`) }])),
      especie: { ...bloque('RESTAURACIÓN — desactivar la especie creada'), final: envDe(summary, 'especie_grandes_final') },
      verificacion: { ...bloque('RESTAURACIÓN — estado final del fixture verificado'),
        camaras_creadas_activas: J(envDe(summary, 'camaras_creadas_activas'), []),
        inventario_final: J(envDe(summary, 'inventario_camaras_final')) }
    }
  };
  fs.writeFileSync(SUMMARY_TMP(), limpiar(JSON.stringify(preservado, null, 2)));

  const st = preservado.stats;
  log('\n================ RUN OFICIAL ================');
  log(`RUN_ID: ${runId}`);
  log(`requests ${st.requests.ejecutados} (fallidos ${st.requests.fallidos}) | assertions ${st.assertions.total} (fallidas ${st.assertions.fallidas})`);
  log(`POST VISION: ${preservado.presupuesto.postCalibracionVision}/${POST_VISION_BUDGET} | telemetría: ${preservado.presupuesto.postTelemetriaVision} | STOP_ALL: ${preservado.stopAll}`);
  log(`setup: especie ${preservado.setup.especie.id} | áreas ${VARIANTES.map(v => v.area + '=' + preservado.setup.areas[v.clave].id).join(' ')} | cámaras a3=${preservado.setup.camaras.a3.id} a4=${preservado.setup.camaras.a4.id} a5=${preservado.setup.camaras.a5.id}`);
  for (const v of VARIANTES) {
    const c = preservado.casos[v.clave];
    log(`  ${v.caso} (${v.area}=${preservado.setup.areas[v.clave].id}): HTTP ${c.post.http} | error_code ${c.post.error_code || '—'} | mensaje exacto ${c.post.mensaje_exacto} | línea base PRE ${c.pre_linea_base.http} POST ${c.post_linea_base.http}`);
  }
  log(`restauración: cámaras ${['a3', 'a4', 'a5'].map(k => k + '=' + preservado.restauracion.camaras[k].final).join(' ')} | áreas ${VARIANTES.map(v => v.area + '=' + preservado.restauracion.areas[v.clave].final).join(' ')} | especie=${preservado.restauracion.especie.final}`);
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
    if (!fs.existsSync(evidenciaPath)) throw new Error('No hay summary del RUN ni evidencia previa: ejecute primero G138_MODO=run.');
    const ev = JSON.parse(fs.readFileSync(evidenciaPath, 'utf8'));
    const htmlPrevio = path.join(RUN_DIR, 'newman', `newman-${GRUPO}.html`);
    if (fs.existsSync(htmlPrevio)) fs.writeFileSync(htmlPrevio, limpiarHtml(fs.readFileSync(htmlPrevio, 'utf8')));
    escribir('evidencia.json', ev);
    ev.seguridad = escanearSeguridad();
    ev.git_post = estadoGit('git_post');
    escribir('evidencia.json', ev);
    refrescarManifest();
    log(`\nCIERRE (recalculo de seguridad y git). GRUPO ${GRUPO} -> ${ev.resultado_grupo}`);
    if (!ev.seguridad.limpio) process.exitCode = 3;
    return;
  }
  const R = JSON.parse(fs.readFileSync(tmp, 'utf8'));
  const num = (x) => (x === null || x === undefined || x === '' ? null : Number(x));

  // ---------------------------------------------------- oráculo por caso
  const resultados = {};
  for (const v of VARIANTES) {
    const c = R.casos[v.clave];
    const area = R.setup.areas[v.clave];
    const cams = R.setup.inventario[v.clave] || {};
    const resp = c.post.cuerpo || {};
    const esperado = MSG_BASE.replace('__AREA__', String(area.id));
    const preIds = (c.pre_historial.ids || []).map(Number);
    const postIds = (c.post_historial.ids || []).map(Number);
    const asserts = [...(c.pre_linea_base.assertions || []), ...(c.pre_historial.assertions || []),
      ...(c.post.assertions || []), ...(c.post_linea_base.assertions || []), ...(c.post_historial.assertions || [])];

    // Fixture: cada caso debe aislar UNA sola precondición inválida.
    const fixtureOk = {
      area_creada: area.http >= 200 && area.http <= 299,
      area_activa: String(area.activa) === 'true',
      area_visible_al_actor: area.verificada.http >= 200 && area.verificada.http <= 299,
      especie_asignada: num(area.especie) !== null
    };
    if (v.clave === 'a2') {
      fixtureOk.modelo_poblacional = POBLACIONALES.includes(String(area.modelo));
      fixtureOk.sin_camaras_asociadas = Number(cams.asociadas) === 0;
    } else if (v.clave === 'a3') {
      fixtureOk.modelo_poblacional = POBLACIONALES.includes(String(area.modelo));
      fixtureOk.exactamente_una_camara = Number(cams.asociadas) === 1;
      fixtureOk.esa_camara_inactiva = Number(cams.activas) === 0;
    } else if (v.clave === 'a4') {
      fixtureOk.modelo_individual = INDIVIDUALES.includes(String(area.modelo));
      fixtureOk.con_camara_activa = Number(cams.activas) >= 1;
    } else {
      fixtureOk.modelo_nulo = area.modelo === null || String(area.modelo) === 'null';
      fixtureOk.con_camara_activa = Number(cams.activas) >= 1;
    }

    const oraculo = {
      fixture_aislado: Object.values(fixtureOk).every(x => x === true),
      http_422: Number(c.post.http) === 422,
      no_es_400: Number(c.post.http) !== 400,
      no_es_403: Number(c.post.http) !== 403,
      no_es_404: Number(c.post.http) !== 404,
      no_es_5xx: Number(c.post.http) < 500,
      mensaje_literal_exacto: (resp.message ?? resp.detail ?? null) === esperado,
      mensaje_con_id_real: String(resp.message ?? '').includes(`El área ${area.id} `),
      sin_id_calibracion_vision: resp.id_calibracion_vision === undefined || resp.id_calibracion_vision === null,
      linea_base_pre_ausente: Number(c.pre_linea_base.http) === 404,
      linea_base_post_ausente: Number(c.post_linea_base.http) === 404,
      sin_linea_base_nueva: Number(c.pre_linea_base.http) === Number(c.post_linea_base.http) &&
        num(c.post_linea_base.id) === num(c.pre_linea_base.id),
      historial_total_sin_cambios: num(c.post_historial.total) === num(c.pre_historial.total),
      historial_ids_sin_cambios: JSON.stringify(postIds.slice().sort()) === JSON.stringify(preIds.slice().sort()),
      sin_calibracion_vision_exitosa: Array.isArray(c.post_historial.exitosas) && c.post_historial.exitosas.length === 0,
      assertions_todas_pass: asserts.length > 0 && asserts.every(a => a.paso)
    };
    resultados[v.clave] = {
      ...v,
      area: { id: num(area.id), nombre: area.nombre, tipo: area.tipo, modelo: area.modelo,
        paradigma: POBLACIONALES.includes(String(area.modelo)) ? 'POBLACIONAL'
          : INDIVIDUALES.includes(String(area.modelo)) ? 'INDIVIDUAL'
          : (area.modelo === null || String(area.modelo) === 'null') ? '(sin modelo)' : '(otro)',
        especie_id: num(area.especie), activa: area.activa, creada_en_el_run: true },
      camaras: cams,
      request: { endpoint: '/configuracion/calibraciones-vision', metodo: 'POST',
        headers: { Authorization: '[REDACTED]', 'Content-Type': 'application/json' },
        bodyTextoEnviado: c.post.enviado, body: c.post.enviado ? JSON.parse(c.post.enviado) : null,
        intentos: 1, reintentos: 0 },
      response: { http: Number(c.post.http), cuerpo: resp,
        error_code: resp.error_code ?? c.post.error_code ?? null,
        message: resp.message ?? resp.detail ?? null, capturado: new Date().toISOString() },
      mensaje_esperado: esperado, mensaje_exacto: oraculo.mensaje_literal_exacto,
      comparacion: 'literal estricta, con el ID real del área sustituido en el mensaje contractual',
      linea_base: { pre_http: Number(c.pre_linea_base.http), pre: c.pre_linea_base.cuerpo,
        post_http: Number(c.post_linea_base.http), post: c.post_linea_base.cuerpo,
        nueva: !oraculo.sin_linea_base_nueva },
      historial: { pre_total: num(c.pre_historial.total), pre_ids: preIds,
        post_total: num(c.post_historial.total), post_ids: postIds,
        nuevos: c.post_historial.nuevos, exitosas: c.post_historial.exitosas },
      fixture_verificado: fixtureOk,
      assertions: { total: asserts.length, fallidas: asserts.filter(a => !a.paso).length, detalle: asserts },
      oraculo,
      resultado: Object.values(oraculo).every(x => x === true) ? 'APROBADO' : 'RECHAZADO'
    };
  }

  const r278 = resultados.a2.resultado, r279 = resultados.a3.resultado;
  const r280 = resultados.a4.resultado, r281 = resultados.a5.resultado;

  // ------------------------------------------------------------------ setup y restauración
  const setupOk = R.setup.especie.http >= 200 && R.setup.especie.http <= 299 &&
    VARIANTES.every(v => R.setup.areas[v.clave].http >= 200 && R.setup.areas[v.clave].http <= 299) &&
    ['a3', 'a4', 'a5'].every(k => R.setup.camaras[k].http >= 200 && R.setup.camaras[k].http <= 299);

  // ------------------------------- verificación final: SOLO LECTURA, después del RUN
  const tokenIng = await login(ING.email, ING.secret);
  const tokenAdm = await login(ADM.email, ADM.secret);
  const dispositivos = await get('/configuracion/dispositivos-iot', tokenIng);
  const camInv = (dispositivos.cuerpo?.items || []).filter(x => String(x.categoria) === 'CAMARA');
  const creadas = ['a3', 'a4', 'a5'].map(k => num(R.setup.camaras[k].id));
  const red = { camaras: [], areas: [], especie: 'no necesaria' };

  // Red de seguridad: si Newman no completó alguna reversión, se ejecuta aquí.
  for (const k of ['a3', 'a4', 'a5']) {
    const id = num(R.setup.camaras[k].id);
    const fila = camInv.find(x => Number(x.id_dispositivo_iot) === id);
    if (fila && fila.es_activo === true) {
      const r = await escribirApi('PATCH', `/configuracion/dispositivos-iot/${id}/desactivar`, tokenIng, null);
      red.camaras.push(`${k} (id ${id}): ejecutada por el cierre, HTTP ${r.status}`);
    }
  }
  const areasFinales = {};
  for (const v of VARIANTES) {
    const id = num(R.setup.areas[v.clave].id);
    let det = await get(`/configuracion/infraestructuras/${id}`, tokenAdm);
    if (det.status === 200 && det.cuerpo?.es_activo === true) {
      const r = await escribirApi('PATCH', `/configuracion/infraestructuras/${id}/desactivar`, tokenAdm, null);
      red.areas.push(`${v.area} (id ${id}): ejecutada por el cierre, HTTP ${r.status}`);
      det = await get(`/configuracion/infraestructuras/${id}`, tokenAdm);
    }
    areasFinales[v.area] = { id, http: det.status, es_activo: det.cuerpo?.es_activo ?? null };
  }
  const especies = await get('/configuracion/especies', tokenAdm);
  const espId = num(R.setup.especie.id);
  let espFila = (especies.cuerpo?.items || []).find(x => Number(x.id_especie) === espId) || null;
  if (espFila && espFila.es_activo === true) {
    const r = await escribirApi('PATCH', `/configuracion/especies/${espId}/desactivar`, tokenAdm, null);
    red.especie = `ejecutada por el cierre: HTTP ${r.status}`;
    const esp2 = await get('/configuracion/especies', tokenAdm);
    espFila = (esp2.cuerpo?.items || []).find(x => Number(x.id_especie) === espId) || espFila;
  }
  const dispositivosFinal = await get('/configuracion/dispositivos-iot', tokenIng);
  const camFinal = (dispositivosFinal.cuerpo?.items || []).filter(x => String(x.categoria) === 'CAMARA');
  const camCreadasActivas = camFinal.filter(x => creadas.includes(Number(x.id_dispositivo_iot)) && x.es_activo === true)
    .map(x => x.id_dispositivo_iot);

  const recursos = [
    ...['a3', 'a4', 'a5'].map(k => ({
      recurso: `cámara de ${k.toUpperCase()}`, id: num(R.setup.camaras[k].id),
      estado_original: 'no existía (creada en este RUN)',
      cambio: k === 'a3' ? 'registrada INACTIVA desde el origen' : 'registrada ACTIVA para aislar la precondición del caso',
      estado_durante: String(R.setup.camaras[k].activa) === 'true' ? 'ACTIVA' : 'INACTIVA',
      restauracion: k === 'a3'
        ? 'ninguna escritura: nacio inactiva, se verifico por GET que sigue inactiva'
        : 'PATCH /configuracion/dispositivos-iot/{id}/desactivar',
      estado_final: (camFinal.find(x => Number(x.id_dispositivo_iot) === num(R.setup.camaras[k].id)) || {}).es_activo ?? null
    })),
    ...VARIANTES.map(v => ({
      recurso: `área ${v.area}`, id: num(R.setup.areas[v.clave].id),
      estado_original: 'no existía (creada en este RUN)',
      cambio: `creada con el perfil: ${v.perfil}`,
      estado_durante: 'ACTIVA',
      restauracion: 'PATCH /configuracion/infraestructuras/{id}/desactivar',
      estado_final: areasFinales[v.area].es_activo
    })),
    { recurso: 'especie de paradigma INDIVIDUAL', id: espId,
      estado_original: 'no existía (creada en este RUN; el catálogo de TEST no tenía ninguna activa)',
      cambio: 'registrada con tipo_modelo MODELO_ESPECIES_GRANDES',
      estado_durante: 'ACTIVA',
      restauracion: 'PATCH /configuracion/especies/{id}/desactivar',
      estado_final: espFila ? espFila.es_activo : null }
  ];
  const pendientes = recursos.filter(x => x.estado_final !== false).map(x => `${x.recurso} (id ${x.id}) sigue activo`);
  const restauracion = {
    criterio: ('Todo lo creado se revierte por desactivación oficial, en orden inverso: cámaras, ' +
      'áreas y por último la especie. No se borra nada por SQL y no se toca ningún dato ajeno: ' +
      'ninguna área, cámara ni especie preexistente de TEST fue modificada.'),
    recursos_modificados: recursos,
    recursos_preexistentes_modificados: 'ninguno',
    camara_de_a3: ('se registró INACTIVA desde el origen, así que no hubo estado previo que ' +
      'restaurar: la única cámara asociada al área nunca estuvo activa.'),
    red_de_seguridad: red,
    camaras_creadas_que_siguen_activas: camCreadasActivas,
    todos_restaurados: pendientes.length === 0,
    pendientes,
    resultado: pendientes.length === 0 ? 'PASS' : 'FAIL'
  };

  // ---------------------------------------------------------------------- BD (solo lectura)
  const bd = await diagnosticoBD(resultados);

  const newmanLimpio = R.failures.length === 0 && (R.stats.requests.fallidos || 0) === 0;
  const lineasBaseIndebidas = VARIANTES.filter(v => resultados[v.clave].linea_base.nueva).map(v => v.caso);
  const resultadoGrupo = ([r278, r279, r280, r281].every(x => x === 'APROBADO') &&
    newmanLimpio && setupOk && restauracion.resultado === 'PASS' && lineasBaseIndebidas.length === 0)
    ? 'APROBADO' : 'RECHAZADO';

  // ------------------------------------------------------- comparación con la primera
  const PRIMERA = {
    runId: BASELINE_RUN,
    fuente: `tests/Test_Testing/Test_Modulo9/RF-24/${GRUPO}/RESULTADOS/${BASELINE_RUN}/${GRUPO}_resultado.md`,
    porCaso: 'RECHAZADO / NO EJECUTABLE FUNCIONALMENTE', grupo: 'RECHAZADO',
    dimensiones: {
      endpoint_vision: 'AUSENTE', post_ejecutados: '0', http_422_observables: 'NO',
      mensajes_observables: 'NO', linea_base_verificable: 'NO'
    },
    causa: 'TEST no publicaba ninguna operación de calibración VISION; no se ejecutó ningún POST.'
  };
  const comparacion = {
    baselineUnico: `PRIMERA EVALUACION OFICIAL ${PRIMERA.runId}`,
    fuente: PRIMERA.fuente,
    porCaso: Object.fromEntries(VARIANTES.map(v => [v.caso, {
      primera: PRIMERA.porCaso, segunda: resultados[v.clave].resultado,
      cambio: `${PRIMERA.porCaso} -> ${resultados[v.clave].resultado}`
    }])),
    grupo: { primera: PRIMERA.grupo, segunda: resultadoGrupo, cambio: `${PRIMERA.grupo} -> ${resultadoGrupo}` },
    dimensiones: {
      endpoint_vision: { primera: PRIMERA.dimensiones.endpoint_vision, segunda: R.contrato.post_vision },
      post_ejecutados: { primera: PRIMERA.dimensiones.post_ejecutados, segunda: String(R.presupuesto.postCalibracionVision) },
      http_422_observables: { primera: PRIMERA.dimensiones.http_422_observables,
        segunda: `${VARIANTES.filter(v => Number(resultados[v.clave].response.http) === 422).length} de 4` },
      mensajes_observables: { primera: PRIMERA.dimensiones.mensajes_observables,
        segunda: `${VARIANTES.filter(v => resultados[v.clave].mensaje_exacto).length} de 4 con el literal exacto` },
      linea_base_verificable: { primera: PRIMERA.dimensiones.linea_base_verificable,
        segunda: `SÍ — PRE y POST verificados por API en las 4 áreas; ${lineasBaseIndebidas.length} líneas base indebidas` }
    },
    causaDelRechazoAnterior: resultadoGrupo === 'APROBADO' ? 'CORREGIDA'
      : (R.contrato.post_vision === 'PRESENTE' ? 'PARCIALMENTE CORREGIDA' : 'NO CORREGIDA')
  };

  const causaRaiz = (() => {
    if (R.contrato.post_vision !== 'PRESENTE') {
      return 'B. TEST sigue sin publicar la operacion VISION: el rechazo anterior no esta corregido.';
    }
    if (lineasBaseIndebidas.length) {
      return ('E. DEFECTO GRAVE DE INTEGRIDAD: un rechazo de precondicion publico linea base en ' +
        lineasBaseIndebidas.join(', ') + '. El 422 no debe tener ningun efecto de escritura.');
    }
    const con2xx = VARIANTES.filter(v => Number(resultados[v.clave].response.http) < 400);
    if (con2xx.length) {
      return ('C. La operacion VISION existe pero al menos una precondicion no se valida: ' +
        con2xx.map(v => `${v.caso} respondio HTTP ${resultados[v.clave].response.http}`).join('; ') +
        '. Regla de negocio ausente o incompleta.');
    }
    const malMensaje = VARIANTES.filter(v => !resultados[v.clave].mensaje_exacto);
    if (malMensaje.length) {
      return ('D. Los cuatro rechazos llegan, pero el mensaje de ' + malMensaje.map(v => v.caso).join(', ') +
        ' no coincide con el literal del contrato: contrato y mensaje desalineados.');
    }
    const malCodigo = VARIANTES.filter(v => Number(resultados[v.clave].response.http) !== 422);
    if (malCodigo.length) {
      return ('D. El rechazo ocurre pero con un codigo distinto de 422 en ' +
        malCodigo.map(v => `${v.caso} (HTTP ${resultados[v.clave].response.http})`).join(', ') + '.');
    }
    if (resultadoGrupo === 'APROBADO') {
      return ('A. Los cuatro rechazos responden HTTP 422 con el mensaje literal del contrato y el ID ' +
        'real de su area, y ninguno publica linea base: la operacion VISION esta expuesta en TEST y ' +
        'las cuatro precondiciones negativas del area se validan correctamente. La causa del rechazo ' +
        'anterior esta corregida y desplegada.');
    }
    return 'F. Por determinar con la evidencia de esta corrida.';
  })();

  const afectados = VARIANTES.filter(v => resultados[v.clave].resultado !== 'APROBADO').map(v => v.caso);
  const incidencias = [];
  if (resultadoGrupo !== 'APROBADO') {
    incidencias.push({
      incidencia_requerida: 'SÍ',
      grupo_responsable: R.contrato.post_vision === 'PRESENTE' ? 'Desarrollo' : 'Desarrollo / Implementación según contraste DEV',
      grupo_de_prueba: GRUPO, casos_afectados: afectados,
      consolidada: afectados.length > 1 ? 'SÍ: los casos afectados comparten la causa' : 'NO',
      resultado: resultadoGrupo, motivo: causaRaiz, causa_raiz: causaRaiz,
      type: 'bug',
      severity: lineasBaseIndebidas.length ? 'Critical' : 'Important',
      priority: 'High',
      evidencia: `evidencia.json y newman/newman-${GRUPO}.html del RUN ${runId}`
    });
  }

  const evidencia = {
    run_id: runId, evaluacion: 'SEGUNDA EVALUACION',
    grupo: GRUPO, casos: CASOS, requisito: RF, casoDeUso: CU,
    herramientas: 'API - Postman / Newman. BD TEST solo como diagnostico de solo lectura.',
    ambiente: { decisorio: 'TEST', base_url: base(), contraste_dev: 'no utilizado' },
    carpeta: `tests/Test_Testing/Test_Modulo9/RF-24/${GRUPO}/EvaluacionV2/`,
    rama: R.gitPre.rama, commit: R.gitPre.commit,
    resultado_grupo: resultadoGrupo,
    resultado_por_caso: { 'TC-M09-278': r278, 'TC-M09-279': r279, 'TC-M09-280': r280, 'TC-M09-281': r281 },

    git_pre: R.gitPre,
    contrato_vision: R.contrato,

    actores: {
      nota: ('La coleccion Newman es duena de sus sesiones: hace sus propios logins y publica los ' +
        'tokens en engineer_session y admin_session. El runner no obtiene tokens ni los inyecta; en ' +
        'el cierre se autentica aparte para la verificacion de solo lectura y la red de seguridad.'),
      ingeniero: { correo: ING.email, credencial: '[REDACTED]', ...R.actores.ingeniero, papel: 'ejecuta los 4 POST VISION funcionales' },
      administrador: { correo: ADM.email, credencial: '[REDACTED]', ...R.actores.administrador, papel: 'crea y revierte el fixture; consulta RF-10. No ejecuta los POST funcionales' }
    },

    estrategia_de_fixtures: {
      descubrimiento: R.descubrimiento,
      criterio: ('Se prefirieron datos existentes: se reutilizan la finca compartida, la especie AVES ' +
        'y el tipo de area del catalogo. Se crean solo los recursos que TEST no tenia, con endpoints ' +
        'oficiales y con reversion oficial verificada. No se uso SQL para preparar nada y no se ' +
        'modifico ningun recurso preexistente.'),
      catalogo_reutilizado: R.catalogo,
      creado_en_el_run: {
        especie_individual: R.setup.especie, areas: R.setup.areas, camaras: R.setup.camaras,
        inventario_por_area: R.setup.inventario
      },
      areas_distintas_por_caso: Object.fromEntries(VARIANTES.map(v => [v.caso, num(R.setup.areas[v.clave].id)])),
      setup_ok: setupOk,
      escrituras: {
        post_setup: { especies: R.presupuesto.postEspecies, areas: R.presupuesto.postInfraestructuras, camaras: R.presupuesto.postDispositivos },
        patch_setup: 0,
        patch_restauracion: R.presupuesto.patchDesactivar,
        post_funcionales_vision: R.presupuesto.postCalibracionVision,
        post_telemetria_vision: R.presupuesto.postTelemetriaVision,
        put: 0, delete: 0, sql_dml: 0,
        nota: 'Las escrituras de setup y de restauracion se cuentan por separado de los 4 POST funcionales.'
      }
    },

    ventana_observacion: R.ventana,

    'TC-M09-278': resultados.a2,
    'TC-M09-279': resultados.a3,
    'TC-M09-280': resultados.a4,
    'TC-M09-281': resultados.a5,

    verificacion_no_publicacion_linea_base: {
      criterio: 'Los cuatro son rechazos de precondicion: CERO lineas base nuevas y CERO calibraciones VISION exitosas.',
      por_caso: Object.fromEntries(VARIANTES.map(v => [v.caso, {
        area_id: resultados[v.clave].area.id,
        linea_base_pre: `HTTP ${resultados[v.clave].linea_base.pre_http}`,
        linea_base_post: `HTTP ${resultados[v.clave].linea_base.post_http}`,
        linea_base_nueva: resultados[v.clave].linea_base.nueva ? 'SI' : 'NO',
        historial_pre: resultados[v.clave].historial.pre_total,
        historial_post: resultados[v.clave].historial.post_total,
        calibraciones_nuevas: resultados[v.clave].historial.nuevos,
        calibraciones_exitosas: resultados[v.clave].historial.exitosas
      }])),
      lineas_base_indebidas: lineasBaseIndebidas,
      stop_all: R.stopAll, stop_all_motivo: J(R.stopAllMotivo),
      auditoria_rf10: {
        rechazos_registrados: R.auditoria.rechazos, eventos_exitosos: R.auditoria.exitosos,
        nota: ('RFC-006 puede registrar los rechazos con resultado FALLIDO. Eso NO constituye una ' +
          'linea base: se distingue la auditoria del rechazo (esperable) de la calibracion exitosa o ' +
          'la linea base (ambas prohibidas en estos cuatro casos).')
      }
    },

    newman: {
      html: `newman/newman-${GRUPO}.html`, htmlPersistentes: 1,
      coleccionEjecutada: `${R.itemsEjecutables} de ${R.itemsTotales} items`,
      iterations: R.stats.iterations, requests: R.stats.requests, assertions: R.stats.assertions,
      failures: R.failures, presupuesto: R.presupuesto, limpio: newmanLimpio,
      nota: 'Un unico HTML oficial. El PRECHECK fue solo de consola y no genero ningun reporte.'
    },

    restauracion,
    verificacion_bd: bd,
    comparacion_primera_segunda: comparacion,
    causa_raiz: causaRaiz,
    incidencias: incidencias.length ? incidencias : [{
      incidencia_requerida: 'NO', causa_anterior: 'CORREGIDA',
      nota: ('Los cuatro rechazos se validan correctamente. Se propone validar y cerrar la incidencia ' +
        'previa de G138 (ausencia de la operacion VISION en TEST).')
    }],
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
    const c = resultados[v.clave];
    const malos = Object.entries(c.oraculo).filter(([, ok]) => ok !== true).map(([k]) => k);
    log(`${v.caso} (${v.area}=${c.area.id}, ${c.area.paradigma}, cams ${c.camaras.asociadas}/${c.camaras.activas} activas): HTTP ${c.response.http} | ${c.response.error_code || '—'} | mensaje exacto ${c.mensaje_exacto ? 'SI' : 'NO'} | LB ${c.linea_base.pre_http}->${c.linea_base.post_http} | nueva LB ${c.linea_base.nueva ? 'SI' : 'NO'} -> ${c.resultado}${malos.length ? ' | incumple: ' + malos.join(', ') : ''}`);
  }
  log(`TC-278 ${r278} | TC-279 ${r279} | TC-280 ${r280} | TC-281 ${r281}`);
  log(`GRUPO ${GRUPO} -> ${resultadoGrupo}`);
  log(`Newman: requests ${R.stats.requests.ejecutados} (fallidos ${R.stats.requests.fallidos}) | assertions ${R.stats.assertions.total} (fallidas ${R.stats.assertions.fallidas}) | limpio ${newmanLimpio ? 'SI' : 'NO'}`);
  log(`Presupuesto: POST VISION ${R.presupuesto.postCalibracionVision}/${POST_VISION_BUDGET} | telemetria ${R.presupuesto.postTelemetriaVision} | setup ${R.presupuesto.postEspecies}+${R.presupuesto.postInfraestructuras}+${R.presupuesto.postDispositivos} POST | restauracion ${R.presupuesto.patchDesactivar} PATCH | STOP_ALL ${R.stopAll}`);
  log(`Restauracion: ${restauracion.resultado}${restauracion.pendientes.length ? ' | pendientes: ' + restauracion.pendientes.join('; ') : ' | todo desactivado'} | red ${JSON.stringify(red)}`);
  log(`BD: ${bd.utilizada ? 'consultada (solo SELECT)' : 'no utilizada'} | ${bd.resumen}`);
  log(`Causa del rechazo anterior: ${comparacion.causaDelRechazoAnterior}`);
  log(`Evidencia limpia de secretos: ${evidencia.seguridad.limpio ? 'SI' : 'NO'}`);
  log('========================================\n');

  if (!evidencia.seguridad.limpio) process.exitCode = 3;
  else if (resultadoGrupo !== 'APROBADO' || restauracion.resultado !== 'PASS') process.exitCode = 2;
}

// --------------------------------------------------------------- BD TEST (SOLO SELECT)
async function diagnosticoBD(resultados) {
  const salida = {
    utilizada: false, solo_select: true, dml_ejecutado: 0,
    motivo: 'La BD no es el oraculo principal; se consulta como diagnostico complementario del fixture.',
    consultas: [], resumen: ''
  };
  if (!process.env.QA_DB_PASSWORD) {
    salida.resumen = 'no se entrego QA_DB_PASSWORD: no se abrio ninguna conexion';
    return salida;
  }
  const areas = VARIANTES.map(v => resultados[v.clave].area.id).filter(x => x !== null);
  const programa = [
    'import json, os, psycopg2, psycopg2.extras',
    'A = json.loads(os.environ["G138_AREAS"])',
    'C = [',
    '  ("privilegios_del_rol_qa", """SELECT n.nspname AS esquema, c.relname AS tabla,',
    "         has_table_privilege(current_user, c.oid, 'SELECT') AS puede_select",
    '       FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace',
    "       WHERE (n.nspname, c.relname) IN (('modulo9','calibraciones_vision'),",
    "             ('modulo9','lineas_base_vision'), ('modulo9','infraestructuras'),",
    "             ('modulo9','dispositivos_iot'))",
    '       ORDER BY 1,2""", None),',
    '  ("areas_del_fixture", """SELECT id_infraestructura, es_activo, id_especie, tipo_modelo_asignado',
    '       FROM modulo9.infraestructuras WHERE id_infraestructura = ANY(%s)',
    '       ORDER BY id_infraestructura""", (A,)),',
    '  ("camaras_por_area_del_fixture", """SELECT d.id_infraestructura, d.id_dispositivo_iot, d.es_activo',
    '       FROM modulo9.dispositivos_iot d',
    '       JOIN modulo9.tipos_dispositivo_iot t ON t.id_tipo_dispositivo = d.id_tipo_dispositivo',
    "       WHERE t.categoria = 'CAMARA' AND d.id_infraestructura = ANY(%s)",
    '       ORDER BY 1,2""", (A,)),',
    '  ("lineas_base_de_las_areas", """SELECT id_infraestructura, id_especie, id_calibracion_vision',
    '       FROM modulo9.lineas_base_vision WHERE id_infraestructura = ANY(%s)""", (A,)),',
    '  ("calibraciones_vision_de_las_areas", """SELECT id_calibracion_vision, id_infraestructura, estado',
    '       FROM modulo9.calibraciones_vision WHERE id_infraestructura = ANY(%s)""", (A,)),',
    ']',
    'salida = []',
    'try:',
    '    conn = psycopg2.connect(host=os.environ["QA_DB_HOST"], port=os.environ["QA_DB_PORT"],',
    '                            dbname=os.environ["QA_DB_NAME"], user=os.environ["QA_DB_USER"],',
    '                            password=os.environ["QA_DB_PASSWORD"], connect_timeout=25)',
    '    conn.autocommit = True',
    '    conn.set_session(readonly=True)',
    '    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)',
    '    for nombre, sql, params in C:',
    '        try:',
    '            cur.execute(sql, params) if params else cur.execute(sql)',
    '            salida.append({"nombre": nombre, "sentencia": "SELECT",',
    '                           "filas": json.loads(json.dumps([dict(f) for f in cur.fetchall()], default=str))})',
    '        except Exception as e:',
    '            salida.append({"nombre": nombre, "sentencia": "SELECT", "error": str(e).splitlines()[0]})',
    '    cur.close(); conn.close()',
    'except Exception as e:',
    '    salida.append({"nombre": "conexion", "error": str(e).splitlines()[0]})',
    'print(json.dumps(salida, ensure_ascii=False))'
  ].join('\n');
  try {
    const stdout = execFileSync('python', ['-I', '-c', programa], {
      encoding: 'utf8', timeout: 120000,
      env: { ...process.env, G138_AREAS: JSON.stringify(areas) }
    });
    salida.utilizada = true;
    salida.cliente = 'psycopg2 en sesion READ ONLY, invocado en linea desde el runner';
    salida.consultas = JSON.parse(stdout.trim().split('\n').pop());
  } catch (e) {
    salida.consultas.push({ nombre: 'conexion', error: limpiar(String(e.message).split('\n')[0]) });
    salida.utilizada = salida.consultas.some(c => !c.error);
  }
  const denegadas = salida.consultas.filter(c => /permission denied|does not exist/i.test(String(c.error || '')));
  salida.limitacion = denegadas.length
    ? ('La cuenta de solo lectura member_qa no tiene SELECT sobre todas las tablas consultadas ' +
       '(las VISION entre ellas) ni EXECUTE sobre las funciones de RLS: las tablas existen, pero el ' +
       'privilegio esta denegado. El oraculo se construyo con los GET de la API, que son la superficie ' +
       'autoritativa del producto; no se sustituye la BD por ninguna inferencia.')
    : null;
  salida.resumen = denegadas.length
    ? `${denegadas.length} de ${salida.consultas.length} consultas denegadas por privilegios de member_qa`
    : `${salida.consultas.length} consultas SELECT ejecutadas`;
  salida.dml_ejecutado = 0;
  return salida;
}

// --------------------------------------------------------------------------- manifiesto
function refrescarManifest() {
  const artefactos = [
    { archivo: 'run-g138-v2.cjs', abs: path.join(__dirname, 'run-g138-v2.cjs'),
      ruta: `${GRUPO}/EvaluacionV2/automation/run-g138-v2.cjs`,
      funcion: ('Runner unico de la reevaluacion, con los modos precheck (Newman de solo lectura sin ' +
        'HTML ni archivos, mas el descubrimiento dinamico de la finca compartida, la especie AVES y el ' +
        'tipo de area), run (RUN funcional oficial con el setup del fixture, los 4 POST de calibracion ' +
        'VISION, la restauracion y el unico HTML) y close (oraculo por caso, verificacion final de solo ' +
        'lectura, red de seguridad de la restauracion, diagnostico de BD solo SELECT y consolidacion de ' +
        'evidencia). No obtiene ni inyecta tokens en Newman, no ejecuta PUT, DELETE ni DML, y aborta si ' +
        'la coleccion intentara cargar observaciones M03.') },
    { archivo: 'TC-M09-G138.postman_collection.json', abs: COLECCION,
      ruta: `${GRUPO}/EvaluacionV2/TC-M09-G138.postman_collection.json`,
      funcion: ('Coleccion de EvaluacionV2. La original solo consultaba /openapi.json porque TEST no ' +
        'publicaba VISION; esta ejercita los cuatro rechazos de precondicion y es duena de sus sesiones ' +
        '(logins dentro de Newman, tokens en engineer_session y admin_session). Crea un area distinta ' +
        'por caso con una sola precondicion invalida aislada, envia los 4 POST con el mensaje esperado ' +
        'construido con el ID real del area, verifica linea base e historial antes y despues, aplica ' +
        'STOP_ALL si un rechazo publicara linea base y revierte todo el fixture por desactivacion.') },
    { archivo: 'TC-M09-G138.postman_collection.json (original)', abs: COLECCION_ORIGINAL,
      ruta: `${GRUPO}/TC-M09-G138.postman_collection.json`,
      funcion: ('Coleccion de la primera evaluacion: un unico GET de /openapi.json para el preflight ' +
        'contractual. Reutilizada en solo lectura como fuente del criterio del preflight; no fue modificada.') },
    { archivo: 'run-newman.cjs (original)', abs: path.join(CASE_DIR, 'run-newman.cjs'),
      ruta: `${GRUPO}/run-newman.cjs`,
      funcion: ('Runner de la primera evaluacion, que decidia el oraculo fuera de Newman ante la ausencia ' +
        'de contrato VISION. NO se utiliza en esta reevaluacion: se registra por trazabilidad del baseline.') }
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
    grupo: GRUPO, casos: CASOS, runId,
    herramienta: 'API - Postman / Newman',
    nota: ('Artefactos finales de la SEGUNDA EVALUACION. Los ejecutables viven unicamente en ' +
      'EvaluacionV2/; no se copian scripts dentro de RESULTADOS.'),
    newmanHtmlPersistentes: 1, automationDentroDeResultados: 'NO', artefactos: filas
  }, null, 2)));
}
