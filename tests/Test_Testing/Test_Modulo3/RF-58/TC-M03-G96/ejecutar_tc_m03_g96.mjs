#!/usr/bin/env node
// TC-M03-187: catálogo externo de conectividad del monitoreo (ONLINE, OFFLINE, SIN_SEÑAL).
//
// Preparación de las tres condiciones de la matriz («conectado, desconectado y sin señal»):
//  - ONLINE (conectado): se CONSTRUYE en el sandbox con APIs oficiales: área QA, dispositivo
//    sin gateway, sensor calibrado y una lectura válida con estado_conectividad=true. El
//    trigger fn_actualizar_estado_sensor registra el estado interno ACTIVO.
//  - SIN_SEÑAL y OFFLINE: según RF-58 «proveniente de RF-60», es decir, la transición por
//    ausencia de reportes que calcula la tarea periódica global de RF-60. Esa tarea no ve el
//    sandbox y no hay disparador aislado, así que NO se construyen (enviar
//    estado_conectividad=false sería el estado comunicado por el dispositivo, no la ausencia
//    de reportes). Se DESCUBREN, en solo lectura, entre unidades del Productor.
// Si falta alguna condición, se evalúan las disponibles y el caso queda BLOQUEADO (sin
// cobertura completa); nunca se simulan estados ni se escribe SQL.
//
// Autenticación del dispositivo: hoy access_key = serial. DEV-06 la sustituirá por un token de
// servicio aún no definido; la adaptación se concentra en `cuerpoLectura` y en la cabecera de
// `ingerir` (pendiente del contrato, sin credenciales inventadas).
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

export const GRUPO = 'TC-M03-G96';
export const CASOS = ['TC-M03-187'];
export const ESTADOS = ['ONLINE', 'OFFLINE', 'SIN_SEÑAL'];
// Estado interno de estados_actuales_sensores que corresponde a cada condición de la matriz.
export const INTERNO = { ONLINE: 'ACTIVO', OFFLINE: 'INACTIVO', 'SIN_SEÑAL': 'SIN_SEÑAL' };
export const CONSTRUIBLES = ['ONLINE'];
const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const ENV = path.join(ROOT, '.env.qa');
const COLLECTION = path.join(DIR, `${GRUPO}.postman_collection.json`);
const fetchReal = globalThis.fetch;
globalThis.fetch = async () => { throw Error('BLOQUEO_RED_G96'); };

export function leerEnv(texto) {
  const v = {};
  for (const linea of texto.split(/\r?\n/)) {
    const m = linea.match(/^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*)$/);
    if (m) v[m[1]] = m[2].trim().replace(/^(['"])(.*)\1$/, '$2');
  }
  return v;
}
export function autorizar(v, a) {
  const motivos = [];
  if (v.QA_AUTORIZADO !== 'SI') motivos.push('QA_AUTORIZADO debe ser SI');
  if (a.ambiente !== 'TEST') motivos.push('Ambiente distinto de TEST');
  if (!a.autorizacion || a.autorizacion.trim().length < 8) motivos.push('Falta referencia verificable de Desarrollo');
  if (!a.efectos.includes('notificacion-login')) motivos.push('Falta aceptar notificacion-login');
  for (const k of ['QA_PROD_EMAIL', 'QA_SETUP_EMAIL', 'QA_SANDBOX_SECRET', 'SIGAB_API_TEST_BASE']) if (!v[k]) motivos.push(`Falta ${k}`);
  if (!(v.QA_PROD_PASSWORD || v.QA_COMMON_PASSWORD)) motivos.push('Falta contraseña QA del Productor');
  if (!(v.QA_SETUP_PASSWORD || v.QA_COMMON_PASSWORD)) motivos.push('Falta contraseña QA de preparación');
  const api = v.SIGAB_API_TEST_BASE?.replace(/\/+$/, '');
  if (api !== 'https://www.api.inmero.co/api-sgpmp-test') motivos.push('API no coincide con la URL oficial de TEST');
  if (!/^https:\/\//i.test(api || '') || /(^|[-/.])dev([-/.]|$)/i.test(api || '')) motivos.push('API no es HTTPS TEST');
  if (v.SIGAB_API_BASE && v.SIGAB_API_BASE.replace(/\/+$/, '') !== api) motivos.push('Alias de API distinto de TEST');
  if (api && api === v.SIGAB_API_DEV_BASE?.replace(/\/+$/, '')) motivos.push('API coincide con DEV');
  if (v.QA_DEVICE_PREFIX && !/^[A-Za-z0-9][A-Za-z0-9_-]{1,19}$/.test(v.QA_DEVICE_PREFIX)) motivos.push('QA_DEVICE_PREFIX con formato inválido');
  return { ok: motivos.length === 0, motivos, api };
}
export function version(dir, tipo, confirmada) {
  const dirs = fs.readdirSync(dir, { withFileTypes: true }).filter(x => x.isDirectory()).map(x => /^EvaluacionV(\d+)$/.exec(x.name)?.[1]).filter(Boolean).map(Number);
  const ultima = Math.max(1, ...dirs);
  const base = n => n === 1 ? path.join(dir, 'RESULTADOS') : path.join(dir, `EvaluacionV${n}`, 'RESULTADOS');
  const runs = fs.existsSync(base(ultima)) ? fs.readdirSync(base(ultima)).map(x => { try { return JSON.parse(fs.readFileSync(path.join(base(ultima), x, 'evidencia.json'), 'utf8')).estado; } catch { return 'INCIERTO'; } }) : [];
  const n = tipo === 'reintento' ? (runs.length ? ultima : null) : !runs.length ? ultima : runs.includes('CONCLUIDA') ? ultima + 1 : runs.every(x => x === 'ABORTADA_PREFLIGHT') ? ultima : null;
  if (!n || (confirmada && Number(confirmada) !== n)) throw Error('Historial ambiguo o versión incoherente');
  return n;
}
export function cobertura(estados) { return ESTADOS.every(x => estados.has(x)); }
export const clave = x => x === 'SIN_SEÑAL' ? 'sin_senal' : x.toLowerCase();

/** Serial QA del dispositivo del RUN: QA_DEVICE_PREFIX opcional (QAAUTO si está vacío). */
export function serialQa(v, sello) { return `${v.QA_DEVICE_PREFIX || 'QAAUTO'}-G96-${sello}`.slice(0, 50); }

/** Lectura válida de un dispositivo conectado (estado_conectividad=true), contrato actual RF-53. */
export function cuerpoLectura({ idDispositivo, idSensor, serial, timestamp }) {
  return {
    device_id: idDispositivo, sensor_id: idSensor, tipo_variable: 'TEMPERATURA_AMBIENTAL', valor: 25, unidad: '°C',
    timestamp_captura: timestamp, access_key: serial, origen: 'TIEMPO_REAL', estado_conectividad: true,
    nivel_bateria: 87, calidad_senal_rssi: -71, calidad_senal_snr: 7.5,
  };
}

/** /test-control/query responde {"data": [filas]}; null si no hubo respuesta válida (nunca 0). */
export function leerConteo(r) {
  if (r?.status !== 200 || !Array.isArray(r?.data?.data) || !r.data.data[0]) return null;
  const n = Number(r.data.data[0].n);
  return Number.isFinite(n) ? n : null;
}
export function consultaTestigoDispositivo(serial) {
  if (!/^[A-Za-z0-9_-]{1,50}$/.test(serial)) throw Error('Serial no apto para el testigo');
  return `SELECT count(*) AS n FROM auditoria.logs_dml WHERE esquema_afectado = 'modulo9' AND tabla_afectada = 'dispositivos_iot' AND tipo_operacion = 'INSERT' AND datos_nuevos->>'serial' = '${serial}'`;
}

/**
 * Veredicto propuesto. Bloquean: entorno, rollback, precondiciones [PRE] y errores de script.
 * Rechaza solo un [ASSERT] incumplido con respuesta real. Sin las tres condiciones de la
 * matriz no hay APROBADO (cobertura incompleta → BLOQUEADO).
 */
export function veredicto({ estado, rollback, aserciones, erroresScript, condiciones }) {
  if (estado !== 'CONCLUIDA' || !rollback) return 'BLOQUEADO';
  if (aserciones.some(a => /\[PRE\]/.test(a.nombre) && !a.ok)) return 'BLOQUEADO';
  if (aserciones.some(a => /\[ASSERT\]/.test(a.nombre) && !a.ok && a.http != null)) return 'RECHAZADO';
  if (erroresScript > 0 || !cobertura(new Set(condiciones))) return 'BLOQUEADO';
  const porCondicion = c => aserciones.filter(a => a.condicion === c);
  const completas = ESTADOS.every(c => ['API-187-01', 'API-187-02'].every(id => porCondicion(c).some(a => a.nombre.includes(id) && a.ok)));
  return completas && aserciones.every(a => a.ok) ? 'APROBADO' : 'BLOQUEADO';
}

function argumentos(argv) {
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
function newmanModulo() {
  const npm = spawnSync('npm', ['root', '-g'], { encoding: 'utf8', shell: process.platform === 'win32' });
  if (npm.status !== 0) throw Error('Newman no disponible');
  const m = createRequire(path.join(ROOT, 'package.json'))(path.join(npm.stdout.trim(), 'newman'));
  if (typeof m.run !== 'function') throw Error('Newman sin API run');
  return m;
}
function local() {
  const checks = []; const ck = (n, x) => checks.push([n, !!x]);
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const col = JSON.parse(fs.readFileSync(COLLECTION, 'utf8'));
  const texto = JSON.stringify(col);
  ck('Matriz TC-M03-187', CASOS.join() === 'TC-M03-187');
  ck('Catálogo cerrado', ESTADOS.join() === 'ONLINE,OFFLINE,SIN_SEÑAL');
  ck('Solo ONLINE se construye; SIN_SEÑAL y OFFLINE dependen de RF-60', CONSTRUIBLES.join() === 'ONLINE');
  ck('Configuración compartida y QA_AUTORIZADO=NO', fs.existsSync(ENV) && v.QA_AUTORIZADO === 'NO');
  ck('Barrera rechaza ejecución actual', !autorizar(v, { ambiente: 'TEST', autorizacion: '', efectos: [] }).ok);
  ck('Barrera acepta condiciones futuras válidas', autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ambiente: 'TEST', autorizacion: 'REF-DESARROLLO', efectos: ['notificacion-login'] }).ok);
  ck('Barrera rechaza DEV', !autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ambiente: 'DEV', autorizacion: 'REF-DESARROLLO', efectos: ['notificacion-login'] }).ok);
  ck('Variables QA resueltas', !!v.QA_PROD_EMAIL && !!v.QA_SETUP_EMAIL && !!(v.QA_PROD_PASSWORD || v.QA_COMMON_PASSWORD) && !!v.QA_SANDBOX_SECRET);
  ck('Prefijo de serial QA disponible (automático si falta)', /^[A-Za-z0-9][A-Za-z0-9_-]{1,19}-G96-/.test(serialQa(v, '20261017000000')));
  ck('Colección Postman v2.1', /v2\.1\.0/.test(col.info?.schema || '') && col.item?.length === 3);
  ck('Aserciones exactas', ['API-187-01', 'API-187-02'].every(x => texto.includes(x)));
  ck('Nombres de prueba sin caracteres corruptos', !/\?(logo|n )/.test(texto));
  ck('Cada condición sin preparar se omite (no se ejecuta con IDs vacíos)', col.item.every(i => JSON.stringify(i.event).includes('skipRequest')));
  const vars = new Set([...texto.matchAll(/\{\{([a-z_]+)\}\}/g)].map(x => x[1]));
  ck('Variables Newman resueltas por el ejecutor', [...vars].every(x => ['base_url', 'run_id', 'sandbox_secret', 'token', ...ESTADOS.flatMap(e => [`id_${clave(e)}`, `sensor_${clave(e)}`, `pagina_${clave(e)}`])].includes(x)));
  ck('Barrera propia de Newman', texto.includes('BLOQUEO_G96'));
  try { for (const e of [...(col.event || []), ...col.item.flatMap(x => x.event || [])]) new Function((e.script?.exec || []).join('\n')); ck('Sintaxis Postman', true); } catch { ck('Sintaxis Postman', false); }
  ck('Sintaxis ejecutor', spawnSync(process.execPath, ['--check', fileURLToPath(import.meta.url)]).status === 0);
  ck('Testigo de aislamiento sin RLS (auditoria.logs_dml)', /auditoria\.logs_dml/.test(consultaTestigoDispositivo('QAAUTO-G96-1')));
  ck('Veredicto: PRE fallida bloquea y cobertura incompleta no aprueba',
    veredicto({ estado: 'CONCLUIDA', rollback: true, aserciones: [{ nombre: '[TC-M03-187][PRE][PRE-187-01]', ok: false, http: 200 }], erroresScript: 0, condiciones: ESTADOS }) === 'BLOQUEADO'
    && veredicto({ estado: 'CONCLUIDA', rollback: true, aserciones: [], erroresScript: 0, condiciones: ['ONLINE'] }) === 'BLOQUEADO');
  ck('Sin RESULTADOS de preparación', !fs.existsSync(path.join(DIR, 'RESULTADOS')));
  ck('Sin secretos literales', [fileURLToPath(import.meta.url), COLLECTION].every(f => ![v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_PROD_PASSWORD, v.QA_SETUP_PASSWORD].filter(x => x?.length > 4).some(x => fs.readFileSync(f, 'utf8').includes(x))));
  const t = spawnSync(process.execPath, ['--test', path.join(DIR, 'validar_local_g96.mjs')], { encoding: 'utf8' });
  ck('Pruebas unitarias locales', t.status === 0);
  try { newmanModulo(); ck('Newman disponible', true); } catch { ck('Newman disponible', false); }
  for (const [n, ok] of checks) console.log(`${ok ? 'OK' : 'FALLO'} ${n}`);
  console.log(`G96 local ${checks.filter(x => x[1]).length}/${checks.length}`);
  return checks.every(x => x[1]) ? 0 : 1;
}

async function ejecutar(a) {
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const gate = autorizar(v, a);
  if (!gate.ok) { console.error(`EJECUCIÓN NO AUTORIZADA: ${gate.motivos.join('; ')}`); return 2; }
  if (!['evaluacion', 'reintento'].includes(a.tipo)) { console.error('Indique --tipo evaluacion|reintento'); return 2; }
  const n = version(DIR, a.tipo, a.version), newman = newmanModulo();
  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14);
  const run = `G96-${n === 1 ? 'EVAL' : 'REEVAL'}-V${n}-${stamp}`;
  const base = n === 1 ? path.join(DIR, 'RESULTADOS') : path.join(DIR, `EvaluacionV${n}`, 'RESULTADOS');
  const out = path.join(base, run); fs.mkdirSync(base, { recursive: true }); fs.mkdirSync(out);
  const serial = serialQa(v, stamp);
  const ev = { grupo: GRUPO, rf: 'RF-58', cu: 'CU04', casos: CASOS, version: n, run_id: run, estado: 'EN_CURSO', fase: 'PREFLIGHT', autorizacion: a.autorizacion, dependencias: [], aserciones: [], sandbox: {}, datos: {}, inicio: new Date().toISOString() };
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_PROD_PASSWORD, v.QA_SETUP_PASSWORD, serial].filter(Boolean);
  const limpiar = x => secretos.reduce((s, y) => s.replaceAll(y, '[REDACTADO]'), String(x)).replace(/eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}/g, '[JWT]');
  const guardar = () => fs.writeFileSync(path.join(out, 'evidencia.json'), limpiar(JSON.stringify(ev, null, 2)));
  let abierto = false, dispositivoCreado = false;
  async function req(m, ruta, { body, token, control = false, runId = run } = {}) {
    const headers = { Accept: 'application/json', 'X-Sandbox-Secret': v.QA_SANDBOX_SECRET };
    if (!control) headers['X-Test-Run-Id'] = runId;
    if (token) headers.Authorization = `Bearer ${token}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const r = await fetchReal(`${gate.api}${ruta}`, { method: m, headers, body: body === undefined ? undefined : JSON.stringify(body), redirect: 'manual', signal: AbortSignal.timeout(30000) });
    const data = await r.json().catch(() => null);
    if (!control && r.headers.get('x-test-run-id') !== runId) throw Error(`Sandbox sin eco: ${m} ${ruta}`);
    return { status: r.status, data };
  }
  function need(r, status, label) { if (r.status !== status) throw Error(`${label}: HTTP ${r.status} ${JSON.stringify(r.data ?? '').slice(0, 300)}`); return r.data; }
  async function testigo(runId) { return leerConteo(await req('POST', '/test-control/query', { body: { query: consultaTestigoDispositivo(serial) }, runId })); }
  async function sondaExterna(sufijo) { const rid = `${run}-${sufijo}`; try { return await testigo(rid); } finally { await req('DELETE', `/test-control/runs/${rid}`, { control: true }); } }
  try {
    const probe = await req('DELETE', `/test-control/runs/${run}-PREFLIGHT`, { control: true });
    if (probe.status !== 404 || !/Run ID no encontrado/i.test(String(probe.data?.detail ?? ''))) throw Error(`Sandbox no disponible: HTTP ${probe.status}`);
    abierto = true;
    // Un login por actor, dentro del sandbox.
    const login = async (email, pass, etiqueta) => { const d = need(await req('POST', '/sesiones/', { body: { correo_electronico: email, contrasena: pass } }), 200, `Login ${etiqueta}`); if (!d?.token) throw Error(`Login ${etiqueta} sin token`); secretos.push(d.token); return d.token; };
    const tokSetup = await login(v.QA_SETUP_EMAIL, v.QA_SETUP_PASSWORD || v.QA_COMMON_PASSWORD, 'preparación');
    const tokProd = await login(v.QA_PROD_EMAIL, v.QA_PROD_PASSWORD || v.QA_COMMON_PASSWORD, 'Productor');
    const meProd = need(await req('GET', '/usuarios/me', { token: tokProd }), 200, 'Identidad Productor');
    if (!/productor/i.test(meProd.nombre_rol || '')) throw Error('La cuenta QA no tiene rol Productor');
    const meSetup = need(await req('GET', '/usuarios/me', { token: tokSetup }), 200, 'Identidad preparación');
    if (!/administrador/i.test(meSetup.nombre_rol || '')) throw Error('QA_SETUP_EMAIL debe ser Administrador (crea fincas y áreas)');

    // ---- ONLINE: construcción en el sandbox --------------------------------
    ev.fase = 'PREPARACION';
    const fincasP = new Set((need(await req('GET', '/configuracion/fincas', { token: tokProd }), 200, 'Fincas Productor').items || []).map(f => Number(f.id_finca)));
    const fincasS = (need(await req('GET', '/configuracion/fincas', { token: tokSetup }), 200, 'Fincas preparación').items || []).map(f => Number(f.id_finca));
    let finca = fincasS.find(id => fincasP.has(id));
    if (!finca) {
      finca = need(await req('POST', '/configuracion/fincas', { token: tokSetup, body: { nombre: `QA Monitoreo G Noventa Seis ${stamp}`.replace(/\d/g, d => 'abcdefghij'[Number(d)]), ubicacion: { departamento: 'Huila', municipio: 'Neiva', vereda: 'QA', latitud: 2.9273, longitud: -75.2819 }, tamano_h: 1, id_usuario: meProd.id_usuario } }), 201, 'Crear finca QA').id_finca;
      ev.datos.finca = { id: finca, origen: 'creada en el RUN con acceso del Productor' };
    } else ev.datos.finca = { id: finca, origen: 'existente compartida (solo se le agrega un área)' };
    const tipo = (need(await req('GET', '/configuracion/tipos-area?solo_activos=true', { token: tokSetup }), 200, 'Tipos de área').items || []).find(x => x.es_activo);
    const especie = (need(await req('GET', '/configuracion/especies?solo_activas=true', { token: tokSetup }), 200, 'Especies').items || []).find(x => x.es_activo);
    const tipoDisp = (need(await req('GET', '/configuracion/tipos-dispositivo-iot', { token: tokSetup }), 200, 'Tipos de dispositivo').items || []).filter(x => x.categoria === 'SENSOR').sort((x, y) => x.id_tipo_dispositivo - y.id_tipo_dispositivo)[0];
    const rango = (need(await req('GET', '/configuracion/sensores/rangos-calibracion', { token: tokSetup }), 200, 'Rangos de calibración').items || []).find(x => x.categoria === 'TEMPERATURA');
    if (!tipo || !especie || !tipoDisp || !rango) throw Error('Catálogos insuficientes para preparar ONLINE (tipo de área, especie, tipo SENSOR o rango TEMPERATURA)');
    const area = need(await req('POST', '/configuracion/infraestructuras', { token: tokSetup, body: { nombre_infraestructura: `QA G96 ${stamp}`, tipo_area: tipo.nombre, superficie: 25, finca_id: finca, descripcion_infraestructura: `QA ${run}`, especie_id: especie.id_especie } }), 201, 'Crear área QA');
    // Sin id_dispositivo_gateway: no hay sincronización MQTT.
    const disp = need(await req('POST', '/configuracion/dispositivos-iot', { token: tokSetup, body: { serial, descripcion: `QA G96 ${stamp}`, id_infraestructura: area.id_infraestructura, id_tipo_dispositivo: tipoDisp.id_tipo_dispositivo, es_activo: true } }), 201, 'Registrar dispositivo QA');
    dispositivoCreado = true;
    const sensor = need(await req('POST', `/configuracion/dispositivos-iot/${disp.id_dispositivo_iot}/sensores`, { token: tokSetup, body: { nombre: `QA G96 ${stamp} ONLINE`, categoria: 'TEMPERATURA' } }), 201, 'Registrar sensor');
    need(await req('POST', `/configuracion/sensores/${sensor.id_sensores}/asociar`, { token: tokSetup, body: { id_dispositivo_iot: disp.id_dispositivo_iot, id_infraestructura: area.id_infraestructura, punto_instalacion: 'QA G96' } }), 201, 'Asociar sensor');
    need(await req('POST', `/configuracion/sensores/${sensor.id_sensores}/calibrar`, { token: tokSetup, body: { id_dispositivo_iot: disp.id_dispositivo_iot, id_infraestructura: area.id_infraestructura, valor_referencia: Number(((Number(rango.valor_min) + Number(rango.valor_max)) / 2).toFixed(2)), ganancia: 1, offset: 0, fecha_calibracion: new Date(Date.now() - 600000).toISOString(), observaciones: `QA ${run}`, modo_calibracion: 'SENSOR' } }), 201, 'Calibrar sensor');
    need(await req('GET', `/configuracion/infraestructuras/${area.id_infraestructura}`, { token: tokProd }), 200, 'Alcance del Productor sobre el área');
    // Aislamiento antes de la lectura: el INSERT del dispositivo consta dentro del RUN y no fuera.
    const dentro = await testigo(run), fuera = await sondaExterna('SONDA');
    ev.sandbox.aislamiento = { testigo: 'auditoria.logs_dml (INSERT del dispositivo)', dentro, fuera };
    if (dentro !== 1 || fuera !== 0) throw Error(`Aislamiento no demostrado (dentro=${dentro}, fuera=${fuera})`);
    const lectura = await req('POST', '/iot/telemetria', { body: cuerpoLectura({ idDispositivo: disp.id_dispositivo_iot, idSensor: sensor.id_sensores, serial, timestamp: new Date(Date.now() - 30000).toISOString() }) });
    ev.datos.online = { id_infraestructura: area.id_infraestructura, id_sensor: sensor.id_sensores, lectura_http: lectura.status, estado_calidad: lectura.data?.estado_calidad ?? null, origen: 'construido en el RUN (lectura válida con estado_conectividad=true)' };
    const condiciones = [];
    const testigos = {};
    if (lectura.status === 201 && lectura.data?.estado_calidad === 'LECTURA_VALIDA') {
      condiciones.push('ONLINE');
      testigos.ONLINE = { id_infraestructura: area.id_infraestructura, id_sensor: sensor.id_sensores, pagina: 1 };
    } else ev.dependencias.push(`ONLINE no preparado: la lectura válida no fue aceptada (HTTP ${lectura.status}, estado_calidad ${lectura.data?.estado_calidad ?? '—'}).`);

    // ---- SIN_SEÑAL y OFFLINE: descubrimiento de solo lectura ------------------
    ev.fase = 'DESCUBRIMIENTO';
    const permitidas = [...fincasP].filter(x => Number.isSafeInteger(x) && x > 0);
    for (const x of ESTADOS.filter(e => !CONSTRUIBLES.includes(e))) {
      if (!permitidas.length) break;
      // Las tablas de modulo9 tienen RLS por rol; la consulta corre con la identidad del último
      // request autenticado del RUN, por eso se declara antes la del Administrador.
      need(await req('GET', '/usuarios/me', { token: tokSetup }), 200, 'Identidad de consulta');
      const sql = `SELECT eas.id_sensor, saa.id_infraestructura FROM modulo3.estados_actuales_sensores eas JOIN LATERAL (SELECT id_infraestructura FROM modulo9.sensores_areas_asociadas WHERE id_sensor = eas.id_sensor AND fecha_finalizacion IS NULL ORDER BY fecha_asociacion DESC LIMIT 1) saa ON true JOIN modulo9.infraestructuras i ON i.id_infraestructura = saa.id_infraestructura WHERE eas.estado_conectividad::text = '${INTERNO[x]}' AND i.id_finca IN (${permitidas.join(',')}) ORDER BY eas.id_sensor LIMIT 1`;
      const r = await req('POST', '/test-control/query', { body: { query: sql } });
      const fila = r.status === 200 ? r.data?.data?.[0] : null;
      if (!fila) { ev.dependencias.push(`${x}: ${r.status === 200 ? 'no se descubrió un sensor en ese estado en unidades del Productor' : `consulta de descubrimiento no disponible (HTTP ${r.status})`}. Depende de la transición RF-60 (tarea periódica global, sin disparador aislado); no se simula ni se escribe SQL.`); continue; }
      const pos = await req('POST', '/test-control/query', { body: { query: `SELECT count(*) AS n FROM modulo3.estados_actuales_sensores eas JOIN modulo9.sensores_areas_asociadas saa ON saa.id_sensor = eas.id_sensor WHERE saa.id_infraestructura = ${Number(fila.id_infraestructura)} AND saa.fecha_finalizacion IS NULL AND eas.id_sensor < ${Number(fila.id_sensor)}` } });
      const antes = leerConteo(pos);
      if (antes === null) { ev.dependencias.push(`${x}: no se pudo calcular la página del sensor descubierto.`); continue; }
      condiciones.push(x);
      testigos[x] = { id_infraestructura: Number(fila.id_infraestructura), id_sensor: Number(fila.id_sensor), pagina: Math.floor(antes / 50) + 1 };
    }
    ev.datos.condiciones = Object.fromEntries(ESTADOS.map(x => [x, testigos[x] ? { ...testigos[x], origen: CONSTRUIBLES.includes(x) ? 'construido' : 'descubierto (solo lectura)' } : null]));
    ev.datos.cobertura_completa = cobertura(new Set(condiciones));
    ev.fase = 'ESCENARIO'; guardar();

    // ---- Newman: las condiciones sin preparar se omiten en la colección -------
    const env = { base_url: gate.api, run_id: run, sandbox_secret: v.QA_SANDBOX_SECRET, token: tokProd, autorizado_run: 'SI' };
    for (const x of ESTADOS) for (const [k, campo] of [['id', 'id_infraestructura'], ['sensor', 'id_sensor'], ['pagina', 'pagina']]) env[`${k}_${clave(x)}`] = testigos[x] ? String(testigos[x][campo]) : '';
    const nr = await new Promise(resolve => newman.run({ ignoreRedirects: true,  collection: JSON.parse(fs.readFileSync(COLLECTION, 'utf8')), environment: { values: Object.entries(env).map(([key, value]) => ({ key, value })) }, reporters: [], silent: true }, (error, summary) => resolve({ error, summary })));
    ev.aserciones = (nr.summary?.run?.executions || []).flatMap(e => {
      const condicion = ESTADOS.find(x => (e.item?.name || '').endsWith(` ${x}`)) ?? null;
      return (e.assertions || []).map(x => ({ condicion, nombre: x.assertion, ok: !x.error, error: x.error ? limpiar(x.error.message) : undefined, http: e.response?.code ?? null }));
    });
    ev.errores_script = (nr.summary?.run?.failures || []).filter(f => !/AssertionError/.test(f.error?.name || '')).map(f => limpiar(`${f.source?.name ?? ''}: ${f.error?.name} ${f.error?.message}`));
    if (nr.error) ev.errores_script.push(limpiar(nr.error.message));
    ev.condiciones_evaluadas = condiciones;
    ev.estado = 'CONCLUIDA';
  } catch (e) { ev.estado = ev.fase === 'ESCENARIO' ? 'INTERRUMPIDA' : 'ABORTADA_PREFLIGHT'; ev.dependencias.push(limpiar(e.message)); }
  finally {
    try {
      if (abierto) {
        const c = await req('DELETE', `/test-control/runs/${run}`, { control: true });
        const d = await req('DELETE', `/test-control/runs/${run}`, { control: true });
        const resto = dispositivoCreado ? await sondaExterna('POST') : 0;
        ev.sandbox.cierre = c.status; ev.sandbox.sonda_posterior = resto;
        ev.sandbox.rollback = c.status === 200 && d.status === 404 && resto === 0;
        if (dispositivoCreado && resto === null) ev.dependencias.push('Rollback no confirmable: testigo auditoria.logs_dml no consultable.');
      }
    } catch (e) { ev.sandbox.rollback = false; ev.dependencias.push(limpiar(e.message)); }
    ev.veredicto = veredicto({ estado: ev.estado, rollback: !!ev.sandbox.rollback, aserciones: ev.aserciones, erroresScript: (ev.errores_script || []).length, condiciones: ev.condiciones_evaluadas || [] });
    ev.naturaleza = ev.veredicto === 'RECHAZADO' ? 'PRODUCTO (criterio [ASSERT] incumplido con respuesta real)' : ev.veredicto === 'BLOQUEADO' ? 'DEPENDENCIA / INFRAESTRUCTURA / AUTOMATIZACION (ver dependencias)' : 'SIN FALLOS';
    ev.fin = new Date().toISOString(); guardar();
    const informe = n === 1 ? `${GRUPO}_resultado.md` : `${GRUPO}_reevaluacion_V${n}.md`;
    fs.writeFileSync(path.join(out, informe), limpiar(`# ${GRUPO} — ${CASOS[0]} — ${n === 1 ? 'EVALUACIÓN V1' : `REEVALUACIÓN V${n}`}\n\n> Borrador técnico generado automáticamente; QA revisa la evidencia antes de emitir el dictamen.\n\nRUN_ID: \`${run}\` · Ambiente: TEST · Estado técnico: ${ev.estado}\n\n**Resultado propuesto: ${ev.veredicto}** (${ev.naturaleza}).\n\nCondiciones de la matriz (conectado / desconectado / sin señal): ${JSON.stringify(ev.datos.condiciones || {})}. Cobertura completa: ${ev.datos.cobertura_completa ? 'sí' : 'no'}.\n\nAserciones: ${JSON.stringify(ev.aserciones)}\n\nDependencias y bloqueos: ${ev.dependencias.join('; ') || 'ninguno'}\n\nSandbox: aislamiento ${JSON.stringify(ev.sandbox.aislamiento || {})}; rollback ${ev.sandbox.rollback ? 'confirmado' : 'NO confirmado'}.\n`));
  }
  console.log(`${GRUPO}: ${ev.estado} — ${out}`); return ev.estado === 'CONCLUIDA' ? 0 : 4;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let code; try { const a = argumentos(process.argv.slice(2)); code = a.modo === 'local' ? local() : await ejecutar(a); } catch (e) { console.error(e.message); code = 2; } process.exitCode = code;
}
