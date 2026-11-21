// Runner único de TC-M09-G137 (RF-24 v2.0, Módulo 9, CU05 Flujo F — calibración VISION).
// Casos TC-M09-275 (Ingeniero), TC-M09-276 (Administrador) y TC-M09-277 (Productor, 403).
//
// REEJECUCIÓN OFICIAL POST-FIX. Desarrollo informó la corrección del defecto de reemplazo de
// línea base VISION: en el RUN anterior (run-20261010-105849) la SEGUNDA calibración del mismo
// par (área, especie) respondía 409 RECURSO_DUPLICADO contra el índice único
// uq_linea_base_vision_id_infraestructura_id_especie. Se reejecutan los TRES casos, porque
// TC-276 depende de la línea base que publica TC-275 y TC-277 comprueba que el Productor no
// altera la línea finalmente publicada.
//
// Un solo archivo, tres modos (G137_MODO):
//
//   precheck  Validación Newman de SOLO LECTURA previa al RUN: solo los items de lectura. No
//             registra nada, no envía ningún POST funcional ni de telemetría, no genera HTML, no
//             crea RESULTADOS y no deja archivos: solo consola. Incluye la revalidación del
//             fixture histórico por API y la verificación del fix por SELECT de solo lectura.
//   run       RUN funcional oficial: la colección completa una única vez, con el setup mínimo,
//             los 3 POST funcionales, la restauración y el ÚNICO HTML persistente.
//   close     Oráculo por caso, verificación final de solo lectura, verificación del fix en BD,
//             red de seguridad de la restauración y consolidación de evidencia y manifiesto.
//
// PROPIEDAD DE SESIONES (regla corregida desde G76): la colección es dueña de las sesiones. Hace
// sus propios logins y publica los tokens en {{engineer_session}}, {{admin_session}} y
// {{productor_session}}. El runner NO obtiene tokens y NO los inyecta en Newman.
//
// FIXTURE REUTILIZADO, sin workarounds: la MISMA finca, la MISMA área, la MISMA especie y la
// línea base previa que ya exista del mismo par. No se cambia de área ni de especie, no se borra
// ninguna línea base y no se evita que exista una línea previa. Lo único que se registra es una
// cámara activa —la del RUN anterior quedó desactivada por su propia restauración y la API no
// publica reactivación de dispositivos— más un lote nuevo de observaciones para esa cámara.
//
// Presupuesto: 3 POST /calibraciones-vision + 1 POST batch de telemetría, sin reintentos.
//
// Uso:
//   $env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
//   $env:QA_ING_EMAIL="ingeniero@pecuaria.co";      $env:QA_ING_PASSWORD="<secreto>"
//   $env:QA_ADM_EMAIL="administador.dev@gmail.com"; $env:QA_ADM_PASSWORD="<secreto>"
//   $env:QA_PROD_EMAIL="m2m.nuevo@ejemplo.com";     $env:QA_PROD_PASSWORD="<secreto>"
//   $env:G137_FINCA="163"; $env:G137_AREA="279"     (referencia histórica; se revalida por API)
//   $env:G137_RUN_ID="run-YYYYMMDD-HHMMSS"          (modos run y close)
//   $env:G137_MODO="precheck" | "run" | "close"
//   node .\run-g137-v2.cjs

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const CASE_DIR = path.resolve(__dirname, '..', '..');
const EVAL_DIR = path.resolve(__dirname, '..');
// La coleccion vive en automation/, junto al runner, como en el resto de los grupos
// (G139 a G143). Antes estaba en la raiz de EvaluacionV2.
const COLECCION = path.join(__dirname, 'TC-M09-G137.postman_collection.json');
const COLECCION_ORIGINAL = path.join(CASE_DIR, 'TC-M09-G137.postman_collection.json');

const GRUPO = 'TC-M09-G137';
const RF = 'RF-24 v2.0';
const CU = 'CU05 — Gestionar Dispositivos IoT, Flujo F (VISION)';
const CASOS = ['TC-M09-275', 'TC-M09-276', 'TC-M09-277'];
const POST_VISION_BUDGET = 3;
const POST_SETUP_BUDGET = 1;

// Baseline de esta reejecución: el RUN válido que quedó RECHAZADO por el 409 de TC-276.
const BASELINE = {
  runId: 'run-20261010-105849',
  fuente: `tests/Test_Testing/Test_Modulo9/RF-24/${GRUPO}/RESULTADOS/run-20261010-105849/${GRUPO}_reevaluacion_V2.md`,
  motivo_de_la_reejecucion: ('Desarrollo informó la corrección del defecto de reemplazo de línea ' +
    'base VISION y solicitó reevaluación en TEST.'),
  '275': { resultado: 'APROBADO', http: '201', id: 4, linea: 'publicada y vigente (id 4)' },
  '276': { resultado: 'RECHAZADO', http: '409', error_code: 'RECURSO_DUPLICADO',
    campo: 'linea_base_vision_id_infraestructura_id_especie',
    crea_calibracion: 'NO', reemplaza_linea: 'NO', admin_ve_linea_previa: 'SÍ (200, id 4)' },
  '277': { resultado: 'APROBADO', http: '403', mensaje: 'literal exacto', efecto: 'ninguno' },
  grupo: 'RECHAZADO',
  primera_evaluacion: { runId: 'run-20261007-100743', grupo: 'RECHAZADO',
    causa: 'TEST no publicaba ninguna operación RF-24 VISION' }
};

const MSG_403 = 'Acceso denegado: La calibración de sensores es una función crítica restringida ' +
  'exclusivamente al Ingeniero de Campo o al Administrador.';

const POBLACIONALES = ['MODELO_AVES', 'MODELO_PORCINOS', 'MODELO_ACUICULTURA'];

const ITEMS_PRECHECK = [
  'Login Ingeniero', 'Login Administrador', 'Login Productor', 'Contrato OpenAPI VISION',
  'Identidad Ingeniero', 'Identidad Administrador', 'Identidad Productor',
  'Permisos Ingeniero', 'Permisos Administrador', 'Permisos Productor',
  'Fixture — finca vista por el Ingeniero', 'Fixture — finca vista por el Administrador',
  'Fixture — área vista por el Ingeniero', 'Fixture — área vista por el Administrador',
  'Fixture — especie del área', 'Fixture — cámaras del área',
  'Estado inicial — línea base del área', 'Estado inicial — historial VISION del área'
];

const MODO = process.env.G137_MODO || 'precheck';
if (!['precheck', 'run', 'close'].includes(MODO)) throw new Error(`G137_MODO no reconocido: ${MODO}`);

const base = () => {
  const b = process.env.QA_BASE_URL;
  if (!b) throw new Error('QA_BASE_URL requerido');
  return b.replace(/\/$/, '');
};
const ING = { email: process.env.QA_ING_EMAIL, secret: process.env.QA_ING_PASSWORD };
const ADM = { email: process.env.QA_ADM_EMAIL, secret: process.env.QA_ADM_PASSWORD };
const PROD = { email: process.env.QA_PROD_EMAIL, secret: process.env.QA_PROD_PASSWORD };
for (const [n, a] of [['ING', ING], ['ADM', ADM], ['PROD', PROD]]) {
  if (!a.email || !a.secret) throw new Error(`QA_${n}_EMAIL y QA_${n}_PASSWORD requeridos (solo en memoria de proceso).`);
}

// Referencia histórica del fixture. Se REVALIDA por API; nada se asume.
const FIXTURE_REF = {
  finca: Number(process.env.G137_FINCA || 163),
  area: Number(process.env.G137_AREA || 279)
};

const log = (...a) => console.log(...a);
const sha256 = (f) => crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');

const runId = process.env.G137_RUN_ID;
if (MODO !== 'precheck' && (!runId || !/^run-\d{8}-\d{6}$/.test(runId))) {
  throw new Error('G137_RUN_ID requerido con formato run-YYYYMMDD-HHMMSS.');
}
if (runId === BASELINE.runId) throw new Error(`El RUN_ID ${BASELINE.runId} es el baseline: no se reutiliza ni se sobrescribe.`);
const CAMERA_SERIAL = runId ? `QA-M09-G137-CAM-${runId.replace('run-', '')}` : null;

// --------------------------------------------------------------------- sanitización
const secretos = () => [ING.secret, ADM.secret, PROD.secret, process.env.QA_DB_PASSWORD, CAMERA_SERIAL].filter(Boolean);
function limpiar(texto) {
  let s = String(texto);
  for (const x of secretos()) s = s.split(x).join('[REDACTED]');
  return s
    .replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[JWT REDACTED]')
    .replace(/Bearer\s+[A-Za-z0-9_.-]{12,}/g, 'Bearer [REDACTED]')
    // Los seriales de cámara de los fixtures de QA son access_key por contrato: se redactan por
    // PATRÓN, no solo los de este RUN, porque el inventario devuelve también los de corridas
    // hermanas y esos tampoco deben quedar persistidos.
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
    [/QA-M09-G1\d{2}-(?:CAM|A\d)-\d{8}-\d{6}/, 'serial completo de una cámara de fixture']
  ];
  const SOLO_VALORES = TODOS.filter(([, n]) =>
    n === 'JWT' || n === 'Authorization con token' || n === 'cadena de conexión' ||
    n === 'serial completo de una cámara de fixture');
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
    alcance: 'todo EvaluacionV2/: runner, coleccion, informes, evidencias, manifiestos y los HTML de Newman',
    limpio: sucios.length === 0, archivosConHallazgos: sucios, revisados,
    credencialesCubiertas: ('contrasenas de API de los tres actores, el access_key (serial) de la camara ' +
      'de setup y, si se entrega por variable de entorno, la de BD. Ninguna aparece como literal en el codigo.'),
    criterio: ('Se marcan solo VALORES de secreto. En los .cjs solo se evaluan valores, el patron del ' +
      'serial completo y la coincidencia literal con las credenciales.'),
    nota: ('Las contrasenas y el access_key solo existieron en memoria de proceso. El reporter htmlextra ' +
      'se ejecuto con omitHeaders, sin environment ni globals y omitiendo las variables sensibles; el HTML ' +
      'se sanitizo despues de generarse. Los seriales se redactan por patron, incluidos los de RUN hermanos.')
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

// ------------------------------- verificación del fix informado por Desarrollo (SOLO SELECT)
// El defecto anterior venía de que `publicar()` busca la fila vigente con SELECT ... FOR UPDATE y
// solo inserta si no la encuentra; sin política RLS de UPDATE, el segundo actor no podía bloquear
// la fila y la operación degeneraba en un INSERT que chocaba con el índice único.
async function verificarFix() {
  const salida = {
    informado_por_desarrollo: true,
    objeto: 'modulo9.lineas_base_vision',
    politica_update_presente: 'NO VERIFICABLE',
    grant_update_sgpmp_app: 'NO VERIFICABLE',
    solo_select: true, dml_ejecutado: 0, consultas: [],
    nota: ('La prueba funcional sigue siendo el oráculo definitivo: la existencia de la política no ' +
      'sustituye los POST. Esta verificación es diagnóstica.')
  };
  if (!process.env.QA_DB_PASSWORD) {
    salida.resumen = 'no se entregó QA_DB_PASSWORD: no se abrió ninguna conexión';
    return salida;
  }
  const programa = [
    'import json, os, psycopg2, psycopg2.extras',
    'C = [',
    '  ("politicas_rls_lineas_base_vision", """SELECT policyname, cmd, qual, with_check',
    "       FROM pg_policies WHERE schemaname = 'modulo9' AND tablename = 'lineas_base_vision'",
    '       ORDER BY policyname"""),',
    '  ("grants_sgpmp_app", """SELECT grantee, privilege_type',
    '       FROM information_schema.role_table_grants',
    "       WHERE table_schema = 'modulo9' AND table_name = 'lineas_base_vision'",
    "         AND grantee = 'sgpmp_app' ORDER BY privilege_type\"\"\"),",
    '  ("rls_de_la_tabla", """SELECT c.relrowsecurity AS rls_activa, c.relforcerowsecurity AS rls_forzada,',
    '         pg_get_userbyid(c.relowner) AS owner',
    '       FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace',
    "       WHERE n.nspname = 'modulo9' AND c.relname = 'lineas_base_vision'\"\"\"),",
    '  ("indices_unicos", """SELECT i.relname AS indice, pg_get_indexdef(idx.indexrelid) AS definicion',
    '       FROM pg_index idx JOIN pg_class i ON i.oid = idx.indexrelid',
    '       JOIN pg_class t ON t.oid = idx.indrelid JOIN pg_namespace n ON n.oid = t.relnamespace',
    "       WHERE n.nspname = 'modulo9' AND t.relname = 'lineas_base_vision' AND idx.indisunique",
    '       ORDER BY i.relname"""),',
    ']',
    'salida = []',
    'try:',
    '    conn = psycopg2.connect(host=os.environ["QA_DB_HOST"], port=os.environ["QA_DB_PORT"],',
    '                            dbname=os.environ["QA_DB_NAME"], user=os.environ["QA_DB_USER"],',
    '                            password=os.environ["QA_DB_PASSWORD"], connect_timeout=25)',
    '    conn.autocommit = True',
    '    conn.set_session(readonly=True)',
    '    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)',
    '    for nombre, sql in C:',
    '        try:',
    '            cur.execute(sql)',
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
    const stdout = execFileSync('python', ['-I', '-c', programa], { encoding: 'utf8', timeout: 120000 });
    salida.consultas = JSON.parse(stdout.trim().split('\n').pop());
  } catch (e) {
    salida.consultas.push({ nombre: 'conexion', error: limpiar(String(e.message).split('\n')[0]) });
  }
  const pol = (salida.consultas.find(c => c.nombre === 'politicas_rls_lineas_base_vision') || {}).filas;
  if (Array.isArray(pol)) {
    const update = pol.filter(p => ['UPDATE', 'ALL'].includes(String(p.cmd).toUpperCase()));
    salida.politicas = pol.map(p => ({ policyname: p.policyname, cmd: p.cmd }));
    salida.politica_update_presente = update.length ? 'SÍ' : 'NO';
    salida.politicas_update = update.map(p => ({ policyname: p.policyname, cmd: p.cmd, qual: p.qual, with_check: p.with_check }));
  }
  const gr = (salida.consultas.find(c => c.nombre === 'grants_sgpmp_app') || {}).filas;
  if (Array.isArray(gr)) {
    salida.grant_update_sgpmp_app = gr.some(g => String(g.privilege_type).toUpperCase() === 'UPDATE')
      ? 'SÍ' : (gr.length ? 'NO' : 'NO VISIBLE PARA member_qa');
    salida.grants_observados = gr;
  }
  const rls = (salida.consultas.find(c => c.nombre === 'rls_de_la_tabla') || {}).filas;
  if (Array.isArray(rls) && rls[0]) salida.rls_de_la_tabla = rls[0];
  const idx = (salida.consultas.find(c => c.nombre === 'indices_unicos') || {}).filas;
  if (Array.isArray(idx)) salida.indices_unicos = idx;
  salida.resumen = `política UPDATE: ${salida.politica_update_presente} | GRANT UPDATE sgpmp_app: ${salida.grant_update_sgpmp_app}`;
  return salida;
}

// ------------------------- revalidación del fixture histórico (nada se asume, todo por API)
async function descubrir() {
  const tIng = await login(ING.email, ING.secret);
  const tAdm = await login(ADM.email, ADM.secret);
  const finca = FIXTURE_REF.finca, area = FIXTURE_REF.area;

  const fIng = await get(`/configuracion/fincas/${finca}`, tIng);
  const fAdm = await get(`/configuracion/fincas/${finca}`, tAdm);
  const aIng = await get(`/configuracion/infraestructuras/${area}`, tIng);
  const aAdm = await get(`/configuracion/infraestructuras/${area}`, tAdm);
  const especieId = aIng.cuerpo?.especie_id ?? null;
  const especies = (await get('/configuracion/especies?solo_activas=true', tIng)).cuerpo?.items || [];
  const especie = especies.find(x => Number(x.id_especie) === Number(especieId)) || null;
  const dispositivos = (await get('/configuracion/dispositivos-iot', tIng)).cuerpo?.items || [];
  const camaras = dispositivos.filter(x => String(x.categoria) === 'CAMARA' && Number(x.id_infraestructura) === Number(area));
  const lb = await get(`/configuracion/calibraciones-vision/linea-base?area_id=${area}`, tIng);
  const lbAdm = await get(`/configuracion/calibraciones-vision/linea-base?area_id=${area}`, tAdm);
  const hist = await get(`/configuracion/calibraciones-vision?area_id=${area}`, tIng);

  const valido = {
    finca_visible_ingeniero: fIng.status === 200,
    finca_visible_administrador: fAdm.status === 200,
    area_visible_ingeniero: aIng.status === 200,
    area_visible_administrador: aAdm.status === 200,
    area_activa: aIng.cuerpo?.es_activo === true,
    especie_presente_y_activa: Boolean(especie) && especie.es_activo === true,
    modelo_poblacional: POBLACIONALES.includes(String(aIng.cuerpo?.tipo_modelo_asignado))
  };
  return {
    referencia_historica: { finca, area, nota: 'IDs de referencia; revalidados por API, no asumidos' },
    finca: { id: finca, nombre: fIng.cuerpo?.nombre ?? null, http_ingeniero: fIng.status, http_administrador: fAdm.status, activa: fIng.cuerpo?.es_activo ?? null },
    area: { id: area, nombre: aIng.cuerpo?.nombre_infraestructura ?? null, http_ingeniero: aIng.status, http_administrador: aAdm.status,
      activa: aIng.cuerpo?.es_activo ?? null, especie_id: especieId, modelo: aIng.cuerpo?.tipo_modelo_asignado ?? null, finca: aIng.cuerpo?.id_finca ?? null },
    especie: especie ? { id_especie: especie.id_especie, nombre: especie.nombre, tipo_modelo: especie.tipo_modelo, activa: especie.es_activo } : null,
    camaras_del_area: camaras.map(c => ({ id: c.id_dispositivo_iot, activa: c.es_activo, fps: c.fps })),
    camaras_activas: camaras.filter(c => c.es_activo === true).map(c => c.id_dispositivo_iot),
    linea_base_previa: { http_ingeniero: lb.status, http_administrador: lbAdm.status,
      id: lb.status === 200 ? lb.cuerpo.id_calibracion_vision : null,
      visible_a_ambos: lb.status === 200 && lbAdm.status === 200 && lb.cuerpo?.id_calibracion_vision === lbAdm.cuerpo?.id_calibracion_vision },
    historial_previo: { http: hist.status, total: hist.cuerpo?.total ?? null, ids: (hist.cuerpo?.items || []).map(x => x.id_calibracion_vision) },
    setup_camara_necesario: camaras.filter(c => c.es_activo === true).length === 0,
    motivo_setup_camara: ('la cámara del RUN anterior quedó desactivada por su propia restauración y la ' +
      'API no publica reactivación de dispositivos, así que registrar una activa es indispensable'),
    reutilizacion: ('se REUTILIZAN finca, área, especie y la línea base previa del mismo par. No se cambia ' +
      'de área ni de especie, no se borra ninguna línea base y no se evita que exista una línea previa.'),
    validaciones: valido,
    valido: Object.values(valido).every(Boolean),
    elegida: Object.values(valido).every(Boolean)
      ? { finca_id: finca, area_id: area, especie_id: Number(especieId), especie_nombre: especie?.nombre ?? null }
      : null
  };
}

// ------------------------------------------------------------------- env de la colección
function construirEnv(fixture) {
  const ahora = Date.now();
  const paso = 30000;
  const n = Number(process.env.G137_OBS || 40);
  const ultima = ahora - 120000;
  const primera = ultima - (n - 1) * paso;
  const timestamps = Array.from({ length: n }, (_, i) => new Date(primera + i * paso).toISOString());
  const inicio = new Date(primera - 120000).toISOString();
  const fin = new Date(ultima + 60000).toISOString();
  if (new Date(fin).getTime() > ahora) throw new Error('ABORTADO: la ventana no puede terminar en el futuro.');
  for (const t of timestamps) {
    if (new Date(t).getTime() >= ahora) throw new Error('ABORTADO: ninguna observación puede ser futura.');
    if (new Date(t) < new Date(inicio) || new Date(t) > new Date(fin)) {
      throw new Error('ABORTADO: toda observación debe caer dentro de la ventana de calibración.');
    }
  }
  const bodyCamara = JSON.stringify({
    serial: CAMERA_SERIAL,
    descripcion: `QA ${GRUPO} camara VISION de la reejecucion post-fix ${runId}`,
    id_infraestructura: null,   // lo fija la colección con el área revalidada
    id_tipo_dispositivo: Number(process.env.G137_TIPO_CAMARA || 5),   // CAMARA_VISION
    es_activo: true,
    resolucion: '1920x1080',
    fps: Number(process.env.G137_FPS || 30),
    area_cobertura_m2: 50
  });
  return {
    env: [
      ['base_url', base()],
      ['ing_email', ING.email], ['ing_secret', ING.secret],
      ['adm_email', ADM.email], ['adm_secret', ADM.secret],
      ['prod_email', PROD.email], ['prod_secret', PROD.secret],
      ['finca_id', String(fixture.finca_id)], ['area_id', String(fixture.area_id)],
      ['msg_403', MSG_403],
      ['camera_serial', CAMERA_SERIAL || ''], ['camera_fps', String(process.env.G137_FPS || 30)],
      ['window_inicio', inicio], ['window_fin', fin],
      ['obs_timestamps', JSON.stringify(timestamps)], ['obs_enviadas', String(n)],
      ['auditoria_desde', new Date(ahora - 600000).toISOString()],
      ['body_camara', bodyCamara]
    ],
    ventana: { inicio, fin, observaciones: n, paso_segundos: paso / 1000, primera: timestamps[0], ultima: timestamps[n - 1],
      criterio: 'timestamps deterministas, sin random, todos en el pasado y dentro de la ventana' },
    timestamps
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
    if (!permitirEscrituras) {
      if (metodo !== 'GET' && !/\/sesiones\/?$/.test(url)) {
        throw new Error(`ABORTADO: el PRECHECK solo admite GET y el login de las sesiones: ${metodo} ${url} (${it.name}).`);
      }
      continue;
    }
    if (['DELETE', 'PUT'].includes(metodo)) throw new Error(`ABORTADO: escritura no autorizada ${metodo} ${url} (${it.name}).`);
    // Esta reejecución NO admite crear finca, área ni especie: el fixture se reutiliza.
    if (metodo === 'POST' && /\/configuracion\/(fincas|infraestructuras|especies)$/.test(url)) {
      throw new Error(`ABORTADO: la reejecución prohíbe crear finca, área o especie (${it.name}).`);
    }
    const permitido =
      (metodo === 'POST' && (/\/sesiones\/?$/.test(url) || /\/calibraciones-vision$/.test(url) ||
        /\/telemetria\/vision$/.test(url) || /\/dispositivos-iot$/.test(url))) ||
      (metodo === 'PATCH' && /\/dispositivos-iot\/[^/]+\/desactivar$/.test(url)) ||
      metodo === 'GET';
    if (!permitido) throw new Error(`ABORTADO: escritura fuera del setup autorizado: ${metodo} ${url} (${it.name}).`);
  }
}

function correrNewman(col, env, html, titulo) {
  const o = { collection: col, reporters: html ? ['cli', 'htmlextra'] : ['cli'], envVar: env.map(([key, value]) => ({ key, value })) };
  if (html) {
    o.reporter = { htmlextra: {
      export: html, omitHeaders: true, showEnvironmentData: false, showGlobalData: false,
      skipEnvironmentVars: ['ing_secret', 'adm_secret', 'prod_secret', 'engineer_session',
        'admin_session', 'productor_session', 'camera_serial', 'body_camara', 'body_camara_sent',
        'body_observaciones'],
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
  log('Reejecución POST-FIX: no se registra nada y no se envía ningún POST funcional.\n');

  const fix = await verificarFix();
  log('--- verificación del fix informado por Desarrollo (SOLO SELECT) ---');
  log(`objeto: ${fix.objeto}`);
  log(`POLITICA_UPDATE_PRESENTE: ${fix.politica_update_presente}`);
  (fix.politicas_update || []).forEach(p => log(`  -> ${p.policyname} (cmd ${p.cmd})`));
  log(`GRANT_UPDATE_SGPMP_APP: ${fix.grant_update_sgpmp_app}`);
  if (fix.rls_de_la_tabla) log(`RLS de la tabla: activa=${fix.rls_de_la_tabla.rls_activa} forzada=${fix.rls_de_la_tabla.rls_forzada} owner=${fix.rls_de_la_tabla.owner}`);
  (fix.indices_unicos || []).forEach(i => log(`  índice único: ${i.indice}`));
  log(`políticas observadas: ${JSON.stringify(fix.politicas || [])}`);
  if (fix.politica_update_presente === 'NO') {
    log('\nPOSIBLE DESFASE DE DESPLIEGUE: Desarrollo informa la corrección pero TEST no publica la política UPDATE.');
    log('No se consumen los POST funcionales. TEST sigue siendo decisorio.');
    process.exitCode = 2;
    return;
  }

  const descubrimiento = await descubrir();
  log('\n--- revalidación del fixture histórico (nada se asume) ---');
  log(`referencia: finca ${descubrimiento.referencia_historica.finca} / área ${descubrimiento.referencia_historica.area}`);
  log(`finca: ${JSON.stringify(descubrimiento.finca)}`);
  log(`área: ${JSON.stringify(descubrimiento.area)}`);
  log(`especie: ${JSON.stringify(descubrimiento.especie)}`);
  log(`cámaras del área: ${JSON.stringify(descubrimiento.camaras_del_area)} | activas: ${JSON.stringify(descubrimiento.camaras_activas)}`);
  log(`línea base previa: ${JSON.stringify(descubrimiento.linea_base_previa)}`);
  log(`historial previo: total ${descubrimiento.historial_previo.total} ids ${JSON.stringify(descubrimiento.historial_previo.ids)}`);
  log(`validaciones: ${JSON.stringify(descubrimiento.validaciones)}`);
  log(`setup de cámara necesario: ${descubrimiento.setup_camara_necesario ? 'SÍ — ' + descubrimiento.motivo_setup_camara : 'NO'}`);
  if (!descubrimiento.valido) {
    log('\nBLOQUEADO: el fixture histórico ya no cumple las precondiciones revalidadas por API.');
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
    administrador: pasa('Identidad Administrador') && pasa('Permisos Administrador'),
    productor: pasa('Identidad Productor') && pasa('Permisos Productor'),
    finca: pasa('Fixture — finca vista por el Ingeniero') && pasa('Fixture — finca vista por el Administrador'),
    area: pasa('Fixture — área vista por el Ingeniero') && pasa('Fixture — área vista por el Administrador'),
    especie: pasa('Fixture — especie del área'),
    estadoInicial: pasa('Estado inicial — línea base del área') && pasa('Estado inicial — historial VISION del área')
  };
  const postFuncionales = contar(summary, /\/calibraciones-vision$/, 'POST');
  const postTelemetria = contar(summary, /\/telemetria\/vision$/, 'POST');
  const autorizar = Object.values(chequeos).every(Boolean) && f.length === 0 &&
    (st.requests.fallidos || 0) === 0 && postFuncionales === 0 && postTelemetria === 0;

  const P = (b) => (b ? 'PASS' : 'FAIL');
  log('\nPRECHECK_G137_POST_FIX\n');
  log(`POST calibraciones-vision:\n${envDe(summary, 'oa_post_vision')}\n`);
  log(`GET historial:\n${envDe(summary, 'oa_get_vision')}\n`);
  log(`GET línea-base:\n${envDe(summary, 'oa_get_linea_base')}\n`);
  log(`Política UPDATE del fix:\n${fix.politica_update_presente}\n`);
  log(`GRANT UPDATE sgpmp_app:\n${fix.grant_update_sgpmp_app}\n`);
  log(`Ingeniero:\n${P(chequeos.ingeniero)}\n`);
  log(`Administrador:\n${P(chequeos.administrador)}\n`);
  log(`Productor:\n${P(chequeos.productor)}\n`);
  log(`Fixture finca:\n${P(chequeos.finca)}\n`);
  log(`Fixture área:\n${P(chequeos.area)}\n`);
  log(`Fixture especie:\n${P(chequeos.especie)}\n`);
  log(`Failures automatización:\n${f.length}\n`);
  log(`POST funcionales:\n${postFuncionales}\n`);
  log(`AUTORIZAR_RUN:\n${autorizar ? 'SÍ' : 'NO'}\n`);

  log('--- detalle observado (solo consola) ---');
  const me = cuerpo('Identidad Ingeniero'); const ma = cuerpo('Identidad Administrador'); const mp = cuerpo('Identidad Productor');
  log(`Ingeniero id ${me?.id_usuario} rol "${me?.nombre_rol}" ${me?.estado_cuenta} | permisos ${envDe(summary, 'perm_ing')}`);
  log(`Administrador id ${ma?.id_usuario} rol "${ma?.nombre_rol}" ${ma?.estado_cuenta} | permisos ${envDe(summary, 'perm_adm')}`);
  log(`Productor id ${mp?.id_usuario} rol "${mp?.nombre_rol}" ${mp?.estado_cuenta} | permisos ${envDe(summary, 'perm_prod')}`);
  log(`fixture: finca ${fixture.finca_id} «${envDe(summary, 'finca_nombre')}» · área ${fixture.area_id} «${envDe(summary, 'area_nombre')}» · especie ${fixture.especie_id} «${envDe(summary, 'especie_nombre')}» modelo ${envDe(summary, 'area_modelo')}`);
  log(`cámaras del área: ${envDe(summary, 'cams_previas')} (activas ${envDe(summary, 'cams_previas_activas')})`);
  log(`línea base inicial: HTTP ${envDe(summary, 'lb_inicial_http')} id ${envDe(summary, 'lb_inicial_id') || '—'}`);
  log(`historial inicial: total ${envDe(summary, 'hist_inicial_total')} ids ${envDe(summary, 'hist_inicial_ids')}`);
  log(`ventana planificada: ${ventana.inicio} → ${ventana.fin} (${ventana.observaciones} observaciones cada ${ventana.paso_segundos}s)`);
  log(`newman: requests ${st.requests.ejecutados}/${st.requests.fallidos} fallidos | assertions ${st.assertions.total}/${st.assertions.fallidas} fallidas`);
  if (f.length) { log('\nfailures:'); f.forEach((x, i) => log(`  ${i + 1}. ${x.item} :: ${x.assertion} :: ${x.error}`)); }
  log('');
  if (!autorizar) { log('El RUN funcional NO está autorizado.'); process.exitCode = 2; }
  else log(`Ejecute el RUN: reutiliza finca ${fixture.finca_id} y área ${fixture.area_id}; solo registra una cámara activa y un lote de observaciones.`);
}

// ------------------------------------------------------------------------------------ run
async function modoRun() {
  if (fs.existsSync(RUN_DIR)) throw new Error(`La carpeta ${runId} ya existe. Un RUN oficial no se repite ni se sobrescribe.`);
  const fix = await verificarFix();
  const descubrimiento = await descubrir();
  if (!descubrimiento.valido) throw new Error('BLOQUEADO: el fixture histórico ya no cumple las precondiciones revalidadas por API.');
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
  const { env, ventana, timestamps } = construirEnv(fixture);

  log(`RUN funcional oficial POST-FIX. RUN_ID: ${runId}`);
  log(`Baseline del defecto: ${BASELINE.runId} (TC-276 → 409 RECURSO_DUPLICADO), conservado intacto.`);
  log(`Fix en TEST: política UPDATE ${fix.politica_update_presente} | GRANT UPDATE sgpmp_app ${fix.grant_update_sgpmp_app}`);
  log(`Fixture REUTILIZADO: finca ${fixture.finca_id} · área ${fixture.area_id} · especie ${fixture.especie_id}`);
  log(`  línea base previa: ${descubrimiento.linea_base_previa.id ?? 'ninguna'} | historial previo: ${JSON.stringify(descubrimiento.historial_previo.ids)}`);
  log(`POST planificados: ${POST_SETUP_BUDGET} de telemetría + ${POST_VISION_BUDGET} de calibración | reintentos: 0\n`);

  const summary = await correrNewman(col, env, html, `${GRUPO} — REEJECUCIÓN POST-FIX · RUN oficial ${runId}`);
  if (fs.existsSync(html)) fs.writeFileSync(html, limpiarHtml(fs.readFileSync(html, 'utf8')));

  const { cuerpo, http, enviadoTexto, asserts, ejecutado } = extraer(summary);
  const bloque = (nombre) => ({ ejecutado: ejecutado(nombre), http: http(nombre), cuerpo: cuerpo(nombre), assertions: asserts(nombre) });

  const preservado = {
    runId, generado: new Date().toISOString(), gitPre, itemsTotales, itemsEjecutables,
    stats: stats(summary), failures: fallos(summary),
    fix, descubrimiento, fixtureElegido: fixture, ventana, timestamps,
    presupuesto: {
      postCalibracionVision: contar(summary, /\/calibraciones-vision$/, 'POST'),
      postTelemetriaVision: contar(summary, /\/telemetria\/vision$/, 'POST'),
      postDispositivos: contar(summary, /\/dispositivos-iot$/, 'POST'),
      postFincas: contar(summary, /\/configuracion\/fincas$/, 'POST'),
      postInfraestructuras: contar(summary, /\/configuracion\/infraestructuras$/, 'POST'),
      postEspecies: contar(summary, /\/configuracion\/especies$/, 'POST'),
      patchDesactivar: contar(summary, /\/desactivar$/, 'PATCH'),
      put: 0, delete: 0, reintentos: 0
    },
    contrato: {
      post_vision: envDe(summary, 'oa_post_vision'), get_vision: envDe(summary, 'oa_get_vision'),
      get_linea_base: envDe(summary, 'oa_get_linea_base'), post_m03: envDe(summary, 'oa_post_m03'),
      dto_vision: J(envDe(summary, 'oa_dto_vision')), codigos_post: J(envDe(summary, 'oa_codigos_post')),
      item: bloque('Contrato OpenAPI VISION')
    },
    actores: {
      ingeniero: { login: bloque('Login Ingeniero').http, identidad: bloque('Identidad Ingeniero'), permisos_recurso12: J(envDe(summary, 'perm_ing')), id: envDe(summary, 'ing_id') },
      administrador: { login: bloque('Login Administrador').http, identidad: bloque('Identidad Administrador'), permisos_recurso12: J(envDe(summary, 'perm_adm')), id: envDe(summary, 'adm_id') },
      productor: { login: bloque('Login Productor').http, identidad: bloque('Identidad Productor'), permisos_recurso12: J(envDe(summary, 'perm_prod')), id: envDe(summary, 'prod_id'), estado: envDe(summary, 'prod_id_estado') }
    },
    fixture: {
      finca: { id: envDe(summary, 'finca_id'), nombre: envDe(summary, 'finca_nombre'), visible_ingeniero: envDe(summary, 'finca_visible_ingeniero'), visible_admin: envDe(summary, 'finca_visible_admin'),
        item_ing: bloque('Fixture — finca vista por el Ingeniero'), item_adm: bloque('Fixture — finca vista por el Administrador') },
      area: { id: envDe(summary, 'area_id'), nombre: envDe(summary, 'area_nombre'), modelo: envDe(summary, 'area_modelo'), activa: envDe(summary, 'area_activa'), visible_admin: envDe(summary, 'area_visible_admin'),
        item_ing: bloque('Fixture — área vista por el Ingeniero'), item_adm: bloque('Fixture — área vista por el Administrador') },
      especie: { id: envDe(summary, 'especie_id'), nombre: envDe(summary, 'especie_nombre'), modelo: envDe(summary, 'especie_modelo'), grupo: envDe(summary, 'grupo_manejo'), item: bloque('Fixture — especie del área') },
      camaras_previas: J(envDe(summary, 'cams_previas')), camaras_previas_activas: envDe(summary, 'cams_previas_activas'),
      compuerta: envDe(summary, 'compuerta_fixture')
    },
    estadoInicial: {
      linea_base_http: envDe(summary, 'lb_inicial_http'), linea_base: J(envDe(summary, 'lb_inicial')),
      linea_base_id: envDe(summary, 'lb_inicial_id'),
      historial_total: envDe(summary, 'hist_inicial_total'), historial_ids: J(envDe(summary, 'hist_inicial_ids'))
    },
    setup: {
      camara: { ...bloque('SETUP — registrar cámara VISION activa en el área'),
        verificacion: bloque('SETUP — cámara activa y asociada verificada'),
        camera_id: envDe(summary, 'camera_id'), fps_nominal: envDe(summary, 'camera_fps_nominal'),
        serial_redactado: envDe(summary, 'camera_serial_red'), activas_del_area: J(envDe(summary, 'cams_activas_run')) },
      observaciones: { ...bloque('SETUP — ingesta M03 de observaciones de visión'),
        enviadas: envDe(summary, 'obs_enviadas'), total: envDe(summary, 'obs_total'),
        aceptadas: envDe(summary, 'obs_aceptadas'), duplicadas: envDe(summary, 'obs_duplicadas'),
        aptas: envDe(summary, 'obs_aptas'), indices: J(envDe(summary, 'obs_indices')),
        clasificaciones: J(envDe(summary, 'obs_clasificaciones')), muestra: J(envDe(summary, 'obs_muestra')),
        componentes: J(envDe(summary, 'obs_vector_componentes')) }
    },
    casos: {
      '275': {
        pre_linea_base: { ...bloque('PRE TC-M09-275 — línea base vigente'), http: envDe(summary, 'lb_pre_275_http'), cuerpo: J(envDe(summary, 'lb_pre_275')), id: envDe(summary, 'lb_pre_275_id') },
        pre_historial: { ...bloque('PRE TC-M09-275 — historial VISION'), total: envDe(summary, 'hist_pre_275_total'), ids: J(envDe(summary, 'hist_pre_275_ids')) },
        post: { ...bloque('TC-M09-275 POST calibrar VISION'), enviado: enviadoTexto('TC-M09-275 POST calibrar VISION'),
          id: envDe(summary, 'c275_id'), estado: envDe(summary, 'c275_estado'), origen: envDe(summary, 'c275_origen'),
          usuario: envDe(summary, 'c275_usuario'), error_code: envDe(summary, 'c275_error_code'),
          linea_base: J(envDe(summary, 'c275_linea_base')), n_obs: envDe(summary, 'c275_n_obs'),
          n_validas: envDe(summary, 'c275_n_validas'), iteraciones: envDe(summary, 'c275_iteraciones') },
        linea_base_vigente: { ...bloque('TC-M09-275 — línea base vigente'), id: envDe(summary, 'lb_post_275_id'), cuerpo: J(envDe(summary, 'lb_post_275')) },
        historial_post: { ...bloque('TC-M09-275 — historial VISION POST'), total: envDe(summary, 'hist_post_275_total'), ids: J(envDe(summary, 'hist_post_275_ids')), nuevos: J(envDe(summary, 'hist_post_275_nuevos')), item: J(envDe(summary, 'hist_post_275_item')) },
        auditoria: { ...bloque('TC-M09-275 — auditoría RF-10'), correlacionados: J(envDe(summary, 'auditoria_275_correlacionados'), []), candidatos: J(envDe(summary, 'auditoria_275_candidatos'), []) }
      },
      '276': {
        pre_linea_base: { ...bloque('PRE TC-M09-276 — línea base vigente'), http: envDe(summary, 'lb_pre_276_http'), cuerpo: J(envDe(summary, 'lb_pre_276')), id: envDe(summary, 'lb_pre_276_id') },
        pre_linea_base_admin: { ...bloque('PRE TC-M09-276 — el Administrador ve la línea base de TC-M09-275'), http: envDe(summary, 'lb_pre_276_admin_http'), id: envDe(summary, 'lb_pre_276_admin_id') },
        pre_historial: { ...bloque('PRE TC-M09-276 — historial VISION'), total: envDe(summary, 'hist_pre_276_total'), ids: J(envDe(summary, 'hist_pre_276_ids')) },
        post: { ...bloque('TC-M09-276 POST calibrar VISION'), enviado: enviadoTexto('TC-M09-276 POST calibrar VISION'),
          id: envDe(summary, 'c276_id'), estado: envDe(summary, 'c276_estado'), origen: envDe(summary, 'c276_origen'),
          usuario: envDe(summary, 'c276_usuario'), error_code: envDe(summary, 'c276_error_code'),
          linea_base: J(envDe(summary, 'c276_linea_base')), n_obs: envDe(summary, 'c276_n_obs'),
          n_validas: envDe(summary, 'c276_n_validas'), iteraciones: envDe(summary, 'c276_iteraciones') },
        historial_post: { ...bloque('TC-M09-276 — historial VISION POST'), total: envDe(summary, 'hist_post_276_total'), ids: J(envDe(summary, 'hist_post_276_ids')), nuevos: J(envDe(summary, 'hist_post_276_nuevos')), item: J(envDe(summary, 'hist_post_276_item')) },
        reemplazo: { ...bloque('TC-M09-276 — la línea vigente fue REEMPLAZADA'), id: envDe(summary, 'lb_post_276_id'), cuerpo: J(envDe(summary, 'lb_post_276')), ok: envDe(summary, 'reemplazo_ok') },
        vigente_admin: { ...bloque('TC-M09-276 — la línea vigente vista por el Administrador'), id: envDe(summary, 'lb_post_276_admin_id') },
        auditoria: { ...bloque('TC-M09-276 — auditoría RF-10 (evidencia complementaria)'), correlacionados: J(envDe(summary, 'auditoria_276_correlacionados'), []) }
      },
      '277': {
        pre_linea_base: { ...bloque('PRE TC-M09-277 — línea base vigente'), http: envDe(summary, 'lb_pre_277_http'), cuerpo: J(envDe(summary, 'lb_pre_277')), id: envDe(summary, 'lb_pre_277_id') },
        pre_historial: { ...bloque('PRE TC-M09-277 — historial VISION'), total: envDe(summary, 'hist_pre_277_total'), ids: J(envDe(summary, 'hist_pre_277_ids')) },
        post: { ...bloque('TC-M09-277 POST calibrar VISION'), enviado: enviadoTexto('TC-M09-277 POST calibrar VISION'),
          error_code: envDe(summary, 'c277_error_code'), mensaje: envDe(summary, 'c277_mensaje'),
          mensaje_exacto: envDe(summary, 'c277_mensaje_exacto'), respuesta: J(envDe(summary, 'c277_respuesta')) },
        linea_base_post: { ...bloque('TC-M09-277 — línea base vigente después del 403'), id: envDe(summary, 'lb_post_277_id'), cuerpo: J(envDe(summary, 'lb_post_277')) },
        historial_post: { ...bloque('TC-M09-277 — historial VISION después del 403'), total: envDe(summary, 'hist_post_277_total'), ids: J(envDe(summary, 'hist_post_277_ids')), nuevos: J(envDe(summary, 'hist_post_277_nuevos')), del_productor: J(envDe(summary, 'hist_post_277_del_productor'), []) },
        auditoria: { ...bloque('TC-M09-277 — auditoría RF-10 del rechazo (evidencia complementaria)'), rechazos: J(envDe(summary, 'auditoria_277_rechazos'), []) }
      }
    },
    restauracion: {
      camara: { ...bloque('RESTAURACIÓN — desactivar la cámara de setup'), ejecutada: envDe(summary, 'restauracion_camara'), estado_final: envDe(summary, 'camera_estado_final') },
      estado_final: { ...bloque('RESTAURACIÓN — estado final verificado'), linea_vigente: envDe(summary, 'lb_final_id') }
    }
  };
  fs.writeFileSync(SUMMARY_TMP(), limpiar(JSON.stringify(preservado, null, 2)));

  const st = preservado.stats;
  log('\n================ RUN OFICIAL POST-FIX ================');
  log(`RUN_ID: ${runId}`);
  log(`requests ${st.requests.ejecutados} (fallidos ${st.requests.fallidos}) | assertions ${st.assertions.total} (fallidas ${st.assertions.fallidas})`);
  log(`POST VISION: ${preservado.presupuesto.postCalibracionVision}/${POST_VISION_BUDGET} | telemetría: ${preservado.presupuesto.postTelemetriaVision}`);
  log(`setup: cámara ${preservado.setup.camara.camera_id} | obs ${preservado.setup.observaciones.aceptadas}/${preservado.setup.observaciones.total} aptas ${preservado.setup.observaciones.aptas}`);
  log(`línea base previa al RUN: ${preservado.estadoInicial.linea_base_id || 'ninguna'}`);
  log(`TC-275: HTTP ${preservado.casos['275'].post.http} id ${preservado.casos['275'].post.id} estado ${preservado.casos['275'].post.estado} | vigente ${preservado.casos['275'].linea_base_vigente.id}`);
  log(`TC-276: HTTP ${preservado.casos['276'].post.http} id ${preservado.casos['276'].post.id} estado ${preservado.casos['276'].post.estado} | error_code ${preservado.casos['276'].post.error_code || '—'} | vigente ${preservado.casos['276'].reemplazo.id}`);
  log(`TC-277: HTTP ${preservado.casos['277'].post.http} mensaje exacto ${preservado.casos['277'].post.mensaje_exacto} | vigente ${preservado.casos['277'].linea_base_post.id}`);
  log(`restauración: cámara ${preservado.restauracion.camara.ejecutada} (activa=${preservado.restauracion.camara.estado_final}) | vigente final ${preservado.restauracion.estado_final.linea_vigente}`);
  if (preservado.failures.length) { log('\nFAILURES:'); preservado.failures.forEach((x, i) => log(`  ${i + 1}. ${x.item} :: ${x.assertion} :: ${x.error}`)); }
  log('======================================================\n');
  log(`HTML: ${path.relative(EVAL_DIR, html).split(path.sep).join('/')}`);
  log('Ejecute ahora el modo close para el oráculo y la evidencia.');
  if (preservado.failures.length) process.exitCode = 2;
}

// ---------------------------------------------------------------------------------- close
async function modoClose() {
  const tmp = SUMMARY_TMP();
  const evidenciaPath = path.join(RUN_DIR, 'evidencia.json');
  if (!fs.existsSync(tmp)) {
    if (!fs.existsSync(evidenciaPath)) throw new Error('No hay summary del RUN ni evidencia previa: ejecute primero G137_MODO=run.');
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
  const F = R.fixtureElegido;
  const num = (x) => (x === null || x === undefined || x === '' ? null : Number(x));

  const exitosa = (clave, idActor, extra) => {
    const c = R.casos[clave];
    const resp = c.post.cuerpo || {};
    const id = num(c.post.id);
    const asserts = [...(c.post.assertions || []), ...(c.pre_linea_base?.assertions || []),
      ...(c.pre_historial?.assertions || []), ...(c.historial_post?.assertions || []),
      ...((c.linea_base_vigente || c.reemplazo)?.assertions || [])];
    const nuevos = Array.isArray(c.historial_post?.nuevos) ? c.historial_post.nuevos.map(Number) : null;
    const preIds = (c.pre_historial?.ids || []).map(Number);
    const vigente = num((c.linea_base_vigente || c.reemplazo)?.id);
    const oraculo = {
      http_2xx: c.post.http >= 200 && c.post.http <= 299,
      no_es_409: Number(c.post.http) !== 409,
      sin_recurso_duplicado: String(c.post.error_code || '') !== 'RECURSO_DUPLICADO',
      id_calibracion_vision_devuelto: Number.isInteger(id),
      modo_vision: resp.modo_calibracion === 'VISION',
      area_correcta: num(resp.area_id) === Number(F.area_id),
      especie_correcta: num(resp.especie_id) === Number(F.especie_id),
      origen_manual: resp.origen_disparo === 'MANUAL',
      usuario_correcto: num(c.post.usuario) === num(idActor),
      estado_exitosa: resp.estado === 'EXITOSA',
      linea_base_publicada: Boolean(c.post.linea_base) && Object.keys(c.post.linea_base || {}).length > 0,
      calibracion_en_historial: Array.isArray(c.historial_post?.ids) && c.historial_post.ids.map(Number).includes(id),
      una_sola_calibracion_nueva: Array.isArray(nuevos) && nuevos.length === 1 && nuevos[0] === id,
      historial_conserva_anteriores: preIds.every(p => (c.historial_post?.ids || []).map(Number).includes(p)),
      linea_base_queda_vigente: vigente === id,
      assertions_todas_pass: asserts.length > 0 && asserts.every(a => a.paso)
    };
    Object.assign(oraculo, extra || {});
    return { oraculo, id, resp, vigente, preIds, nuevos, asserts };
  };

  const e275 = exitosa('275', R.actores.ingeniero.id);
  e275.oraculo.auditoria_rf10_exitosa_correlacionada = (R.casos['275'].auditoria.correlacionados || []).length > 0;
  const r275 = Object.values(e275.oraculo).every(x => x === true) ? 'APROBADO' : 'RECHAZADO';

  const e276 = exitosa('276', R.actores.administrador.id, {
    administrador_veia_la_linea_previa: Number(R.casos['276'].pre_linea_base_admin.http) === 200 &&
      num(R.casos['276'].pre_linea_base_admin.id) === e275.id,
    id_distinto_de_275: num(R.casos['276'].post.id) !== null && num(R.casos['276'].post.id) !== e275.id,
    reemplazo_de_la_vigente: num(R.casos['276'].reemplazo.id) === num(R.casos['276'].post.id) &&
      num(R.casos['276'].pre_linea_base.id) === e275.id,
    la_vigente_ya_no_es_275: num(R.casos['276'].reemplazo.id) !== e275.id,
    historial_conserva_275: Array.isArray(R.casos['276'].historial_post?.ids) &&
      R.casos['276'].historial_post.ids.map(Number).includes(e275.id),
    vigente_visible_al_administrador: num(R.casos['276'].vigente_admin.id) === num(R.casos['276'].post.id)
  });
  const r276 = Object.values(e276.oraculo).every(x => x === true) ? 'APROBADO' : 'RECHAZADO';

  const c277 = R.casos['277'];
  const resp277 = c277.post.cuerpo || {};
  const preIds277 = (c277.pre_historial?.ids || []).map(Number);
  const postIds277 = (c277.historial_post?.ids || []).map(Number);
  const asserts277 = [...(c277.post.assertions || []), ...(c277.pre_linea_base?.assertions || []),
    ...(c277.pre_historial?.assertions || []), ...(c277.linea_base_post?.assertions || []),
    ...(c277.historial_post?.assertions || [])];
  const o277 = {
    productor_activo_al_ejecutar: R.actores.productor.estado === 'Activo',
    identidad_confirmada: (R.actores.productor.identidad.cuerpo || {}).nombre_rol === 'Productor' &&
      (R.actores.productor.identidad.cuerpo || {}).correo_electronico === PROD.email,
    request_vision_valido: (() => {
      const b = c277.post.enviado ? JSON.parse(c277.post.enviado) : null;
      return Boolean(b) && b.modo_calibracion === 'VISION' && Number(b.area_id) === Number(F.area_id) &&
        Boolean(b.ventana_observacion?.inicio) && Boolean(b.ventana_observacion?.fin);
    })(),
    http_403: Number(c277.post.http) === 403,
    no_es_401: Number(c277.post.http) !== 401,
    no_es_422: Number(c277.post.http) !== 422,
    mensaje_literal_exacto: (resp277.message ?? resp277.detail ?? null) === MSG_403,
    sin_calibracion_vision: resp277.id_calibracion_vision === undefined || resp277.id_calibracion_vision === null,
    linea_vigente_previa_era_la_de_276: num(c277.pre_linea_base.id) === num(R.casos['276'].post.id),
    linea_vigente_no_cambio: num(c277.linea_base_post.id) === num(c277.pre_linea_base.id),
    linea_vigente_sigue_siendo_la_del_administrador: num(c277.linea_base_post.id) === num(R.casos['276'].post.id),
    historial_total_sin_cambios: num(c277.historial_post.total) === num(c277.pre_historial.total),
    historial_ids_sin_cambios: JSON.stringify(postIds277.slice().sort()) === JSON.stringify(preIds277.slice().sort()),
    sin_calibracion_atribuible_al_productor: Array.isArray(c277.historial_post.del_productor) && c277.historial_post.del_productor.length === 0,
    assertions_todas_pass: asserts277.length > 0 && asserts277.every(a => a.paso)
  };
  const r277 = Object.values(o277).every(x => x === true) ? 'APROBADO' : 'RECHAZADO';

  const setupOk = R.setup.camara.http >= 200 && R.setup.camara.http <= 299 &&
    Number(R.setup.observaciones.http) === 201;
  const sinWorkarounds = {
    misma_area_que_el_baseline: num(R.fixture.area.id) === FIXTURE_REF.area,
    misma_especie_del_area: num(R.fixture.especie.id) === Number(F.especie_id),
    no_creo_finca: R.presupuesto.postFincas === 0,
    no_creo_area: R.presupuesto.postInfraestructuras === 0,
    no_creo_especie: R.presupuesto.postEspecies === 0,
    no_borro_nada: R.presupuesto.delete === 0,
    sin_sql_dml: true,
    existia_linea_previa_al_run: num(R.estadoInicial.linea_base_id) !== null,
    tc276_fue_una_segunda_calibracion: num(R.casos['276'].pre_linea_base.id) === e275.id
  };

  // ------------------------------- verificación final: SOLO LECTURA, después del RUN
  const tokenIng = await login(ING.email, ING.secret);
  const tokenAdm = await login(ADM.email, ADM.secret);
  const hist = await get(`/configuracion/calibraciones-vision?area_id=${F.area_id}`, tokenIng);
  const lb = await get(`/configuracion/calibraciones-vision/linea-base?area_id=${F.area_id}`, tokenIng);
  const lbAdm = await get(`/configuracion/calibraciones-vision/linea-base?area_id=${F.area_id}`, tokenAdm);
  const dispositivos = await get('/configuracion/dispositivos-iot', tokenIng);
  const camaraFinal = (dispositivos.cuerpo?.items || []).find(x => Number(x.id_dispositivo_iot) === num(R.setup.camara.camera_id)) || null;
  const idsFinales = (hist.cuerpo?.items || []).map(x => x.id_calibracion_vision);

  const red = { camara: 'no necesaria' };
  if (camaraFinal && camaraFinal.es_activo === true) {
    const r = await escribirApi('PATCH', `/configuracion/dispositivos-iot/${R.setup.camara.camera_id}/desactivar`, tokenIng, null);
    red.camara = `ejecutada por el cierre: HTTP ${r.status}`;
  }
  const dispositivosFinal = await get('/configuracion/dispositivos-iot', tokenIng);
  const camaraCerrada = (dispositivosFinal.cuerpo?.items || []).find(x => Number(x.id_dispositivo_iot) === num(R.setup.camara.camera_id)) || null;

  const restauracion = {
    criterio: ('Se revierte por desactivación oficial el único recurso creado, la cámara. Las ' +
      'calibraciones y la línea base vigente son resultados válidos del caso y NO se borran; la ' +
      'finca, el área y la especie se conservan, igual que la línea base previa al RUN.'),
    recursos_modificados: [{
      recurso: 'cámara de setup', id: num(R.setup.camara.camera_id),
      estado_original: 'no existía (creada en este RUN)',
      cambio: 'registrada ACTIVA porque el área no tenía ninguna cámara activa y la API no publica reactivación',
      estado_durante: 'ACTIVA',
      restauracion: 'PATCH /configuracion/dispositivos-iot/{id}/desactivar',
      estado_final: camaraCerrada ? camaraCerrada.es_activo : null
    }],
    recursos_preexistentes_modificados: 'ninguno',
    red_de_seguridad: red,
    camara_desactivada_verificado: camaraCerrada ? camaraCerrada.es_activo === false : null,
    pendientes: []
  };
  if (restauracion.camara_desactivada_verificado !== true) restauracion.pendientes.push('la cámara de setup no quedó desactivada');
  restauracion.resultado = restauracion.pendientes.length === 0 ? 'PASS' : 'FAIL';

  const bd = await diagnosticoBD(F, e275.id, num(R.casos['276'].post.id));
  const fixFinal = await verificarFix();

  const newmanLimpio = R.failures.length === 0 && (R.stats.requests.fallidos || 0) === 0;
  const resultadoGrupo = (r275 === 'APROBADO' && r276 === 'APROBADO' && r277 === 'APROBADO' &&
    newmanLimpio && setupOk && restauracion.resultado === 'PASS' &&
    Object.values(sinWorkarounds).every(x => x === true)) ? 'APROBADO' : 'RECHAZADO';
  const correccionValidada = (r276 === 'APROBADO' && Number(R.casos['276'].post.http) !== 409 &&
    String(R.casos['276'].post.error_code || '') !== 'RECURSO_DUPLICADO' &&
    e276.oraculo.reemplazo_de_la_vigente === true && e276.oraculo.historial_conserva_275 === true)
    ? 'VALIDADA' : 'NO VALIDADA';

  const comparacion = {
    baseline: BASELINE,
    tabla: {
      'TC-275': { antes: `${BASELINE['275'].resultado} (HTTP ${BASELINE['275'].http})`, ahora: `${r275} (HTTP ${R.casos['275'].post.http})` },
      'Linea despues de TC-275': { antes: BASELINE['275'].linea, ahora: `publicada y vigente (id ${num(R.casos['275'].linea_base_vigente.id)})` },
      'Admin ve linea previa': { antes: BASELINE['276'].admin_ve_linea_previa, ahora: `${Number(R.casos['276'].pre_linea_base_admin.http) === 200 ? 'SÍ' : 'NO'} (${R.casos['276'].pre_linea_base_admin.http}, id ${num(R.casos['276'].pre_linea_base_admin.id)})` },
      'TC-276 HTTP': { antes: BASELINE['276'].http, ahora: String(R.casos['276'].post.http) },
      'TC-276 error': { antes: BASELINE['276'].error_code, ahora: R.casos['276'].post.error_code || '(ninguno)' },
      'TC-276 crea calibracion': { antes: BASELINE['276'].crea_calibracion, ahora: num(R.casos['276'].post.id) !== null ? `SÍ (id ${num(R.casos['276'].post.id)})` : 'NO' },
      'TC-276 reemplaza linea': { antes: BASELINE['276'].reemplaza_linea, ahora: e276.oraculo.reemplazo_de_la_vigente ? 'SÍ' : 'NO' },
      'TC-277': { antes: `${BASELINE['277'].resultado} (403, ${BASELINE['277'].mensaje})`, ahora: `${r277} (HTTP ${c277.post.http}, mensaje exacto ${c277.post.mensaje_exacto})` },
      'G137': { antes: BASELINE.grupo, ahora: resultadoGrupo }
    },
    causa_del_rechazo_anterior: correccionValidada === 'VALIDADA' ? 'CORREGIDA' : 'NO CORREGIDA'
  };

  const causaRaiz = correccionValidada === 'VALIDADA'
    ? ('A. La correccion informada por Desarrollo esta desplegada y operativa en TEST. La politica RLS ' +
       'de UPDATE sobre modulo9.lineas_base_vision (pol_lineas_base_vision_update) permite ahora que el ' +
       'segundo actor bloquee la fila vigente en el SELECT ... FOR UPDATE de publicar(), de modo que la ' +
       'segunda calibracion del mismo par ACTUALIZA la linea base en lugar de intentar insertar una ' +
       'duplicada contra el indice unico uq_linea_base_vision_id_infraestructura_id_especie. El indice ' +
       'unico sigue existiendo, como debe: lo que cambio es que ya no se alcanza.')
    : (Number(R.casos['276'].post.http) === 409
      ? ('B. CORRECCION NO VALIDADA EN TEST: TC-M09-276 vuelve a responder 409 RECURSO_DUPLICADO. ' +
         `Politica UPDATE observada: ${fixFinal.politica_update_presente}; GRANT UPDATE sgpmp_app: ` +
         `${fixFinal.grant_update_sgpmp_app}. No se reintento el POST ni se altero el fixture para ` +
         'forzar un resultado favorable.')
      : 'C. Por determinar con la evidencia de esta corrida.');

  const evidencia = {
    run_id: runId, evaluacion: 'REEJECUCION OFICIAL POST-FIX',
    motivo_de_la_reejecucion: BASELINE.motivo_de_la_reejecucion,
    grupo: GRUPO, casos: CASOS, requisito: RF, casoDeUso: CU,
    herramientas: 'API - Postman / Newman. BD TEST solo SELECT, para verificar el fix y la persistencia.',
    ambiente: { decisorio: 'TEST', base_url: base(), contraste_dev: 'no utilizado' },
    carpeta: `tests/Test_Testing/Test_Modulo9/RF-24/${GRUPO}/EvaluacionV2/`,
    rama: R.gitPre.rama, commit: R.gitPre.commit,
    resultado_grupo: resultadoGrupo,
    resultado_por_caso: { 'TC-M09-275': r275, 'TC-M09-276': r276, 'TC-M09-277': r277 },
    correccion_del_409: correccionValidada,
    git_pre: R.gitPre,
    verificacion_del_fix: { antes_del_run: R.fix, al_cerrar: fixFinal },
    contrato_vision: R.contrato,
    actores: {
      nota: ('La coleccion Newman es duena de sus tres sesiones; el runner no obtiene tokens ni los ' +
        'inyecta. En el cierre se autentica aparte para la verificacion de solo lectura y la red de ' +
        'seguridad de la restauracion.'),
      ingeniero: { correo: ING.email, credencial: '[REDACTED]', ...R.actores.ingeniero, papel: 'ejecuta TC-M09-275' },
      administrador: { correo: ADM.email, credencial: '[REDACTED]', ...R.actores.administrador, papel: 'ejecuta TC-M09-276 y consulta RF-10' },
      productor: { correo: PROD.email, credencial: '[REDACTED]', ...R.actores.productor, papel: 'ejecuta TC-M09-277 (403 esperado)' }
    },
    fixture: {
      estrategia: 'REUTILIZADO del RUN anterior y ACTUALIZADO solo en la camara y las observaciones',
      revalidacion: R.descubrimiento, detalle: R.fixture,
      sin_workarounds: { ...sinWorkarounds, criterio: ('No se cambio de area ni de especie, no se borro ' +
        'la linea de TC-275 ni ninguna otra, no se uso otra finca, no se elimino nada, no se ejecuto SQL ' +
        'DML y no se evito que existiera una linea previa: TC-276 fue una SEGUNDA calibracion sobre el ' +
        'MISMO par.') },
      setup: { camara: R.setup.camara, observaciones: R.setup.observaciones, setup_ok: setupOk,
        motivo_camara: R.descubrimiento.motivo_setup_camara },
      estado_inicial: R.estadoInicial
    },
    ventana_observacion: R.ventana,
    'TC-M09-275': { actor: 'Ingeniero de Campo', ...R.casos['275'], oraculo: e275.oraculo, resultado: r275 },
    'TC-M09-276': { actor: 'Administrador', ...R.casos['276'], oraculo: e276.oraculo, resultado: r276,
      nota_fix: ('Este es el caso que fallaba con 409 RECURSO_DUPLICADO. El PRE confirma que el ' +
        'Administrador veia la linea base de TC-275 antes de calibrar, que era la condicion en la que ' +
        'el defecto se manifestaba.') },
    'TC-M09-277': { actor: 'Productor', ...R.casos['277'], mensaje_esperado: MSG_403,
      comparacion: 'literal estricta', oraculo: o277, resultado: r277 },
    newman: {
      html: `newman/newman-${GRUPO}.html`, htmlPersistentes: 1,
      coleccionEjecutada: `${R.itemsEjecutables} de ${R.itemsTotales} items`,
      iterations: R.stats.iterations, requests: R.stats.requests, assertions: R.stats.assertions,
      failures: R.failures, presupuesto: R.presupuesto, limpio: newmanLimpio
    },
    verificacion_api_final: {
      soloLectura: true, fecha: new Date().toISOString(),
      historial: { http: hist.status, total: hist.cuerpo?.total ?? null, ids: idsFinales },
      linea_base_vigente: { http: lb.status, cuerpo: lb.cuerpo },
      linea_base_vigente_vista_por_el_administrador: { http: lbAdm.status, id: lbAdm.cuerpo?.id_calibracion_vision ?? null },
      la_vigente_es_la_de_276: num(lb.cuerpo?.id_calibracion_vision) === num(R.casos['276'].post.id),
      ambas_calibraciones_conservadas: idsFinales.map(Number).includes(e275.id) && idsFinales.map(Number).includes(num(R.casos['276'].post.id)),
      linea_previa_al_run_conservada_en_historial: num(R.estadoInicial.linea_base_id) === null ||
        idsFinales.map(Number).includes(num(R.estadoInicial.linea_base_id)),
      no_se_borro_nada: 'ninguna calibracion ni linea base fue eliminada'
    },
    verificacion_bd: bd,
    restauracion,
    comparacion_antes_despues: comparacion,
    causa_raiz: causaRaiz,
    incidencias: correccionValidada === 'VALIDADA'
      ? [{ incidencia_requerida: 'NO NUEVA',
           incidencia_del_409: 'VALIDADA COMO CORREGIDA',
           propuesta: 'CERRAR la incidencia del 409 RECURSO_DUPLICADO de TC-M09-276',
           nota: ('La incidencia historica sobre la ausencia de la operacion VISION en TEST permanece ' +
             'resuelta; no se abre ninguna incidencia nueva.') }]
      : [{ incidencia_requerida: 'SÍ (mantener/reabrir la actual)',
           grupo_responsable: 'Desarrollo', grupo_de_prueba: GRUPO, casos_afectados: ['TC-M09-276'],
           resultado: resultadoGrupo, motivo: causaRaiz, causa_raiz: causaRaiz,
           type: 'bug', severity: 'Important', priority: 'High',
           nota: 'No se crea una incidencia duplicada: la causa es la misma que la ya registrada.',
           evidencia: `evidencia.json y newman/newman-${GRUPO}.html del RUN ${runId}` }],
    seguridad: null,
    git_post: estadoGit('git_post')
  };
  escribir('evidencia.json', evidencia);
  evidencia.seguridad = escanearSeguridad();
  escribir('evidencia.json', evidencia);
  refrescarManifest();
  fs.unlinkSync(tmp);

  log('\n================ CIERRE POST-FIX ================');
  log(`RUN_ID: ${runId} | baseline del defecto: ${BASELINE.runId} (intacto)`);
  log(`Fix en TEST: política UPDATE ${fixFinal.politica_update_presente} | GRANT UPDATE sgpmp_app ${fixFinal.grant_update_sgpmp_app}`);
  log(`Fixture: finca ${F.finca_id} · área ${F.area_id} · especie ${F.especie_id} | línea previa al RUN: ${R.estadoInicial.linea_base_id || 'ninguna'}`);
  log(`TC-M09-275: HTTP ${R.casos['275'].post.http} | id ${e275.id} | vigente ${num(R.casos['275'].linea_base_vigente.id)} | RF-10 ${(R.casos['275'].auditoria.correlacionados || []).length} -> ${r275}`);
  log(`TC-M09-276: HTTP ${R.casos['276'].post.http} | error_code ${R.casos['276'].post.error_code || '—'} | id ${num(R.casos['276'].post.id)} | vigente ${num(R.casos['276'].reemplazo.id)} | conserva 275 ${e276.oraculo.historial_conserva_275 ? 'SI' : 'NO'} -> ${r276}`);
  log(`TC-M09-277: HTTP ${c277.post.http} | mensaje exacto ${c277.post.mensaje_exacto} | vigente ${num(c277.linea_base_post.id)} | nuevos ${JSON.stringify(c277.historial_post.nuevos)} -> ${r277}`);
  log(`GRUPO ${GRUPO} -> ${resultadoGrupo} | corrección del 409: ${correccionValidada}`);
  log(`Sin workarounds: ${JSON.stringify(sinWorkarounds)}`);
  log(`Newman: requests ${R.stats.requests.ejecutados} (fallidos ${R.stats.requests.fallidos}) | assertions ${R.stats.assertions.total} (fallidas ${R.stats.assertions.fallidas}) | limpio ${newmanLimpio ? 'SI' : 'NO'}`);
  log(`Restauración: ${restauracion.resultado} | cámara desactivada ${restauracion.camara_desactivada_verificado} | red ${JSON.stringify(red)}`);
  log(`BD: ${bd.utilizada ? 'consultada (solo SELECT)' : 'no utilizada'} | ${bd.resumen}`);
  log(`Evidencia limpia de secretos: ${evidencia.seguridad.limpio ? 'SI' : 'NO'}`);
  log('=================================================\n');

  if (!evidencia.seguridad.limpio) process.exitCode = 3;
  else if (resultadoGrupo !== 'APROBADO' || restauracion.resultado !== 'PASS') process.exitCode = 2;
}

// --------------------------------------------------------------- BD TEST (SOLO SELECT)
async function diagnosticoBD(F, id275, id276) {
  const salida = {
    utilizada: false, solo_select: true, dml_ejecutado: 0,
    motivo: ('Verificacion complementaria de la persistencia del reemplazo: el defecto anterior ' +
      'ocurria exactamente al publicar o reemplazar la fila de lineas_base_vision.'),
    consultas: [], resumen: ''
  };
  if (!process.env.QA_DB_PASSWORD) {
    salida.resumen = 'no se entrego QA_DB_PASSWORD: no se abrio ninguna conexion';
    return salida;
  }
  const programa = [
    'import json, os, psycopg2, psycopg2.extras',
    'A = int(os.environ["G137_AREA_BD"]); E = int(os.environ["G137_ESPECIE_BD"])',
    'C = [',
    '  ("privilegios_del_rol_qa", """SELECT n.nspname AS esquema, c.relname AS tabla,',
    "         has_table_privilege(current_user, c.oid, 'SELECT') AS puede_select",
    '       FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace',
    "       WHERE (n.nspname, c.relname) IN (('modulo9','calibraciones_vision'),",
    "             ('modulo9','lineas_base_vision')) ORDER BY 1,2\"\"\", None),",
    '  ("calibraciones_vision_del_area", """SELECT id_calibracion_vision, id_infraestructura, id_especie,',
    '         origen_disparo, id_usuario, estado FROM modulo9.calibraciones_vision',
    '       WHERE id_infraestructura = %s ORDER BY id_calibracion_vision""", (A,)),',
    '  ("linea_base_vigente_del_par", """SELECT id_infraestructura, id_especie, id_calibracion_vision,',
    '         fecha_publicacion FROM modulo9.lineas_base_vision',
    '       WHERE id_infraestructura = %s AND id_especie = %s""", (A, E)),',
    '  ("cuantas_lineas_del_par", """SELECT count(*) AS n FROM modulo9.lineas_base_vision',
    '       WHERE id_infraestructura = %s AND id_especie = %s""", (A, E)),',
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
      env: { ...process.env, G137_AREA_BD: String(F.area_id), G137_ESPECIE_BD: String(F.especie_id) }
    });
    salida.utilizada = true;
    salida.cliente = 'psycopg2 en sesion READ ONLY, invocado en linea desde el runner';
    salida.consultas = JSON.parse(stdout.trim().split('\n').pop());
  } catch (e) {
    salida.consultas.push({ nombre: 'conexion', error: limpiar(String(e.message).split('\n')[0]) });
    salida.utilizada = salida.consultas.some(c => !c.error);
  }
  const cal = (salida.consultas.find(c => c.nombre === 'calibraciones_vision_del_area') || {}).filas;
  const lbv = (salida.consultas.find(c => c.nombre === 'linea_base_vigente_del_par') || {}).filas;
  const cnt = (salida.consultas.find(c => c.nombre === 'cuantas_lineas_del_par') || {}).filas;
  salida.comprobaciones = {};
  if (Array.isArray(cal)) {
    const ids = cal.map(x => Number(x.id_calibracion_vision));
    salida.comprobaciones.id275_existe = id275 !== null ? ids.includes(Number(id275)) : null;
    salida.comprobaciones.id276_existe = id276 !== null ? ids.includes(Number(id276)) : null;
    salida.comprobaciones.calibraciones_del_area = cal;
  }
  if (Array.isArray(lbv)) {
    salida.comprobaciones.linea_vigente_del_par = lbv[0] ?? null;
    salida.comprobaciones.apunta_a_276 = Boolean(lbv[0]) && id276 !== null && Number(lbv[0].id_calibracion_vision) === Number(id276);
  }
  if (Array.isArray(cnt) && cnt[0]) {
    salida.comprobaciones.lineas_del_par = Number(cnt[0].n);
    salida.comprobaciones.una_sola_linea_vigente = Number(cnt[0].n) === 1;
  }
  const denegadas = salida.consultas.filter(c => /permission denied|does not exist/i.test(String(c.error || '')));
  salida.limitacion = denegadas.length
    ? ('La cuenta de solo lectura member_qa no tiene SELECT sobre las tablas VISION: existen, pero el ' +
       'privilegio esta denegado. El oraculo se construyo con los GET de la API, que son la superficie ' +
       'autoritativa del producto; no se sustituye la BD por ninguna inferencia. Las politicas RLS si ' +
       'fueron observables desde pg_policies, que es catalogo y no requiere ese GRANT.')
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
    { archivo: 'run-g137-v2.cjs', abs: path.join(__dirname, 'run-g137-v2.cjs'),
      ruta: `${GRUPO}/EvaluacionV2/automation/run-g137-v2.cjs`,
      funcion: ('Runner unico de la reejecucion POST-FIX, con los modos precheck (Newman de solo lectura ' +
        'sin HTML ni archivos, mas la verificacion del fix por SELECT y la revalidacion por API del ' +
        'fixture historico), run (RUN oficial con el setup minimo, los 3 POST funcionales, la ' +
        'restauracion y el unico HTML) y close (oraculo por caso, verificacion final de solo lectura, ' +
        'comprobacion en BD del reemplazo, red de seguridad y consolidacion de evidencia). Aborta si la ' +
        'coleccion intentara crear finca, area o especie, que esta reejecucion prohibe.') },
    { archivo: 'TC-M09-G137.postman_collection.json', abs: COLECCION,
      ruta: `${GRUPO}/EvaluacionV2/TC-M09-G137.postman_collection.json`,
      funcion: ('Coleccion de la reejecucion POST-FIX. Es duena de sus tres sesiones y reutiliza el ' +
        'fixture anterior sin tocarlo: revalida finca, area y especie por API, comprueba que AMBOS ' +
        'actores ven la finca y el area, registra solo una camara activa y un lote de observaciones, y ' +
        'ejercita los tres casos con el PRE que confirma que el Administrador ve la linea de TC-275 ' +
        'antes de calibrar, que es la condicion en la que se manifestaba el 409.') },
    { archivo: 'TC-M09-G137.postman_collection.json (original)', abs: COLECCION_ORIGINAL,
      ruta: `${GRUPO}/TC-M09-G137.postman_collection.json`,
      funcion: ('Coleccion de la primera evaluacion: un unico GET de /openapi.json. Reutilizada en solo ' +
        'lectura como fuente del criterio del preflight; no fue modificada.') },
    { archivo: 'run-newman.cjs (original)', abs: path.join(CASE_DIR, 'run-newman.cjs'),
      ruta: `${GRUPO}/run-newman.cjs`,
      funcion: 'Runner de la primera evaluacion. NO se utiliza: se registra por trazabilidad del baseline.' }
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
    grupo: GRUPO, casos: CASOS, runId, evaluacion: 'REEJECUCION OFICIAL POST-FIX',
    herramienta: 'API - Postman / Newman',
    nota: ('Artefactos finales de la reejecucion. El runner y la coleccion se actualizaron respecto del ' +
      'RUN baseline para reutilizar el fixture en vez de crearlo; los artefactos del RUN baseline quedan ' +
      'intactos en su propia carpeta.'),
    baseline_conservado: BASELINE.runId,
    newmanHtmlPersistentes: 1, automationDentroDeResultados: 'NO', artefactos: filas
  }, null, 2)));
}
