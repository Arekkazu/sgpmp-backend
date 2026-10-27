import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';
import { CASOS, CAPACIDADES, SEMILLA, LIMITE, planTemporal, cuerpoAlerta, exigirAlertaNueva, escrituraPermitida, evaluarComprobacion, decidirCaso } from './lib/g89_escenario.mjs';
import { sanearArtefacto } from './lib/g89_seguridad.mjs';
import { informe, validarResultado, completarResultado } from './lib/g89_presentacion.mjs';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const COLECCION = path.join(DIR, 'G89.postman_collection.json');
const JSON_BONITO = (x) => JSON.stringify(x, null, 2);

// Se llama exclusivamente tras validar el contrato del lanzador; --comprobar no lee .env.qa.
export function leerEnv({ raiz = RAIZ, proceso = process.env } = {}) {
  const valores = {};
  const archivo = path.join(raiz, '.env.qa');
  if (fs.existsSync(archivo)) for (const linea of fs.readFileSync(archivo, 'utf8').split(/\r?\n/)) {
    const m = linea.match(/^\s*([A-Z0-9_]+)\s*=(.*)$/);
    if (m) valores[m[1]] = m[2].trim().replace(/^(['"])(.*)\1$/, '$2');
  }
  Object.assign(valores, Object.fromEntries(Object.entries(proceso).filter(([, v]) => v)));
  valores.QA_AUTORIZADO = proceso.QA_AUTORIZADO;
  return valores;
}

export function comprobar({ dir = DIR } = {}) {
  globalThis.fetch = () => { throw new Error('RED_PROHIBIDA_EN_COMPROBAR'); };
  const requeridos = ['g89.mjs', 'G89.postman_collection.json', 'README.md',
    'lib/contrato_ejecutor.mjs', 'lib/g89_escenario.mjs', 'lib/g89_presentacion.mjs',
    'lib/g89_seguridad.mjs', 'pruebas/g89.test.mjs'];
  const ausentes = requeridos.filter((f) => !fs.existsSync(path.join(dir, f)));
  const c = JSON.parse(fs.readFileSync(path.join(dir, 'G89.postman_collection.json'), 'utf8'));
  const script = JSON.stringify(c);
  const scripts = [...(c.event ?? []), ...(c.item ?? []).flatMap((item) => item.event ?? [])];
  let sintaxis = true;
  for (const e of scripts) try { new vm.Script((e.script?.exec ?? []).join('\n')); }
  catch { sintaxis = false; }
  const ids = Object.values(CAPACIDADES.comprobaciones_obligatorias)
    .flatMap((fuentes) => Object.values(fuentes).flat());
  const capacidadesValidas = CAPACIDADES.contrato === 'sigab-qa-ejecutor/1'
    && ['evaluar', 'reintentar'].every((x) => CAPACIDADES.operaciones.includes(x))
    && JSON.stringify(Object.keys(CAPACIDADES.comprobaciones_obligatorias)) === JSON.stringify(CASOS)
    && Object.values(CAPACIDADES.comprobaciones_obligatorias).every((fuentes) =>
      Object.keys(fuentes).every((fuente) => ['API', 'UI'].includes(fuente))
      && Object.values(fuentes).every((lista) => Array.isArray(lista) && lista.length > 0))
    && ids.length === new Set(ids).size && ids.every((id) => /^[A-Za-z0-9_-]{1,100}$/.test(id));
  const valido = !ausentes.length && c.item?.length === 1 && script.includes('X-Test-Run-Id')
    && script.includes('X-Sandbox-Secret') && sintaxis
    && CASOS.length === 2 && LIMITE.ingestas === 3 && capacidadesValidas;
  console.log(JSON_BONITO({ comprobacion: 'G89_LOCAL_SIN_RED', valido, ausentes,
    coleccion: c.info?.name, casos: CASOS, capacidades_validas: capacidadesValidas, limite: LIMITE }));
  return valido ? 0 : 2;
}

function exigirAmbiente(v) {
  const nombres = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_ADMIN_EMAIL',
    'QA_ADMIN_PASSWORD', 'QA_PROD_EMAIL', 'QA_PROD_PASSWORD',
    'BROKER_SERVICE_TOKEN', 'QA_G88_169_171_SERIAL'];
  const ausentes = nombres.filter((n) => !v[n]);
  if (v.QA_AUTORIZADO !== 'SI' || ausentes.length) throw new Error(`PREFLIGHT_LOCAL: ${ausentes.join(', ') || 'QA_AUTORIZADO'}`);
  if (!/^https?:\/\//.test(v.SIGAB_API_TEST_BASE)) throw new Error('BASE_TEST_INVALIDA');
}

export function contextoSolicitud({ abierto, token, enRun }) {
  if (abierto && token && enRun === false) throw new Error('CONTEXTO_MIXTO');
  return abierto ? true : enRun === true;
}

export function crearTransporte({ base, runId, secreto, bitacora, secretos, limite = LIMITE.solicitudes }) {
  let abierto = false; let detenido = false; let cuenta = 0;
  const escrituras = {};
  let permitidos = null;
  const rutaSinQuery = (ruta) => ruta.split('?')[0];
  async function solicitar(metodo, ruta, { token, cuerpo, enRun, cierre = false } = {}) {
    if (detenido && !cierre) throw new Error('PARADA_SEGURIDAD');
    if (abierto && ruta === '/sesiones/') throw new Error('LOGIN_DENTRO_RUN_PROHIBIDO');
    if (cierre && (metodo !== 'DELETE' || ruta !== `/test-control/runs/${runId}`))
      throw new Error('CIERRE_NO_PERMITIDO');
    if (++cuenta > limite) throw new Error('LIMITE_SOLICITUDES');
    if (metodo !== 'GET' && !cierre && ruta !== '/sesiones/') {
      if (!abierto) throw new Error('ESCRITURA_FUERA_RUN');
      escrituraPermitida(metodo, ruta, cuerpo, escrituras, permitidos);
    }
    const dentro = contextoSolicitud({ abierto, token, enRun });
    const headers = { Accept: 'application/json' };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (dentro) { headers['X-Test-Run-Id'] = runId; headers['X-Sandbox-Secret'] = secreto; }
    if (cierre) headers['X-Sandbox-Secret'] = secreto;
    if (cuerpo !== undefined) headers['Content-Type'] = 'application/json';
    const inicio = Date.now();
    try {
      const response = await fetch(base + ruta, { method: metodo, headers,
        body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
        signal: AbortSignal.timeout(30000), redirect: 'manual' });
      const texto = await response.text();
      let json; try { json = JSON.parse(texto); } catch { json = texto.slice(0, 250); }
      const eco = response.headers.get('X-Test-Run-Id');
      bitacora.push({ metodo, ruta: rutaSinQuery(ruta), en_run: dentro,
        latencia_ms: Date.now() - inicio, http: response.status,
        eco_run: dentro ? eco === runId : null,
        ...(response.status >= 400 ? { error: sanearArtefacto(JSON_BONITO(json), secretos).slice(0, 500) } : {}) });
      if (cierre && response.status === 200) { abierto = false; detenido = false; }
      if (dentro && eco !== runId && !cierre) throw new Error('ECO_RUN_AUSENTE');
      return { status: response.status, json };
    } catch (e) {
      bitacora.push({ metodo, ruta: rutaSinQuery(ruta), en_run: dentro,
        latencia_ms: Date.now() - inicio, error: sanearArtefacto(String(e.message), secretos) });
      if (e.name === 'TimeoutError' || e.name === 'AbortError') detenido = true;
      throw e;
    }
  }
  return { solicitar, abrir: () => { abierto = true; },
    configurarEscenario: (x) => { permitidos = x; },
    estado: () => ({ abierto, detenido, cuenta, escrituras }),
    detener: () => { detenido = true; } };
}

function sensorDe(x) { return (x?.sensores ?? []).find((s) => Number(s.id_sensor) === SEMILLA.sensor) ?? null; }
function normalizarSensor(s) { return s ? { id_sensor: s.id_sensor, ultimo_valor: s.ultimo_valor,
  estado_semaforo: s.estado_semaforo, id_alerta: s.id_alerta ?? null,
  ultimo_timestamp_captura: s.ultimo_timestamp_captura } : null; }
export function compararDashboard(antes, despues) {
  const completa = (r) => r?.status === 200 && Array.isArray(r.json?.sensores)
    && Number.isInteger(r.json.total) && r.json.total >= 0 && r.json.total <= 50
    && r.json.sensores.length === r.json.total && r.json.pagina === 1 && r.json.por_pagina === 50;
  const previoCompleto = completa(antes), posteriorCompleto = completa(despues);
  const previo = normalizarSensor(sensorDe(antes?.json));
  const posterior = normalizarSensor(sensorDe(despues?.json));
  return { tipo: 'dashboard_previo', http: despues?.status ?? null,
    ruta: `/iot/monitoreo/dashboard?id_infraestructura=${SEMILLA.area}&por_pagina=50`,
    actor: 'Productor', pagina: 1, por_pagina: 50,
    previo_completo: previoCompleto, posterior_completo: posteriorCompleto,
    total_previo: antes?.json?.total ?? null, total_posterior: despues?.json?.total ?? null,
    sensor_previo_presente: previo !== null, sensor_posterior_presente: posterior !== null,
    coincide: previoCompleto && posteriorCompleto
      && antes.json.total === despues.json.total
      && JSON.stringify(antes.json.sensores.map(normalizarSensor))
        === JSON.stringify(despues.json.sensores.map(normalizarSensor))
      && JSON.stringify(previo) === JSON.stringify(posterior) };
}
export function confirmarRollback(cierre, alertas, telemetrias) {
  const checks = cierre.comprobaciones ?? [];
  return cierre.http === 200 && checks.some((x) => x.tipo === 'dashboard_previo'
      && x.previo_completo && x.posterior_completo && x.coincide)
    && alertas.every((id) => checks.some((x) => x.tipo === 'alerta_ausente'
      && x.id_alerta === id && x.http === 404 && x.coincide))
    && (!telemetrias.length || checks.some((x) => x.tipo === 'telemetrias_ausentes'
      && x.completo && x.http === 200 && x.coincide && x.total_ids === telemetrias.length))
    && checks.every((x) => x.coincide);
}
export function preflightLocal(contrato, valores, { dir = DIR } = {}) {
  const nombres = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_ADMIN_EMAIL',
    'QA_ADMIN_PASSWORD', 'QA_PROD_EMAIL', 'QA_PROD_PASSWORD',
    'BROKER_SERVICE_TOKEN', 'QA_G88_169_171_SERIAL', 'QA_AUTORIZADO'];
  const variables = nombres.map((nombre) => ({ nombre,
    fuente: process.env[nombre] ? 'proceso' : 'ambiente autorizado (.env.qa o inyección local)',
    presente: Boolean(valores[nombre]) }));
  const barreras = [];
  if (!contrato || !/^RUN-G89-V\d+-\d{8}-\d{6}$/.test(contrato.runId ?? '')
    || path.basename(contrato.directorio ?? '') !== contrato.runId
    || !CASOS.every((id) => contrato.contexto?.casos?.includes(id))
    || !contrato.referencia) barreras.push('CONTRATO_INCOHERENTE');
  if (valores.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO_AUSENTE');
  if (variables.some((x) => !x.presente)) barreras.push('VARIABLES_REQUERIDAS_AUSENTES');
  if (valores.SIGAB_API_TEST_BASE && !/^https?:\/\//.test(valores.SIGAB_API_TEST_BASE))
    barreras.push('BASE_TEST_INVALIDA');
  if (!fs.existsSync(path.join(dir, 'G89.postman_collection.json'))) barreras.push('COLECCION_AUSENTE');
  let temporal = null;
  try { temporal = planTemporal(); } catch { barreras.push('PLAN_TEMPORAL_INVALIDO'); }
  const resultado = { fase: 'PREFLIGHT_LOCAL', grupo: 'G89', run_id: contrato?.runId,
    contrato: { operacion: contrato?.operacion, version: contrato?.version,
      intento: contrato?.intento, contexto_validado: !barreras.includes('CONTRATO_INCOHERENTE') },
    variables, casos: CASOS, ejecutables: barreras.length ? [] : CASOS,
    semilla_candidata: { finca: SEMILLA.finca, area: SEMILLA.area, especie: SEMILLA.especie,
      dispositivo: SEMILLA.dispositivo, sensor: SEMILLA.sensor, valor: SEMILLA.valor,
      unidad: SEMILLA.unidad, verificacion_en_run: 'relaciones, calibración, umbral y alertas por GET' },
    plan_temporal: temporal ? { calculable: true, marcas: temporal.marcas.length,
      ancla_anterior_al_inicio: Date.parse(temporal.ancla) < Date.parse(temporal.inicio) } : { calculable: false },
    limites: LIMITE, lista_blanca: ['POST /iot/telemetria', 'POST /iot/alertas',
      'PATCH /iot/alertas/{id}/estado', 'DELETE /test-control/runs/{id}'],
    barreras, motivos: barreras, ok: barreras.length === 0 };
  return { resultado, temporal };
}
function afirmar(ok, mensaje) { if (!ok) throw new Error(mensaje); }

export async function verificarSemilla(solicitar, token, serial) {
  const get = async (ruta) => { const x = await solicitar('GET', ruta, { token });
    afirmar(x.status === 200, `GET ${ruta.split('?')[0]} HTTP ${x.status}`); return x.json?.data ?? x.json; };
  const d = await get(`/configuracion/dispositivos-iot/${SEMILLA.dispositivo}`);
  afirmar(Number(d.id_infraestructura) === SEMILLA.area && d.es_activo !== false && d.serial === serial,
    'DISPOSITIVO_INCOMPATIBLE');
  const i = await get(`/configuracion/infraestructuras/${SEMILLA.area}`);
  afirmar(Number(i.especie_id) === SEMILLA.especie, 'AREA_ESPECIE_INCOMPATIBLE');
  const sensores = await get(`/configuracion/dispositivos-iot/${SEMILLA.dispositivo}/sensores`);
  afirmar((sensores.items ?? []).some((x) => Number(x.id_sensores) === SEMILLA.sensor
    && x.categoria === 'TEMPERATURA' && x.es_activo !== false), 'SENSOR_INCOMPATIBLE');
  const as = await get(`/configuracion/sensores/${SEMILLA.sensor}/asociaciones`);
  afirmar((as.items ?? []).some((x) => Number(x.id_infraestructura) === SEMILLA.area
    && x.tiene_estado === true && !x.fecha_finalizacion), 'ASOCIACION_INCOMPATIBLE');
  const cal = await get(`/configuracion/sensores/${SEMILLA.sensor}/calibraciones`);
  const calibracion = (cal.items ?? []).filter((x) => Number(x.id_dispositivo_iot) === SEMILLA.dispositivo)
    .sort((a, b) => String(b.fecha_calibracion ?? '').localeCompare(String(a.fecha_calibracion ?? '')))[0];
  afirmar(calibracion && Number.isFinite(Number(calibracion.ganancia))
    && Number.isFinite(Number(calibracion.offset ?? calibracion.offset_calibracion)),
  'CALIBRACION_INCOMPATIBLE');
  const valorAjustado = SEMILLA.valor * Number(calibracion.ganancia)
    + Number(calibracion.offset ?? calibracion.offset_calibracion);
  afirmar(Number.isFinite(valorAjustado), 'VALOR_AJUSTADO_INVALIDO');
  const um = await get(`/configuracion/umbrales?id_especie=${SEMILLA.especie}`);
  afirmar((um.items ?? []).some((x) => x.es_activo && Number(x.id_variable_ambiental) === SEMILLA.variable
    && ['normal', 'precaucion', 'critico'].every((nivel) => x.niveles?.some((n) => n.nivel === nivel))),
  'UMBRALES_INCOMPATIBLES');
  const umbral = (um.items ?? []).find((x) => x.es_activo && Number(x.id_variable_ambiental) === SEMILLA.variable);
  const normal = umbral.niveles.find((n) => n.nivel === 'normal');
  afirmar(valorAjustado >= Number(normal.limite_inferior)
    && valorAjustado <= Number(normal.limite_superior), 'VALOR_NO_VERDE_EN_NIVELES');
  const alertas = await get(`/iot/alertas?estado=ACTIVA&id_sensor=${SEMILLA.sensor}`);
  afirmar(Number(alertas.total) === 0, 'ALERTA_PREEXISTENTE_ACTIVA');
  const atencion = await get(`/iot/alertas?estado=EN_ATENCION&id_sensor=${SEMILLA.sensor}`);
  afirmar(Number(atencion.total) === 0, 'ALERTA_PREEXISTENTE_EN_ATENCION');
  return { dispositivo: SEMILLA.dispositivo, sensor: SEMILLA.sensor, area: SEMILLA.area,
    especie: SEMILLA.especie, asociacion: true, calibracion: true, umbral: true,
    umbral_normal: { minimo: Number(normal.limite_inferior), maximo: Number(normal.limite_superior) },
    sin_alerta_activa: true };
}

export function ejecutarNewman({ contrato, variables, secretos, indice }) {
  if (indice > LIMITE.newman) throw new Error('LIMITE_NEWMAN');
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g89-newman-'));
  try {
    const env = path.join(temporal, 'env.json');
    const rep = path.join(temporal, 'reporte.json');
    fs.writeFileSync(env, JSON_BONITO({ values: Object.entries(variables).map(([key, value]) =>
      ({ key, value: String(value ?? ''), enabled: true })) }), { mode: 0o600 });
    const inicio = Date.now();
    const cmd = spawnSync('newman', ['run', COLECCION, '-e', env, '--reporters', 'json',
      '--reporter-json-export', rep, '--timeout-request', '30000', '--color', 'off'],
    { encoding: 'utf8', shell: process.platform === 'win32', timeout: 45_000 });
    if (cmd.error?.code === 'ETIMEDOUT') {
      const error = new Error('NEWMAN_TIMEOUT_PARADA_SEGURIDAD');
      error.code = 'ETIMEDOUT';
      throw error;
    }
    if (cmd.error || !fs.existsSync(rep)) throw new Error(`NEWMAN_SIN_REPORTE ${cmd.error?.code ?? cmd.status}`);
    const bruto = JSON.parse(fs.readFileSync(rep, 'utf8'));
    const ex = bruto.run?.executions?.[0];
    if (!ex) throw new Error('NEWMAN_SIN_EJECUCION');
    const http = ex.response?.code ?? null;
    const eco = (ex.response?.header ?? []).find((h) => String(h.key).toLowerCase() === 'x-test-run-id')?.value;
    let cuerpo = null;
    try { cuerpo = JSON.parse(Buffer.from(ex.response.stream?.data ?? []).toString('utf8')); } catch { /* respuesta no JSON */ }
    const fallos = (bruto.run?.failures ?? []).map((f) => ({
      nombre: String(f.error?.test ?? f.source?.name ?? 'asercion'),
      mensaje: sanearArtefacto(String(f.error?.message ?? ''), secretos).slice(0, 250) }));
    const newmanDir = path.join(contrato.directorio, 'newman');
    fs.mkdirSync(newmanDir, { recursive: true });
    const nombre = `newman-${variables.caso}-${String(indice).padStart(2, '0')}.json`;
    fs.writeFileSync(path.join(newmanDir, nombre), sanearArtefacto(JSON_BONITO(bruto), secretos));
    return { archivo: `newman/${nombre}`, http, cuerpo, fallos, eco: eco === variables.run_id,
      aserciones: bruto.run?.stats?.assertions?.total ?? 0, latencia_ms: Date.now() - inicio,
      ejecuciones: bruto.run?.executions?.length ?? 0, status_proceso: cmd.status };
  } finally { fs.rmSync(temporal, { recursive: true, force: true }); }
}

export function consolidarNewman(resultado, directorio) {
  const informes = resultado.newman.map((x) => ({ archivo: x.archivo, caso: x.caso,
    comprobacion: x.check_id, http: x.http, aserciones: x.aserciones,
    fallos: x.fallos, ejecuciones: x.ejecuciones }));
  const esc = (s) => String(s).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
  const filas = informes.map((x) => `<tr><td>${esc(x.caso)}</td><td>${esc(x.comprobacion)}</td><td>${esc(x.http)}</td><td>${esc(x.aserciones)}</td><td>${esc(x.fallos.length)}</td><td>${esc(x.archivo)}</td></tr>`).join('');
  const detalles = informes.map((x) => {
    const reporte = JSON.parse(fs.readFileSync(path.join(directorio, x.archivo), 'utf8'));
    const solicitudes = (reporte.run?.executions ?? []).map((ex) => {
      const aserciones = (ex.assertions ?? []).map((a) => `<li>${esc(a.assertion ?? a.name ?? 'Aserción')}: ${a.error ? 'FALLA' : 'OK'}</li>`).join('');
      return `<h3>${esc(ex.item?.name ?? 'Solicitud')}</h3><p>${esc(ex.request?.method ?? '?')} — HTTP ${esc(ex.response?.code ?? '?')}</p><ul>${aserciones}</ul>`;
    }).join('');
    return `<h2>${esc(x.caso)} ${esc(x.comprobacion)}</h2><p>Solicitudes: ${esc(x.ejecuciones)}; aserciones: ${esc(x.aserciones)}.</p>${solicitudes}<pre>${esc(JSON_BONITO(x.fallos))}</pre>`;
  }).join('');
  const html = `<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G89 consolidado</title><h1>Newman G89: solicitudes y aserciones</h1><table border="1"><tr><th>Caso</th><th>Comprobación</th><th>HTTP</th><th>Aserciones</th><th>Fallos</th><th>JSON</th></tr>${filas}</table>${detalles}</html>`;
  if (informes.length) {
    const archivo = 'newman/newman-G89-consolidado.html';
    fs.writeFileSync(path.join(directorio, archivo), html);
    resultado.evidencias.push(archivo);
  }
}

export async function evaluar(contrato, { valores = leerEnv(), newman = ejecutarNewman } = {}) {
  fs.mkdirSync(contrato.directorio, { recursive: true });
  const previoLocal = preflightLocal(contrato, valores);
  fs.writeFileSync(path.join(contrato.directorio, 'preflight.json'), JSON_BONITO(previoLocal.resultado));
  if (!previoLocal.resultado.ok) return 2;
  exigirAmbiente(valores);
  const base = valores.SIGAB_API_TEST_BASE.replace(/\/$/, '');
  const runId = contrato.runId.slice(4);
  const secretos = [valores.QA_SANDBOX_SECRET, valores.BROKER_SERVICE_TOKEN,
    valores.QA_ADMIN_EMAIL, valores.QA_ADMIN_PASSWORD, valores.QA_PROD_EMAIL,
    valores.QA_PROD_PASSWORD, valores.QA_G88_169_171_SERIAL].filter(Boolean);
  const resultado = { grupo: 'G89', rf: 'RF-58', casos: Object.fromEntries(CASOS.map((id) => [id, {
    veredicto: null, estado_tecnico: 'NO_EJECUTADA', comprobaciones: [], prerequisitos: [] }])),
  ejecucion: { run_id: contrato.runId, version: contrato.version, ambiente: 'TEST',
    autorizacion: contrato.referencia, inicio: new Date().toISOString(),
    operacion: contrato.operacion, commit: contrato.contexto.commit ?? 'NO_VERIFICADO' },
  semilla: null, plan_temporal: previoLocal.temporal, bitacora: [], newman: [], evidencias: ['resultado.json', 'preflight.json'],
  alertas_creadas: [], telemetrias_creadas: [], incidencias: [], hallazgos: [], problemas_tecnicos: [],
  cierre: { http: null, rollback_verificado: false, comprobaciones: [], motivo: 'NO_EJECUTADO' },
  parada_seguridad: null };
  const transporte = crearTransporte({ base, runId, secreto: valores.QA_SANDBOX_SECRET,
    bitacora: resultado.bitacora, secretos });
  const { solicitar } = transporte;
  let tokenAdmin, tokenProd, indice = 0, previo, abortado = false;
  const rutaDashboard = `/iot/monitoreo/dashboard?id_infraestructura=${SEMILLA.area}&por_pagina=50`;
  const auth = async (rol) => {
    const x = await solicitar('POST', '/sesiones/', { cuerpo: {
      correo_electronico: valores[`QA_${rol}_EMAIL`], contrasena: valores[`QA_${rol}_PASSWORD`] }, enRun: false });
    afirmar(x.status === 200 && x.json?.token, `LOGIN_${rol}_HTTP_${x.status}`);
    secretos.push(x.json.token);
    return x.json.token;
  };
  const leer = async (ruta, token = tokenAdmin) => solicitar('GET', ruta, { token });
  const checkpoint = (caso, etapa, id, idAlerta = null) => {
    let n;
    try { n = newman({ contrato, indice: ++indice, secretos, variables: {
      qa_autorizado: 'SI', base_url: base, run_id: runId,
      sandbox_secret: valores.QA_SANDBOX_SECRET, token_productor: tokenProd,
      area_id: SEMILLA.area, sensor_id: SEMILLA.sensor, caso, check_id: id,
      esperado_estado: { base173: 'VERDE', critica: 'ROJO', base174: 'VERDE',
        noCriticaActiva: 'AMARILLO', resuelta: 'VERDE', baseDescarte: 'VERDE',
        noCriticaDescarte: 'AMARILLO', descartada: 'VERDE' }[etapa],
      esperado_alerta: idAlerta ?? '' } }); }
    catch (e) { if (e.code === 'ETIMEDOUT') transporte.detener(); throw e; }
    resultado.newman.push({ caso, check_id: id, archivo: n.archivo, http: n.http,
      fallos: n.fallos, aserciones: n.aserciones, ejecuciones: n.ejecuciones });
    resultado.evidencias.push(n.archivo);
    resultado.bitacora.push({ metodo: 'GET', ruta: '/iot/monitoreo/dashboard', en_run: true,
      latencia_ms: n.latencia_ms, http: n.http, eco_run: n.eco,
      via: 'Newman', caso, comprobacion: id });
    const c = evaluarComprobacion(caso, etapa, n.cuerpo, idAlerta);
    c.id_comprobacion = id; c.http = n.http; c.evidencia = n.archivo;
    if (n.http !== 200 || n.ejecuciones !== 1 || n.aserciones < 3
      || !n.eco || !Array.isArray(n.cuerpo?.sensores)) {
      c.cumple = false;
      throw new Error(`NEWMAN_RESPUESTA_O_CONTEXTO_NO_CONCLUYENTE_${n.http}_${n.ejecuciones}`);
    }
    if (c.cumple && n.fallos.length) throw new Error('NEWMAN_SCRIPT_O_CONTEXTO_FALLIDO');
    resultado.casos[caso].comprobaciones.push(c);
    return c;
  };
  const ingestar = async (marca) => {
    const x = await solicitar('POST', '/iot/telemetria', { token: valores.BROKER_SERVICE_TOKEN,
      cuerpo: { device_id: SEMILLA.dispositivo, sensor_id: SEMILLA.sensor,
        tipo_variable: SEMILLA.tipo_variable, valor: SEMILLA.valor, unidad: SEMILLA.unidad,
        timestamp_captura: marca, serial: valores.QA_G88_169_171_SERIAL,
        nivel_bateria: 81, calidad_senal_rssi: -71, calidad_senal_snr: 7.5 } });
    afirmar(x.status === 201 && Number.isInteger(Number(x.json?.id_telemetria)), `INGESTA_HTTP_${x.status}`);
    resultado.telemetrias_creadas.push(Number(x.json.id_telemetria));
    return Number(x.json.id_telemetria);
  };
  const alertar = async (severidad, idTelemetria) => {
    const x = await solicitar('POST', '/iot/alertas', { token: valores.BROKER_SERVICE_TOKEN,
      cuerpo: cuerpoAlerta({ serial: valores.QA_G88_169_171_SERIAL, severidad,
        idTelemetria, timestampEvento: resultado.plan_temporal.ancla }) });
    const id = exigirAlertaNueva(x, severidad);
    resultado.alertas_creadas.push(id);
    const detalle = await leer(`/iot/alertas/${id}`);
    afirmar(detalle.status === 200 && detalle.json?.estado_alerta === 'ACTIVA'
      && detalle.json?.severidad === severidad && Number(detalle.json?.id_sensor) === SEMILLA.sensor,
    `ALERTA_${id}_NO_ACREDITADA`);
    return id;
  };
  const transicionar = async (id, nuevo_estado) => {
    const x = await solicitar('PATCH', `/iot/alertas/${id}/estado`, { token: tokenAdmin,
      cuerpo: { nuevo_estado, motivo: `QA G89 ${nuevo_estado}` } });
    afirmar(x.status === 200 && x.json?.estado_alerta === nuevo_estado,
      `TRANSICION_${nuevo_estado}_HTTP_${x.status}`);
  };
  const registrarError = (id, e) => {
    resultado.casos[id].estado_tecnico = String(e.message).startsWith('ALERTA_DUPLICADA_')
      ? 'ERROR_QA' : 'NO_CONCLUYENTE';
    resultado.casos[id].prerequisitos.push(sanearArtefacto(String(e.message), secretos));
  };
  try {
    tokenAdmin = await auth('ADMIN'); tokenProd = await auth('PROD');
    transporte.configurarEscenario({ marcas: resultado.plan_temporal.marcas,
      ancla: resultado.plan_temporal.ancla, serial: valores.QA_G88_169_171_SERIAL,
      telemetrias: resultado.telemetrias_creadas,
      alertas: resultado.alertas_creadas });
    transporte.abrir();
    const apertura = await leer('/usuarios/me', tokenProd);
    afirmar(apertura.status === 200, 'APERTURA_RUN_FALLIDA');
    resultado.semilla = await verificarSemilla(solicitar, tokenAdmin, valores.QA_G88_169_171_SERIAL);
    const antes = await leer(rutaDashboard, tokenProd);
    afirmar(antes.status === 200, 'DASHBOARD_PREVIO_NO_DISPONIBLE');
    previo = antes;
    const marcas = resultado.plan_temporal.marcas;
    let critica = null;
    try {
      const tel = await ingestar(marcas[0]);
      const base173 = checkpoint('TC-M03-173', 'base173', 'PRE-173-01');
      afirmar(base173.cumple, 'BASE_173_NO_VERDE');
      critica = await alertar('CRITICO', tel);
      checkpoint('TC-M03-173', 'critica', 'API-173-01', critica);
      resultado.casos['TC-M03-173'] = { ...resultado.casos['TC-M03-173'],
        ...decidirCaso(resultado.casos['TC-M03-173']) };
    } catch (e) { registrarError('TC-M03-173', e); }
    // El segundo caso es independiente tras cerrar la alerta crítica conocida.
    if (critica) {
      await transicionar(critica, 'EN_ATENCION'); await transicionar(critica, 'RESUELTA');
    } else {
      const activas = await leer(`/iot/alertas?estado=ACTIVA&id_sensor=${SEMILLA.sensor}`);
      afirmar(activas.status === 200 && Number(activas.json?.total) === 0,
        'ALERTA_CRITICA_INCIERTA_IMPIDE_REUSO_SENSOR');
    }
    try {
      const tel2 = await ingestar(marcas[1]);
      const base174 = checkpoint('TC-M03-174', 'base174', 'PRE-174-01');
      afirmar(base174.cumple, 'BASE_174_NO_VERDE');
      const leve = await alertar('LEVE', tel2);
      checkpoint('TC-M03-174', 'noCriticaActiva', 'API-174-01');
      await transicionar(leve, 'EN_ATENCION'); await transicionar(leve, 'RESUELTA');
      checkpoint('TC-M03-174', 'resuelta', 'API-174-02');
      const tel3 = await ingestar(marcas[2]);
      const baseDescarte = checkpoint('TC-M03-174', 'baseDescarte', 'PRE-174-02');
      afirmar(baseDescarte.cumple, 'BASE_DESCARTE_NO_VERDE');
      const moderada = await alertar('MODERADO', tel3);
      checkpoint('TC-M03-174', 'noCriticaDescarte', 'API-174-03');
      await transicionar(moderada, 'DESCARTADA');
      checkpoint('TC-M03-174', 'descartada', 'API-174-04');
      resultado.casos['TC-M03-174'] = { ...resultado.casos['TC-M03-174'],
        ...decidirCaso(resultado.casos['TC-M03-174']) };
    } catch (e) { registrarError('TC-M03-174', e); }
  } catch (e) {
    abortado = true;
    resultado.problemas_tecnicos.push(sanearArtefacto(String(e.message), secretos));
    if (transporte.estado().detenido) resultado.parada_seguridad = {
      causa: 'TIMEOUT_O_ABORT', casos_pendientes: CASOS.filter((id) => !resultado.casos[id].veredicto) };
  } finally {
    if (transporte.estado().abierto) {
      try {
        const c = await solicitar('DELETE', `/test-control/runs/${runId}`, { cierre: true, enRun: false });
        resultado.cierre.http = c.status;
      } catch (e) { resultado.cierre.motivo = sanearArtefacto(String(e.message), secretos); }
      try {
        if (resultado.cierre.http === 200) {
          tokenAdmin = await auth('ADMIN');
          tokenProd = await auth('PROD');
          const actual = await leer(rutaDashboard, tokenProd);
          resultado.cierre.comprobaciones.push(compararDashboard(previo, actual));
          for (const id of resultado.alertas_creadas) {
            const a = await leer(`/iot/alertas/${id}`);
            resultado.cierre.comprobaciones.push({ tipo: 'alerta_ausente', http: a.status,
              coincide: a.status === 404, id_alerta: id });
          }
          if (resultado.telemetrias_creadas.length) {
            const inicio = resultado.plan_temporal.marcas[0].slice(0, 10);
            const fin = new Date().toISOString().slice(0, 10);
            const h = await leer(`/iot/monitoreo/historial?fecha_inicio=${inicio}&fecha_fin=${fin}&sensor_id=${SEMILLA.sensor}&por_pagina=200`);
            const completo = h.status === 200 && Array.isArray(h.json?.items)
              && Number(h.json.total) === h.json.items.length;
            const ausentes = completo && resultado.telemetrias_creadas.every((id) =>
              !h.json.items.some((x) => Number(x.id_telemetria) === id));
            resultado.cierre.comprobaciones.push({ tipo: 'telemetrias_ausentes', http: h.status,
              completo, coincide: ausentes, total_ids: resultado.telemetrias_creadas.length });
          }
          if (!resultado.alertas_creadas.length && !resultado.telemetrias_creadas.length)
            resultado.cierre.comprobaciones.push({ tipo: 'sin_objetos_creados', coincide: true,
              detalle: 'No se crearon alertas ni telemetrías en el RUN.' });
          resultado.cierre.rollback_verificado = confirmarRollback(resultado.cierre,
            resultado.alertas_creadas, resultado.telemetrias_creadas);
          resultado.cierre.motivo = resultado.cierre.rollback_verificado
            ? 'DELETE y lecturas posteriores acreditan reversión de los objetos comprobados.'
            : 'DELETE ejecutado; reversión no confirmada por todas las lecturas.';
        }
      } catch (e) { resultado.cierre.motivo = sanearArtefacto(String(e.message), secretos); }
    }
    resultado.ejecucion.fin = new Date().toISOString();
    for (const id of CASOS) if (!resultado.casos[id].veredicto && resultado.casos[id].estado_tecnico === 'NO_EJECUTADA')
      resultado.casos[id].motivo = 'No ejecutado por fallo previo o parada de seguridad.';
    if (resultado.newman.length) consolidarNewman(resultado, contrato.directorio);
    resultado.incidencias = CASOS.flatMap((id) => resultado.casos[id].comprobaciones
      .filter((x) => x.http === 200 && !x.cumple && !x.id_comprobacion.startsWith('PRE-'))
      .map((x) => ({ caso: id, comprobacion: x.id_comprobacion, evidencia: x.evidencia,
        equipo_inicial: 'Desarrollo', severidad: 'MEDIA', certeza: 'CONFIRMADA',
        causa_raiz: 'NO DETERMINADA' })));
    completarResultado(resultado, contrato.directorio);
    if (abortado || resultado.parada_seguridad) resultado.oficial = false;
    resultado.estado = resultado.oficial ? 'COMPLETO' : 'NO_CONCLUYENTE';
    const limpio = JSON.parse(sanearArtefacto(JSON_BONITO(resultado), secretos));
    fs.writeFileSync(path.join(contrato.directorio, 'resultado.json'), JSON_BONITO(limpio));
    fs.writeFileSync(path.join(contrato.directorio, contrato.version === 1
      ? 'TC-M03-G89_resultado.md' : `TC-M03-G89_reevaluacion_V${contrato.version}.md`),
    informe(limpio));
    validarResultado(limpio, contrato.directorio);
  }
  return resultado.estado === 'COMPLETO' ? 0 : 3;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const a = process.argv.slice(2);
  if (a.length === 1 && a[0] === '--capacidades') console.log(JSON_BONITO(CAPACIDADES));
  else if (a.length === 1 && a[0] === '--comprobar') process.exitCode = comprobar();
  else {
    try {
      const contrato = contextoEjecucion(a, { grupo: 'G89', casos: CASOS, directorio: DIR });
      if (contrato.operacion === 'recuperar') throw new Error('RECUPERACION_REQUIERE_CIERRE_MANUAL_DEL_RUN_OBJETIVO');
      process.exitCode = await evaluar(contrato);
    } catch (e) { console.error(`G89: ${e.message}`); process.exitCode = 2; }
  }
}
