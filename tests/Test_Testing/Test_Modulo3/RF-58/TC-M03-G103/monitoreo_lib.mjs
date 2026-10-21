// Librería común del lote G102–G104 (RF-58 / CU04, dashboard de monitoreo).
// Copia idéntica en TC-M03-G102, TC-M03-G103 y TC-M03-G104: cada carpeta es autónoma.
//
// Contiene solo mecanismos (barrera, versión, sandbox, preparación por APIs oficiales,
// ejecución de Newman/Cypress y veredicto). Los casos, aserciones y escenarios de cada
// grupo viven en su propio ejecutor.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';

// Ningún mecanismo local puede usar la red por accidente: solo `req` (ejecución autorizada)
// usa la referencia real.
export const fetchReal = globalThis.fetch;
globalThis.fetch = async () => { throw Error('BLOQUEO_RED_M03_MONITOREO'); };

export const POR_VISTA = 50;

export function leerEnv(texto) {
  const v = {};
  for (const linea of texto.split(/\r?\n/)) {
    const m = linea.match(/^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*)$/);
    if (m) v[m[1]] = m[2].trim().replace(/^(['"])(.*)\1$/, '$2');
  }
  return v;
}

/** Barrera del ejecutor: TEST explícito, referencia de Desarrollo, cuentas y destinos HTTPS distintos de DEV. */
export function autorizar(v, a, { roles = ['SETUP', 'ENG'], frontend = false } = {}) {
  const motivos = [];
  if (v.QA_AUTORIZADO !== 'SI') motivos.push('QA_AUTORIZADO debe ser SI');
  if (a.ambiente !== 'TEST') motivos.push('Ambiente distinto de TEST');
  if (!a.autorizacion || a.autorizacion.trim().length < 8) motivos.push('Falta referencia verificable de Desarrollo');
  if (!(a.efectos || []).includes('notificacion-login')) motivos.push('Falta aceptar notificacion-login');
  for (const rol of roles) {
    if (!v[`QA_${rol}_EMAIL`]) motivos.push(`Falta QA_${rol}_EMAIL`);
    if (!(v[`QA_${rol}_PASSWORD`] || v.QA_COMMON_PASSWORD)) motivos.push(`Falta contraseña QA ${rol}`);
  }
  if (!v.QA_SANDBOX_SECRET) motivos.push('Falta QA_SANDBOX_SECRET');
  const dev = /(^|[-/.])dev([-/.]|$)/i;
  const api = v.SIGAB_API_TEST_BASE?.replace(/\/+$/, '');
  if (api !== 'https://www.api.inmero.co/api-sgpmp-test') motivos.push('API no coincide con la URL oficial de TEST');
  if (!/^https:\/\//i.test(api || '') || dev.test(api || '')) motivos.push('API no es HTTPS TEST');
  if (v.SIGAB_API_BASE && v.SIGAB_API_BASE.replace(/\/+$/, '') !== api) motivos.push('Alias de API distinto de TEST');
  if (api && api === v.SIGAB_API_DEV_BASE?.replace(/\/+$/, '')) motivos.push('API coincide con DEV');
  const front = v.SIGAB_FRONT_TEST_URL?.replace(/\/+$/, '');
  if (frontend) {
    if (front !== 'https://api.inmero.co/sigab-test') motivos.push('Frontend no coincide con la URL oficial de TEST');
    if (!/^https:\/\//i.test(front || '') || dev.test(front || '')) motivos.push('Frontend no es HTTPS TEST');
    if (v.SIGAB_FRONT_URL && v.SIGAB_FRONT_URL.replace(/\/+$/, '') !== front) motivos.push('Alias frontend distinto de TEST');
    if (front && front === v.SIGAB_FRONT_DEV_URL?.replace(/\/+$/, '')) motivos.push('Frontend coincide con DEV');
  }
  if (v.QA_DEVICE_PREFIX && !/^[A-Za-z0-9][A-Za-z0-9_-]{1,19}$/.test(v.QA_DEVICE_PREFIX)) motivos.push('QA_DEVICE_PREFIX con formato inválido');
  return { ok: motivos.length === 0, motivos, api, front };
}

/**
 * Versión de la evaluación a partir del historial de la carpeta del grupo (una sola
 * implementación para V1, V2, ...). ABORTADA_PREFLIGHT no consume versión; reintento la conserva.
 */
export function version(dir, tipo, confirmada) {
  const dirs = fs.readdirSync(dir, { withFileTypes: true }).filter(x => x.isDirectory()).map(x => /^EvaluacionV(\d+)$/.exec(x.name)?.[1]).filter(Boolean).map(Number);
  const ultima = Math.max(1, ...dirs);
  const base = n => n === 1 ? path.join(dir, 'RESULTADOS') : path.join(dir, `EvaluacionV${n}`, 'RESULTADOS');
  const runs = fs.existsSync(base(ultima)) ? fs.readdirSync(base(ultima)).map(x => { try { return JSON.parse(fs.readFileSync(path.join(base(ultima), x, 'evidencia.json'), 'utf8')).estado; } catch { return 'INCIERTO'; } }) : [];
  const n = tipo === 'reintento' ? (runs.length ? ultima : null) : !runs.length ? ultima : runs.includes('CONCLUIDA') ? ultima + 1 : runs.every(x => x === 'ABORTADA_PREFLIGHT') ? ultima : null;
  if (!n || (confirmada && Number(confirmada) !== n)) throw Error('Historial ambiguo o versión incoherente');
  return n;
}
export const carpetaResultados = (dir, n) => n === 1 ? path.join(dir, 'RESULTADOS') : path.join(dir, `EvaluacionV${n}`, 'RESULTADOS');
export const runId = (grupo, n, sello) => `${grupo.replace('TC-M03-', '')}-${n === 1 ? 'EVAL' : 'REEVAL'}-V${n}-${sello}`;
export const nombreInforme = (grupo, n) => n === 1 ? `${grupo}_resultado.md` : `${grupo}_reevaluacion_V${n}.md`;

export function argumentos(argv) {
  const a = { modo: 'local', efectos: [] };
  for (let i = 0; i < argv.length; i++) {
    const x = argv[i];
    if (x === '--ejecutar') a.modo = 'ejecutar';
    else if (x === '--validar-local') a.modo = 'local';
    else if (['--ambiente', '--autorizacion', '--tipo', '--version'].includes(x)) a[x.slice(2)] = argv[++i];
    else if (x === '--aceptar-efectos') a.efectos.push(...String(argv[++i] || '').split(','));
    else throw Error(`Argumento desconocido: ${x}`);
  }
  return a;
}
export function newmanModulo(root) {
  const npm = spawnSync('npm', ['root', '-g'], { encoding: 'utf8', shell: process.platform === 'win32' });
  if (npm.status !== 0) throw Error('Newman no disponible');
  const m = createRequire(path.join(root, 'package.json'))(path.join(npm.stdout.trim(), 'newman'));
  if (typeof m.run !== 'function') throw Error('Newman sin API run');
  return m;
}
export const cypressModulo = root => createRequire(path.join(root, 'package.json'))('cypress');

export const sello = () => new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14);
/** Serial QA de un dispositivo del RUN: QA_DEVICE_PREFIX opcional (QAAUTO si está vacío). */
export function serialQa(v, grupo, marca, sufijo) {
  const s = `${v.QA_DEVICE_PREFIX || 'QAAUTO'}-${grupo}-${marca}${sufijo ? `-${sufijo}` : ''}`;
  if (s.length > 50 || !/^[A-Za-z0-9_-]+$/.test(s)) throw Error('Serial QA fuera de formato');
  return s;
}
export const nombreSensor = (prefijo, unidad, i) => `${prefijo} ${unidad} S${String(i).padStart(3, '0')}`;

// ---- Contratos de dispositivo (punto único de adaptación para DEV-06 / DEV-11–13) ----------
// Hoy el dispositivo se identifica con access_key = serial. DEV-06 lo sustituirá por un token de
// servicio cuyo contrato aún no está definido: no se inventa; solo se cambiará aquí.
export function cuerpoLectura({ idDispositivo, idSensor, serial, timestamp, valor = 25 }) {
  return {
    device_id: idDispositivo, sensor_id: idSensor, access_key: serial, tipo_variable: 'TEMPERATURA_AMBIENTAL', valor, unidad: '°C',
    timestamp_captura: timestamp, origen: 'TIEMPO_REAL', estado_conectividad: true, nivel_bateria: 87, calidad_senal_rssi: -71, calidad_senal_snr: 7.5,
  };
}
export function cuerpoAlerta({ idDispositivo, idSensor, serial, idTelemetria, severidad, valor = 25 }) {
  if (!['LEVE', 'MODERADO', 'CRITICO'].includes(severidad)) throw Error('Severidad fuera del contrato RF-57');
  return {
    device_id: idDispositivo, sensor_id: idSensor, access_key: serial, tipo_variable: 'TEMPERATURA_AMBIENTAL', valor, unidad: '°C',
    timestamp_evento: new Date().toISOString(), estado_dato: 'LECTURA_VALIDA', severidad_edge: severidad, origen_evento: 'EDGE', id_telemetria: idTelemetria, reglas_activadas: [],
  };
}

// ---- /test-control/query: {"data": [filas]}; un fallo es null (no verificable), nunca 0 -----
export function filas(r) { return r?.status === 200 && Array.isArray(r?.data?.data) ? r.data.data : null; }
export function leerConteo(r) { const f = filas(r); if (!f || !f[0]) return null; const n = Number(f[0].n); return Number.isFinite(n) ? n : null; }
/** Testigo de aislamiento sin RLS: el INSERT del dispositivo en auditoria.logs_dml (trigger incondicional SECURITY DEFINER). */
export function consultaTestigoDispositivo(serial) {
  if (!/^[A-Za-z0-9_-]{1,50}$/.test(serial)) throw Error('Serial no apto para el testigo');
  return `SELECT count(*) AS n FROM auditoria.logs_dml WHERE esquema_afectado = 'modulo9' AND tabla_afectada = 'dispositivos_iot' AND tipo_operacion = 'INSERT' AND datos_nuevos->>'serial' = '${serial}'`;
}
/** modulo3 no tiene RLS: el conteo de estados actuales es fiable para comprobar la precondición. */
export function consultaEstadosActuales(ids) {
  if (!ids.length || !ids.every(x => Number.isSafeInteger(x) && x > 0)) throw Error('IDs de sensor no aptos');
  return `SELECT count(*) AS n FROM modulo3.estados_actuales_sensores WHERE id_sensor IN (${ids.join(',')})`;
}

// ---- Clasificación de aserciones por su nombre ------------------------------------------
// Formato: [TC-M03-XXX][PRE|ASSERT|INFO][ID-XXX-NN][V:VARIANTE] texto
export const casoDeTexto = t => (String(t).match(/TC-M03-\d{3}/) || [null])[0];
export const idDeTexto = t => (String(t).match(/\[((?:API|UI|PERF)-\d{3}-\d{2})\]/) || [null, null])[1];
export const varianteDeTexto = t => (String(t).match(/\[V:([A-Z0-9_]+)\]/) || [null, null])[1];
export const tipoDeTexto = t => /\[PRE\]/.test(t) ? 'PRE' : /\[ASSERT\]/.test(t) ? 'ASSERT' : /\[INFO\]/.test(t) ? 'INFO' : null;
export const claveAsercion = a => a.variante ? `${a.id}@${a.variante}` : a.id;

/**
 * Veredicto propuesto por caso.
 * - BLOQUEADO: RUN no concluido o rollback no confirmado; o falta cobertura, hay bloqueos,
 *   precondiciones o errores de automatización sin evidencia de incumplimiento.
 * - RECHAZADO: un [ASSERT] incumplido con respuesta real del producto, en un escenario cuya
 *   precondición ([PRE] de la misma variante, o general) no falló.
 * - APROBADO: todas las aserciones requeridas verificadas y ninguna falla.
 * INFO nunca decide.
 */
export function veredictoCasos({ casos, requeridas, estado, rollback, aserciones, bloqueos = {} }) {
  const out = {};
  for (const caso of casos) {
    const propias = aserciones.filter(a => a.caso === caso && a.tipo !== 'INFO');
    const invalidas = new Set(propias.filter(a => a.tipo !== 'ASSERT' && !a.ok).map(a => a.variante ?? '*'));
    const rechazo = propias.some(a => a.tipo === 'ASSERT' && !a.ok && a.evidencia && !invalidas.has('*') && !invalidas.has(a.variante ?? '*'));
    const completas = (requeridas[caso] || []).every(k => propias.some(a => claveAsercion(a) === k && a.tipo === 'ASSERT' && a.ok));
    let v;
    if (estado !== 'CONCLUIDA' || !rollback) v = 'BLOQUEADO';
    else if (rechazo) v = 'RECHAZADO';
    else if ((bloqueos[caso] || []).length || propias.some(a => !a.ok) || !completas || !(requeridas[caso] || []).length) v = 'BLOQUEADO';
    else v = 'APROBADO';
    out[caso] = v;
  }
  const estados = Object.values(out);
  return { casos: out, grupo: estados.includes('RECHAZADO') ? 'RECHAZADO' : estados.length && estados.every(x => x === 'APROBADO') ? 'APROBADO' : 'BLOQUEADO' };
}

/** Estadísticos de muestras de tiempo (ms). */
export function estadisticos(ms) {
  const x = ms.filter(n => Number.isFinite(n)).sort((a, b) => a - b);
  if (!x.length) return null;
  const q = p => x[Math.min(x.length - 1, Math.ceil(p * x.length) - 1)];
  return { n: x.length, min: x[0], mediana: q(0.5), p95: q(0.95), max: x.at(-1) };
}

// ---- Sandbox del RUN ------------------------------------------------------------------------
/**
 * Peticiones SIEMPRE secuenciales: el sandbox comparte una sola sesión de base de datos por RUN.
 * Toda respuesta de negocio debe traer el eco X-Test-Run-Id del RUN.
 */
export function sandbox({ api, run, secreto }) {
  async function req(m, ruta, { body, token, control = false, runId = run } = {}) {
    const headers = { Accept: 'application/json', 'X-Sandbox-Secret': secreto };
    if (!control) headers['X-Test-Run-Id'] = runId;
    if (token) headers.Authorization = `Bearer ${token}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const r = await fetchReal(`${api}${ruta}`, { method: m, headers, body: body === undefined ? undefined : JSON.stringify(body), redirect: 'manual', signal: AbortSignal.timeout(30000) });
    const data = await r.json().catch(() => null);
    if (!control && r.headers.get('x-test-run-id') !== runId) throw Error(`Sandbox sin eco: ${m} ${ruta}`);
    return { status: r.status, data };
  }
  const need = (r, status, etiqueta) => { if (r.status !== status) throw Error(`${etiqueta}: HTTP ${r.status} ${JSON.stringify(r.data ?? '').slice(0, 300)}`); return r.data; };
  const sql = (query, rid = run) => req('POST', '/test-control/query', { body: { query }, runId: rid });
  async function sondaExterna(serial, sufijo) {
    const rid = `${run}-${sufijo}`;
    try { return leerConteo(await sql(consultaTestigoDispositivo(serial), rid)); } finally { await req('DELETE', `/test-control/runs/${rid}`, { control: true }); }
  }
  async function abrir() {
    const probe = await req('DELETE', `/test-control/runs/${run}-PREFLIGHT`, { control: true });
    if (probe.status !== 404 || !/Run ID no encontrado/i.test(String(probe.data?.detail ?? ''))) throw Error(`Sandbox no disponible: HTTP ${probe.status}`);
  }
  async function aislamiento(serial) {
    const dentro = leerConteo(await sql(consultaTestigoDispositivo(serial))), fuera = await sondaExterna(serial, 'SONDA');
    const r = { testigo: 'auditoria.logs_dml (INSERT del dispositivo)', dentro, fuera, demostrado: dentro === 1 && fuera === 0 };
    if (!r.demostrado) throw Error(`Aislamiento no demostrado (dentro=${dentro}, fuera=${fuera}; null = no verificable)`);
    return r;
  }
  /** Cierra el RUN y confirma el rollback: cierre 200, segundo cierre 404 y testigo en 0 fuera del RUN. */
  async function cerrar(serial) {
    const c = await req('DELETE', `/test-control/runs/${run}`, { control: true });
    const d = await req('DELETE', `/test-control/runs/${run}`, { control: true });
    const resto = serial ? await sondaExterna(serial, 'POST') : 0;
    return { cierre: c.status, segundo_cierre: d.status, sonda_posterior: resto, rollback: c.status === 200 && d.status === 404 && resto === 0 };
  }
  async function login(email, contrasena, etiqueta, patronRol) {
    const d = need(await req('POST', '/sesiones/', { body: { correo_electronico: email, contrasena } }), 200, `Login ${etiqueta}`);
    if (!d?.token) throw Error(`Login ${etiqueta} sin token`);
    const me = need(await req('GET', '/usuarios/me', { token: d.token }), 200, `Identidad ${etiqueta}`);
    if (!patronRol.test(me.nombre_rol || '')) throw Error(`La cuenta QA ${etiqueta} no tiene el rol esperado`);
    return { token: d.token, id: me.id_usuario };
  }
  return { req, need, sql, sondaExterna, abrir, aislamiento, cerrar, login };
}

// ---- Preparación con APIs oficiales ---------------------------------------------------------
export async function catalogos(sb, tok) {
  const get = async (ruta, e) => sb.need(await sb.req('GET', ruta, { token: tok }), 200, e).items || [];
  const tipo = (await get('/configuracion/tipos-area?solo_activos=true', 'Tipos de área')).find(x => x.es_activo);
  const especie = (await get('/configuracion/especies?solo_activas=true', 'Especies')).find(x => x.es_activo);
  const tipoDisp = (await get('/configuracion/tipos-dispositivo-iot', 'Tipos de dispositivo')).filter(x => x.categoria === 'SENSOR').sort((a, b) => a.id_tipo_dispositivo - b.id_tipo_dispositivo)[0];
  const rango = (await get('/configuracion/sensores/rangos-calibracion', 'Rangos de calibración')).find(x => x.categoria === 'TEMPERATURA');
  if (!tipo || !especie || !tipoDisp || !rango) throw Error('Catálogos insuficientes (tipo de área, especie, tipo SENSOR o rango TEMPERATURA)');
  return { tipo, especie, tipoDisp, rango };
}
/**
 * Finca con alcance del actor del dashboard: una compartida con la cuenta de preparación o, si no
 * existe, una nueva creada con id_usuario del actor (no modifica sus asignaciones previas).
 */
export async function fincaConAcceso(sb, { tokSetup, tokActor, idActor, nombre }) {
  const ids = async t => (sb.need(await sb.req('GET', '/configuracion/fincas', { token: t }), 200, 'Fincas').items || []).map(f => Number(f.id_finca));
  const delActor = new Set(await ids(tokActor));
  const compartida = (await ids(tokSetup)).find(id => delActor.has(id));
  if (compartida) return { id: compartida, origen: 'existente compartida (solo se le agregan áreas QA)' };
  const id = sb.need(await sb.req('POST', '/configuracion/fincas', { token: tokSetup, body: { nombre: nombre.replace(/\d/g, d => 'abcdefghij'[Number(d)]), ubicacion: { departamento: 'Huila', municipio: 'Neiva', vereda: 'QA', latitud: 2.9273, longitud: -75.2819 }, tamano_h: 1, id_usuario: idActor } }), 201, 'Crear finca QA').id_finca;
  return { id, origen: 'creada en el RUN con acceso del actor' };
}
/**
 * Unidad productiva QA con N sensores activos: área, un dispositivo sin gateway (sin MQTT) y por
 * cada sensor registro, asociación, calibración y una lectura válida (RF-53).
 * `alCrearDispositivo` permite comprobar el aislamiento antes de enviar lecturas.
 */
export async function construirUnidad(sb, { tok, cat, finca, run, nombreUnidad, serial, nombres, alCrearDispositivo }) {
  const area = sb.need(await sb.req('POST', '/configuracion/infraestructuras', { token: tok, body: { nombre_infraestructura: nombreUnidad, tipo_area: cat.tipo.nombre, superficie: 25, finca_id: finca, descripcion_infraestructura: `QA ${run}`, especie_id: cat.especie.id_especie } }), 201, `Crear área ${nombreUnidad}`);
  const disp = sb.need(await sb.req('POST', '/configuracion/dispositivos-iot', { token: tok, body: { serial, descripcion: nombreUnidad, id_infraestructura: area.id_infraestructura, id_tipo_dispositivo: cat.tipoDisp.id_tipo_dispositivo, es_activo: true } }), 201, `Registrar dispositivo de ${nombreUnidad}`);
  if (alCrearDispositivo) await alCrearDispositivo(disp);
  const referencia = Number(((Number(cat.rango.valor_min) + Number(cat.rango.valor_max)) / 2).toFixed(2));
  const sensores = [];
  for (const nombre of nombres) {
    const s = sb.need(await sb.req('POST', `/configuracion/dispositivos-iot/${disp.id_dispositivo_iot}/sensores`, { token: tok, body: { nombre, categoria: 'TEMPERATURA' } }), 201, `Registrar ${nombre}`);
    sb.need(await sb.req('POST', `/configuracion/sensores/${s.id_sensores}/asociar`, { token: tok, body: { id_dispositivo_iot: disp.id_dispositivo_iot, id_infraestructura: area.id_infraestructura, punto_instalacion: 'QA' } }), 201, `Asociar ${nombre}`);
    sb.need(await sb.req('POST', `/configuracion/sensores/${s.id_sensores}/calibrar`, { token: tok, body: { id_dispositivo_iot: disp.id_dispositivo_iot, id_infraestructura: area.id_infraestructura, valor_referencia: referencia, ganancia: 1, offset: 0, fecha_calibracion: new Date(Date.now() - 600000).toISOString(), observaciones: `QA ${run}`, modo_calibracion: 'SENSOR' } }), 201, `Calibrar ${nombre}`);
    const l = sb.need(await sb.req('POST', '/iot/telemetria', { body: cuerpoLectura({ idDispositivo: disp.id_dispositivo_iot, idSensor: s.id_sensores, serial, timestamp: new Date(Date.now() - 30000).toISOString() }) }), 201, `Lectura de ${nombre}`);
    if (l.estado_calidad !== 'LECTURA_VALIDA') throw Error(`La lectura de ${nombre} no quedó LECTURA_VALIDA (${l.estado_calidad})`);
    sensores.push({ id: s.id_sensores, nombre, id_telemetria: l.id_telemetria });
  }
  return { id: area.id_infraestructura, nombre: nombreUnidad, id_dispositivo: disp.id_dispositivo_iot, serial, sensores };
}
/** Precondición: cada sensor construido tiene estado actual (base del dashboard). Null = no verificable. */
export async function estadosActualesCompletos(sb, unidad) {
  const n = leerConteo(await sb.sql(consultaEstadosActuales(unidad.sensores.map(s => Number(s.id)))));
  return { esperados: unidad.sensores.length, encontrados: n, ok: n === unidad.sensores.length };
}

// ---- Herramientas -------------------------------------------------------------------------
export async function correrNewman(newman, coleccion, vars, { iteraciones = 1, limpiar = x => x } = {}) {
  const nr = await new Promise(resolve => newman.run({ ignoreRedirects: true,  collection: coleccion, environment: { values: Object.entries(vars).map(([key, value]) => ({ key, value: String(value) })) }, iterationCount: iteraciones, reporters: [], silent: true }, (error, summary) => resolve({ error, summary })));
  const aserciones = [], muestras = [], errores = [];
  for (const e of nr.summary?.run?.executions || []) {
    const http = e.response?.code ?? null;
    muestras.push({ peticion: e.item?.name, iteracion: e.cursor?.iteration ?? 0, http, ms: e.response?.responseTime ?? null, bytes: e.response?.responseSize ?? null });
    for (const x of e.assertions || []) {
      const nombre = String(x.assertion);
      aserciones.push({ herramienta: 'Newman', caso: casoDeTexto(nombre) ?? casoDeTexto(e.item?.name), tipo: tipoDeTexto(nombre), id: idDeTexto(nombre), variante: varianteDeTexto(nombre) ?? varianteDeTexto(e.item?.name), nombre, ok: !x.error && !x.skipped, evidencia: http != null, http, error: x.error ? limpiar(x.error.message) : undefined });
    }
  }
  for (const f of (nr.summary?.run?.failures || []).filter(f => !/AssertionError/.test(f.error?.name || ''))) errores.push({ caso: casoDeTexto(f.source?.name), mensaje: limpiar(`AUTOMATIZACION: error de script en «${f.source?.name ?? ''}»: ${f.error?.message}`) });
  if (nr.error) errores.push({ caso: null, mensaje: limpiar(`AUTOMATIZACION: Newman — ${nr.error.message}`) });
  return { aserciones, muestras, errores };
}
/** Cypress con reporter de consola (no escribe fuera de la carpeta del RUN). Un fallo de hook es [PRE]. */
export async function correrCypress(cypress, { root, spec, front, out, env, etiqueta, limpiar = x => x }) {
  const r = await cypress.run({ project: root, spec, quiet: true, env, config: { baseUrl: front, supportFile: false, fixturesFolder: false, video: false, screenshotOnRunFailure: true, screenshotsFolder: path.join(out, 'capturas'), downloadsFolder: path.join(out, 'descargas'), trashAssetsBeforeRuns: false, specPattern: path.relative(root, spec).split(path.sep).join('/'), testIsolation: false, retries: 0, reporter: 'spec', defaultCommandTimeout: 15000 } });
  if (!r || r.status === 'failed') return { lanzado: false, mensaje: limpiar(`AUTOMATIZACION: Cypress (${etiqueta}) no pudo ejecutarse: ${r?.message ?? ''}`), aserciones: [] };
  const aserciones = [];
  for (const t of (r.runs || []).flatMap(x => x.tests || [])) {
    const nombre = Array.isArray(t.title) ? t.title.at(-1) : String(t.title || '');
    const err = String(t.displayError || '');
    const hook = /before all|before each|after all|after each/i.test(err);
    aserciones.push({ herramienta: `Cypress ${etiqueta}`, caso: casoDeTexto(nombre), tipo: hook ? 'PRE' : tipoDeTexto(nombre), id: idDeTexto(nombre), variante: varianteDeTexto(nombre), nombre, ok: t.state === 'passed', evidencia: t.state === 'failed' && !hook, error: err ? limpiar(err.split(/\r?\n/).slice(0, 3).join(' ')) : undefined });
  }
  return { lanzado: true, aserciones, resumen: { total: r.totalTests, passed: r.totalPassed, failed: r.totalFailed, skipped: r.totalSkipped } };
}

// ---- Evidencia ------------------------------------------------------------------------------
export function redactor(secretos) {
  return x => secretos.filter(s => s && String(s).length > 3).reduce((s, y) => s.replaceAll(String(y), '[REDACTADO]'), String(x)).replace(/eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}/g, '[JWT]');
}
export function informe({ grupo, n, run, ev, casos, extra = '' }) {
  const fila = c => `| ${c} | ${ev.veredicto?.casos?.[c] ?? 'BLOQUEADO'} |`;
  const fallas = (ev.aserciones || []).filter(a => !a.ok && a.tipo !== 'INFO').map(a => `- [${a.tipo}] ${a.nombre}${a.error ? ` — ${a.error}` : ''}`).join('\n') || '- ninguna';
  const info = (ev.aserciones || []).filter(a => a.tipo === 'INFO').map(a => `- ${a.nombre}`).join('\n') || '- ninguna';
  return `# ${grupo} — ${n === 1 ? 'EVALUACIÓN V1' : `REEVALUACIÓN V${n}`}

> Borrador técnico generado automáticamente; QA revisa la evidencia antes de emitir el dictamen.

Casos: ${casos.join(', ')} · RUN_ID: \`${run}\` · Ambiente: TEST · Estado técnico: ${ev.estado}

| Caso | Resultado propuesto |
| --- | --- |
${casos.map(fila).join('\n')}
| **Grupo** | **${ev.veredicto?.grupo ?? 'BLOQUEADO'}** |

## Escenario preparado
${JSON.stringify(ev.datos)}

## Aserciones no superadas
${fallas}

## Información registrada (no decisoria)
${info}

## Bloqueos y dependencias
Bloqueos por caso: ${JSON.stringify(ev.bloqueos)}

Dependencias: ${(ev.dependencias || []).join('; ') || 'ninguna'}

## Sandbox
Aislamiento: ${JSON.stringify(ev.sandbox?.aislamiento || {})} · Rollback: ${ev.sandbox?.rollback ? 'confirmado' : 'NO confirmado'} (${JSON.stringify(ev.sandbox?.cierre || {})})
${extra}
Detalle completo en \`evidencia.json\`.
`;
}

// ---- Comprobaciones locales comunes ---------------------------------------------------------
/** Sintaxis de todos los scripts de la colección, incluidos los de nivel colección. */
export function sintaxisColeccion(col) {
  const eventos = [...(col.event || []), ...(col.item || []).flatMap(x => x.event || [])];
  for (const e of eventos) new Function('pm', (e.script?.exec || []).join('\n'));
  return eventos.length;
}
export function nombresDeTests(col) {
  const texto = [...(col.event || []), ...(col.item || []).flatMap(x => x.event || [])].flatMap(e => e.script?.exec || []).join('\n');
  return [...texto.matchAll(/pm\.test\(\s*[`'"]([^`'"]+)[`'"]/g)].map(m => m[1]);
}
