#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { spawn, spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';
import { sanearArtefacto, contieneMojibake } from './lib/seguridad.mjs';
import { onnxMinimo, sha256 } from './lib/artefactos.mjs';
import { CASOS, IDS, METRICAS, PRESUPUESTO, CAPACIDADES, escenarios } from './lib/g051_escenario.mjs';

const require = createRequire(import.meta.url);
const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION = path.join(DIR, 'G051.postman_collection.json');
const ARCHIVOS = ['.gitkeep', 'g051.mjs', 'G051.postman_collection.json', 'README.md',
  'lib/contrato_ejecutor.mjs', 'lib/seguridad.mjs', 'lib/artefactos.mjs', 'lib/g051_escenario.mjs',
  'pruebas/registro_qa.mjs', 'pruebas/g051_ensayo.mjs', 'pruebas/g051_env.test.mjs',
  'pruebas/fixture_run_tecnico_v2.json'];
const limpio = x => String(x ?? '').replaceAll('|', '/').replace(/[\r\n]+/g, ' ').slice(0, 350);
const celda = x => limpio(x === null || x === undefined ? 'nulo' : typeof x === 'object' ? JSON.stringify(x) : x);
const guardar = (p, x) => fs.writeFileSync(p, JSON.stringify(x, null, 2), 'utf8');
const idVersion = x => x?.id_version_modelo ?? x?.id_version ?? null;
const nombreInforme = v => v === 1 ? 'TC-M04-G051_resultado.md' : `TC-M04-G051_reevaluacion_V${v}.md`;

// Igual que G050: el entorno del proceso prevalece; la autorización solo viene del lanzador.
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

function paqueteNewman() {
  try { return path.dirname(require.resolve('newman/package.json', { paths: [RAIZ] })); }
  catch {
    const p = String(process.env.PATH ?? '').split(path.delimiter)
      .map(x => path.join(x, 'node_modules', 'newman', 'package.json')).find(fs.existsSync);
    if (!p) throw Error('NEWMAN_NO_RESUELTO');
    return path.dirname(p);
  }
}
function binNewman() { const p = paqueteNewman(); return path.join(p, require(path.join(p, 'package.json')).bin.newman); }
function versionNewman(ensayo) {
  try {
    const x = spawnSync(process.execPath, [binNewman(), '--version'],
      { timeout: 30000, encoding: 'utf8', windowsHide: true });
    if (ensayo && x.error?.code === 'EPERM') {
      const p = paqueteNewman();
      return { ok: true, version: require(path.join(p, 'package.json')).version,
        modo: 'paquete local por spawn EPERM' };
    }
    return { ok: x.status === 0 && !!x.stdout.trim(), version: x.stdout.trim(), error: x.error?.code ?? null };
  } catch (e) { return { ok: false, error: e.code ?? e.message }; }
}
export function comprobar() {
  let coleccion = false;
  try {
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const i of col.item) for (const e of i.event ?? []) new vm.Script((e.script?.exec ?? []).join('\n'));
    coleccion = col.item.length === 1 && col.item[0].name === 'API-G051-POST'
      && col.item[0].request.method === 'POST' && !contieneMojibake(JSON.stringify(col));
  } catch { /* se informa */ }
  const faltantes = ARCHIVOS.filter(x => !fs.existsSync(path.join(DIR, x)));
  const presentes = fs.readdirSync(DIR).filter(x => !['lib', 'pruebas', 'Resultados', 'EvaluacionV2'].includes(x))
    .concat(...['lib', 'pruebas'].map(d => fs.existsSync(path.join(DIR, d))
      ? fs.readdirSync(path.join(DIR, d)).map(x => `${d}/${x}`) : []));
  const inesperados = presentes.filter(x => !ARCHIVOS.includes(x));
  const markdownSuperior = fs.existsSync(path.join(DIR, 'Resultados'))
    && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const fuentesLocales = ['g051.mjs', 'README.md',
    ...['lib', 'pruebas'].flatMap(d => fs.readdirSync(path.join(DIR, d)).map(x => `${d}/${x}`))]
    .filter(x => /\.(?:mjs|md|json)$/.test(x));
  const runTecnico = /RUN-G051-V2-20261101-(?:022937|024639)/;
  const referenciasRunTecnico = fuentesLocales.filter(x => {
    const contenido = fs.readFileSync(path.join(DIR, x), 'utf8');
    return /EvaluacionV2[\\/]Resultados[\\/]RUN-G051-V2-20261101-(?:022937|024639)/.test(contenido)
      || /\]\([^)]*RUN-G051-V2-20261101-(?:022937|024639)[\\/]/.test(contenido)
      || (x.endsWith('.mjs') && contenido.split(/\r?\n/).some(linea =>
        runTecnico.test(linea) && /(?:readFile|existsSync|readdirSync|import\s|from\s)/.test(linea)));
  });
  const e = escenarios({ variable: 1, inexistente: 999, hash: 'a'.repeat(64),
    dataset: 'b'.repeat(64), archivo: 'local.onnx' });
  const presupuestoValido = PRESUPUESTO.timeout_post_ms === 120000
    && PRESUPUESTO.timeout_ms === 30000
    && PRESUPUESTO.timeout_newman_ms >= 4 * PRESUPUESTO.timeout_post_ms + 19 * PRESUPUESTO.timeout_ms
    && PRESUPUESTO.duracion_segundos * 1000 >= PRESUPUESTO.timeout_newman_ms
      + 10 * PRESUPUESTO.timeout_ms;
  const ok = coleccion && !faltantes.length && !inesperados.length && !markdownSuperior
    && !referenciasRunTecnico.length
    && e.length === PRESUPUESTO.posts && presupuestoValido;
  console.log(JSON.stringify({ grupo: 'G051', ok, coleccion, escenarios: e.length,
    faltantes, inesperados, markdownSuperior, referenciasRunTecnico,
    presupuestoValido, presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}
export function preflight(c, env, ensayo = false) {
  const base = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const claves = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_ADMIN_EMAIL',
    'QA_ADMIN_PASSWORD', 'RF71_INTERNAL_KEY'];
  const barreras = claves.filter(k => !String(env[k] ?? '').trim());
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base) : base !== API) barreras.push('API_NO_CANONICA');
  const alcance = c.contexto?.alcance_reevaluacion;
  const reintentoValido = c.operacion === 'reintentar' && alcance
    && !Array.isArray(alcance) && Array.isArray(alcance.casos)
    && JSON.stringify(alcance.casos) === JSON.stringify(CASOS)
    && alcance.version_anterior === c.version - 1
    && c.contexto.version_anterior === c.version - 1;
  if (c.version > 1 && c.operacion !== 'reevaluar' && !reintentoValido)
    barreras.push('REEVALUACION_SIN_DECISION');
  return { fase: 'PREFLIGHT_LOCAL', grupo: 'G051', run_id: c.runId, version: c.version,
    ok: !barreras.length, barreras, presupuesto: PRESUPUESTO,
    efectos_declarados: ['4_versiones_aceptadas_segun_oraculo_BD_sujetas_a_rollback_externo',
       'version_adicional_posible_si_fecha_futura_se_acepta_indebidamente',
       'archivos_ONNX_en_MODELOS_STORAGE_PATH_no_verificables_por_API_ni_revertidos_por_sandbox',
      'posible_respaldo_local_RF73_no_revertido',
      'aviso_correo_Veterinarios_por_f1_0_0_RECHAZADO_despues_commit',
      'login_fuera_RUN_puede_persistir'] };
}
function errorPublico(data) {
  const d = data?.detail && typeof data.detail === 'object' ? data.detail : data;
  return { codigo: limpio(d?.error_code ?? d?.code ?? d?.codigo),
    mensaje: limpio(d?.message ?? d?.mensaje ?? (typeof data?.detail === 'string' ? data.detail : '')),
    campos: Array.isArray(d?.fields) ? d.fields.map(x => ({ campo: limpio(x.field), mensaje: limpio(x.message) })) : [] };
}
async function pedir(api, metodo, ruta, { token, secreto, runId, cuerpo, bitacora } = {}) {
  let http = null, eco = null;
  try {
    const x = await fetch(api + ruta, { method: metodo, redirect: 'manual',
      headers: { ...(cuerpo ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(secreto ? { 'X-Sandbox-Secret': secreto } : {}),
        ...(runId ? { 'X-Test-Run-Id': runId, 'X-Zona-Horaria': 'UTC' } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined, signal: AbortSignal.timeout(PRESUPUESTO.timeout_ms) });
    http = x.status; eco = runId ? x.headers.get('x-test-run-id') === runId : null;
    const data = await x.json().catch(() => null);
    return { http, eco, cuerpo: data, error: http >= 400 ? errorPublico(data) : null,
      fechaServidor: x.headers.get('date') };
  } finally { bitacora.push({ metodo, ruta, http, eco, en_run: !!runId }); }
}
function extracto(ex, runId) {
  const hs = ex?.response?.header ?? [];
  const eco = hs.find(h => String(h.key).toLowerCase() === 'x-test-run-id')?.value === runId;
  const bytes = Buffer.from(ex?.response?.stream?.data ?? []);
  let cuerpo = null; try { cuerpo = JSON.parse(bytes.toString('utf8')); } catch { /* sin cuerpo */ }
  const http = ex?.response?.code ?? null;
  return { iteracion: ex?.cursor?.iteration ?? null, http, eco, cuerpo,
    duracion_ms: Number.isFinite(ex?.response?.responseTime) ? ex.response.responseTime : null,
    duracion_origen: Number.isFinite(ex?.response?.responseTime) ? 'newman_responseTime' : 'sin_medicion_newman',
    error: http >= 400 ? errorPublico(cuerpo) : null,
    fechaServidor: hs.find(h => String(h.key).toLowerCase() === 'date')?.value ?? null };
}
export function parametrosTimeoutNewman() {
  return ['--timeout-request', String(PRESUPUESTO.timeout_post_ms),
    '--timeout', String(PRESUPUESTO.timeout_newman_ms)];
}
async function ejecutarNewman(c, api, env, escenariosRun, secretos, temporal) {
  const raw = path.join(temporal, 'raw.json'), environment = path.join(temporal, 'environment.json');
  const entornoFinal = path.join(temporal, 'environment-final.json');
  const datos = path.join(temporal, 'iteraciones.json');
  guardar(environment, { values: Object.entries({ autorizado_run: 'SI', ensayo_loopback: c.ensayo ? 'SI' : 'NO',
    base_url: api, run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET,
    rf71_internal_key: env.RF71_INTERNAL_KEY }).map(([key, value]) => ({ key, value, enabled: true })) });
  guardar(datos, escenariosRun.map(x => ({ ...x,
    metricas_validacion: JSON.stringify(x.metricas_validacion),
    compatibilidad_variables: JSON.stringify(x.compatibilidad_variables) })));
  const args = [binNewman(), 'run', COLECCION, '--environment', environment, '--iteration-data', datos,
    '--reporters', 'json', '--reporter-json-export', raw, '--working-dir', temporal,
    '--export-environment', entornoFinal,
    ...parametrosTimeoutNewman(), '--color', 'off'];
  let salida = await new Promise(resolve => {
    let p; try { p = spawn(process.execPath, args, { stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true }); }
    catch (e) { resolve({ code: null, error: e.code ?? 'NEWMAN_SPAWN' }); return; }
    p.stdout.on('data', () => {}); p.stderr.on('data', () => {});
    p.on('error', e => resolve({ code: null, error: e.code ?? 'NEWMAN_SPAWN' }));
    p.on('close', code => resolve({ code, error: null }));
  });
  if (c.ensayo && salida.error === 'EPERM') {
    salida = await new Promise(resolve => require(paqueteNewman()).run({ collection: JSON.parse(fs.readFileSync(COLECCION, 'utf8')),
      environment: JSON.parse(fs.readFileSync(environment, 'utf8')),
      iterationData: JSON.parse(fs.readFileSync(datos, 'utf8')), reporters: ['json'],
      reporter: { json: { export: raw } }, timeoutRequest: PRESUPUESTO.timeout_post_ms,
      timeout: PRESUPUESTO.timeout_newman_ms, color: 'off' },
    (error, summary) => {
      if (summary?.environment) guardar(entornoFinal, summary.environment.toJSON());
      resolve({ code: error ? 1 : 0, error: null, modo: 'API_LOCAL_POR_SPAWN_EPERM' });
    }));
  }
  if (!fs.existsSync(raw)) return { salida, respuestas: [], fallos: [], artefactos: [] };
  const original = JSON.parse(fs.readFileSync(raw, 'utf8'));
  const respuestas = (original.run?.executions ?? []).map(ex => extracto(ex, c.runId));
  const valores = fs.existsSync(entornoFinal)
    ? new Map((JSON.parse(fs.readFileSync(entornoFinal, 'utf8')).values ?? [])
      .map(x => [x.key, x.value])) : new Map();
  for (const p of respuestas) {
    if (p.duracion_ms !== null || !Number.isSafeInteger(p.iteracion)) continue;
    const duracion = Number(valores.get(`g051_duracion_${p.iteracion}`));
    const inicio = Number(valores.get(`g051_inicio_${p.iteracion}`));
    if (Number.isFinite(duracion) && duracion > 0) {
      p.duracion_ms = duracion; p.duracion_origen = 'iteracion_newman';
    } else if (Number.isFinite(inicio) && inicio > 0) {
      p.duracion_ms = Date.now() - inicio; p.duracion_origen = 'fin_newman_estimado';
    }
  }
  const fallos = (original.run?.failures ?? []).map(f => ({ name: limpio(f.error?.name),
    test: limpio(f.error?.test), mensaje: limpio(f.error?.message) }));
  fs.mkdirSync(path.join(c.directorio, 'newman'), { recursive: true });
  const artefactos = ['newman/newman-G051.json', 'newman/newman-G051.html'];
  guardar(path.join(c.directorio, artefactos[0]), JSON.parse(sanearArtefacto(JSON.stringify({
    info: { nombre: 'Newman G051', generado: true, saneado: true },
    run: { stats: original.run?.stats ?? null, executions: respuestas, failures: fallos } }), secretos)));
  const filas = respuestas.map(x => `<tr><td>${x.iteracion}</td><td>${x.http ?? 'sin respuesta'}</td><td>${x.eco}</td><td>${x.duracion_ms ?? 'no medida'}</td></tr>`).join('');
  fs.writeFileSync(path.join(c.directorio, artefactos[1]),
    `<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G051</title><h1>Newman G051</h1><table><tr><th>Iteración</th><th>HTTP</th><th>Eco RUN</th><th>Duración ms</th></tr>${filas}</table></html>`, 'utf8');
  return { salida, respuestas, fallos, artefactos };
}

function resultadoInicial(c) {
  return { grupo: 'G051', run_id: c.runId, version: c.version, operacion: c.operacion,
    autorizacion: c.referencia, intento: c.intento ?? null, ambiente: c.ensayo ? 'LOOPBACK_LOCAL' : 'TEST',
    oficial: false, consume_version: false,
    casos: Object.fromEntries(CASOS.map(x => [x, { estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación' }])),
    comprobaciones: CASOS.map((caso, i) => ({ caso, fuente: 'API', id: IDS[i], tipo: 'ASSERT',
      estado: 'NO_CONCLUYENTE', motivo: 'Sin respuesta', evidencia: null })),
    cypress: { total_pruebas: 0 }, preflight_herramientas: {}, evidencias: [], bitacora: [],
    datos: null, solicitudes: [], incidencias: [], problemas_tecnicos: [], observaciones_tecnicas: [],
    conteo: { inicial: null, final: null, delta: null, aceptados: 0, conciliados: 0,
      rechazados_con_id: 0 },
    cierre: { run: { cierre_http: null }, rollback: { verificado: false,
      motivo: 'Sin cierre ni comprobación de reversión de BD' } } };
}
function asignar(r, i, estado, motivo) {
  r.casos[CASOS[i]] = { estado, motivo };
  Object.assign(r.comprobaciones[i], { estado, motivo, evidencia:
    r.evidencias.includes('newman/newman-G051.json') ? 'newman/newman-G051.json' : null });
}
const errorTexto = x => [x?.error?.codigo, x?.error?.mensaje,
  ...(x?.error?.campos ?? []).flatMap(f => [f.campo, f.mensaje])].join(' ').toLowerCase();
function evaluarSolicitud(s) {
  const { escenario: e, post: p, get: g } = s;
  if (!p?.http) {
    if (s.conciliacion?.registrado) return { estado: e.aceptado ? 'APROBADO' : 'RECHAZADO',
      motivo: e.aceptado
        ? 'POST sin respuesta en el límite; registro acreditado por id_proceso_rf71 en el listado'
        : 'POST sin respuesta; se registró una solicitud que exigía rechazo' };
    return { estado: 'NO_CONCLUYENTE',
      motivo: e.aceptado
        ? 'POST sin respuesta; id_proceso_rf71 ausente del listado; aceptación no acreditada'
        : 'POST sin respuesta; id_proceso_rf71 ausente del listado; HTTP 422 no comprobable' };
  }
  if (p.http === 403 || (e.aceptado && p.http >= 500))
    return { estado: 'BLOQUEADO', motivo: `POST válido/control HTTP ${p.http}; impedimento técnico` };
  if (!p.eco) return { estado: 'NO_CONCLUYENTE', motivo: 'POST sin eco del RUN' };
  const id = idVersion(p.cuerpo);
  if (e.aceptado) {
    const esperadoHttp = e.dato === 'f1=0.0' ? [200, 201] : [201];
    if (!esperadoHttp.includes(p.http)) return { estado: 'RECHAZADO', motivo: `Registro válido devolvió HTTP ${p.http}` };
    if (id === null) return { estado: 'NO_CONCLUYENTE', motivo: 'Registro sin id de versión' };
    if (!g?.http) return { estado: 'NO_CONCLUYENTE', motivo: 'GET de versión sin respuesta' };
    if (g.http === 403 || g.http >= 500) return { estado: 'BLOQUEADO', motivo: `GET HTTP ${g.http}` };
    if (g.http !== 200 || !g.eco || idVersion(g.cuerpo) !== id
      || g.cuerpo?.tipo_modelo !== 'MODELO_ESPECIES_GRANDES')
      return { estado: 'RECHAZADO', motivo: `GET ${g.http} no confirma la versión aceptada` };
    return { estado: 'APROBADO', motivo: `POST ${p.http}; GET 200 confirmó id ${id}` };
  }
  if (p.http !== 422) return { estado: 'RECHAZADO', motivo: `HTTP ${p.http} contradice E2 (422)` };
  if (id !== null) return { estado: 'RECHAZADO', motivo: 'HTTP 422 devolvió id de versión' };
  if (s.aparece_en_listado_final) return { estado: 'RECHAZADO', motivo: 'HTTP 422 creó versión identificada por proceso RF-71' };
  const t = errorTexto(p);
  if (e.caso === CASOS[0] && !/compatibilidad_variables|variable/.test(t))
    return { estado: 'RECHAZADO', motivo: '422 no identifica la variable' };
  if (e.caso === CASOS[1] && e.dato === 'mañana' && !t.includes('fecha_entrenamiento'))
    return { estado: 'RECHAZADO', motivo: '422 no identifica fecha_entrenamiento' };
  if (e.caso === CASOS[2] && (!t.includes('tipo_modelo') || ![
    'MODELO_AVES', 'MODELO_PORCINOS', 'MODELO_ACUICULTURA',
    'MODELO_ESPECIES_MEDIANAS', 'MODELO_ESPECIES_GRANDES', 'MODELO_RIESGO_CONTAGIO'
  ].every(tipo => t.includes(tipo.toLowerCase()))))
    return { estado: 'RECHAZADO', motivo: '422 no identifica tipo_modelo y los seis tipos admitidos' };
  if (e.caso === CASOS[3]) {
    const campo = e.dato.slice(4);
    if (!t.includes(campo)) return { estado: 'RECHAZADO', motivo: `422 no identifica ${campo}` };
  }
  if (e.caso === CASOS[4] && !/rango|\[0[.,]0\s*[,–-]\s*1[.,]0\]/.test(t))
    return { estado: 'RECHAZADO', motivo: '422 no indica el rango' };
  if (e.caso === CASOS[5] && !t.includes(e.dato.split(':')[0]))
    return { estado: 'RECHAZADO', motivo: '422 no identifica el hash afectado' };
  if (e.caso === CASOS[6] && !e.omitir.every(campo => t.includes(campo)))
    return { estado: 'RECHAZADO', motivo: `422 no identifica ${e.omitir.join(' y ')}` };
  return { estado: 'APROBADO', motivo: 'HTTP 422 sin identificador y detalle suficiente' };
}
const REQUISITOS = {
  'TC-M04-121': 'Resultado esperado del caso: “Con variables existentes procede; con una inexistente HTTP 422 indicando el campo”. RF-69, entrada compatibilidad_variables (línea 1966) y fase 2 (líneas 2016-2017).',
  'TC-M04-122': 'Resultado esperado del caso: “Las dos primeras se registran; la futura HTTP 422 sin crear la versión”. RF-69, fecha_entrenamiento (línea 1964) y E2 (líneas 2142-2151).',
  'TC-M04-123': 'Resultado esperado del caso: “Las tres HTTP 422 indicando el catálogo admitido”. RF-69, tipo_modelo (línea 1959), actualización RFC-009 (línea 1784) y RF-65 (líneas 381-390).',
  'TC-M04-124': 'Resultado esperado del caso: “Las tres HTTP 422 identificando el campo ausente”. RF-69, métricas (línea 1962), fase 2 y E2 (líneas 2142-2151).',
  'TC-M04-125': 'Resultado esperado del caso: “0.0 y 1.0 se aceptan; -0.01 y 1.01 HTTP 422 indicando el rango”. RF-69, métricas (línea 1962), fase 2 y E2 (líneas 2142-2151).',
  'TC-M04-126': 'Resultado esperado del caso: “Las seis HTTP 422 identificando el hash afectado”. RF-69, hash del artefacto (línea 1961), hash del dataset (línea 1963), fase 2 y E2 (líneas 2142-2151).',
  'TC-M04-127': 'Resultado esperado del caso: “Las tres HTTP 422 sin crear la versión”. RF-69, restricción 8 (líneas 1893-1897) y E2 (líneas 2142-2151): identificar cada hash omitido.'
};
function incidencia(r, caso, solicitudes) {
  const detalles = caso === CASOS[1] && solicitudes.some(x => x.escenario.dato === 'mañana')
    ? r.solicitudes.filter(x => x.escenario.caso === CASOS[1]
      || x.escenario.dato === 'variables existentes / ayer') : solicitudes;
  const observados = detalles.map(x => `${x.escenario.caso} ${x.escenario.dato}`
    + (x.escenario.dato === 'mañana' ? ` (${x.escenario.fecha_entrenamiento})` : '')
    + `: HTTP ${x.post?.http ?? 'sin respuesta'}, código ${x.post?.error?.codigo ?? 'nulo'}, `
    + `mensaje ${x.post?.error?.mensaje ?? 'nulo'}, campos ${JSON.stringify(x.post?.error?.campos ?? [])}, `
    + `id ${idVersion(x.post?.cuerpo) ?? 'nulo'}, en listado final ${x.aparece_en_listado_final}`).join('; ');
  const casosAfectados = [...new Set(solicitudes.map(x => x.escenario.caso))];
  const esFecha = caso === CASOS[1] && solicitudes.some(x => x.escenario.dato === 'mañana');
  const esVal400 = solicitudes.length > 0 && solicitudes.every(x =>
    x.post?.http === 400 && x.post?.error?.codigo === 'VAL_ENTRADA'
    && !x.aparece_en_listado_final && idVersion(x.post?.cuerpo) === null);
  const creaProhibida = solicitudes.some(x => !x.escenario.aceptado && x.aparece_en_listado_final);
  const alta = creaProhibida;
  const fecha500 = esFecha && solicitudes.some(x => x.escenario.dato === 'mañana' && x.post?.http >= 500);
  return { id: esVal400 ? 'INC-M04-G051-VAL400' : `INC-M04-G051-${caso.slice(-3)}`,
    caso: casosAfectados[0], casos_afectados: casosAfectados,
    titulo: fecha500 ? 'Una fecha de entrenamiento futura produce error interno 500 en lugar de rechazo 422'
      : esVal400 ? 'Los campos obligatorios vacíos u omitidos del registro de versión se rechazan con HTTP 400 en lugar de 422'
        : `Validación de metadatos divergente en ${caso}`,
    equipo: 'Desarrollo', derivacion: 'Primera discrepancia comprobada en la API; Desarrollo atiende inicialmente. La causa raíz no está determinada.',
    severidad: alta ? 'ALTA' : esVal400 ? 'BAJA' : 'MEDIA', certeza: 'CONFIRMADA',
    sustento_severidad: alta
      ? 'Se creó una versión con metadatos prohibidos; la validación relevante quedó bloqueada sin alternativa.'
       : fecha500 ? 'La fecha futura no creó una versión según el listado, pero el 500 genérico no identifica el campo ni permite a RF-71 distinguir el dato inválido de una caída; los archivos residuales no son verificables por API.'
         : esVal400 ? `${solicitudes.length} solicitudes se rechazaron sin crear versión; el HTTP 400 difiere del 422 contractual, con impacto menor en clientes como RF-71.`
        : 'La validación o el detalle de error de un metadato difiere del requisito; impacto parcial en el registro.',
    requisito: esVal400
       ? 'RF-69 E2, líneas 2142-2151: HTTP 422 con detalle del campo específico y registro no creado. Restricción 8, líneas 1893-1897: ambos hashes son obligatorios. Resultado esperado de TC-M04-123: “Las tres HTTP 422 indicando el catálogo admitido”; de TC-M04-127: “Las tres HTTP 422 sin crear la versión”.'
      : REQUISITOS[caso],
    precondiciones: `RUN ${r.run_id} autorizado; catálogo I3P-1 leído; clave interna RF-71; artefacto ONNX y hash real.`,
    pasos: esFecha ? [
      'Consultar GET /prediccion/modelos?tipo_modelo=MODELO_ESPECIES_GRANDES&limit=100&offset=0 y conservar el total inicial.',
       `Enviar POST /prediccion/modelos multipart con tipo_modelo=MODELO_ESPECIES_GRANDES, fecha_entrenamiento=${solicitudes.find(x => x.escenario.dato === 'mañana')?.escenario.fecha_entrenamiento ?? 'fecha futura'}, artefacto ONNX y hash SHA-256 real, id_proceso_rf71 único y cabecera X-RF71-Internal-Key.`,
      'Comparar la respuesta y el listado final con el inicial; comprobar que el proceso rechazado no aparece.'
    ] : esVal400 ? [
      'Consultar GET /prediccion/modelos?tipo_modelo=MODELO_ESPECIES_GRANDES&limit=100&offset=0 y conservar el total inicial.',
      'Enviar POST /prediccion/modelos multipart con X-RF71-Internal-Key e id_proceso_rf71 único para tipo_modelo vacío (TC-M04-123); repetir omitiendo hash_artefacto_sha256, omitiendo dataset_entrenamiento_hash y omitiendo ambos (TC-M04-127).',
      'Comprobar HTTP, error_code, message y fields en cada respuesta; comparar los procesos RF-71 y el total del listado final con el inicial.'
    ] : [
      `Consultar el listado inicial y enviar POST /prediccion/modelos multipart para ${solicitudes.map(x => x.escenario.dato).join(', ')}, con X-RF71-Internal-Key e id_proceso_rf71 único por solicitud.`,
      'Comprobar HTTP, error y campos; comparar los procesos RF-71 y el total del listado final con el inicial.'
    ],
    esperado: esVal400
       ? 'HTTP 422 con detalle del campo inválido o incompleto y sin crear versión; para TC-M04-123, enumerar los seis tipos admitidos; para TC-M04-127, identificar cada hash omitido.'
      : REQUISITOS[caso], obtenido: observados,
    evidencia: ['newman/newman-G051.json', 'resultado.json'],
    analisis: r.version >= 2
      ? 'La respuesta de la API acredita la discrepancia; issue #820 / PR #864 informan una corrección local, pero su despliegue y la causa raíz en TEST no están verificados.'
      : esFecha
      ? 'Hipótesis local (no causa confirmada en TEST): el DTO y normalizador UTC no rechazan futuro (registrar_version_modelo_dto.py:45; src/shared/fechas.py:33-40); el use case guarda el archivo antes del INSERT (registrar_version_modelo_use_case.py:105-155), el trigger rechaza fecha futura con P0408 (alembic/baseline/esquema_baseline.sql:10642-10654) y ese código no figura en src/shared/db_error_translator.py:255-283, cuyo caso residual devuelve ERROR_INTERNO (:432-435). Puede quedar un ONNX huérfano; no se verificó el disco de TEST.'
      : esVal400 ? 'Hipótesis local, no causa raíz confirmada en TEST: Form(...) obligatorio para los hashes (src/prediction/infrastructure/dto/registrar_version_modelo_dto.py:42-43) y para tipo_modelo (:41), junto al manejador src/shared/error_handlers.py:193-200,298-324, que usa 400 por defecto si la ruta no declara x-codigo-validacion 422; la ruta revisada src/prediction/infrastructure/routers/version_modelo_router.py:47-77 no lo declara.'
        : 'El código local orienta la investigación, sin demostrar causa raíz en TEST.',
    impacto: esFecha && fecha500 ? 'RF-71 no puede distinguir un dato inválido de una caída; los archivos residuales no son verificables por API.'
      : esFecha ? 'Una fecha de entrenamiento futura podría quedar registrada.'
      : esVal400 ? 'Clientes como RF-71 que distinguen validación por HTTP 422 pueden manejar este rechazo como otra clase de error; los cuatro registros inválidos fueron rechazados y no aparecen en el listado.'
      : 'La validación del metadato o la respuesta exigida por E2 es divergente.',
    cierre: r.version >= 2 ? 'Atender la discrepancia observada y repetir el caso afectado en una ejecución autorizada.'
      : esFecha ? 'Traducir P0408 a HTTP 422 E2 identificando fecha_entrenamiento, o validar antes del guardado; no guardar el ONNX antes de validar. Reevaluar TC-M04-122 en V2 autorizada.'
      : esVal400 ? 'Declarar HTTP 422 para la validación de esta ruta o tratar los campos vacíos/ausentes en el caso de uso; reevaluar TC-M04-123 y TC-M04-127 en V2 autorizada.'
        : 'Corregir la discrepancia y reevaluar el caso en RUN autorizado.' };
}
export function agruparIncidencias(r) {
  const grupos = new Map();
  for (const caso of CASOS.filter(c => r.casos[c].estado === 'RECHAZADO')) {
    const solicitudes = r.solicitudes.filter(x => x.escenario.caso === caso);
    const discrepantes = solicitudes.filter(x => evaluarSolicitud(x).estado === 'RECHAZADO'
      || !x.escenario.aceptado && x.aparece_en_listado_final);
    for (const x of discrepantes) {
      const clave = !x.escenario.aceptado && x.post?.http !== 422 && x.post?.error?.codigo
        ? `${x.post.http}:${x.post.error.codigo}` : caso;
      if (!grupos.has(clave)) grupos.set(clave, []);
      grupos.get(clave).push(x);
    }
    if (!discrepantes.length) grupos.set(caso, solicitudes);
  }
  return [...grupos.values()].map(xs => incidencia(r, xs[0].escenario.caso, xs));
}
function detallePorCaso(r) {
  const criterios = [
    ['Con variables existentes procede; con una inexistente HTTP 422 indicando el campo', 'RF-69, entrada compatibilidad_variables (línea 1966), fase 2 (líneas 2016-2017) y E2 (líneas 2148-2151).'],
    ['Las dos primeras se registran; la futura HTTP 422 sin crear la versión', 'RF-69, entrada fecha_entrenamiento (línea 1964) y E2 (líneas 2148-2151).'],
    ['Las tres HTTP 422 indicando el catálogo admitido', 'RF-69, entrada tipo_modelo (línea 1959), actualización RFC-009 (línea 1784) y E2 (líneas 2148-2151).'],
    ['Las tres HTTP 422 identificando el campo ausente', 'RF-69, entrada metricas_validacion (línea 1962), fase 2 (líneas 2013-2015) y E2 (líneas 2142-2151).'],
    ['0.0 y 1.0 se aceptan; -0.01 y 1.01 HTTP 422 indicando el rango', 'RF-69, entrada metricas_validacion (línea 1962), fase 2 (líneas 2013-2015) y E2 (líneas 2142-2151).'],
    ['Las seis HTTP 422 identificando el hash afectado', 'RF-69, entradas de hashes (líneas 1961 y 1963), fase 2 (líneas 2008-2012) y E2 (líneas 2143-2151).'],
    ['Las tres HTTP 422 sin crear la versión', 'RF-69, restricción 8 (líneas 1893-1897) y E2 (líneas 2148-2151).']
  ];
  const nombreCampo = { tipo_modelo: 'tipo de modelo', compatibilidad_variables: 'variables compatibles',
    metricas_validacion: 'métricas', hash_artefacto_sha256: 'hash del artefacto',
    dataset_entrenamiento_hash: 'hash del dataset' };
  const listados = r.bitacora.filter(x => x.metodo === 'GET' && x.ruta?.startsWith('/prediccion/modelos?'));
  const listadoFinal = listados.length >= 2;
  const etiqueta = dato => dato.replaceAll('hash_artefacto_sha256', 'hash del artefacto')
    .replaceAll('dataset_entrenamiento_hash', 'hash del dataset')
    .replaceAll('f1_score_global', 'f1 global')
    .replaceAll('recall_clase_riesgo_alto', 'recall de riesgo alto')
    .replaceAll('matriz_confusion', 'matriz de confusión');
  const entrada = (x, i) => {
    const e = x.escenario;
    const comun = `tipo ${e.tipo_modelo || 'vacío'}${i === 0 ? '' : `, variable ${e.compatibilidad_variables?.join(', ') || 'no indicada'}`}`;
    const valor = i === 0 ? `variables [${e.compatibilidad_variables?.join(', ')}], fecha ${e.fecha_entrenamiento}`
      : i === 1 ? `fecha ${e.fecha_entrenamiento}`
        : i === 2 ? `tipo ${e.tipo_modelo || 'vacío'}`
          : i === 5 ? `${etiqueta(e.dato)} (valor ${e.dato.startsWith('hash_artefacto') ? e.hash_artefacto_sha256 : e.dataset_entrenamiento_hash})`
            : etiqueta(e.dato);
    return `${valor} (proceso RF-71 ${e.id_proceso_rf71})${i === 2 ? '' : `, ${comun}`}`;
  };
  const observado = (x, i) => {
    const p = x.post;
    if (!p) return `${x.escenario.dato}: sin respuesta POST`;
    const version = idVersion(p.cuerpo);
    if (version !== null) return `${etiqueta(x.escenario.dato)}: HTTP ${p.http}, versión ${version} en estado ${p.cuerpo.estado_version}, GET ${x.get?.http ?? 'sin respuesta'}, ${listadoFinal ? x.aparece_en_listado_final ? 'presente en listado final' : 'ausente del listado final' : 'sin comprobación del listado final'}`;
    const campos = p.error?.campos?.map(c => nombreCampo[c.campo] || c.campo) ?? [];
    const detalle = p.http === 500 ? 'error interno genérico'
      : i === 2 && p.http === 422 ? 'enumeró los seis tipos admitidos'
        : i === 2 && p.http === 400 ? 'indicó que el tipo es obligatorio, sin enumerar el catálogo'
          : i === 3 ? `identificó la ausencia de ${etiqueta(x.escenario.dato.slice(4))}`
            : i === 4 ? 'indicó el rango válido de 0.0 a 1.0'
              : i === 6 ? `indicó que ${[...new Set(campos)].join(' y ')} ${campos.length === 1 ? 'es obligatorio' : 'son obligatorios'}`
                : campos.length ? `señaló ${[...new Set(campos)].join(' y ')}` : 'sin detalle de campo';
    return `${etiqueta(x.escenario.dato)}: HTTP ${p.http}, ${detalle}, ${listadoFinal ? x.aparece_en_listado_final ? 'aparece una versión en listado final' : 'sin versión en listado final' : 'sin comprobación del listado final'}`;
  };
  const razones = [
    `La variable ${r.datos?.variable_existente} permitió registrar la versión; al añadir la inexistente ${r.datos?.variable_inexistente} se obtuvo HTTP 422 que señaló las variables compatibles y no apareció otra versión.`,
    'La fecha futura devolvió HTTP 500 con error interno genérico en lugar de HTTP 422, aunque no apareció una versión; INC-M04-G051-122.',
    'El tipo vacío devolvió HTTP 400 en lugar de HTTP 422 y no enumeró el catálogo admitido en esa respuesta; INC-M04-G051-VAL400.',
    'Las tres omisiones devolvieron HTTP 422 e identificaron la métrica faltante, sin crear versiones.',
    'Los extremos 0.0 y 1.0 se registraron; los valores -0.01 y 1.01 devolvieron HTTP 422 indicando el rango y no crearon versiones. La versión con 0.0 quedó en estado RECHAZADO por umbrales, pero sí se registró.',
    'Las seis variantes devolvieron HTTP 422, señalaron el hash afectado y no crearon versiones.',
    'Las tres omisiones devolvieron HTTP 400 en lugar de HTTP 422; no crearon versiones, pero incumplieron el estado HTTP exigido; INC-M04-G051-VAL400.'
  ];
  return CASOS.map((c, i) => {
    const estado = r.casos[c].estado;
    const solicitudes = r.solicitudes.filter(x => x.escenario.caso === c);
    const compartida = i === 1 ? r.solicitudes.find(x => x.escenario.caso === CASOS[0] && x.escenario.aceptado) : null;
    const hizo = solicitudes.length
      ? `Tras el inicio de sesión como Administrador, la integración RF-71 envió ${solicitudes.length} solicitudes POST de registro para estos datos: ${solicitudes.map(x => entrada(x, i)).join('; ')}.${compartida ? ` Se reutilizó la solicitud de ayer del caso anterior (proceso RF-71 ${compartida.escenario.id_proceso_rf71}).` : ''} ${r.bitacora.some(x => x.ruta?.startsWith('/configuracion/variables-ambientales')) ? 'Se consultó el catálogo; ' : ''}${listados.length ? `se consult${listadoFinal ? 'aron los listados inicial y final' : 'ó el listado inicial'}` : 'no se consultó el listado'}; ${r.bitacora.some(x => x.metodo === 'GET' && /^\/prediccion\/modelos\/\d+$/.test(x.ruta ?? '')) ? 'los registros creados se consultaron por ID' : 'no hubo consulta por ID de versión'}.`
      : 'No se ejecutaron solicitudes POST de este caso.';
    const observacion = solicitudes.length ? `${compartida ? `ayer: HTTP ${compartida.post?.http}, versión ${idVersion(compartida.post?.cuerpo)}, GET ${compartida.get?.http}, ${listadoFinal ? 'presente en listado final' : 'sin comprobación del listado final'}; ` : ''}${solicitudes.map(x => observado(x, i)).join('; ')}.` : 'No hay respuesta de este caso.';
    const incidenciaEsperada = i === 1 ? 'INC-M04-G051-122' : [2, 6].includes(i) ? 'INC-M04-G051-VAL400' : null;
    const incidenciaVigente = incidenciaEsperada && r.incidencias.some(x => x.id === incidenciaEsperada && (x.casos_afectados ?? [x.caso]).includes(c));
    const porQue = estado === 'APROBADO' || (estado === 'RECHAZADO' && incidenciaVigente) ? razones[i]
      : estado === 'RECHAZADO' ? `${r.casos[c].motivo}. ${r.incidencias.filter(x => (x.casos_afectados ?? [x.caso]).includes(c)).map(x => x.id).join('; ')}.`
        : `No se pudo completar el oráculo: ${r.casos[c].motivo}. Hace falta resolver el impedimento y repetir las solicitudes con evidencia de respuesta y listado final.`;
    return `### ${c} — ${estado}\n\n**Qué se hizo:** ${hizo}\n**Qué se esperaba:** Resultado esperado del caso: “${criterios[i][0]}”. ${criterios[i][1]}\n**Qué se observó:** ${observacion}\n**Por qué ${estado}:** ${porQue}`;
  }).join('\n\n');
}

function informeV2(r) {
  const estados = CASOS.map(c => r.casos[c].estado);
  const decision = estados.includes('BLOQUEADO') ? 'BLOQUEADO TÉCNICO'
    : estados.includes('NO_CONCLUYENTE') ? 'NO_CONCLUYENTE TÉCNICO'
      : estados.includes('RECHAZADO') ? 'RECHAZADO' : 'APROBADO';
  const v1 = ['APROBADO', 'RECHAZADO', 'RECHAZADO', 'APROBADO', 'APROBADO', 'APROBADO', 'RECHAZADO'];
  const comparacion = CASOS.map((caso, i) =>
    `| ${caso} | ${IDS[i]} | ${v1[i]} | ${r.casos[caso].estado} | ${[0, 3, 4, 5].includes(i) ? 'Regresión' : 'Corrección informada'} |`).join('\n');
  const esperado = e => e.aceptado
    ? `Registro ${e.dato === 'f1=0.0' ? 'HTTP 200 o 201' : 'HTTP 201'} con ID y GET 200`
    : `HTTP 422, sin ID ni versión en listado${e.caso === CASOS[1] ? ', fecha_entrenamiento' : ''}`
      + (e.caso === CASOS[2] ? ', tipo_modelo y seis tipos admitidos' : '')
      + (e.caso === CASOS[6] ? `, ${e.omitir.join(' y ')}` : '');
  const observado = x => {
    const p = x.post;
    const duracion = `; duración POST ${p?.duracion_ms === null || p?.duracion_ms === undefined
      ? `no medida (límite configurado ${PRESUPUESTO.timeout_post_ms / 1000} s)`
      : `${p.duracion_ms} ms (${p.duracion_origen})`}`;
    if (!p?.http) return (x.conciliacion?.registrado
      ? `POST sin respuesta en el límite; registro acreditado por id_proceso_rf71 en el listado; ID ${x.conciliacion.id_version_modelo}; estado ${x.conciliacion.estado_version}${x.get ? `; GET ${x.get.http ?? 'sin respuesta'}` : ''}`
      : `POST sin respuesta; ${x.conciliacion?.listado_completo ? 'proceso ausente del listado final' : 'listado final no exhaustivo'}; HTTP desconocido`) + duracion;
    const campos = (p.error?.campos ?? []).map(f => `${f.campo}: ${f.mensaje}`).join('; ');
    return `HTTP ${p.http}; código ${p.error?.codigo || 'sin error'}; ${p.error?.mensaje || 'sin mensaje de error'}`
      + `${campos ? `; campos ${campos}` : '; sin campos detallados'}`
      + `; ID ${idVersion(p.cuerpo) ?? 'ausente'}; ${x.aparece_en_listado_final ? 'presente' : 'ausente'} en listado final`
      + `${x.get ? `; GET ${x.get.http ?? 'sin respuesta'}` : ''}` + duracion;
  };
  const detalle = CASOS.map((caso, i) => {
    const xs = r.solicitudes.filter(x => x.escenario.caso === caso
      || i === 1 && x.escenario.dato === 'variables existentes / ayer');
    const filas = xs.map(x => `| ${limpio(x.escenario.dato)} | ${esperado(x.escenario)} | ${limpio(observado(x))} | ${evaluarSolicitud(x).estado} |`).join('\n');
    const catalogo = r.bitacora.some(x => x.metodo === 'GET' && x.ruta?.startsWith('/configuracion/variables-ambientales'));
    const listados = r.bitacora.filter(x => x.metodo === 'GET' && x.ruta?.startsWith('/prediccion/modelos?')).length;
    const consultaId = xs.some(x => x.get);
    return `### ${caso} — ${r.casos[caso].estado}\n\n**Qué se hizo:** ${xs.length} solicitudes POST de registro; ${catalogo ? 'se consultó' : 'no se consultó'} el catálogo, ${listados >= 2 ? 'se consultaron los listados inicial y final' : listados ? 'se consultó solo el listado inicial' : 'no se consultó el listado'} y ${consultaId ? 'se consultaron las versiones creadas por ID' : 'no hubo GET de versión por ID'}. ${i === 1 ? 'La solicitud válida de ayer se comparte con TC-M04-121. ' : ''}${[0, 3, 4, 5].includes(i) ? 'Comprobación de regresión.' : 'Comprobación de la corrección informada.'}\n\n**Qué se esperaba:** ${REQUISITOS[caso]}\n\n| Solicitud | Esperado | Observado | Evaluación |\n|---|---|---|---|\n${filas || '| Sin solicitud | Pendiente | Sin respuesta | NO_CONCLUYENTE |'}\n\n**Qué se observó:** ${xs.map(x => `${limpio(x.escenario.dato)}: ${limpio(observado(x))}`).join(' ') || 'No se obtuvo respuesta.'}\n\n**Por qué ${r.casos[caso].estado}:** ${limpio(r.casos[caso].motivo)}.`;
  }).join('\n\n');
  const estado122 = r.casos[CASOS[1]].estado === 'APROBADO' ? 'CORREGIDA' : 'PENDIENTE';
  const estadoVal = [CASOS[2], CASOS[6]].every(c => r.casos[c].estado === 'APROBADO') ? 'CORREGIDA' : 'PENDIENTE';
  const incidencias = r.incidencias.length ? r.incidencias.map(x =>
    `- ${x.id}: ${x.titulo}. Casos ${x.casos_afectados.join(', ')}; severidad ${x.severidad}; certeza ${x.certeza}; primer contacto ${x.equipo}, por discrepancia observada en la API. La causa raíz no se determina con este RUN. Evidencia: newman/newman-G051.json y resultado.json.`).join('\n')
    : 'Sin incidencias de producto nuevas confirmadas.';
  const pendientes = CASOS.filter(c => r.casos[c].estado !== 'APROBADO');
  const accion = pendientes.length ? `Atender ${pendientes.join(', ')} según las respuestas y repetir la reevaluación con autorización específica.`
    : 'Registrar el cierre de las incidencias corregidas y conservar la evidencia del RUN.';
  const f1 = r.solicitudes.find(x => x.escenario.dato === 'f1=0.0');
  let efectoF1 = f1?.conciliacion?.registrado
    ? `f1=0.0 quedó registrada por conciliación con ID ${f1.conciliacion.id_version_modelo} y estado ${f1.conciliacion.estado_version}, aunque el POST no respondió. La entrega de correo no se verificó.`
    : idVersion(f1?.post?.cuerpo) !== null
      ? 'La variante f1=0.0 creó una versión en estado RECHAZADO y puede enviar un aviso por correo; su entrega no se verificó.'
      : 'No se comprobó una versión creada por la variante f1=0.0; la posible entrega de un aviso por correo queda sin verificar.';
  const antecedenteTecnico = ' Antecedentes QA: RUN-G051-V2-20261101-022937 fue un intento técnico, exit 2; un POST f1=0.0 agotó 30 s, se registró y el ejecutor no concilió su id_proceso_rf71. El delta 4 frente a 3 respuestas aceptadas dejó los siete casos NO_CONCLUYENTE. RUN-G051-V2-20261101-024639 fue un reintento técnico detenido en PREFLIGHT_LOCAL por REEVALUACION_SIN_DECISION, sin peticiones a TEST ni cierre. Este parche usa 120 s para Newman, concilia el listado y admite REINTENTAR V2 con alcance válido; los antecedentes no son veredictos de producto.';
  const respaldoAntecedentes = r.run_id === 'RUN-G051-V2-20261101-025552'
    ? ' Los extractos saneados de [intento 1](api/antecedentes/intento-1.json) y [intento 2](api/antecedentes/intento-2.json), con [índice y SHA-256 de los originales](api/antecedentes/indice.json), quedan en este RUN oficial. Los dos RUN técnicos de origen fueron eliminados con autorización del responsable QA el 2026-11-01.'
    : '';
  const resumenConciliacion = ` Aceptados con respuesta ${r.conteo.aceptados}; registrados por conciliación ${r.conteo.conciliados}; delta ${celda(r.conteo.delta)}. ${r.observaciones_tecnicas.join('; ')}`;
  efectoF1 += antecedenteTecnico + respaldoAntecedentes + resumenConciliacion;
  return `# TC-M04-G051 — reevaluación V2 — ${decision}\n\n## Identificación\n\nGrupo G051; casos ${CASOS.join(', ')}; RF-69 v2.1; V2; RUN ${r.run_id}; operación ${r.operacion?.toUpperCase() ?? 'no indicada'}; intento ${r.intento ?? 'no indicado'}; ambiente ${r.ambiente}; autorización ${celda(r.autorizacion)}. Issue #820 / PR #864: corrección informada por Desarrollo; despliegue en TEST no verificado antes del RUN. Commit de despliegue: no verificado por esta orden, que excluye Git. Newman ${r.preflight_herramientas.newman?.version ?? 'no verificado'}; Cypress no aplica, pues los siete casos exigen API. Versión anterior: ${r.version - 1}.\n\n## Resumen y comparación V1 → V2\n\nV1: [RUN-G051-V1-20261028-032158](../../../Resultados/RUN-G051-V1-20261028-032158/TC-M04-G051_resultado.md). Decisión V2: ${decision}.\n\n| Caso | Comprobación | V1 | V2 | Propósito |\n|---|---|---|---|---|\n${comparacion}\n\nINC-M04-G051-122: ${estado122}. INC-M04-G051-VAL400: ${estadoVal}; requiere aprobación conjunta de 123 y 127. Estas etiquetas describen el resultado de V2 y no cambian los veredictos de V1.\n\n## Detalle por caso\n\n${detalle}\n\n## Comprobaciones API y efectos\n\nAPI-121-01 a API-127-01: 23 POST previstos. Fecha de servidor ${celda(r.datos?.fecha_servidor)}; la variante “ahora” usa el reloj del cliente menos 10 segundos. Conteo inicial ${celda(r.conteo.inicial)}, final ${celda(r.conteo.final)}, delta ${celda(r.conteo.delta)}, aceptados ${r.conteo.aceptados}, rechazados con ID ${r.conteo.rechazados_con_id}. ${efectoF1}\n\n## Incidencias de producto\n\n${incidencias}\n\n## Problemas técnicos y análisis\n\n${r.problemas_tecnicos.length ? r.problemas_tecnicos.map(x => `- ${celda(x)}`).join('\n') : 'Sin problemas técnicos observados en este RUN.'} Las respuestas públicas acreditan el comportamiento observado; el código local y el PR no prueban por sí solos la causa raíz ni el despliegue.\n\n## Cierre y rollback\n\nDELETE RUN HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. ${r.cierre.rollback.verificado ? 'El sandbox respondió al cierre; la reversión de BD no se comprobó por consulta posterior.' : 'No se confirmó el cierre ni la reversión de BD.'} Los archivos residuales en MODELOS_STORAGE_PATH no se pueden verificar por esta API; si se requiere comprobarlos, correspondería a Implementación o DBA. Esto limita la comprobación de efectos persistentes y no cambia el veredicto de los casos. Tampoco se verificó la entrega de correo ni la eliminación de posibles respaldos RF-73.\n\n## Evidencias\n\n${r.evidencias.map(x => `- ${x}`).join('\n') || 'Sin evidencias registradas.'}\n\n## Conclusión y acción\n\n${decision}. ${accion}\n`;
}

export function informe(r) {
  if (r.version >= 2) return informeV2(r);
  const estados = CASOS.map(c => r.casos[c].estado);
  const decision = estados.includes('BLOQUEADO') ? 'BLOQUEADO TÉCNICO'
    : estados.includes('NO_CONCLUYENTE') ? 'NO_CONCLUYENTE TÉCNICO'
      : estados.includes('RECHAZADO') ? 'RECHAZADO' : 'APROBADO';
  const breve = c => c === CASOS[1] && r.casos[c].estado === 'RECHAZADO'
    ? 'Fecha futura: HTTP 500 genérico; se esperaba 422 sin versión.'
    : [CASOS[2], CASOS[6]].includes(c) && r.casos[c].estado === 'RECHAZADO'
      && r.incidencias.some(x => x.id === 'INC-M04-G051-VAL400' && x.casos_afectados.includes(c))
      ? c === CASOS[2] ? 'Tipo vacío: HTTP 400; se esperaba 422.'
        : 'Tres omisiones de hash: HTTP 400; se esperaba 422.'
      : celda(r.casos[c].motivo);
  const tabla = CASOS.map((c, i) => `| ${c} | ${IDS[i]} | ${r.casos[c].estado} | ${breve(c)} |`).join('\n');
  const filas = r.solicitudes.map(x => {
    const e = x.escenario, p = x.post, g = x.get;
    return `| ${e.caso} | ${celda(e.dato)} | ${e.aceptado ? 'Registro' : '422 sin versión'} | `
      + `${p?.http ?? 'sin respuesta'} | ${celda(p?.error?.codigo)}; ${/tipo_modelo debe ser uno de:/.test(p?.error?.mensaje ?? '') ? 'lista de 6 tipos válidos' : celda(p?.error?.mensaje)}; `
      + `${/tipo_modelo debe ser uno de:/.test(JSON.stringify(p?.error?.campos ?? [])) ? 'tipo_modelo: lista de 6 tipos válidos' : celda(p?.error?.campos)} | ${x.aparece_en_listado_final ? 'sí (listado)' : 'no (listado)'}; `
      + `GET ${g?.http ?? 'no aplica'} |`;
  }).join('\n');
  const incidencias = r.incidencias.length ? r.incidencias.map(x =>
    `### ${x.id} — ${x.titulo}\n\n- **Casos afectados y equipo inicial:** ${(x.casos_afectados ?? [x.caso]).join(', ')}; ${x.equipo}. ${x.derivacion}\n`
    + `- **Severidad y certeza:** ${x.severidad}, ${x.certeza}. ${x.sustento_severidad}\n`
    + `- **Requisito:** ${x.requisito}\n- **Precondiciones:** ${x.precondiciones}\n`
    + `- **Pasos:**\n${x.pasos.map((p, i) => `  ${i + 1}. ${p}`).join('\n')}\n`
    + `- **Esperado:** ${x.esperado}\n- **Obtenido:** ${x.obtenido}\n`
    + `- **Evidencia:** ${x.evidencia.join('; ')}; RUN ${r.run_id}\n`
    + `- **Análisis:** ${x.analisis}\n- **Impacto:** ${x.impacto}\n- **Cierre:** ${x.cierre}`).join('\n\n')
    : 'Sin incidencias de producto confirmadas.';
  const motivo = r.casos[CASOS[1]].estado === 'RECHAZADO'
    && r.incidencias.some(x => x.id === 'INC-M04-G051-VAL400'
      && x.casos_afectados?.includes(CASOS[2]) && x.casos_afectados?.includes(CASOS[6]))
    ? 'Fecha futura responde 500 (TC-M04-122) y los campos obligatorios vacíos u omitidos responden 400 en lugar de 422 (TC-M04-123 y TC-M04-127); el resto de validaciones de metadatos cumple.'
    : [...new Set(CASOS.filter(c => r.casos[c].estado !== 'APROBADO').map(c => breve(c)))].join(' ') || 'Los siete oráculos se cumplieron por API.';
  const falta = decision === 'APROBADO' ? 'Ninguna comprobación pendiente en este RUN.'
    : decision === 'RECHAZADO' ? `Corrección de ${r.incidencias.map(x => x.id).join(' e ')} por Desarrollo y reevaluación V2 de ${CASOS.filter(c => r.casos[c].estado === 'RECHAZADO').map(c => c.slice(-3)).join(', ')}.`
      : 'Resolver el impedimento técnico y repetir con autorización específica.';
  return `# TC-M04-G051 — ${decision}\n\n## Decisión del caso\n\nCaso agrupado TC-M04-G051 (RF-69); originales ${CASOS.join(', ')}. Decisión: ${decision}. Motivo: ${motivo}\n\n| Caso | Comprobación | Decisión | Motivo breve |\n|---|---|---|---|\n${tabla}\n\nRUN oficial: ${r.oficial ? `sí (registro QA OFICIAL, intento ${r.intento ?? 'no indicado'}; DELETE ${r.cierre.run.cierre_http ?? 'sin respuesta'}, rollback ${r.cierre.rollback.verificado ? 'confirmado' : 'no confirmado'})` : 'no; falta comprobación o cierre'}.\n\nQué falta: ${falta}\n\n## Detalle por caso\n\n${detallePorCaso(r)}\n\n## Identificación\n\nGrupo G051; RF-69 v2.1; versión V${r.version}; RUN ${r.run_id}; ambiente ${r.ambiente}; autorización ${celda(r.autorizacion)}; referencia de código origin/test daefc3a5 (despliegue no verificado); Newman ${r.preflight_herramientas.newman?.version ?? 'no verificado'}; Cypress no aplica (solo API).\n\n## Esperado vs observado por solicitud\n\n| Caso | Dato enviado | Esperado | HTTP POST | Código; mensaje; campos | Versión creada / GET |\n|---|---|---|---|---|---|\n${filas}\n\n## Comprobaciones API y observaciones\n\nAPI-121-01 a API-127-01 se evaluaron por significado. TC-M04-121 con variables existentes reutiliza el POST de ayer de TC-M04-122. Para “ahora” se envió el instante del cliente menos 10 segundos; fecha HTTP del servidor: ${celda(r.datos?.fecha_servidor)}. f1=0.0 produjo una versión RECHAZADO por umbrales con HTTP 200; el correo previsto, entregado o no, quedó fuera de verificación. Conteo inicial ${celda(r.conteo.inicial)}, final ${celda(r.conteo.final)}, delta ${celda(r.conteo.delta)}, aceptados ${r.conteo.aceptados}, rechazados con id ${r.conteo.rechazados_con_id}. La ausencia de versión se acredita con el delta y la ausencia de id en cada rechazo; si el listado no fue verificable, el caso queda no concluyente.\n\n${r.run_id === 'RUN-G051-V1-20261028-032158' ? '## Observaciones de intentos y efectos persistentes\n\nIntento 1: preflight sin peticiones. Intento 2: detenido por el HTTP 500 de la fecha futura; incidencia técnica de continuidad del intento. El intento 3 completó los casos independientes. Se prevén cuatro archivos ONNX de registros aceptados y probablemente un quinto huérfano de la fecha futura; el almacenamiento de TEST no fue inspeccionado. El aviso por f1=0.0 se prevé por código; su entrega no fue verificada.\n\n' : ''}## Incidencias de producto\n\n${incidencias}\n\n## Problemas técnicos y análisis\n\n${r.problemas_tecnicos.length ? r.problemas_tecnicos.map(x => `- ${celda(x)}`).join('\n') : 'Sin problemas técnicos observados en este intento.'} Las hipótesis de código local no demuestran causa raíz en TEST.\n\n## Cierre y rollback\n\nDELETE RUN HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. ${r.cierre.rollback.verificado ? 'Respuesta de cierre del sandbox recibida; no se verificó por consulta posterior la reversión de BD' : 'Rollback de BD no confirmado'}: ${celda(r.cierre.rollback.motivo)}. Los archivos en MODELOS_STORAGE_PATH, posibles respaldos RF-73 y el correo no son revertidos por el sandbox; su eliminación o entrega no se verificó.\n\n## Evidencias\n\n${r.evidencias.map(x => `- ${x}`).join('\n') || 'Sin evidencias registradas.'}\n\n## Revisión QA\n\n${r.revision_qa ? `${r.revision_qa.fecha}; ${r.revision_qa.realizada_por}: ${r.revision_qa.motivo}.` : 'Sin revisión posterior registrada en este resultado.'}\n\n## Conclusión y acción\n\n${decision}. ${falta}\n`;
}
function finalizar(c, r, secretos) {
  const nombre = nombreInforme(r.version);
  r.evidencias = [...new Set([...r.evidencias, nombre, 'resultado.json'])];
  const completos = r.comprobaciones.every(x => ['APROBADO', 'RECHAZADO'].includes(x.estado)
    && x.evidencia && r.evidencias.includes(x.evidencia));
  r.oficial = completos && r.cierre.run.cierre_http === 200 && r.cierre.rollback.verificado
    && r.problemas_tecnicos.length === 0 && r.evidencias.filter(x => ![nombre, 'resultado.json'].includes(x))
      .every(x => fs.existsSync(path.join(c.directorio, x)));
  r.consume_version = r.oficial;
  fs.writeFileSync(path.join(c.directorio, nombre), sanearArtefacto(informe(r), secretos), 'utf8');
  guardar(path.join(c.directorio, 'resultado.json'), JSON.parse(sanearArtefacto(JSON.stringify(r), secretos)));
}
export async function evaluar(c, { env, ensayo = false }) {
  if (!fs.existsSync(c.directorio)) throw Error('RUN_NO_CREADO_POR_LANZADOR');
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = resultadoInicial(c);
  const secretos = [env.QA_SANDBOX_SECRET, env.RF71_INTERNAL_KEY, env.QA_ADMIN_EMAIL,
    env.QA_ADMIN_PASSWORD].filter(Boolean);
  let temporal = null, tocado = false;
  try {
    const pre = preflight(c, env, ensayo); guardar(path.join(c.directorio, 'preflight.json'), pre);
    r.evidencias.push('preflight.json');
    if (!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
    tocado = true;
    r.preflight_herramientas.newman = versionNewman(ensayo);
    if (!r.preflight_herramientas.newman.ok) throw Error('NEWMAN_NO_DISPONIBLE');
    const login = await pedir(api, 'POST', '/sesiones/', { cuerpo: {
      correo_electronico: env.QA_ADMIN_EMAIL, contrasena: env.QA_ADMIN_PASSWORD }, bitacora: r.bitacora });
    if (login.http !== 200 || !login.cuerpo?.token) throw Error(`LOGIN_HTTP_${login.http}`);
    const token = login.cuerpo.token; secretos.push(token);
    const catalogo = await pedir(api, 'GET', '/configuracion/variables-ambientales',
      { token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, bitacora: r.bitacora });
    if (catalogo.http !== 200 || !catalogo.eco || !Array.isArray(catalogo.cuerpo?.items))
      throw Error(`CATALOGO_I3P1_NO_VERIFICABLE_HTTP_${catalogo.http}`);
    const ids = catalogo.cuerpo.items.map(x => x.id_variable_ambiental)
      .filter(Number.isSafeInteger);
    if (!ids.length) throw Error('CATALOGO_I3P1_SIN_VARIABLE_ACTIVA');
    const inexistente = Math.max(...ids) + 1;
    const rutaListado = '/prediccion/modelos?tipo_modelo=MODELO_ESPECIES_GRANDES&limit=100&offset=0';
    const inicial = await pedir(api, 'GET', rutaListado,
      { token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, bitacora: r.bitacora });
    if (inicial.http !== 200 || !inicial.eco || !Number.isSafeInteger(inicial.cuerpo?.total))
      throw Error(`LISTADO_INICIAL_NO_VERIFICABLE_HTTP_${inicial.http}`);
    r.conteo.inicial = inicial.cuerpo.total;
    temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g051-newman-'));
    const archivo = path.join(temporal, 'g051.onnx'); fs.writeFileSync(archivo, onnxMinimo());
    const hash = sha256(fs.readFileSync(archivo));
    const ahora = Date.now();
    const desfase = inicial.fechaServidor ? Math.abs(Date.parse(inicial.fechaServidor) - ahora) : NaN;
    const casos = escenarios({ variable: ids[0], inexistente, hash,
      dataset: sha256(Buffer.from('G051 dataset QA RF-71')), ahora, archivo });
    r.datos = { variable_existente: ids[0], variable_inexistente: inexistente,
      hash_artefacto: hash, fecha_cliente_ahora: new Date(ahora).toISOString(),
      fecha_servidor: inicial.fechaServidor ?? catalogo.fechaServidor,
      procesos: casos.map(x => x.id_proceso_rf71) };
    const n = await ejecutarNewman(c, api, env, casos, secretos, temporal);
    r.evidencias.push(...n.artefactos);
    if (!n.artefactos.length || n.salida.error || n.fallos.some(f =>
      /SyntaxError|ReferenceError|TypeError/.test(f.name))) throw Error(`NEWMAN_TECNICO:${n.salida.error ?? n.fallos.map(x => x.name).join(',')}`);
    const posts = casos.map((_, i) => n.respuestas.find(x => x.iteracion === i) ?? null);
    let consecutivos = 0, falloSistemico = false;
    for (const p of posts) {
      consecutivos = p?.http >= 500 ? consecutivos + 1 : 0;
      if (consecutivos >= 3) { falloSistemico = true; break; }
    }
    if (posts.some(p => p?.http === 403)) throw Error('POST_403_CLAVE_SIN_REINTENTO');
    if (falloSistemico) throw Error('POST_5XX_CONSECUTIVOS_SIN_REINTENTO');
    const get = Array(casos.length).fill(null);
    for (let i = 0; i < casos.length; i++) {
      if (!casos[i].aceptado || ![200, 201].includes(posts[i]?.http) || idVersion(posts[i]?.cuerpo) === null) continue;
      try { get[i] = await pedir(api, 'GET', `/prediccion/modelos/${encodeURIComponent(idVersion(posts[i].cuerpo))}`,
        { token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, bitacora: r.bitacora }); }
      catch { r.problemas_tecnicos.push(`GET_SIN_RESPUESTA_ITERACION_${i}`); }
    }
    const final = await pedir(api, 'GET', rutaListado,
      { token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, bitacora: r.bitacora });
    if (final.http === 200 && final.eco && Number.isSafeInteger(final.cuerpo?.total)) {
      r.conteo.final = final.cuerpo.total; r.conteo.delta = final.cuerpo.total - r.conteo.inicial;
    } else r.problemas_tecnicos.push(`LISTADO_FINAL_NO_VERIFICABLE_HTTP_${final.http}`);
    const listadoValido = r.conteo.delta !== null && Array.isArray(final.cuerpo?.items);
    const itemsFinales = listadoValido ? final.cuerpo.items : [];
    const listadoCompleto = listadoValido && final.cuerpo.total <= itemsFinales.length;
    const porProceso = new Map(itemsFinales.filter(x => x.id_proceso_rf71)
      .map(x => [String(x.id_proceso_rf71), x]));
    const idsFinales = new Set(porProceso.keys());
    const conciliaciones = casos.map((escenario, i) => {
      if (posts[i]?.http) return null;
      const item = porProceso.get(escenario.id_proceso_rf71);
      return { id_proceso_rf71: escenario.id_proceso_rf71,
        registrado: !!item && idVersion(item) !== null && !!item.estado_version,
        id_version_modelo: item ? idVersion(item) : null,
        estado_version: item?.estado_version ?? null,
        listado_completo: listadoCompleto };
    });
    for (let i = 0; i < casos.length; i++) {
      const conciliacion = conciliaciones[i];
      if (!casos[i].aceptado || !conciliacion?.registrado) continue;
      if (get.filter(Boolean).length >= PRESUPUESTO.get_aceptados) break;
      try { get[i] = await pedir(api, 'GET',
        `/prediccion/modelos/${encodeURIComponent(conciliacion.id_version_modelo)}`,
        { token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, bitacora: r.bitacora }); }
      catch { r.observaciones_tecnicas.push(`GET_CONCILIADO_SIN_RESPUESTA_ITERACION_${i}`); }
    }
    r.conteo.aceptados = posts.filter((p, i) => casos[i].aceptado && [200, 201].includes(p?.http)
      && idVersion(p.cuerpo) !== null).length;
    r.conteo.conciliados = conciliaciones.filter((x, i) => casos[i].aceptado && x?.registrado).length;
    r.conteo.rechazados_con_id = posts.filter((p, i) => !casos[i].aceptado && idVersion(p?.cuerpo) !== null).length;
    r.solicitudes = casos.map((escenario, i) => ({ escenario: { caso: escenario.caso,
      dato: escenario.dato, aceptado: escenario.aceptado, omitir: escenario.omitir,
      id_proceso_rf71: escenario.id_proceso_rf71, fecha_entrenamiento: escenario.fecha_entrenamiento,
      tipo_modelo: escenario.tipo_modelo, metricas_validacion: escenario.metricas_validacion,
      compatibilidad_variables: escenario.compatibilidad_variables,
      hash_artefacto_sha256: escenario.omitir.includes('hash_artefacto_sha256') ? null : escenario.hash_artefacto_sha256,
      dataset_entrenamiento_hash: escenario.omitir.includes('dataset_entrenamiento_hash') ? null : escenario.dataset_entrenamiento_hash },
    post: posts[i], get: get[i], conciliacion: conciliaciones[i],
    aparece_en_listado_final: idsFinales.has(escenario.id_proceso_rf71) }));
    const bloqueo = posts.find((x, i) => casos[i].aceptado && x?.http >= 500);
    if (bloqueo) r.problemas_tecnicos.push(`POST_VALIDO_HTTP_${bloqueo.http}_SIN_REINTENTO`);
    conciliaciones.forEach((x, i) => {
      if (!x) return;
      if (x.registrado) r.observaciones_tecnicas.push(`POST_SIN_RESPUESTA_CONCILIADO_ITERACION_${i}`);
      else r.problemas_tecnicos.push(`POST_SIN_RESPUESTA_NO_CONCILIADO_ITERACION_${i}`);
    });
    for (let k = 0; k < CASOS.length; k++) {
      const xs = r.solicitudes.filter(x => x.escenario.caso === CASOS[k]
        || k === 1 && x.escenario.dato === 'variables existentes / ayer');
      const evaluados = xs.map(evaluarSolicitud);
      let estado = evaluados.some(x => x.estado === 'BLOQUEADO') ? 'BLOQUEADO'
        : evaluados.some(x => x.estado === 'NO_CONCLUYENTE') ? 'NO_CONCLUYENTE'
          : evaluados.some(x => x.estado === 'RECHAZADO') ? 'RECHAZADO' : 'APROBADO';
      let motivo = evaluados.filter(x => x.estado !== 'APROBADO').map(x => x.motivo).join('; ')
        || `${xs.length} solicitudes cumplen el oráculo`;
      if (estado === 'APROBADO') {
        const conciliados = xs.filter(x => x.conciliacion?.registrado);
        if (conciliados.length) motivo += `; ${conciliados.map(x =>
          `POST sin respuesta en el límite; registro acreditado por id_proceso_rf71 en el listado (ID ${x.conciliacion.id_version_modelo}, estado ${x.conciliacion.estado_version})`).join('; ')}`;
      }
      if (k === 1 && (!Number.isFinite(desfase) || desfase > 5000)) {
        estado = 'NO_CONCLUYENTE'; motivo = 'Desfase cliente-servidor mayor de 5 s o fecha HTTP ausente; instante actual no fiable';
        r.problemas_tecnicos.push('RELOJ_CLIENTE_SERVIDOR_NO_FIABLE');
      }
      if (r.conteo.delta === null) {
        estado = final.http === 403 || final.http >= 500 ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
        motivo = `Listado final no verificable: HTTP ${final.http ?? 'sin respuesta'}`;
      }
      else if (xs.some(x => !x.escenario.aceptado && x.aparece_en_listado_final)
        && estado !== 'BLOQUEADO' && estado !== 'NO_CONCLUYENTE') {
        estado = 'RECHAZADO'; motivo = 'Una solicitud rechazada aparece en el listado final por id_proceso_rf71';
      } else if (r.conteo.delta !== r.conteo.aceptados + r.conteo.conciliados && estado === 'APROBADO'
        && !r.solicitudes.some(x => !x.escenario.aceptado && x.aparece_en_listado_final)) {
        estado = 'NO_CONCLUYENTE'; motivo = `Delta ${r.conteo.delta} no atribuible a ${r.conteo.aceptados} aceptados con respuesta y ${r.conteo.conciliados} conciliados`;
      }
      asignar(r, k, estado, motivo);
    }
    r.incidencias = agruparIncidencias(r);
    return r;
  } catch (e) {
    const motivo = limpio(e.message); r.problemas_tecnicos.push(motivo);
    const tipo = /5XX|_5\d\d|403|CATALOGO|LOGIN|LISTADO/.test(motivo) ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
    CASOS.forEach((caso, i) => { if (r.casos[caso].motivo === 'Sin comprobación') asignar(r, i, tipo, motivo); });
    return r;
  } finally {
    if (tocado) try {
      const x = await pedir(api, 'DELETE', `/test-control/runs/${encodeURIComponent(c.runId)}`,
        { secreto: env.QA_SANDBOX_SECRET, bitacora: r.bitacora });
      r.cierre.run.cierre_http = x.http;
      r.cierre.rollback.verificado = x.http === 200 && /rollback|cerrad/i.test(JSON.stringify(x.cuerpo ?? {}));
      r.cierre.rollback.motivo = r.cierre.rollback.verificado
        ? 'Sandbox confirmó cierre; no hay consulta posterior de BD' : `DELETE HTTP ${x.http}; respuesta sin confirmación de rollback`;
    } catch (e) { r.problemas_tecnicos.push(`CIERRE_SIN_RESPUESTA:${limpio(e.message)}`); }
    if (temporal) {
      if (!path.resolve(temporal).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
      fs.rmSync(temporal, { recursive: true, force: true });
    }
    finalizar(c, r, secretos);
  }
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
  else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
  else try {
    const c = contextoEjecucion(process.argv.slice(2), { grupo: 'G051', casos: CASOS, directorio: DIR });
    const r = await evaluar(c, { env: leerEnv() });
    console.log(JSON.stringify({ run_id: r.run_id, casos: r.casos, oficial: r.oficial }));
    if (!r.oficial) process.exitCode = 2;
  } catch (e) { console.error(`G051: ${limpio(e.message)}`); process.exitCode = 2; }
}
