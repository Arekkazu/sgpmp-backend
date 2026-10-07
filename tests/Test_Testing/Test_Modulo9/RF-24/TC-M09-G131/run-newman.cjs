// TC-M09-G131: un RUN en TEST, hasta cuatro POST sin reintentos.
// Los POST se envían únicamente mediante Newman. GET, preflight e informe se
// gestionan aquí para poder detener los siguientes POST al detectar persistencia.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

if (path.basename(__dirname) !== 'TC-M09-G131') throw new Error('Carpeta de ejecución incorrecta.');
const runId = process.env.G131_RUN_ID;
if (!/^run-\d{8}-\d{6}$/.test(runId || '')) throw new Error('G131_RUN_ID debe tener formato run-YYYYMMDD-HHMMSS.');
const base = (process.env.QA_BASE_URL || '').replace(/\/$/, '');
if (base !== 'https://api.inmero.co/back-sigab-test') throw new Error('El ambiente decisorio debe ser TEST.');
const email = process.env.QA_EMAIL;
const password = process.env.QA_PASSWORD;
if (!email || !password) throw new Error('Faltan QA_EMAIL o QA_PASSWORD.');
const out = path.join(__dirname, 'RESULTADOS', runId);
if (fs.existsSync(out)) throw new Error('RUN_ID ya existente: no se sobrescribe evidencia.');
fs.mkdirSync(out, { recursive: true });
const cases = [
  ['TC-M09-258', '—'], ['TC-M09-259', '—'],
  ['TC-M09-260', 'OTRO'], ['TC-M09-260', 'VACIO']
];
const key = (id, variant) => id === 'TC-M09-260' ? variant : id;
const evidence = {
  grupo: 'TC-M09-G131', casos: ['TC-M09-258', 'TC-M09-259', 'TC-M09-260'],
  run_id: runId, ambiente: 'TEST', base_url: base, prueba_local: false,
  post_planificados: 4, post_ejecutados: 0, git: {}, openapi: {}, actor: {},
  fixtures: {}, 'TC-M09-258': {}, 'TC-M09-259': {},
  'TC-M09-260': { OTRO: {}, VACIO: {} },
  stop_all: false, resultado_general: '', motivo_general: '', incidencias: []
};
const secretValues = [password, process.env.QA_ADMIN_PASSWORD].filter(Boolean);
function clean(value) {
  let s = String(value ?? '');
  for (const secret of secretValues) s = s.split(secret).join('[REDACTED]');
  return s.replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[JWT REDACTED]')
    .replace(/Bearer\s+[A-Za-z0-9_.-]+/gi, 'Bearer [REDACTED]');
}
function git(args) {
  try {
    let d = __dirname;
    while (!fs.existsSync(path.join(d, '.git')) && path.dirname(d) !== d) d = path.dirname(d);
    return execFileSync('git', args, { cwd: d, encoding: 'utf8' }).trim();
  } catch (e) { return `ERROR: ${clean(e.message)}`; }
}
function save() { fs.writeFileSync(path.join(out, 'evidencia.json'), clean(JSON.stringify(evidence, null, 2)), 'utf8'); }
function esc(x) { return String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function resultRef(id, variant) { return id === 'TC-M09-260' ? evidence[id][variant] : evidence[id]; }
function markRemaining(status, reason) {
  for (const [id, variant] of cases) {
    const r = resultRef(id, variant);
    if (!r.resultado) Object.assign(r, { resultado: status, motivo: reason });
  }
}
function render() {
  const rows = cases.map(([id, variant]) => {
    const r = resultRef(id, variant);
    return `| ${id} | ${variant === 'VACIO' ? 'vacío' : variant} | ${r.resultado} | ${r.motivo} |`;
  }).join('\n');
  const details = cases.map(([id, variant]) => {
    const r = resultRef(id, variant), label = `${id} / ${variant}`;
    return `### ${label}\n\nEsperado: HTTP 4xx y ausencia de persistencia.\n\nObtenido: ${r.http ?? 'sin POST'}${r.error_code ? `; ${r.error_code}` : ''}${r.mensaje ? `; ${r.mensaje}` : ''}. ${r.motivo}\n\nPRE: ${JSON.stringify(r.pre ?? null)}. POST: ${JSON.stringify(r.post ?? null)}.\n`;
  }).join('\n');
  const incidents = evidence.incidencias.length ? evidence.incidencias.map(i =>
    `INCIDENCIA REQUERIDA: SÍ\n\nGrupo responsable: ${i.grupo_responsable}\n\nGrupo de prueba: TC-M09-G131\n\nCasos afectados: ${i.casos.join(', ')}\n\nResultado: RECHAZADO\n\nMotivo: ${i.motivo}\n\nEsperado: 4xx y sin persistencia.\n\nObtenido: ${i.obtenido}\n\nCausa raíz: ${i.causa_raiz}\n\nType: ${i.type} | Severity: ${i.severity} | Priority: ${i.priority}\n\nEvidencia: evidencia.json / newman.html`)
    .join('\n\n') : 'INCIDENCIA REQUERIDA: NO. La precondición no verificada no demuestra un defecto de producto.';
  const md = `# TC-M09-G131 — Resultado\n\n## Decisión general\n\n**${evidence.resultado_general}**. ${evidence.motivo_general}\n\n| Caso | Variante | Resultado | Motivo |\n|---|---|---|---|\n${rows}\n\n## Entorno y actor\n\nTEST: ${base}. Prueba local: NO. RUN_ID: ${runId}. Rama: ${evidence.git.rama}. HEAD: ${evidence.git.head}. Actor: ${JSON.stringify(evidence.actor)}.\n\n## Fixtures\n\n${JSON.stringify(evidence.fixtures, null, 2)}\n\n## Esperado vs obtenido\n\n${details}\n## Persistencia\n\nLa comparación usa total e IDs de cada historial PRE/POST. Ver detalles por variante y evidencia.json.\n\n## STOP_ALL\n\n${evidence.stop_all ? 'SÍ: ' + evidence.motivo_stop_all : 'NO'}. POST planificados: 4. POST ejecutados: ${evidence.post_ejecutados}.\n\n## Incidencias\n\n${incidents}\n\n## Conclusión\n\n${evidence.motivo_general}\n`;
  fs.writeFileSync(path.join(out, 'TC-M09-G131_resultado.md'), clean(md), 'utf8');
  const trs = cases.map(([id, variant]) => { const r = resultRef(id, variant); return `<tr><td>${esc(id)}</td><td>${esc(variant)}</td><td>${esc(r.resultado)}</td><td>${esc(r.http ?? '—')}</td><td>${esc(r.motivo)}</td></tr>`; }).join('');
  fs.writeFileSync(path.join(out, 'newman.html'), `<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman ${esc(runId)}</title><style>body{font:16px Arial,sans-serif;max-width:1000px;margin:40px auto;color:#182331}table{border-collapse:collapse;width:100%}td,th{border:1px solid #bbc5ce;padding:9px;text-align:left}th{background:#e9eef2}</style><h1>Newman — TC-M09-G131</h1><p>RUN ${esc(runId)} · TEST · ${esc(evidence.resultado_general)} · ${evidence.post_ejecutados}/4 POST</p><table><thead><tr><th>Caso</th><th>Variante</th><th>Resultado</th><th>HTTP</th><th>Motivo</th></tr></thead><tbody>${trs}</tbody></table><p>${esc(evidence.motivo_general)}</p><p>Detalle estructurado: evidencia.json. Informe: TC-M09-G131_resultado.md.</p></html>`, 'utf8');
}
function finalize() {
  const all = cases.map(([id, v]) => resultRef(id, v).resultado);
  evidence.resultado_general = all.every(x => x === 'APROBADO') ? 'APROBADO' :
    all.includes('RECHAZADO') ? 'RECHAZADO' : 'BLOQUEADO / NO VERIFICABLE';
  if (!evidence.motivo_general) evidence.motivo_general = evidence.resultado_general === 'APROBADO'
    ? 'Los cuatro subcasos respondieron 4xx y conservaron total e IDs de historial.'
    : evidence.resultado_general === 'RECHAZADO'
      ? 'Al menos un subcaso incumplió el oráculo de 4xx y ausencia de persistencia.'
      : 'No se alcanzó el oráculo por una precondición externa.';
  save(); render();
  console.log(`TC-M09-G131 → ${evidence.resultado_general}; POST ejecutados: ${evidence.post_ejecutados}; STOP_ALL: ${evidence.stop_all ? 'SÍ' : 'NO'}`);
  console.log(path.join(out, 'TC-M09-G131_resultado.md'));
}
async function request(method, route, token, body) {
  const r = await fetch(base + route, { method, headers: {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(body ? { 'Content-Type': 'application/json' } : {})
  }, body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(30000) });
  return { status: r.status, body: await r.json().catch(() => null) };
}
async function login(user, pass) {
  const r = await request('POST', '/sesiones/', null, { correo_electronico: user, contrasena: pass });
  if (r.status !== 200 || !r.body?.token) throw new Error(`La cuenta ${user} no autentica (HTTP ${r.status}).`);
  return r.body.token;
}
async function get(route, primary, auxiliary) {
  const first = await request('GET', route, primary);
  if (first.status === 200) return { body: first.body, fuente: 'Ingeniero' };
  if (first.status === 404 && auxiliary) {
    const second = await request('GET', route, auxiliary);
    if (second.status === 200) return { body: second.body, fuente: 'actor auxiliar GET' };
    throw new Error(`GET ${route}: Ingeniero HTTP ${first.status}; auxiliar HTTP ${second.status}.`);
  }
  throw new Error(`GET ${route}: Ingeniero HTTP ${first.status}; sin actor auxiliar GET.`);
}
function snapshot(data) {
  if (!Number.isInteger(data?.total) || !Array.isArray(data?.items)) throw new Error('Formato de historial no verificable.');
  const ids = data.items.map(x => x.id_calibracion).sort((a,b) => a-b);
  if (ids.some(x => !Number.isInteger(x))) throw new Error('Historial sin IDs íntegros.');
  return { total: data.total, ids };
}
async function fixture(owner, sensorId, areaId, token, readToken, ranges) {
  const device = (await get(`/configuracion/dispositivos-iot/${owner}`, token, readToken)).body;
  const sensorList = (await get(`/configuracion/dispositivos-iot/${owner}/sensores`, token, readToken)).body;
  const sensor = sensorList.items?.find(x => x.id_sensores === sensorId && x.id_dispositivo_iot === owner);
  const assocList = (await get(`/configuracion/sensores/${sensorId}/asociaciones`, token, readToken)).body;
  const assoc = assocList.items?.find(x => x.id_sensor === sensorId && x.id_dispositivo_iot === owner && x.id_infraestructura === areaId && x.tiene_estado === true && x.fecha_finalizacion === null);
  const area = (await get(`/configuracion/infraestructuras/${areaId}`, token, readToken)).body;
  const range = ranges.items?.find(x => x.categoria === sensor?.categoria);
  if (device.es_activo !== true || sensor?.es_activo !== true || !assoc || area.es_activo !== true || !range) return null;
  return { sensor: sensorId, dispositivo: owner, area: areaId, categoria: sensor.categoria, rango: { min: range.valor_min, max: range.valor_max }, asociacion: assoc.id_sensores_area_asociada, fuente: 'GET en TEST' };
}
function validValue(f, n) { return f && Number(f.rango.min) <= n && n <= Number(f.rango.max); }
async function findFixtures(token, readToken, ranges) {
  let f258 = null, f259 = null, mismatch = null;
  try { f258 = await fixture(1, 3, 1, token, readToken, ranges); } catch (e) { evidence.fixtures.preferido_258 = clean(e.message); }
  try { f259 = await fixture(3, 6, 3, token, readToken, ranges); } catch (e) { evidence.fixtures.preferido_259 = clean(e.message); }
  try { mismatch = (await get('/configuracion/dispositivos-iot/3', token, readToken)).body; }
  catch (e) { evidence.fixtures.dispositivo_alterno = clean(e.message); }
  if (f258 && !validValue(f258, 10)) f258 = null;
  if (f259 && !validValue(f259, 22.5)) f259 = null;
  if (mismatch?.es_activo !== true || mismatch.id_dispositivo_iot === f258?.dispositivo) mismatch = null;
  if (!f258 || !f259 || !mismatch) {
    const devices = (await get('/configuracion/dispositivos-iot', token, readToken)).body.items || [];
    const active = devices.filter(x => x.es_activo === true);
    const candidates = [];
    for (const d of active) {
      const sensors = (await get(`/configuracion/dispositivos-iot/${d.id_dispositivo_iot}/sensores`, token, readToken)).body.items || [];
      for (const s of sensors.filter(x => x.es_activo === true)) {
        const associations = (await get(`/configuracion/sensores/${s.id_sensores}/asociaciones`, token, readToken)).body.items || [];
        for (const a of associations.filter(x => x.tiene_estado === true && x.fecha_finalizacion === null && x.id_dispositivo_iot === d.id_dispositivo_iot)) {
          try { const f = await fixture(d.id_dispositivo_iot, s.id_sensores, a.id_infraestructura, token, readToken, ranges); if (f) candidates.push(f); } catch { /* siguiente fixture */ }
        }
      }
    }
    if (!f259) f259 = candidates.find(x => validValue(x, 22.5)) || null;
    if (!f258 || !mismatch) {
      for (const f of candidates.filter(x => validValue(x, 10))) {
        const other = active.find(x => x.id_dispositivo_iot !== f.dispositivo);
        if (other) { f258 = f; mismatch = other; break; }
      }
    }
  }
  if (!f258 || !f259 || !mismatch) throw new Error('No se pudo verificar por GET un fixture activo con asociación vigente, valor válido y dispositivo alterno activo.');
  return { f258, f259, alterno: mismatch.id_dispositivo_iot };
}
function newmanOnce(vars) {
  let newman;
  try { newman = require('newman'); }
  catch { newman = require(path.join(path.dirname(process.execPath), 'node_modules', 'newman')); }
  return new Promise((resolve, reject) => newman.run({
    collection: path.join(__dirname, 'TC-M09-G131.postman_collection.json'),
    reporters: ['cli'],
    envVar: Object.entries(vars).map(([key, value]) => ({ key, value: String(value) })),
    timeoutRequest: 30000
  }, (err, summary) => {
    const ex = summary?.run?.executions?.[0];
    if (err || !ex?.response) reject(new Error(`Newman: ${clean(err?.message || 'sin respuesta HTTP')}`));
    else resolve({ status: ex.response.code, body: (() => { try { return JSON.parse(ex.response.stream.toString('utf8')); } catch { return null; } })(), assertions: ex.assertions?.map(a => ({ name: a.assertion, error: a.error?.message || null })) || [] });
  }));
}
async function main() {
  evidence.git = {
    rama: git(['branch','--show-current']), status_short: git(['status','--short']),
    diff_stat: git(['diff','--stat']), diff_cached_stat: git(['diff','--cached','--stat']),
    head: git(['rev-parse','HEAD']), origin_test: git(['rev-parse','origin/test']),
    divergencia: git(['rev-list','--left-right','--count','HEAD...origin/test'])
  };
  if (evidence.git.rama !== 'qa/juan-esteban-rf24-v2') throw new Error('La rama QA requerida no está activa.');
  const oa = await request('GET', '/openapi.json');
  if (oa.status !== 200) throw new Error(`OpenAPI inaccesible: HTTP ${oa.status}.`);
  const api = oa.body;
  const post = api.paths?.['/configuracion/sensores/{id_sensor}/calibrar']?.post;
  const history = api.paths?.['/configuracion/sensores/{id_sensor}/calibraciones']?.get;
  const schema = api.components?.schemas?.RegistrarCalibracionDTO;
  const mode = schema?.properties?.modo_calibracion;
  evidence.openapi = { endpoints: { calibrar: Boolean(post), calibraciones: Boolean(history) },
    modo_calibracion_declarado: Boolean(mode), required: schema?.required?.includes('modo_calibracion') || false,
    dominio: mode?.enum || mode?.anyOf?.flatMap(x => x.enum || []) || [] };
  if (!post || !history) throw new Error('Endpoint de calibración o historial ausente en OpenAPI TEST.');
  const token = await login(email, password);
  const identity = await get('/usuarios/me', token, null);
  const perms = await get('/sesiones/me/permisos', token, null);
  evidence.actor = { id_usuario: identity.body.id_usuario, correo: identity.body.correo_electronico,
    rol: identity.body.nombre_rol, estado: identity.body.estado_cuenta,
    permisos_calibracion: (perms.body.permisos || []).filter(p => p.id_recurso === 12).map(p => p.id_accion) };
  if (evidence.actor.correo !== email || evidence.actor.rol !== 'Ingeniero de Campo' || evidence.actor.estado !== 'Activo' ||
    !evidence.actor.permisos_calibracion.includes(1) || !evidence.actor.permisos_calibracion.includes(2))
    throw new Error('Identidad, estado o permisos del Ingeniero no cumplen las precondiciones.');
  let readToken = null;
  let readEmail = null;
  const adminAttempts = [];
  if (process.env.QA_ADMIN_PASSWORD) {
    for (const candidate of ['admin.dev@gmail.com', 'administador.dev@gmail.com']) {
      try {
        const candidateToken = await login(candidate, process.env.QA_ADMIN_PASSWORD);
        const probe = await request('GET', '/configuracion/dispositivos-iot/1', candidateToken);
        adminAttempts.push({ correo: candidate, login: 200, get_dispositivo_1: probe.status });
        if (probe.status === 200) { readToken = candidateToken; readEmail = candidate; break; }
      } catch (e) { adminAttempts.push({ correo: candidate, resultado: clean(e.message) }); }
    }
  }
  evidence.actor.actor_auxiliar_get = readEmail;
  evidence.actor.intentos_admin = adminAttempts;
  const ranges = (await get('/configuracion/sensores/rangos-calibracion', token, readToken)).body;
  const fixtures = await findFixtures(token, readToken, ranges);
  evidence.fixtures = { ...evidence.fixtures, ...fixtures };
  const plan = [
    { id:'TC-M09-258', v:'—', f: fixtures.f258, body: { modo_calibracion:'SENSOR', id_dispositivo_iot:fixtures.alterno, id_infraestructura:fixtures.f258.area, valor_referencia:10.0000, observaciones:'QA TC-M09-258' } },
    { id:'TC-M09-259', v:'—', f: fixtures.f259, body: { id_dispositivo_iot:fixtures.f259.dispositivo, id_infraestructura:fixtures.f259.area, valor_referencia:22.5000, observaciones:'QA TC-M09-259' } },
    { id:'TC-M09-260', v:'OTRO', f: fixtures.f259, body: { modo_calibracion:'OTRO', id_dispositivo_iot:fixtures.f259.dispositivo, id_infraestructura:fixtures.f259.area, valor_referencia:22.5000, observaciones:'QA TC-M09-260' } },
    { id:'TC-M09-260', v:'VACIO', f: fixtures.f259, body: { modo_calibracion:'', id_dispositivo_iot:fixtures.f259.dispositivo, id_infraestructura:fixtures.f259.area, valor_referencia:22.5000, observaciones:'QA TC-M09-260' } }
  ];
  for (const step of plan) {
    const r = resultRef(step.id, step.v);
    const route = `/configuracion/sensores/${step.f.sensor}/calibraciones`;
    r.sensor = step.f.sensor;
    r.pre = snapshot((await get(route, token, null)).body);
    const body = { ...step.body, fecha_calibracion: new Date().toISOString() };
    const literal = step.id === 'TC-M09-258' ? '10.0000' : '22.5000';
    const bodyJson = JSON.stringify(body).replace(/"valor_referencia":(?:10|22\.5)(?=,)/, `"valor_referencia":${literal}`);
    r.request = { ruta: `/configuracion/sensores/${step.f.sensor}/calibrar`, body: JSON.parse(bodyJson), valor_referencia_literal: literal };
    evidence.post_ejecutados += 1;
    try {
      const response = await newmanOnce({ base_url: base, sensor_id: step.f.sensor, token, body_json: bodyJson });
      r.http = response.status;
      r.error_code = response.body?.error_code || null;
      r.mensaje = clean(response.body?.message || response.body?.detail || '');
      r.id_respuesta = response.body?.id_calibracion || null;
      r.assertions_newman = response.assertions;
    } catch (e) { r.error_ejecucion = clean(e.message); }
    // Reconciliación inmediata incluso si Newman no obtuvo respuesta.
    try { r.post = snapshot((await get(route, token, null)).body); }
    catch (e) { r.error_historial_post = clean(e.message); }
    const changed = r.post && (r.pre.total !== r.post.total || JSON.stringify(r.pre.ids) !== JSON.stringify(r.post.ids));
    const created = changed && r.post.ids.some(x => !r.pre.ids.includes(x));
    r.ids_creados = created ? r.post.ids.filter(x => !r.pre.ids.includes(x)) : [];
    if (changed || r.http && !(r.http >= 400 && r.http < 500)) {
      r.resultado = 'RECHAZADO';
      r.motivo = changed ? `El historial cambió tras la petición inválida; IDs nuevos: ${r.ids_creados.join(', ') || 'ninguno'}.` : `TEST respondió HTTP ${r.http}, fuera de 4xx.`;
    } else if (r.http >= 400 && r.http < 500 && r.post) {
      r.resultado = 'APROBADO'; r.motivo = `HTTP ${r.http}; total e IDs del historial sin cambios.`;
    } else { r.resultado = 'BLOQUEADO / NO VERIFICABLE'; r.motivo = 'No fue posible verificar la respuesta o el historial posterior.'; }
    if (created || !r.post || !r.http) {
      evidence.stop_all = true;
      evidence.motivo_stop_all = created ? `Persistencia inesperada en ${step.id} ${step.v}; IDs ${r.ids_creados.join(', ')}.` : `Ejecución ambigua en ${step.id} ${step.v}; no se arriesgan más POST.`;
      markRemaining('NO EJECUTADO', `STOP_ALL: ${evidence.motivo_stop_all}`);
      break;
    }
  }
  const rejected = cases.filter(([id,v]) => resultRef(id,v).resultado === 'RECHAZADO');
  if (rejected.length) evidence.incidencias.push({ grupo_responsable:'Por determinar', casos:[...new Set(rejected.map(x=>x[0]))],
    motivo:'Una o más peticiones inválidas incumplieron el oráculo RF-24 v2.0.',
    obtenido:rejected.map(([id,v]) => `${id}/${v}: HTTP ${resultRef(id,v).http}; ${resultRef(id,v).motivo}`).join(' '),
    causa_raiz:'Por determinar; contrastar contrato desplegado y código sin inferirla solo de la API.',
    type:'bug', severity:'Important', priority:'High' });
}
main().catch(e => { evidence.motivo_general = `BLOQUEADO: ${clean(e.message)}`; markRemaining('BLOQUEADO / NO VERIFICABLE', evidence.motivo_general); })
  .finally(finalize);
