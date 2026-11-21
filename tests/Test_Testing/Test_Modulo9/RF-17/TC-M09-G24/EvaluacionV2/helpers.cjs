// TC-M09-G24 — REEVALUACION V2 (RF-17, niveles de alerta). Discovery, construccion
// exacta de payloads y saneamiento. Contrasena solo por variable de proceso; token en memoria.
const fs = require('fs');
const path = require('path');

// HTTPS: el backend TEST por HTTP responde 404 del proxy (verificado en el preflight).
const BASE = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const BASE_HTTP_SUMINISTRADA = 'http://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const ACTOR = 'administador.dev@gmail.com';
const ROLES_RF17 = ['Administrador', 'Veterinario'];
const RECURSO_UMBRALES = 20;
const CASOS = ['TC-M09-52', 'TC-M09-53', 'TC-M09-54'];
const META = { grupo: 'TC-M09-G24', rf: 'RF-17', tipo: 'REEVALUACION V2', entorno: 'TEST', rama: 'qa/juan-esteban-re-evaluacion-M02', base: BASE };

// Oraculos V2, resueltos antes del primer POST (ver reporte, seccion ORACULO HTTP TC53).
const ORACULO = {
  'TC-M09-52': { status: 400, error_code: 'NIVEL_FUERA_DE_RANGO', persiste: false },
  'TC-M09-53': { status: 422, error_code: 'SOLAPAMIENTO_NIVELES', persiste: false },
  'TC-M09-54': { status: 201, error_code: null, persiste: true },
};

function settings({ requiereCaso = true } = {}) {
  const runId = process.env.G24_REEVAL_V2_RUN_ID;
  if (!runId || !/^[\w-]+$/.test(runId)) throw Error('G24_REEVAL_V2_RUN_ID requerido');
  if (!process.env.TEST_ADMIN_PASSWORD) throw Error('TEST_ADMIN_PASSWORD requerida');
  const caso = process.env.G24_CASE;
  const intento = Number(process.env.G24_INTENTO || 1);
  if (requiereCaso && !CASOS.includes(caso)) throw Error('G24_CASE debe ser TC-M09-52 | TC-M09-53 | TC-M09-54');
  if (![1, 2].includes(intento)) throw Error('G24_INTENTO solo 1 o 2: maximo dos POST por original');
  return { runId, caso, intento };
}

function clean(s) {
  if (s == null) return s;
  s = String(s);
  if (process.env.TEST_ADMIN_PASSWORD) s = s.split(process.env.TEST_ADMIN_PASSWORD).join('[REDACTED]');
  return s.replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[JWT REDACTED]')
    .replace(/Bearer\s+(?!\{\{)[A-Za-z0-9_.\-]+/g, 'Bearer [REDACTED]')
    .replace(/refresh_token=[^;"\s]+/gi, 'refresh_token=[REDACTED]');
}
function dir(runId, ...sub) { const d = path.join(__dirname, 'RESULTADOS', runId, ...sub); fs.mkdirSync(d, { recursive: true }); return d; }
function save(runId, name, value, { sobrescribir = false } = {}) {
  const p = path.join(dir(runId), name);
  if (fs.existsSync(p) && !sobrescribir) throw Error('No sobrescribir evidencia existente: ' + name);
  fs.writeFileSync(p, clean(JSON.stringify({ ...META, runId, fecha: new Date().toISOString(), ...value }, null, 2)));
}
function load(runId, name) { const p = path.join(dir(runId), name); return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : null; }

async function get(endpoint, token) {
  const r = await fetch(BASE + endpoint, { headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(25000) });
  if (r.status !== 200) throw Error(`GET ${endpoint} HTTP ${r.status}`);
  return r.json();
}
async function login() {
  const r = await fetch(BASE + '/sesiones/', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correo_electronico: ACTOR, contrasena: process.env.TEST_ADMIN_PASSWORD }), signal: AbortSignal.timeout(25000) });
  if (r.status !== 200) throw Error(`ENVIRONMENT_ERROR login HTTP ${r.status}`);
  const j = await r.json();
  if (!j.token) throw Error('ENVIRONMENT_ERROR login sin token');
  return j.token;
}
async function validarActor(token) {
  const me = await get('/usuarios/me', token);
  const permisos = (await get('/sesiones/me/permisos', token)).permisos.filter((p) => p.id_recurso === RECURSO_UMBRALES).map((p) => p.id_accion).sort();
  if (me.correo_electronico !== ACTOR) throw Error('Identidad inesperada');
  if (!ROLES_RF17.includes(me.nombre_rol)) throw Error('Rol no autorizado por RF-17: ' + me.nombre_rol);
  if (![1, 2].every((a) => permisos.includes(a))) throw Error('BLOCKED permisos crear/consultar recurso 20 ausentes');
  return { correo_electronico: me.correo_electronico, id_usuario: me.id_usuario, nombre_rol: me.nombre_rol, estado_cuenta: me.estado_cuenta, permisosRecurso20: permisos };
}

async function preflight() {
  const salida = [];
  try { const r = await fetch(BASE_HTTP_SUMINISTRADA + '/health', { redirect: 'manual', signal: AbortSignal.timeout(20000) }); salida.push({ url: BASE_HTTP_SUMINISTRADA + '/health', status: r.status, nota: 'URL suministrada' }); }
  catch (e) { salida.push({ url: BASE_HTTP_SUMINISTRADA + '/health', error: clean(e.message) }); }
  for (const url of [BASE + '/health', BASE + '/openapi.json']) {
    const r = await fetch(url, { signal: AbortSignal.timeout(25000) });
    salida.push({ url, status: r.status });
    if (r.status !== 200) throw Error('ENVIRONMENT_ERROR preflight HTTP ' + r.status);
    if (url.endsWith('openapi.json')) {
      const op = (await r.json()).paths['/configuracion/umbrales']?.post;
      if (!op) throw Error('Contrato ausente: POST /configuracion/umbrales');
      salida.push({ contrato: 'POST /configuracion/umbrales', respuestasDeclaradas: Object.keys(op.responses) });
    }
  }
  return salida;
}

// Aritmetica decimal exacta a dos decimales (literales, sin coma flotante).
function d2(v) { const [e, d = ''] = String(v).split('.'); const neg = e.startsWith('-'); return (neg ? -1n : 1n) * BigInt((neg ? e.slice(1) : e) + (d + '00').slice(0, 2)); }
function txt(c) { const neg = c < 0n; const a = (neg ? -c : c).toString().padStart(3, '0'); return (neg ? '-' : '') + a.slice(0, -2) + '.' + a.slice(-2); }

// Puntos del rango fisico real: padre [a,d]; b y c fronteras internas; e entre b y c; g por encima de d.
const FRACCIONES = { a: 25n, b: 40n, e: 48n, c: 55n, d: 70n, g: 85n };
function puntos(fmin, fmax) {
  const lo = d2(fmin), hi = d2(fmax), R = hi - lo;
  const p = Object.fromEntries(Object.entries(FRACCIONES).map(([k, f]) => [k, lo + (R * f) / 100n]));
  const orden = [p.a, p.b, p.e, p.c, p.d, p.g];
  if (!orden.every((x, i) => !i || x > orden[i - 1]) || p.g > hi) return null;
  return Object.fromEntries(Object.entries(p).map(([k, v]) => [k, txt(v)]));
}
function niveles(caso, p) {
  const n = (nivel, limite_inferior, limite_superior) => ({ nivel, limite_inferior, limite_superior });
  return {
    // Unica invalidez: critico termina en g > valor_max (d).
    'TC-M09-52': [n('normal', p.a, p.b), n('precaucion', p.b, p.c), n('critico', p.c, p.g)],
    // Unica invalidez: critico empieza en e < c, solapando [e, c] con precaucion; dentro del padre y sin huecos en los extremos.
    'TC-M09-53': [n('normal', p.a, p.b), n('precaucion', p.b, p.c), n('critico', p.e, p.d)],
    // Continuo: fronteras compartidas exactas (contrato: superior_i == inferior_i+1), cubre [a, d].
    'TC-M09-54': [n('normal', p.a, p.b), n('precaucion', p.b, p.c), n('critico', p.c, p.d)],
  }[caso];
}

const ACUATICA = /cachama|camar[oó]n|mojarra|tilapia|trucha/i;
const ES_QA = /\bqa\b|\btest\b/i;
const VAR_PREFERIDAS = [/temperatura del agua/i, /ox[ií]geno disuelto/i, /salinidad/i, /turbidez/i];

// Mapa completo especie-variable y seleccion de una combinacion libre coherente
// (umbral activo o inactivo = ocupada, la unicidad es por especie+variable).
async function mapa(token) {
  const especies = (await get('/configuracion/especies', token)).items;
  const activas = especies.filter((s) => s.es_activo);
  const variables = (await get('/configuracion/variables-ambientales', token)).items;
  const umbrales = {};
  for (const s of activas) umbrales[s.id_especie] = (await get(`/configuracion/umbrales?id_especie=${s.id_especie}`, token)).items;
  const filas = [];
  for (const s of activas) for (const v of variables) {
    const existentes = umbrales[s.id_especie].filter((u) => u.id_variable_ambiental === v.id_variable_ambiental);
    filas.push({ id_especie: s.id_especie, especie: s.nombre, especieActiva: true, id_variable_ambiental: v.id_variable_ambiental, variable: v.nombre,
      configExistente: existentes.map((u) => ({ id: u.id_umbral_ambiental, es_activo: u.es_activo })), libre: existentes.length === 0 });
  }
  return { especies, activas, variables, umbrales, filas };
}
function elegir(m, excluir = []) {
  const rank = (f) => {
    const s = m.activas.find((x) => x.id_especie === f.id_especie);
    const iv = VAR_PREFERIDAS.findIndex((r) => r.test(f.variable));
    return (ACUATICA.test(s.nombre) ? 0 : 10) + (ES_QA.test(s.nombre) ? 5 : 0) + (iv === -1 ? 50 : iv);
  };
  const candidatas = m.filas.filter((f) => f.libre && !excluir.some((x) => x.id_especie === f.id_especie && x.id_variable_ambiental === f.id_variable_ambiental))
    .sort((a, b) => rank(a) - rank(b) || a.id_especie - b.id_especie || a.id_variable_ambiental - b.id_variable_ambiental);
  for (const f of candidatas) {
    const v = m.variables.find((x) => x.id_variable_ambiental === f.id_variable_ambiental);
    const p = puntos(String(v.valor_fisico_min), String(v.valor_fisico_max));
    if (p) return { fila: f, variable: v, puntos: p };
  }
  return null;
}
function construir(caso, sel, m) {
  const { fila, variable, puntos: p } = sel;
  const s = m.activas.find((x) => x.id_especie === fila.id_especie);
  return {
    caso,
    especie: { id: s.id_especie, nombre: s.nombre, es_activo: s.es_activo },
    variable: { id: variable.id_variable_ambiental, nombre: variable.nombre, unidad: variable.unidad, fisicoMin: String(variable.valor_fisico_min), fisicoMax: String(variable.valor_fisico_max) },
    rangoGeneral: { valor_min: p.a, valor_max: p.d },
    puntos: p,
    umbralesPreviosEspecie: m.umbrales[s.id_especie].map((u) => ({ id: u.id_umbral_ambiental, id_variable_ambiental: u.id_variable_ambiental })),
    oraculo: ORACULO[caso],
    payload: { id_especie: s.id_especie, id_variable_ambiental: variable.id_variable_ambiental, valor_min: p.a, valor_max: p.d, niveles: niveles(caso, p) },
  };
}
function cuerpo(p) {
  const nivel = (n) => `{"nivel":"${n.nivel}","limite_inferior":${n.limite_inferior},"limite_superior":${n.limite_superior}}`;
  return `{"id_especie":${p.id_especie},"id_variable_ambiental":${p.id_variable_ambiental},"valor_min":${p.valor_min},"valor_max":${p.valor_max},"niveles":[${p.niveles.map(nivel).join(',')}]}`;
}

// Analisis matematico del payload (con BigInt, sin coma flotante).
function analizar(payload) {
  const min = d2(payload.valor_min), max = d2(payload.valor_max);
  const ns = payload.niveles.map((n) => ({ nivel: n.nivel, inf: d2(n.limite_inferior), sup: d2(n.limite_superior) }));
  const ord = [...ns].sort((x, y) => (x.inf < y.inf ? -1 : x.inf > y.inf ? 1 : 0));
  const fuera = ns.filter((n) => n.inf < min || n.sup > max).map((n) => n.nivel);
  const solapes = [], huecos = [];
  for (let i = 0; i < ord.length - 1; i++) {
    if (ord[i].sup > ord[i + 1].inf) solapes.push(`${ord[i].nivel}/${ord[i + 1].nivel} [${txt(ord[i + 1].inf)}, ${txt(ord[i].sup)}]`);
    if (ord[i].sup < ord[i + 1].inf) huecos.push(`${ord[i].nivel}/${ord[i + 1].nivel} (${txt(ord[i].sup)}, ${txt(ord[i + 1].inf)})`);
  }
  if (ord[0].inf > min) huecos.push(`inicio (${txt(min)}, ${txt(ord[0].inf)})`);
  if (ord[ord.length - 1].sup < max) huecos.push(`final (${txt(ord[ord.length - 1].sup)}, ${txt(max)})`);
  return { minMenorQueMax: min < max, tresNiveles: ns.length === 3, nombresContrato: ns.map((n) => n.nivel).sort().join(',') === 'critico,normal,precaucion',
    cadaNivelInfMenorSup: ns.every((n) => n.inf < n.sup), fueraDelGeneral: fuera, solapamientos: solapes, huecos };
}

module.exports = { BASE, ACTOR, CASOS, ORACULO, META, settings, clean, dir, save, load, get, login, validarActor, preflight, mapa, elegir, construir, cuerpo, analizar };
