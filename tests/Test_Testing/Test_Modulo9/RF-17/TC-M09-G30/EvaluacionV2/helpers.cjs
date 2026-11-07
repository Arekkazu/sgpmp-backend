// TC-M09-G30 / TC-M09-64 — REEVALUACION V2 (RF-17, auditoria de umbrales).
// Contrasena solo por variable de proceso; token en memoria; evidencias saneadas.
const fs = require('fs');
const path = require('path');

// HTTPS: el backend TEST por HTTP responde 404 del proxy (verificado en el preflight).
const BASE = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const BASE_HTTP_SUMINISTRADA = 'http://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
// Correo real del Administrador TEST (el paquete lo cita como admin.dev@gmail.com, que era un error del responsable QA).
const ACTOR = 'administador.dev@gmail.com';
const ROLES_RF17 = ['Administrador', 'Veterinario'];
const META = { grupo: 'TC-M09-G30', caso: 'TC-M09-64', rf: 'RF-17', cu: 'CU-03', tipo: 'REEVALUACION V2', entorno: 'TEST', rama: 'qa/juan-esteban-re-evaluacion-M02', base: BASE };

function settings() {
  const runId = process.env.G30_REEVAL_V2_RUN_ID;
  const fase = process.env.G30_FASE;
  const intento = Number(process.env.G30_INTENTO || 1);
  if (!runId || !/^[\w-]+$/.test(runId)) throw Error('G30_REEVAL_V2_RUN_ID requerido');
  if (!['plan', 'create', 'audit-create', 'update', 'audit'].includes(fase)) throw Error('G30_FASE: plan | create | audit-create | update | audit');
  if (![1, 2].includes(intento)) throw Error('G30_INTENTO solo 1 o 2');
  if (!process.env.TEST_ADMIN_PASSWORD) throw Error('TEST_ADMIN_PASSWORD requerida');
  return { runId, fase, intento };
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

async function pedir(endpoint, token) {
  const r = await fetch(BASE + endpoint, { headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(25000) });
  let body = null; try { body = await r.json(); } catch { /* sin JSON */ }
  return { status: r.status, body };
}
async function get(endpoint, token) { const r = await pedir(endpoint, token); if (r.status !== 200) throw Error(`GET ${endpoint} HTTP ${r.status}`); return r.body; }
async function login() {
  const r = await fetch(BASE + '/sesiones/', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correo_electronico: ACTOR, contrasena: process.env.TEST_ADMIN_PASSWORD }), signal: AbortSignal.timeout(25000) });
  if (r.status !== 200) throw Error(`ENVIRONMENT_ERROR login HTTP ${r.status}`);
  const j = await r.json(); if (!j.token) throw Error('login sin token');
  return j.token;
}
async function validarActor(token) {
  const me = await get('/usuarios/me', token);
  const perms = (await get('/sesiones/me/permisos', token)).permisos;
  const r20 = perms.filter((p) => p.id_recurso === 20).map((p) => p.id_accion).sort();
  const r6 = perms.filter((p) => p.id_recurso === 6).map((p) => p.id_accion).sort();
  if (me.correo_electronico !== ACTOR) throw Error('Identidad inesperada');
  if (!ROLES_RF17.includes(me.nombre_rol)) throw Error('Rol no autorizado RF-17: ' + me.nombre_rol);
  if (![1, 2, 3].every((a) => r20.includes(a))) throw Error('BLOCKED permisos crear/consultar/modificar recurso 20 ausentes');
  return { correo_electronico: me.correo_electronico, id_usuario: me.id_usuario, nombre_rol: me.nombre_rol, estado_cuenta: me.estado_cuenta, permisosRecurso20: r20, permisosRecurso6_D09: r6 };
}
async function preflight() {
  const out = [];
  try { const r = await fetch(BASE_HTTP_SUMINISTRADA + '/health', { redirect: 'manual', signal: AbortSignal.timeout(20000) }); out.push({ url: BASE_HTTP_SUMINISTRADA + '/health', status: r.status, nota: 'URL suministrada' }); }
  catch (e) { out.push({ url: BASE_HTTP_SUMINISTRADA + '/health', error: clean(e.message) }); }
  for (const url of [BASE + '/health', BASE + '/openapi.json']) {
    const r = await fetch(url, { signal: AbortSignal.timeout(25000) });
    out.push({ url, status: r.status });
    if (r.status !== 200) throw Error('ENVIRONMENT_ERROR preflight ' + r.status);
    if (url.endsWith('openapi.json')) {
      const j = await r.json();
      const p = j.paths;
      const aud = p['/configuracion/umbrales/{id_umbral_ambiental}/auditoria']?.get;
      if (!p['/configuracion/umbrales']?.post || !p['/configuracion/umbrales/{id_umbral_ambiental}']?.patch) throw Error('Contrato RF-17 ausente');
      out.push({ contrato: {
        post: Object.keys(p['/configuracion/umbrales'].post.responses), patch: Object.keys(p['/configuracion/umbrales/{id_umbral_ambiental}'].patch.responses),
        auditoriaUmbral: aud ? Object.keys(aud.responses) : null,
        auditoriaUmbralSchema: Object.keys(j.components.schemas.AuditoriaUmbralResponse?.properties || {}),
        d09Global: p['/auditoria/']?.get ? Object.keys(p['/auditoria/'].get.responses) : null,
      } });
    }
  }
  return out;
}

// Decimales exactos a dos cifras.
function d2(v) { const [e, d = ''] = String(v).split('.'); const neg = e.startsWith('-'); return (neg ? -1n : 1n) * BigInt((neg ? e.slice(1) : e) + (d + '00').slice(0, 2)); }
function txt(c) { const neg = c < 0n; const a = (neg ? -c : c).toString().padStart(3, '0'); return (neg ? '-' : '') + a.slice(0, -2) + '.' + a.slice(-2); }
function rango(fmin, fmax, desde, hasta) {
  const lo = d2(fmin), hi = d2(fmax), R = hi - lo;
  const a = lo + (R * BigInt(desde)) / 100n, d = lo + (R * BigInt(hasta)) / 100n, paso = (d - a) / 3n;
  if (paso <= 0n) return null;
  const pts = [a, a + paso, a + 2n * paso, d].map(txt);
  return { valor_min: pts[0], valor_max: pts[3], niveles: [
    { nivel: 'normal', limite_inferior: pts[0], limite_superior: pts[1] },
    { nivel: 'precaucion', limite_inferior: pts[1], limite_superior: pts[2] },
    { nivel: 'critico', limite_inferior: pts[2], limite_superior: pts[3] }] };
}

const ACUATICA = /cachama|camar[oó]n|mojarra|tilapia|trucha/i;
const TERRESTRE = /bovin|equin|\bave\b|porcin|ovin|capr/i;
const ES_QA = /\bqa\b|\btest\b/i;
async function mapa(token) {
  const activas = (await get('/configuracion/especies', token)).items.filter((s) => s.es_activo);
  const variables = (await get('/configuracion/variables-ambientales', token)).items;
  const umbrales = {};
  for (const s of activas) umbrales[s.id_especie] = (await get(`/configuracion/umbrales?id_especie=${s.id_especie}`, token)).items;
  const filas = [];
  for (const s of activas) for (const v of variables) {
    const ex = umbrales[s.id_especie].filter((u) => u.id_variable_ambiental === v.id_variable_ambiental);
    filas.push({ id_especie: s.id_especie, especie: s.nombre, id_variable_ambiental: v.id_variable_ambiental, variable: v.nombre, configExistente: ex.map((u) => u.id_umbral_ambiental), libre: ex.length === 0 });
  }
  return { activas, variables, umbrales, filas };
}
// Preferencia: Temperatura coherente con el tipo de especie (agua/acuatica, corporal o ambiental/terrestre), especie no QA.
function elegir(m) {
  const rank = (f) => {
    const s = m.activas.find((x) => x.id_especie === f.id_especie);
    if (!/temperatura/i.test(f.variable)) return 1000;
    let r = ES_QA.test(s.nombre) ? 50 : 0;
    if (ACUATICA.test(s.nombre)) r += /del agua/i.test(f.variable) ? 0 : 20;
    else if (TERRESTRE.test(s.nombre)) r += /corporal/i.test(f.variable) ? 1 : /ambiental/i.test(f.variable) ? 2 : 20;
    else r += 30;
    return r;
  };
  const c = m.filas.filter((f) => f.libre).sort((a, b) => rank(a) - rank(b) || a.id_especie - b.id_especie);
  for (const f of c) {
    const v = m.variables.find((x) => x.id_variable_ambiental === f.id_variable_ambiental);
    const A = rango(String(v.valor_fisico_min), String(v.valor_fisico_max), 40, 60);
    const B = rango(String(v.valor_fisico_min), String(v.valor_fisico_max), 35, 65);
    if (A && B && A.valor_min !== B.valor_min && A.valor_max !== B.valor_max) return { fila: f, variable: v, A, B };
  }
  return null;
}
function cuerpo(obj) {
  const nivel = (n) => `{"nivel":"${n.nivel}","limite_inferior":${n.limite_inferior},"limite_superior":${n.limite_superior}}`;
  const partes = [];
  if (obj.id_especie != null) partes.push(`"id_especie":${obj.id_especie}`, `"id_variable_ambiental":${obj.id_variable_ambiental}`);
  partes.push(`"valor_min":${obj.valor_min}`, `"valor_max":${obj.valor_max}`, `"niveles":[${obj.niveles.map(nivel).join(',')}]`);
  if (Object.prototype.hasOwnProperty.call(obj, 'fecha_actualizacion')) partes.push(`"fecha_actualizacion":${obj.fecha_actualizacion == null ? 'null' : JSON.stringify(obj.fecha_actualizacion)}`);
  return `{${partes.join(',')}}`;
}

// D09 global (GET /auditoria/): solo observacion, campos minimos sin IP ni user agent.
async function d09Global(token, idUsuario, desde, hasta) {
  const q = new URLSearchParams({ id_usuario: String(idUsuario), fecha_desde: desde, fecha_hasta: hasta, pagina: '1', tamano: '50' });
  const r = await pedir(`/auditoria/?${q}`, token);
  const items = Array.isArray(r.body?.items) ? r.body.items : [];
  return { endpoint: 'GET /auditoria/', status: r.status, total: r.body?.total ?? items.length,
    eventos: items.map((e) => ({ id_evento: e.id_evento, tipo_evento: e.tipo_evento, fecha_evento: e.fecha_evento, modulo: e.modulo, resultado: e.resultado, descripcion: e.descripcion })) };
}

module.exports = { BASE, ACTOR, META, settings, clean, dir, save, load, pedir, get, login, validarActor, preflight, mapa, elegir, cuerpo, d09Global };
