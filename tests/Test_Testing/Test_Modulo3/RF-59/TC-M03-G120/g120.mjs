#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';
import { sanearArtefacto } from './lib/seguridad.mjs';
import PRESUPUESTO from './lib/g120_presupuesto.cjs';
import { CASOS, IDS, CAPACIDADES, marcas, fixture, filas, evaluarHistorial, sincronizacion } from './lib/g120_escenario.mjs';

const require = createRequire(import.meta.url);
const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION = path.join(DIR, 'G120.postman_collection.json');
const BACKEND = 'referencia origin/test 5b46ca00a0ba92774f8e3d4b9eeaeec169344f17; commit desplegado en TEST no verificado';
const ORACULOS = [
  'Las lecturas sincronizadas aparecen en el historial con su timestamp_captura original, se identifican con origen_dato = BUFFER_LOCAL y se diferencian de las lecturas TIEMPO_REAL, sin dejar vacíos dentro del intervalo controlado.',
  'Después de la segunda sincronización, el historial contiene una sola lectura lógica para la combinación (sensor_id, timestamp_captura); no aparecen duplicados ni se altera el timestamp original.',
  'Ambas lecturas son integradas al historial conservando su timestamp_captura original. El sistema registra también el momento de sincronización, permitiendo comprobar el retraso de 23 h y 24 h respectivamente.',
];
const ARCHIVOS = ['README.md', 'g120.mjs', 'G120.postman_collection.json',
  'lib/contrato_ejecutor.mjs', 'lib/seguridad.mjs', 'lib/g120_escenario.mjs', 'lib/g120_presupuesto.cjs',
  'pruebas/registro_qa.mjs', 'pruebas/g120_ensayo.mjs', 'pruebas/g120.test.mjs'];
const json = (p, x) => fs.writeFileSync(p, JSON.stringify(x, null, 2));
const rutaHistorial = (sensor, variable, inicio, fin) => `/iot/monitoreo/historial?${new URLSearchParams({
  fecha_inicio: inicio, fecha_fin: fin, sensor_id: String(sensor), tipo_variable: variable,
  por_pagina: '500', pagina: '1', orden: 'ASC' })}`;
const fechas = m => [m.bordes[1].slice(0, 10), m.envio.slice(0, 10)];
export function leerEnv(proceso = process.env, archivo = path.join(RAIZ, '.env.qa')) {
  const env = {};
  if (fs.existsSync(archivo)) for (const linea of fs.readFileSync(archivo, 'utf8').split(/\r?\n/)) {
    const m = linea.match(/^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$/);
    if (m) env[m[1]] = m[2].trim().replace(/^(['"])(.*)\1$/, '$2');
  }
  Object.assign(env, proceso);
  env.QA_AUTORIZADO = proceso.QA_AUTORIZADO;
  return env;
}
export function preflight(c, env, ensayo = false) {
  const claves = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'BROKER_SERVICE_TOKEN',
    'QA_PROD_EMAIL', 'QA_PROD_PASSWORD'];
  const barreras = claves.filter(k => !String(env[k] ?? '').trim());
  const base = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base) : base !== API) barreras.push('API_NO_CANONICA');
  if (c.version > 1 && c.operacion !== 'reevaluar') barreras.push('REEVALUACION_SIN_DECISION');
  if (c.operacion === 'recuperar') barreras.push('RECUPERACION_NO_IMPLEMENTADA');
  return { fase: 'PREFLIGHT_LOCAL', grupo: 'G120', run_id: c.runId, version: c.version,
    barreras, variables: [...claves, 'QA_ADMIN_EMAIL', 'QA_ADMIN_PASSWORD'].map(nombre => ({ nombre, presente: !!env[nombre] })),
    decision_qa: { fecha: '2026-10-26', informativa: true,
      efecto_auditoria_externo: 'Aceptado para declaración en SOL: ruta_ingesta_auditada.py puede persistir auditoría ante 422 estructural o fallo de persistencia.',
      momento_sincronizacion: 'Observación: TC-M03-243 se decide por ambas lecturas en historial con timestamp_captura original; consultar RF-63 como Administrador si tiene permiso (39,2). Su ausencia no cambia el veredicto.' },
    efectos_declarados: ['login_persistente_fuera_RUN', 'lectura_rollback_fuera_RUN',
      'dashboard_sin_umbral_puede_enviar_correo_y_registrar_auditoria_fuera_RUN',
      'rechazo_estructural_o_5xx_podria_auditar_fuera_RUN', 'worker_postcommit_independiente'],
    presupuesto: PRESUPUESTO, ok: barreras.length === 0 };
}
function newmanPaquete() {
  try { return path.dirname(require.resolve('newman/package.json', { paths: [RAIZ] })); }
  catch {
    const carpeta = String(process.env.PATH ?? '').split(path.delimiter)
      .find(p => fs.existsSync(path.join(p, 'node_modules', 'newman', 'package.json')));
    if (!carpeta) throw Error('NEWMAN_NO_RESUELTO');
    return path.join(carpeta, 'node_modules', 'newman');
  }
}
function validarNewman() {
  try {
    const paquete = newmanPaquete();
    return { ok: typeof require(paquete).run === 'function', version: require(path.join(paquete, 'package.json')).version, error: null };
  } catch (e) { return { ok: false, version: null, error: e.code ?? e.message }; }
}
export function comprobar() {
  let sintaxis = false;
  try {
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const e of col.item.flatMap(i => i.event ?? [])) new vm.Script((e.script?.exec ?? []).join('\n'));
    sintaxis = col.item.length === 1 && col.item[0].request.method === 'GET'
      && IDS.every(id => JSON.stringify(col).includes(id));
  } catch { /* se reporta sintaxis=false */ }
  const presentes = fs.readdirSync(DIR).filter(x => !['lib', 'pruebas', 'Resultados', 'EvaluacionV2'].includes(x))
    .concat(...['lib', 'pruebas'].map(d => fs.readdirSync(path.join(DIR, d)).map(x => `${d}/${x}`)));
  const faltantes = ARCHIVOS.filter(x => !fs.existsSync(path.join(DIR, x)));
  const inesperados = presentes.filter(x => !ARCHIVOS.includes(x));
  const resultadoSuperior = fs.existsSync(path.join(DIR, 'Resultados'))
    && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const ok = sintaxis && !faltantes.length && !inesperados.length && !resultadoSuperior;
  console.log(JSON.stringify({ grupo: 'G120', ok, sintaxis, faltantes, inesperados, resultadoSuperior, presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}
async function pedir(api, metodo, ruta, { token, secreto, runId, cuerpo, bitacora, timeout = 30000, presupuesto, cierre = false } = {}) {
  if (presupuesto) {
    if (runId && presupuesto.ultimaPeticionRun && Date.now() - presupuesto.ultimaPeticionRun > PRESUPUESTO.inactividad_guardia_segundos * 1000)
      throw Error('INACTIVIDAD_RUN_EXCEDIDA');
    if (runId) presupuesto.ultimaPeticionRun = Date.now();
    presupuesto.directas++;
    if (presupuesto.directas > PRESUPUESTO.solicitudes_directas - (cierre ? 0 : PRESUPUESTO.margen_cierre)
      || (!cierre && Date.now() - presupuesto.inicio > (PRESUPUESTO.duracion_segundos - 60) * 1000))
      throw Error('PRESUPUESTO_EXCEDIDO');
  }
  const headers = { Accept: 'application/json', 'X-Zona-Horaria': 'UTC' };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (secreto) headers['X-Sandbox-Secret'] = secreto;
  if (runId) headers['X-Test-Run-Id'] = runId;
  if (cuerpo) headers['Content-Type'] = 'application/json';
  let http = null, eco = false;
  try {
    const r = await fetch(api + ruta, { method: metodo, headers, body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      redirect: 'manual', signal: AbortSignal.timeout(timeout) });
    http = r.status; eco = r.headers.get('X-Test-Run-Id') === runId;
    return { http, eco, cuerpo: await r.json().catch(() => null) };
  } finally { bitacora?.push({ metodo, ruta, http, en_run: !!runId, eco: runId ? eco : null }); }
}
function exigir(x, descripcion) {
  if (x.http !== 200 || !x.eco) throw Error(`${descripcion}: HTTP ${x.http ?? 'sin respuesta'}, eco ${x.eco}`);
  return x.cuerpo;
}
function errorPublico(cuerpo) {
  if (!cuerpo || typeof cuerpo !== 'object') return null;
  const d = cuerpo.detail;
  const fuente = d && typeof d === 'object' && !Array.isArray(d) ? d : cuerpo;
  const valor = x => typeof x === 'string' ? x.slice(0, 300) : null;
  return { codigo: valor(fuente.error_code ?? fuente.code ?? fuente.codigo),
    mensaje: valor(fuente.message ?? fuente.mensaje ?? fuente.error ?? (typeof d === 'string' ? d : null)),
    campo: valor(fuente.field ?? fuente.campo),
    campos: Array.isArray(fuente.fields) ? fuente.fields.slice(0, 5).map(x => ({ campo: valor(x.field),
      mensaje: valor(x.message) })) : null,
    timestamp: valor(fuente.timestamp),
    detalle: Array.isArray(d) ? d.slice(0, 5).map(x => ({ campo: Array.isArray(x.loc) ? x.loc.slice(-2).join('.') : null,
      mensaje: valor(x.msg), tipo: valor(x.type) })) : null };
}
function aceptados(batch, esperados) {
  return batch?.http === 200 && batch.eco && Number(batch.cuerpo?.aceptados) === esperados
    && Array.isArray(batch.cuerpo?.detalle) && batch.cuerpo.detalle.length === esperados
    && batch.cuerpo.detalle.every(x => Number.isSafeInteger(Number(x.id_telemetria)) && Number(x.id_telemetria) > 0);
}
function rechazoAntiguedad(batch, marcas) {
  if (batch?.http !== 200 || !batch.eco || !Array.isArray(batch.cuerpo?.detalle)) return false;
  return batch.cuerpo.detalle.some(x => marcas.some(ts => Date.parse(ts) === Date.parse(x.timestamp_captura))
    && x.estado === 'RECHAZADO' && /(?:72\s*h|72\s*horas|antig[uü]edad|retraso\s+superior)/i.test(String(x.error ?? '')));
}
function motivoIngreso(x, nombre) {
  const errores = Array.isArray(x?.cuerpo?.detalle) ? x.cuerpo.detalle.filter(z => z.estado === 'RECHAZADO')
    .map(z => String(z.error ?? 'sin motivo')) : [];
  return `${nombre}: HTTP ${x?.http ?? 'sin respuesta'}, eco ${x?.eco ?? false}, aceptados ${x?.cuerpo?.aceptados ?? 'sin dato'}, rechazos ${errores.join(' | ') || 'sin motivo'}`;
}
function validarContrato(openapi) {
  const paths = openapi?.paths ?? {};
  const dto = JSON.stringify(openapi?.components?.schemas ?? {});
  return !!paths['/iot/telemetria/batch']?.post && !!paths['/iot/telemetria']?.post
    && !!paths['/configuracion/variables-ambientales']?.get
    && !!paths['/iot/monitoreo/historial']?.get
    && ['serial', 'timestamp_captura', 'timestamp_envio', 'origen', 'registros'].every(x => dto.includes(`"${x}"`));
}
async function descubrir(api, h, r, tokenAdmin = null) {
  const diag = r.diagnostico_semilla = { pasos: [], filtros: { dispositivos_activos_sensor: 0,
    sensores_activos_vinculados: 0, dashboard_verde: 0, historial_valido: 0, valores_aptos: 0 },
    alcance_incompleto: false, fuente: null, fuente_valor: null, errores_unidad: 0, sin_valor_seguro: 0,
    efecto_dashboard: 'GET dashboard puede registrar auditoría y enviar correo a administradores si hay sensores sin umbral' };
  const apto = x => x !== null && x !== undefined && x !== '' && Number.isFinite(Number(x));
  const consultar = async (paso, ruta, lista, tolerarTransporte = false, tokenLectura = null) => {
    let x;
    try { x = await pedir(api, 'GET', ruta, { ...h, token: tokenLectura ?? h.token,
      timeout: PRESUPUESTO.timeout_descubrimiento_ms }); }
    catch (e) {
      const presupuestoAgotado = /PRESUPUESTO|INACTIVIDAD_RUN/.test(String(e.message));
      if (presupuestoAgotado) diag.alcance_incompleto = true;
      diag.pasos.push({ paso, http: null, eco: null, recibidos: null, filtros: {},
        error: presupuestoAgotado ? String(e.message) : e.name ?? 'TRANSPORTE' });
      if (presupuestoAgotado) throw Error('ERROR_QA_BUSQUEDA_SEMILLA_ACOTADA');
      if (tolerarTransporte) { diag.errores_unidad++; return null; }
      throw Error(`ERROR_QA_SEMILLA_TRANSPORTE_${paso}`);
    }
    const items = lista(x.cuerpo);
    const registro = { paso, http: x.http, eco: x.eco,
      recibidos: Array.isArray(items) ? items.length : null, filtros: {} };
    diag.pasos.push(registro);
    if (x.http !== 200 || !x.eco) throw Error(`ERROR_QA_SEMILLA_HTTP_${paso}_${x.http ?? 'SIN_RESPUESTA'}`);
    if (!Array.isArray(items)) throw Error(`ERROR_QA_CONTRATO_SEMILLA_${paso}`);
    if (paso !== 'dispositivos_rf60' && (!Number.isSafeInteger(x.cuerpo?.total) || x.cuerpo.total < items.length))
      throw Error(`ERROR_QA_CONTRATO_SEMILLA_${paso}_TOTAL`);
    const campos = {
      dashboard_unidad: ['id_sensor', 'id_dispositivo_iot', 'estado_semaforo', 'estado_calidad',
        'ultimo_valor', 'ultima_unidad', 'tipo_variable'],
      historial_semilla: ['id_sensor', 'estado_calidad', 'valor', 'tipo_variable',
        'unidad_medida', 'timestamp_captura'],
    }[paso] ?? [];
    if (items.some(fila => !fila || campos.some(campo => !Object.hasOwn(fila, campo))))
      throw Error(`ERROR_QA_CONTRATO_SEMILLA_${paso}_CAMPOS`);
    return { cuerpo: x.cuerpo, items, registro };
  };
  const config = await consultar('dispositivos_config', '/configuracion/dispositivos-iot?solo_activos=true', x => x?.items);
  const catalogo = await consultar('variables_catalogo', '/configuracion/variables-ambientales',
    x => x?.items, false, tokenAdmin);
  if (catalogo.items.some(x => !Number.isSafeInteger(Number(x?.id_variable_ambiental))
    || !x?.nombre || !x?.unidad || !Number.isFinite(Number(x?.valor_fisico_min))
    || !Number.isFinite(Number(x?.valor_fisico_max)))) throw Error('ERROR_QA_CONTRATO_CATALOGO');
  const normalizar = nombre => nombre.normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .toUpperCase().replace(/[^A-Z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  const rf60 = await consultar('dispositivos_rf60', '/iot/dispositivos', x => x);
  if (config.cuerpo.total > config.items.length) diag.alcance_incompleto = true;
  if (config.items.some(x => !x || !Object.hasOwn(x, 'id_dispositivo_iot') || !Object.hasOwn(x, 'es_activo')
    || !Object.hasOwn(x, 'categoria') || !Object.hasOwn(x, 'serial') || !Object.hasOwn(x, 'id_infraestructura'))
    || rf60.items.some(x => !x || !Object.hasOwn(x, 'id_dispositivo_iot') || !Object.hasOwn(x, 'estado_actual')))
    throw Error('ERROR_QA_CONTRATO_SEMILLA_DISPOSITIVOS_CAMPOS');
  const conectividad = new Map(rf60.items.map(x => [Number(x.id_dispositivo_iot), x.estado_actual]));
  diag.conectividad = { activo: rf60.items.filter(x => x.estado_actual === 'ACTIVO').length,
    otros: rf60.items.filter(x => x.estado_actual !== 'ACTIVO').length };
  rf60.registro.filtros = { ...diag.conectividad };
  const dispositivos = config.items.filter(d => d?.es_activo === true && d.categoria !== 'CAMARA'
    && Number.isSafeInteger(Number(d.id_dispositivo_iot)) && Number(d.id_dispositivo_iot) > 0
    && Number.isSafeInteger(Number(d.id_infraestructura)) && Number(d.id_infraestructura) > 0
    && typeof d.serial === 'string' && d.serial.length > 0);
  diag.filtros.dispositivos_activos_sensor = dispositivos.length;
  config.registro.filtros.activos_no_camara_aptos = dispositivos.length;
  const porId = new Map(dispositivos.map(d => [Number(d.id_dispositivo_iot), d]));
  const unidades = [...new Set([...PRESUPUESTO.unidades_conocidas,
    ...dispositivos.map(d => Number(d.id_infraestructura))])];
  if (unidades.length > PRESUPUESTO.unidades_dashboard) diag.alcance_incompleto = true;
  const ahora = Date.now();
  const inicio = '1970-01-01';
  const fin = new Date(ahora).toISOString().slice(0, 10);
  const candidatos = [];
  for (const unidad of unidades.slice(0, PRESUPUESTO.unidades_dashboard)) {
    const dash = await consultar('dashboard_unidad', `/iot/monitoreo/dashboard/${unidad}?pagina=1&por_pagina=50`, x => x?.sensores, true);
    if (!dash) continue;
    if (Number(dash.cuerpo.total) > dash.items.length) diag.alcance_incompleto = true;
    const aptos = dash.items.filter(x => {
      const d = porId.get(Number(x.id_dispositivo_iot));
      return d && Number(d.id_infraestructura) === unidad && Number.isSafeInteger(Number(x.id_sensor))
        && Number(x.id_sensor) > 0;
    });
    const reciente = x => x.estado_calidad === 'LECTURA_VALIDA' && apto(x.ultimo_valor)
      && x.tipo_variable && x.ultima_unidad && Number.isFinite(Date.parse(x.ultimo_timestamp_captura))
      && Date.parse(x.ultimo_timestamp_captura) <= ahora
      && Date.parse(x.ultimo_timestamp_captura) >= ahora - 7 * 86400000;
    dash.registro.filtros.verdes_validos = aptos.filter(x => x.estado_semaforo === 'VERDE' && reciente(x)).length;
    dash.registro.filtros.lecturas_validas_recientes = aptos.filter(reciente).length;
    dash.registro.filtros.sensores_vinculables = aptos.length;
    diag.filtros.dashboard_verde += dash.registro.filtros.verdes_validos;
    candidatos.push(...aptos.map(x => ({ dispositivo: porId.get(Number(x.id_dispositivo_iot)), sensor: x })));
  }
  const reciente = x => x.estado_calidad === 'LECTURA_VALIDA' && apto(x.ultimo_valor)
    && Number.isFinite(Date.parse(x.ultimo_timestamp_captura))
    && Date.parse(x.ultimo_timestamp_captura) >= ahora - 7 * 86400000;
  candidatos.sort((a, b) => Number(reciente(b.sensor)) - Number(reciente(a.sensor)));
  const vistos = new Set();
  const cache = new Map();
  const intentados = new Set();
  let historiales = 0;
  const sensoresDe = async d => {
    const id = Number(d.id_dispositivo_iot);
    if (vistos.has(id)) return null;
    if (vistos.size >= PRESUPUESTO.dispositivos) { diag.alcance_incompleto = true; return null; }
    vistos.add(id);
    const sensores = await consultar('sensores', `/configuracion/dispositivos-iot/${id}/sensores`, x => x?.items);
    if (sensores.items.some(x => !x || !Object.hasOwn(x, 'id_sensores')
      || !Object.hasOwn(x, 'id_dispositivo_iot') || !Object.hasOwn(x, 'es_activo')))
      throw Error('ERROR_QA_CONTRATO_SEMILLA_SENSORES_CAMPOS');
    const activos = sensores.items.filter(s => s?.es_activo === true && Number(s.id_dispositivo_iot) === id
      && Number.isSafeInteger(Number(s.id_sensores)) && Number(s.id_sensores) > 0);
    sensores.registro.filtros.activos_vinculados = activos.length;
    diag.filtros.sensores_activos_vinculados += activos.length;
    if (activos.length > PRESUPUESTO.sensores_por_dispositivo) diag.alcance_incompleto = true;
    return activos;
  };
  const intentar = async (d, s, verde = null) => {
      const id = Number(d.id_dispositivo_iot), sensorId = Number(s.id_sensores);
      if (intentados.has(sensorId)) return null;
      if (historiales >= PRESUPUESTO.historiales_semilla) { diag.alcance_incompleto = true; return null; }
      intentados.add(sensorId);
      historiales++;
      const ruta = `/iot/monitoreo/historial?${new URLSearchParams({ fecha_inicio: inicio, fecha_fin: fin,
        sensor_id: String(sensorId), estado_dato: 'LECTURA_VALIDA', por_pagina: '20', pagina: '1', orden: 'DESC' })}`;
      const hist = await consultar('historial_semilla', ruta, x => x?.items);
      if (Number(hist.cuerpo.total) > hist.items.length) diag.alcance_incompleto = true;
      const validas = hist.items.filter(x => Number(x.id_sensor) === sensorId
        && x.estado_calidad === 'LECTURA_VALIDA' && apto(x.valor)
        && Number.isSafeInteger(Number(x.id_variable)) && x.tipo_variable && x.unidad_medida
        && Number.isFinite(Date.parse(x.timestamp_captura))
        && Date.parse(x.timestamp_captura) <= ahora && Date.parse(x.timestamp_captura) >= Date.parse(inicio));
      hist.registro.filtros.validas_historial = validas.length;
      const historico = validas[0];
      if (!historico) { diag.sin_valor_seguro++; return null; }
      const variables = catalogo.items.filter(x => Number(x.id_variable_ambiental) === Number(historico.id_variable)
        && x.nombre === historico.tipo_variable && x.unidad === historico.unidad_medida);
      if (variables.length !== 1) throw Error('ERROR_QA_VARIABLE_CATALOGO_NO_COINCIDE');
      const variable = variables[0];
      const codigo = normalizar(variable.nombre);
      if (!/^[A-Z][A-Z0-9_]{1,39}$/.test(codigo)) throw Error('ERROR_QA_CODIGO_VARIABLE_INVALIDO');
      diag.filtros.historial_valido++;
      const minimo = historico?.valor_min_umbral;
      const maximo = historico?.valor_max_umbral;
      const conUmbral = apto(minimo) && apto(maximo) && Number(minimo) <= Number(maximo);
      const valor = conUmbral
        ? (Number(minimo) + Number(maximo)) / 2
        : Number(historico.valor);
      if (!Number.isFinite(valor)) { diag.sin_valor_seguro++; return null; }
      diag.filtros.valores_aptos++;
      const semilla = { device_id: id, sensor_id: sensorId, serial: d.serial,
        id_variable: Number(variable.id_variable_ambiental), tipo_variable: codigo,
        nombre_variable: variable.nombre, unidad: variable.unidad, valor };
      r.semilla = { device_id: id, sensor_id: sensorId, id_variable: semilla.id_variable,
        tipo_variable: semilla.tipo_variable, unidad: semilla.unidad, valor };
      diag.fuente = verde ? 'dashboard' : 'sensores_dispositivo';
      diag.fuente_valor = { origen: conUmbral ? 'historial_umbral_punto_medio' : 'historial_LECTURA_VALIDA',
        timestamp_captura: historico.timestamp_captura, unidad: variable.unidad,
        rango: conUmbral ? [Number(minimo), Number(maximo)] : null };
      diag.estado_conectividad_informativo = conectividad.get(id) ?? 'NO_LISTADO';
      return semilla;
  };
  for (const { dispositivo: d, sensor } of candidatos) {
    const id = Number(d.id_dispositivo_iot);
    const activos = vistos.has(id) ? null : await sensoresDe(d);
    const disponibles = activos ?? cache.get(id) ?? [];
    if (activos) cache.set(id, activos);
    const s = disponibles.find(x => Number(x.id_sensores) === Number(sensor.id_sensor));
    if (s) { const semilla = await intentar(d, s, sensor); if (semilla) return semilla; }
  }
  for (const d of dispositivos) {
    const activos = cache.get(Number(d.id_dispositivo_iot)) ?? await sensoresDe(d);
    if (!activos) continue;
    for (const s of activos.slice(0, PRESUPUESTO.sensores_por_dispositivo)) {
      const semilla = await intentar(d, s);
      if (semilla) return semilla;
    }
  }
  if (dispositivos.length > vistos.size || historiales >= PRESUPUESTO.historiales_semilla) diag.alcance_incompleto = true;
  throw Error(diag.errores_unidad ? 'ERROR_QA_SEMILLA_UNIDADES_NO_EVALUADAS'
    : diag.alcance_incompleto ? 'ERROR_QA_BUSQUEDA_SEMILLA_ACOTADA'
      : diag.sin_valor_seguro ? 'DATOS_SEMILLA_SIN_VALOR_SEGURO' : 'DATOS_SEMILLA_NO_DISPONIBLES');
}
async function ejecutarNewman(c, api, token, env, semilla, m, secretos, ensayo) {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'g120-newman-'));
  try {
    const [inicio, fin] = fechas(m);
    const variables = { autorizado_run: 'SI', ensayo_loopback: ensayo ? 'SI' : 'NO', base_url: api,
      run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET, token,
      fecha_inicio: inicio, fecha_fin: fin, sensor_id: String(semilla.sensor_id),
      tipo_variable: semilla.nombre_variable, marcas: JSON.stringify(m) };
    const entorno = path.join(temp, 'entorno.json');
    json(entorno, { values: Object.entries(variables).map(([key, value]) => ({ key, value, enabled: true })) });
    const bruto = path.join(temp, 'newman.json');
    const p = await new Promise(resolve => {
      const newman = require(newmanPaquete());
      newman.run({ collection: JSON.parse(fs.readFileSync(COLECCION, 'utf8')),
        environment: JSON.parse(fs.readFileSync(entorno, 'utf8')),
        reporters: ['json'], reporter: { json: { export: bruto } },
        timeoutRequest: 30000, timeout: 60000, color: 'off' },
      (error, summary) => resolve({ status: error ? null : (summary?.run?.failures?.length ? 1 : 0),
        error: error?.message ?? null }));
    });
    if (!fs.existsSync(bruto)) return { proceso: p, error: 'SIN_REPORTE', artefactos: [], fallos: [], respuesta: null };
    const reporte = JSON.parse(fs.readFileSync(bruto, 'utf8'));
    const salida = path.join(c.directorio, 'newman'); fs.mkdirSync(salida, { recursive: true });
    fs.writeFileSync(path.join(salida, 'newman-G120.json'), sanearArtefacto(JSON.stringify(reporte), secretos));
    const ex = reporte.run?.executions?.[0];
    let cuerpo = null;
    try { cuerpo = JSON.parse(Buffer.from(ex?.response?.stream?.data ?? []).toString('utf8')); } catch { /* sin JSON */ }
    const http = ex?.response?.code ?? null;
    const eco = (ex?.response?.header ?? []).some(x => String(x.key).toLowerCase() === 'x-test-run-id' && x.value === c.runId);
    const fallos = (reporte.run?.failures ?? []).map(f => ({ name: String(f.error?.name ?? ''),
      test: String(f.error?.test ?? ''), source: String(f.source?.name ?? ''), mensaje: String(f.error?.message ?? '').slice(0, 150) }));
    const filasHtml = CASOS.map((caso, i) => `<tr><td>${caso}</td><td>${IDS[i]}</td><td>${fallos.some(f => f.test.includes(IDS[i])) ? 'FALLÓ' : 'sin fallo'}</td></tr>`).join('');
    fs.writeFileSync(path.join(salida, 'newman-G120.html'), `<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G120</title><h1>Newman G120</h1><p>HTTP ${http ?? 'sin respuesta'}; eco ${eco}</p><table>${filasHtml}</table></html>`);
    return { proceso: p, artefactos: ['newman/newman-G120.json', 'newman/newman-G120.html'],
      fallos, respuesta: { http, eco, cuerpo } };
  } finally {
    if (!path.resolve(temp).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
    fs.rmSync(temp, { recursive: true, force: true });
  }
}
async function observarAuditoria(api, tokenAdmin, bordes, h, r) {
  const ids = (bordes.cuerpo?.detalle ?? []).map(x => x.id_telemetria)
    .filter(x => Number.isSafeInteger(Number(x)) && Number(x) > 0).slice(0, 2);
  if (!tokenAdmin) { r.observacion_sincronizacion.auditoria = { estado: 'sin_login_admin' }; return; }
  if (ids.length !== 2) { r.observacion_sincronizacion.auditoria = { estado: 'sin_dos_ids_de_lectura' }; return; }
  const consultas = [];
  for (const id of ids) {
    try {
      const ruta = `/iot/auditoria?${new URLSearchParams({ entidad_afectada_id: String(id), pagina: '1', por_pagina: '50' })}`;
      const x = await pedir(api, 'GET', ruta, { ...h, token: tokenAdmin });
      const items = x.http === 200 && x.eco && Array.isArray(x.cuerpo?.items) ? x.cuerpo.items : [];
      consultas.push({ id_telemetria: Number(id), http: x.http, eco: x.eco, total: x.cuerpo?.total ?? null,
        eventos: items.filter(e => String(e.entidad_afectada_id) === String(id)).map(e => ({
          id_evento: e.id_evento, tipo_evento: e.tipo_evento, fecha_hora: e.fecha_hora,
          timestamp_sincronizacion: e.accion_detallada?.timestamp_sincronizacion ?? e.timestamp_sincronizacion ?? null,
        })) });
    } catch (e) { consultas.push({ id_telemetria: Number(id), error: String(e.message).slice(0, 80) }); }
  }
  r.observacion_sincronizacion.auditoria = { estado: 'consultada', filtro: 'entidad_afectada_id por lectura', consultas };
}
export function informe(r) {
  const global = r.oficial ? (Object.values(r.casos).some(x => x.estado === 'RECHAZADO') ? 'RECHAZADO' : 'APROBADO') : 'NO_CONCLUYENTE';
  const tabla = CASOS.map((caso, i) => `| ${caso} | ${IDS[i]} | API | ${r.casos[caso].estado} | Esperado: «${ORACULOS[i]}» Observado: ${r.casos[caso].motivo.replaceAll('|', '/')} | ${r.comprobaciones[i].evidencia ?? 'sin evidencia'} |`).join('\n');
  const incidencias = CASOS.flatMap((caso, i) => {
    if (r.ambiente !== 'TEST' || r.casos[caso].estado !== 'RECHAZADO' || !r.comprobaciones[i].evidencia) return [];
    const requisito = i === 0 ? 'RF-59 CA-3, Especificacion-Requerimientos-Modulo3.md:6240-6241: «los datos sincronizados deben aparecer con su timestamp_captura original y marcados como origen BUFFER_LOCAL».'
      : i === 1 ? 'RF-59 CA-18, Especificacion-Requerimientos-Modulo3.md:6289-6290: «misma clave de 4 campos (sensor_id, tipo_variable, timestamp_captura, origen)» y «la nueva lectura debe descartarse».'
      : 'RF-59 CA-3, Especificacion-Requerimientos-Modulo3.md:6240-6241; Restricción 14:5718-5721 permite hasta 72 horas; TC-M03-243 exige integrar las capturas de 23 h y 24 h.';
    if (r.casos[caso].motivo.includes('rechazada por antigüedad')) return [
      `### INC-M03-${caso.slice(-3)}-G120-01 — rechazo de BUFFER_LOCAL dentro de 72 h\n\n` +
      `- **ID:** INC-M03-${caso.slice(-3)}-G120-01; certeza CONFIRMADA por respuesta API del RUN; causa raíz NO DETERMINADA; identificador de informe, no ticket definitivo.\n` +
      `- **Equipo:** Desarrollo. Primera discrepancia: rechazo de la API pública a una lectura dentro de la ventana; no se atribuye causa técnica.\n` +
      `- **Severidad:** MEDIA. Una lectura de borde del escenario no se integra.\n` +
      `- **Requisito incumplido:** RF-59 Restricción 14, Especificacion-Requerimientos-Modulo3.md:5718-5721: buffer con desfase máximo de 72 horas; CA-3:6240-6241.\n` +
      `- **Precondiciones:** Sensor activo vinculado y dispositivo activo con serial; código aceptado por el catálogo M09, id_variable y unidad contrastados por API pública; captura 23 h o 24 h antes del envío.\n` +
      `- **Pasos:** Enviar las lecturas BUFFER_LOCAL dentro del RUN y consultar historial con eco.\n` +
      `- **Esperado:** Aceptación e integración con captura original.\n` +
      `- **Obtenido:** ${r.casos[caso].motivo}; batch ${JSON.stringify(r.ingestas.bordes)}.\n` +
      `- **Evidencia:** ${r.comprobaciones[i].evidencia}, resultado.json; rutas del RUN.\n` +
      `- **Análisis:** La respuesta acredita el rechazo; la causa raíz no está determinada.\n` +
      `- **Impacto:** No se acredita la integración de las dos capturas de borde.\n` +
      `- **Qué se necesita para cerrarla:** Desarrollo revisa el primer punto causal; QA repite con autorización de reevaluación.`];
    return [`### INC-M03-${caso.slice(-3)}-G120-01 — ${r.casos[caso].motivo}\n\n- **ID:** INC-M03-${caso.slice(-3)}-G120-01; certeza CONFIRMADA por API en RUN autorizado; causa raíz NO DETERMINADA; identificador de informe, no ticket definitivo.\n- **Equipo:** Desarrollo. La primera discrepancia aparece en la API pública de ingesta/historial; no se atribuye causa raíz.\n- **Severidad:** ${i === 2 ? 'MEDIA' : 'ALTA'}. ${i === 2 ? 'La integración de una lectura de borde falló' : 'Falla una función relevante de historial sin alternativa demostrada'} en la semilla observada.\n- **Requisito incumplido:** ${requisito}\n- **Precondiciones:** Dispositivo activo en configuración con serial y sensor activo vinculado; variable y unidad contrastadas entre historial y catálogo públicos, código normalizado del catálogo; valor obtenido del punto medio del umbral expuesto o de la última LECTURA_VALIDA; cuerpo validado contra OpenAPI.\n- **Pasos:** Login previo; ${i === 0 ? 'enviar intervalo BUFFER_LOCAL y contraste TIEMPO_REAL' : i === 1 ? 'enviar dos veces el mismo dato BUFFER_LOCAL' : 'enviar dos capturas BUFFER_LOCAL con 23 h y 24 h declaradas'} dentro del RUN; consultar historial con eco.\n- **Esperado:** ${i === 0 ? 'Intervalo completo con timestamp original, origen BUFFER_LOCAL y contraste TIEMPO_REAL' : i === 1 ? 'Una lectura lógica con timestamp original' : 'Ambas lecturas integradas con timestamp original'}.\n- **Obtenido:** ${r.casos[caso].motivo}; filas observadas: ${JSON.stringify(r.filas.filter(x => i === 0 ? r.marcas?.intervalo.includes(x.captura) || x.captura === r.marcas?.real : i === 1 ? x.captura === r.marcas?.duplicado : r.marcas?.bordes.includes(x.captura)))}; ingestas: ${JSON.stringify(i === 0 ? [r.ingestas.intervalo, r.ingestas.real] : i === 1 ? [r.ingestas.duplicado_primero, r.ingestas.duplicado_segundo] : [r.ingestas.bordes])}.\n- **Evidencia:** ${r.comprobaciones[i].evidencia}, resultado.json; rutas existentes en este RUN.\n- **Análisis:** La primera discrepancia está en la API pública; origin/test solo orienta hipótesis. Causa raíz NO DETERMINADA.\n- **Impacto:** El historial incumple la propiedad probada para este sensor.\n- **Qué se necesita para cerrarla:** Desarrollo debe localizar el primer punto causal; QA repetirá la comprobación pública con autorización de reevaluación.`];
  }).join('\n\n') || 'Ninguna incidencia de producto confirmada. La ausencia de timestamp_sincronizacion en el contrato origin/test es DEFECTO_FUNCIONAL_CANDIDATO hasta una respuesta pública de TEST.';
  return `# TC-M03-G120 — ${global}\n\n## Decisión del caso\n\n${CASOS.map(c => `${c}: **${r.casos[c].estado}** — ${r.casos[c].motivo}.`).join('\n\n')}\n\n| Caso | Comprobación | Fuente | Estado | Motivo | Evidencia |\n| --- | --- | --- | --- | --- | --- |\n${tabla}\n\n## Identificación\n\nGrupo G120; RF-59 / CU04; versión V${r.version}; RUN ${r.run_id}; ambiente ${r.ambiente}; autorización ${r.autorizacion}; presupuesto ${JSON.stringify(PRESUPUESTO)}; backend ${BACKEND}; Newman ${r.preflight_herramientas.newman?.version ?? 'no verificado'}. UI no requerida; Cypress 0. RUN ${r.oficial ? 'OFICIAL' : 'NO_OFICIAL'}.\n\n## Esperado y requisito\n\nMatriz Casos_Prueba(Modulo3 Agrupado).csv, registro TC-M03-G120: TC-M03-241 conserva captura y origen BUFFER_LOCAL sin vacíos; TC-M03-242 evita duplicado de sensor/captura; TC-M03-243 integra 23 h y 24 h con momento de sincronización. RF-59 CA-3:6240-6241, CA-18:6289-6290, restricciones 7/8/14:5677-5681,5718-5721. La matriz dice dos campos y 24 h; el requisito vigente cuatro campos y 72 h. La variable y origen se mantienen iguales en el duplicado y ambos retrasos quedan dentro de 72 h; no se altera el oráculo.\n\n## Observado por caso\n\nSemilla pública (sin serial): ${JSON.stringify(r.semilla ?? null)}. Marcas: ${JSON.stringify(r.marcas ?? null)}. Ingestas: ${JSON.stringify(r.ingestas)}. Sincronización expuesta: ${JSON.stringify(r.observacion_sincronizacion.batch)}. Filas saneadas: ${JSON.stringify(r.filas)}.\n\n## Diagnóstico de semilla\n\n${JSON.stringify(r.diagnostico_semilla ?? null)}. DATOS_SEMILLA_NO_DISPONIBLES indica ausencia de sensor apto; DATOS_SEMILLA_SIN_VALOR_SEGURO indica ausencia de umbral y lectura válida en el alcance completo. Un error de transporte sin semilla o una respuesta inesperada es ERROR_QA técnico.\n\n## Comprobaciones API/UI y evidencias\n\nAPI: ${r.comprobaciones.map(x => `${x.id}=${x.estado}`).join(', ')}. UI: no obligatoria, cero ejecuciones. Evidencias reales: ${r.evidencias.join(', ') || 'ninguna'}.\n\n## Incidencias de producto\n\n${incidencias}\n\n## Incidencias técnicas QA\n\n${r.problemas_tecnicos.join('; ') || 'Ninguna.'}\n\n## Observaciones\n\nDecisión QA 2026-10-26: se acepta para declarar en SOL la posible auditoría persistente fuera del sandbox de ruta_ingesta_auditada.py ante 422 estructural o fallo de persistencia. TC-M03-243 se decide por las dos lecturas BUFFER_LOCAL de 23 h y 24 h con timestamp_captura original. El caso pide registrar el momento de sincronización y RF-59 Restricción 14 (Especificacion-Requerimientos-Modulo3.md:5718-5721) lo exige para auditoría, sin exigir mostrarlo en historial. Lectura informativa RF-63 con Administrador y permiso (39,2): ${JSON.stringify(r.observacion_sincronizacion)}. Su ausencia no cambia el veredicto. Discrepancia documental: matriz pide clave de dos campos y 24 h; RF-59 CA-18 pide cuatro campos y Restricción 14 permite 72 h. Variable y origen se mantienen iguales; las capturas están dentro de 72 h.\n\n## Análisis de causas\n\nEl código revisado es origin/test; no prueba el despliegue ni la causa raíz de una discrepancia.\n\n## Efectos, cierre y rollback\n\nLogin Productor y posible login Administrador anteriores al RUN y lectura pública posterior al DELETE pueden persistir auditoría de sesión/consulta. Las escrituras de la sesión de ingesta se esperan revertidas por el sandbox y se comprueban por historial cuando existen escrituras. Sin escrituras confirmadas y sin resultado desconocido, DELETE 200 acredita el cierre sin escrituras de escenario. El worker postcommit usa conexión propia y podría persistir efectos si procesa datos visibles. Un 422 estructural o fallo de persistencia puede registrar auditoría fuera del RUN; DELETE no la revierte. DELETE RUN HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. Rollback ${r.cierre.rollback.verificado ? (r.cierre.rollback.metodo === 'sin_escrituras' ? 'verificado sin escrituras de escenario' : 'verificado por historial público') : 'NO verificado'}: ${r.cierre.rollback.motivo}.\n\n## Conclusión y acción\n\n${global}. ${r.oficial ? 'Conservar evidencia y derivar las incidencias confirmadas.' : 'Resolver los impedimentos documentados antes de un nuevo intento autorizado.'}\n`;
}
function finalizar(c, r, secretos) {
  const nombre = c.version === 1 ? 'TC-M03-G120_resultado.md' : `TC-M03-G120_reevaluacion_V${c.version}.md`;
  r.evidencias = [...new Set([...r.evidencias, 'resultado.json', nombre])];
  const archivosOk = r.evidencias.filter(x => x !== 'resultado.json' && x !== nombre)
    .every(x => fs.existsSync(path.join(c.directorio, x)));
  r.oficial = Object.values(r.casos).every(x => ['APROBADO', 'RECHAZADO'].includes(x.estado))
    && r.comprobaciones.every(x => ['APROBADO', 'RECHAZADO'].includes(x.estado) && !!x.evidencia)
    && r.cierre.run.cierre_http === 200 && r.cierre.rollback.verificado && archivosOk
    && r.problemas_tecnicos.length === 0;
  r.consume_version = r.oficial;
  const informeSaneado = sanearArtefacto(informe(r), secretos);
  fs.writeFileSync(path.join(c.directorio, nombre), informeSaneado);
  json(path.join(c.directorio, 'resultado.json'), JSON.parse(sanearArtefacto(JSON.stringify(r), secretos)));
}
export async function evaluar(c, { env, ensayo = false }) {
  if (!fs.existsSync(c.directorio)) throw Error('RUN_NO_CREADO_POR_LANZADOR');
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G120', run_id: c.runId, version: c.version, operacion: c.operacion,
    autorizacion: c.referencia, ambiente: ensayo ? 'LOOPBACK_LOCAL' : 'TEST', oficial: false,
    consume_version: false, casos: Object.fromEntries(CASOS.map(x => [x, { estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación' }])),
    comprobaciones: CASOS.map((caso, i) => ({ caso, fuente: 'API', id: IDS[i], tipo: 'ASSERT',
      estado: 'NO_CONCLUYENTE', motivo: 'Sin respuesta', evidencia: null })),
    cypress: { total_pruebas: 0 }, preflight_herramientas: {}, evidencias: [], bitacora: [],
    semilla: null, diagnostico_semilla: null, marcas: null, ingestas: {}, observacion_sincronizacion: { batch: null, auditoria: { estado: 'no_intentada' } }, filas: [],
    problemas_tecnicos: [], cierre: { run: { cierre_http: null }, rollback: { verificado: false, motivo: 'Sin cierre' } },
    inicio: new Date().toISOString() };
  const secretos = [env.QA_SANDBOX_SECRET, env.BROKER_SERVICE_TOKEN, env.QA_PROD_EMAIL, env.QA_PROD_PASSWORD,
    env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD].filter(Boolean);
  const presupuesto = { directas: 0, inicio: Date.now() };
  let tocado = false, token = null, tokenAdmin = null, semilla = null, m = null, escritos = [], desconocidas = 0;
  try {
    const pre = preflight(c, env, ensayo); json(path.join(c.directorio, 'preflight.json'), pre);
    r.evidencias.push('preflight.json');
    if (!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
    r.preflight_herramientas.newman = validarNewman();
    if (!r.preflight_herramientas.newman.ok) throw Error('NEWMAN_NO_DISPONIBLE');
    const open = await pedir(api, 'GET', '/openapi.json', { bitacora: r.bitacora, presupuesto });
    if (open.http !== 200 || !validarContrato(open.cuerpo)) throw Error('CONTRATO_INGESTA_HISTORIAL_NO_VERIFICADO');
    const login = await pedir(api, 'POST', '/sesiones/', { cuerpo: { correo_electronico: env.QA_PROD_EMAIL,
      contrasena: env.QA_PROD_PASSWORD }, bitacora: r.bitacora, presupuesto });
    if (login.http !== 200 || !login.cuerpo?.token) throw Error(`LOGIN_PRODUCTOR_HTTP_${login.http}`);
    token = login.cuerpo.token; secretos.push(token);
    if (env.QA_ADMIN_EMAIL && env.QA_ADMIN_PASSWORD) {
      try {
        const admin = await pedir(api, 'POST', '/sesiones/', { cuerpo: { correo_electronico: env.QA_ADMIN_EMAIL,
          contrasena: env.QA_ADMIN_PASSWORD }, bitacora: r.bitacora, presupuesto });
        if (admin.http === 200 && admin.cuerpo?.token) { tokenAdmin = admin.cuerpo.token; secretos.push(tokenAdmin); }
        else r.observacion_sincronizacion.auditoria = { estado: 'login_admin_no_disponible', http: admin.http };
      } catch (e) { r.observacion_sincronizacion.auditoria = { estado: 'login_admin_sin_respuesta', error: e.name }; }
    } else r.observacion_sincronizacion.auditoria = { estado: 'credenciales_admin_ausentes' };
    const h = { token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, bitacora: r.bitacora, presupuesto };
    tocado = true;
    semilla = await descubrir(api, h, r, tokenAdmin); secretos.push(semilla.serial);
    m = marcas(new Date().toISOString()); r.marcas = m;
    const [inicio, fin] = fechas(m); const ruta = rutaHistorial(semilla.sensor_id, semilla.nombre_variable, inicio, fin);
    const base = exigir(await pedir(api, 'GET', ruta, h), 'Historial basal');
    if (!Array.isArray(base.items) || Number(base.total) > 480
      || [...m.intervalo, m.duplicado, ...m.bordes].some(ts => filas(base.items, semilla, ts).length))
      throw Error('SEMILLA_CON_COLISION_O_HISTORIAL_NO_ACOTADO');
    const ocupadas = [...m.intervalo, m.duplicado, ...m.bordes].map(Date.parse);
    const existentes = base.items.filter(x => x.origen_dato === 'TIEMPO_REAL'
      && Number.isFinite(Date.parse(x.timestamp_captura))
      && Date.parse(x.timestamp_captura) <= Date.now()
      && !ocupadas.includes(Date.parse(x.timestamp_captura))
      && filas(base.items, semilla, x.timestamp_captura, 'TIEMPO_REAL').length === 1
      && filas(base.items, semilla, x.timestamp_captura).length === 1
      && Number.isSafeInteger(Number(x.id_telemetria)) && Number(x.id_telemetria) > 0)
      .sort((a, b) => Date.parse(b.timestamp_captura) - Date.parse(a.timestamp_captura));
    const contrasteExistente = existentes[0] ?? null;
    if (contrasteExistente) m.real = contrasteExistente.timestamp_captura;
    else {
      const ahora = Date.now();
      const candidata = [5, 6, 7, 8, 9, 10].map(min => new Date(ahora - min * 60000).toISOString())
        .find(ts => !filas(base.items, semilla, ts).length && !ocupadas.includes(Date.parse(ts)));
      if (!candidata) throw Error('COLISION_CONTRASTE_TIEMPO_REAL');
      m.real = candidata;
    }
    r.ingestas.real = contrasteExistente
      ? { fuente: 'historial_existente', http: null, eco: true,
        id_telemetria: contrasteExistente.id_telemetria, error: null, error_cuerpo: null }
      : { fuente: 'ingesta', http: null, eco: false, id_telemetria: null, error: null, error_cuerpo: null };
    const broker = { ...h, token: env.BROKER_SERVICE_TOKEN };
    const construir = (ts, origen, envio) => {
      const cuerpo = fixture(semilla, ts, origen, envio);
      if (ensayo && env.QA_G120_ENSAYO_TIPO_INVALIDO === 'SI') cuerpo.tipo_variable = 'TIPO_INVALIDO';
      return cuerpo;
    };
    const enviar = async (clave, registros) => {
      let x;
      try { x = await pedir(api, 'POST', '/iot/telemetria/batch', { ...broker, cuerpo: { registros } }); }
      catch (e) {
        if (String(e.message).includes('PRESUPUESTO_EXCEDIDO')) throw e;
        desconocidas += registros.length;
        x = { http: null, eco: false, cuerpo: null, error: e.name ?? 'SIN_RESPUESTA' };
      }
      r.ingestas[clave] = { http: x.http, eco: x.eco, aceptados: x.cuerpo?.aceptados ?? null,
        rechazados: x.cuerpo?.rechazados ?? null, duplicados: x.cuerpo?.duplicados ?? null,
        error: x.error ?? null, error_cuerpo: errorPublico(x.cuerpo),
        detalle: Array.isArray(x.cuerpo?.detalle) ? x.cuerpo.detalle.map(z => ({ sensor_id: z.sensor_id,
          timestamp_captura: z.timestamp_captura,
          estado: z.estado, id_telemetria: z.id_telemetria ?? null, error: typeof z.error === 'string' ? z.error.slice(0, 300) : null })) : [] };
      if (x.http === 200 && x.eco) {
        const confirmados = (x.cuerpo?.detalle ?? []).filter(z => z.id_telemetria && z.timestamp_captura);
        escritos.push(...confirmados.map(z => z.timestamp_captura));
        desconocidas += Math.max(0, Number(x.cuerpo?.aceptados ?? 0) - confirmados.length);
      } else if (x.http && x.http >= 500) desconocidas += registros.length;
      return x;
    };
    if (Date.now() - Date.parse(m.envio) > 45000) throw Error('VENTANA_SYNC_NO_CONTROLADA');
    const bordes = await enviar('bordes', m.bordes.map(ts => construir(ts, 'BUFFER_LOCAL', m.envio)));
    r.observacion_sincronizacion.batch = sincronizacion(bordes.cuerpo, m.bordes);
    if (Date.now() - Date.parse(m.envio) > 60000) r.observacion_sincronizacion.batch.estado = 'preparacion_tardia';
    const intervalo = await enviar('intervalo', m.intervalo.map(ts => construir(ts, 'BUFFER_LOCAL', m.envio)));
    let real = null;
    if (!contrasteExistente) {
      try { real = await pedir(api, 'POST', '/iot/telemetria', { ...broker,
        cuerpo: construir(m.real, 'TIEMPO_REAL', new Date().toISOString()) }); }
      catch (e) {
        if (String(e.message).includes('PRESUPUESTO_EXCEDIDO')) throw e;
        desconocidas++;
        real = { http: null, eco: false, cuerpo: null, error: e.name ?? 'SIN_RESPUESTA' };
      }
      r.ingestas.real = { fuente: 'ingesta', http: real.http, eco: real.eco,
        id_telemetria: real.cuerpo?.id_telemetria ?? null,
        error: real.error ?? null, error_cuerpo: errorPublico(real.cuerpo) };
      if (real.http === 201 && real.eco) {
        if (real.cuerpo?.id_telemetria) escritos.push(m.real);
        else desconocidas++;
      } else if (real.http && real.http >= 500) desconocidas++;
    }
    const primero = await enviar('duplicado_primero', [construir(m.duplicado, 'BUFFER_LOCAL', m.envio)]);
    const segundo = await enviar('duplicado_segundo', [construir(m.duplicado, 'BUFFER_LOCAL', m.envio)]);
    if ([bordes, intervalo, primero, segundo].some(x => Number(x.cuerpo?.rechazados) > 0
      && (x.cuerpo?.detalle ?? []).some(z => /variable no existe|tipo_variable|VARIABLE_NO_ENCONTRADA/i.test(String(z.error ?? '')))))
      r.problemas_tecnicos.push('ERROR_QA_CUERPO_TIPO_VARIABLE');
    if (real?.http === 404 && errorPublico(real.cuerpo)?.codigo === 'VARIABLE_NO_ENCONTRADA')
      r.problemas_tecnicos.push('ERROR_QA_CONTRASTE_TIPO_VARIABLE');
    await observarAuditoria(api, tokenAdmin, bordes, h, r);
    presupuesto.newman = (presupuesto.newman ?? 0) + 1;
    if (presupuesto.newman > PRESUPUESTO.solicitudes_newman) throw Error('PRESUPUESTO_NEWMAN_EXCEDIDO');
    const n = await ejecutarNewman(c, api, token, env, semilla, m, secretos, ensayo);
    r.evidencias.push(...n.artefactos);
    r.bitacora.push({ metodo: 'GET', ruta, http: n.respuesta?.http ?? null, en_run: true, eco: n.respuesta?.eco ?? false });
    const respuesta = n.respuesta;
    const falloTecnico = n.error || n.proceso?.error
      || (n.proceso?.status != null && n.proceso.status !== 0 && n.fallos.length === 0)
      || n.fallos.some(f => f.name !== 'AssertionError'
      || f.source !== 'API-G120-HISTORIAL' || !IDS.some(id => f.test.includes(`[${id}]`)));
    if (falloTecnico) r.problemas_tecnicos.push('NEWMAN_ERROR_SCRIPT_O_TRANSPORTE');
    if (respuesta?.http === 200 && respuesta.eco && Array.isArray(respuesta.cuerpo?.items)) {
      const evaluados = evaluarHistorial(respuesta.cuerpo.items, semilla, m);
      r.filas = evaluados[0].valores.todos ?? [];
      const httpCaso = [intervalo, primero, bordes];
      for (let i = 0; i < CASOS.length; i++) {
        let e = evaluados[i];
        const lote = httpCaso[i];
        const cantidad = i === 0 ? m.intervalo.length : i === 1 ? 1 : m.bordes.length;
        const marcasCaso = i === 0 ? m.intervalo : i === 1 ? [m.duplicado] : m.bordes;
        if (lote.http >= 500) e = { estado: 'BLOQUEADO', motivo: `Infraestructura de ingesta HTTP ${lote.http}` };
        else if (rechazoAntiguedad(lote, marcasCaso)) e = { estado: 'RECHAZADO',
          motivo: `Lectura BUFFER_LOCAL dentro de 72 h rechazada por antigüedad: ${motivoIngreso(lote, 'ingesta')}` };
        else if (!aceptados(lote, cantidad)) {
          const motivo = motivoIngreso(lote, 'ingesta');
          const datos = /dispositivo|sensor.*(?:inactivo|no encontrado)|autenticaci[oó]n/i.test(motivo);
          e = { estado: datos ? 'BLOQUEADO' : 'NO_CONCLUYENTE', motivo };
          if (!datos) r.problemas_tecnicos.push(`ERROR_QA_CUERPO_${CASOS[i]}: ${motivo}`);
        } else if (i === 0 && !contrasteExistente && real.http >= 500
          && evaluados[0].valores.intervaloAcreditado) {
          e = { estado: 'BLOQUEADO',
            motivo: `Intervalo BUFFER_LOCAL acreditado (timestamp original, origen y sin vacíos); contraste impedido por infraestructura HTTP ${real.http}` };
        } else if (i === 0 && !contrasteExistente && (real.http !== 201 || !real.eco || !real.cuerpo?.id_telemetria)) {
          const parcial = evaluados[0].valores.intervaloAcreditado
            ? 'Intervalo BUFFER_LOCAL acreditado (timestamp original, origen y sin vacíos); diferenciación TIEMPO_REAL NO_CONCLUYENTE'
            : 'Intervalo BUFFER_LOCAL incumplido (timestamp original, origen o vacíos)';
          e = { estado: evaluados[0].valores.intervaloAcreditado ? 'NO_CONCLUYENTE' : 'RECHAZADO',
            motivo: `${parcial}; contraste HTTP ${real.http ?? 'sin respuesta'}; error ${JSON.stringify(errorPublico(real.cuerpo))}` };
          r.problemas_tecnicos.push('ERROR_QA_CONTRASTE_TIEMPO_REAL');
        } else if (i === 1 && segundo.http >= 500) e = { estado: 'BLOQUEADO', motivo: `Infraestructura del segundo envío HTTP ${segundo.http}` };
        else if (i === 1 && (segundo.http !== 200 || !segundo.eco ||
          (Number(segundo.cuerpo?.duplicados) !== 1 && !aceptados(segundo, 1)))) {
          e = { estado: 'NO_CONCLUYENTE', motivo: motivoIngreso(segundo, 'segundo envío') };
          r.problemas_tecnicos.push('ERROR_QA_SEGUNDO_ENVIO_NO_EVALUABLE');
        }
        r.casos[CASOS[i]] = { estado: e.estado, motivo: e.motivo };
        r.comprobaciones[i] = { ...r.comprobaciones[i], estado: e.estado, motivo: e.motivo,
          evidencia: n.artefactos[0] ?? null };
      }
    } else {
      const estado = respuesta?.http >= 500 ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
      for (let i = 0; i < CASOS.length; i++) {
        const lote = [intervalo, primero, bordes][i];
        const marcasCaso = i === 0 ? m.intervalo : i === 1 ? [m.duplicado] : m.bordes;
        const edad = rechazoAntiguedad(lote, marcasCaso);
        const estadoCaso = edad ? 'RECHAZADO' : estado;
        const motivo = edad ? `Lectura BUFFER_LOCAL dentro de 72 h rechazada por antigüedad: ${motivoIngreso(lote, 'ingesta')}`
          : `Historial HTTP ${respuesta?.http ?? 'sin respuesta'}, eco ${respuesta?.eco ?? false}`;
        r.casos[CASOS[i]] = { estado: estadoCaso, motivo };
        r.comprobaciones[i] = { ...r.comprobaciones[i], estado: estadoCaso, motivo,
          evidencia: edad ? n.artefactos[0] ?? 'resultado.json' : n.artefactos[0] ?? null };
      }
    }
  } catch (e) {
    const motivo = String(e.message).slice(0, 180);
    if (!motivo.startsWith('DATOS_SEMILLA_')) r.problemas_tecnicos.push(motivo);
    const estado = /DATOS_SEMILLA/.test(motivo) ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
    for (let i = 0; i < CASOS.length; i++) if (r.casos[CASOS[i]].motivo === 'Sin comprobación') {
      r.casos[CASOS[i]] = { estado, motivo };
      r.comprobaciones[i].motivo = motivo; r.comprobaciones[i].estado = estado;
    }
  } finally {
    if (tocado) {
      try {
        const x = await pedir(api, 'DELETE', `/test-control/runs/${c.runId}`,
          { secreto: env.QA_SANDBOX_SECRET, bitacora: r.bitacora, timeout: 30000, presupuesto, cierre: true });
        r.cierre.run.cierre_http = x.http;
        if (x.http === 200 && semilla && escritos.length && token && m) {
          const [inicio, fin] = fechas(m);
          const comprobacion = await pedir(api, 'GET', rutaHistorial(semilla.sensor_id, semilla.nombre_variable, inicio, fin),
            { token, bitacora: r.bitacora, timeout: 30000, presupuesto, cierre: true });
          const restos = comprobacion.http === 200 && Array.isArray(comprobacion.cuerpo?.items)
            ? escritos.filter(ts => filas(comprobacion.cuerpo.items, semilla, ts).length) : escritos;
          r.cierre.rollback.verificado = comprobacion.http === 200 && restos.length === 0 && desconocidas === 0
            && Number(comprobacion.cuerpo?.total) <= 500;
          r.cierre.rollback.motivo = `GET público HTTP ${comprobacion.http}; escrituras ${escritos.length}; sin ID ${desconocidas}; restos ${restos.length}; total ${comprobacion.cuerpo?.total ?? 'desconocido'}`;
        } else if (x.http === 200 && escritos.length === 0 && desconocidas === 0) {
          r.cierre.rollback.verificado = true;
          r.cierre.rollback.metodo = 'sin_escrituras';
          r.cierre.rollback.motivo = 'sin escrituras de escenario; DELETE 200';
        } else r.cierre.rollback.motivo = `DELETE HTTP ${x.http}; escrituras confirmadas ${escritos.length}; sin ID ${desconocidas}`;
      } catch (e) { r.cierre.rollback.motivo = `Cierre o lectura sin respuesta: ${String(e.message).slice(0, 100)}`;
        r.problemas_tecnicos.push('CIERRE_O_ROLLBACK_NO_ACREDITADO'); }
    }
    finalizar(c, r, secretos);
  }
  return r;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
  else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
  else {
    try {
      const ensayo = process.argv.includes('--ensayo-loopback');
      const c = contextoEjecucion(process.argv.slice(2), { grupo: 'G120', casos: CASOS, directorio: DIR, modoEnsayo: ensayo });
      const env = ensayo ? { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: process.env.G120_ENSAYO_BASE,
        QA_SANDBOX_SECRET: 'ENSAYO_SECRET', BROKER_SERVICE_TOKEN: 'ENSAYO_BROKER',
        QA_PROD_EMAIL: 'productor@example.test', QA_PROD_PASSWORD: 'ENSAYO_PASS',
        QA_ADMIN_EMAIL: 'admin@example.test', QA_ADMIN_PASSWORD: 'ENSAYO_ADMIN_PASS' } : leerEnv();
      const r = await evaluar(c, { env, ensayo });
      console.log(JSON.stringify({ run_id: r.run_id, casos: r.casos, oficial: r.oficial }));
      if (!r.oficial) process.exitCode = 2;
    } catch (e) { console.error(`G120: ${e.message}`); process.exitCode = 2; }
  }
}
