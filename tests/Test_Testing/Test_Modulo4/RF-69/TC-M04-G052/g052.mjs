#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';
import { sanearArtefacto, contieneMojibake } from './lib/seguridad.mjs';
import { onnxMinimo, sha256 } from './lib/artefactos.mjs';
import { CASOS, IDS, PRESUPUESTO, CAPACIDADES, escenarios, detalleCubre, auditoriaValida } from './lib/g052_escenario.mjs';

const require = createRequire(import.meta.url);
const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
let limiteGlobal = Infinity;
const COLECCION = path.join(DIR, 'G052.postman_collection.json');
const ARCHIVOS = ['.gitkeep', 'g052.mjs', 'G052.postman_collection.json', 'README.md',
  'lib/contrato_ejecutor.mjs', 'lib/seguridad.mjs', 'lib/artefactos.mjs', 'lib/g052_escenario.mjs',
  'pruebas/g052_ensayo.mjs', 'pruebas/g052_env.test.mjs', 'pruebas/registro_qa.mjs'];
const limpio = x => String(x ?? '').replaceAll('|', '/').replace(/[\r\n]+/g, ' ').slice(0, 350);
const celda = x => limpio(x === null || x === undefined ? 'nulo' : typeof x === 'object' ? JSON.stringify(x) : x);
const guardar = (p, x) => fs.writeFileSync(p, JSON.stringify(x, null, 2), 'utf8');
const idVersion = x => x?.id_version_modelo ?? x?.id_version ?? null;
const nombreInforme = v => v === 1 ? 'TC-M04-G052_resultado.md' : `TC-M04-G052_reevaluacion_V${v}.md`;

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
    if (ensayo && x.error?.code === 'EPERM') return { ok: true,
      version: require(path.join(paqueteNewman(), 'package.json')).version, modo: 'paquete local' };
    return { ok: x.status === 0 && !!x.stdout.trim(), version: x.stdout.trim(), error: x.error?.code ?? null };
  } catch (e) { return { ok: false, error: e.code ?? e.message }; }
}
export function comprobar() {
  let coleccion = false;
  try {
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const i of col.item) for (const e of i.event ?? []) new vm.Script((e.script?.exec ?? []).join('\n'));
    coleccion = col.item.length === 1 && col.item[0].name === 'API-G052-POST'
      && col.item[0].request.method === 'POST' && !contieneMojibake(JSON.stringify(col));
  } catch { /* comunicado en salida */ }
  const faltantes = ARCHIVOS.filter(x => !fs.existsSync(path.join(DIR, x)));
  const presentes = fs.readdirSync(DIR).filter(x => !['lib', 'pruebas', 'Resultados', 'EvaluacionV2'].includes(x))
    .concat(...['lib', 'pruebas'].map(d => fs.existsSync(path.join(DIR, d))
      ? fs.readdirSync(path.join(DIR, d)).map(x => `${d}/${x}`) : []));
  const inesperados = presentes.filter(x => !ARCHIVOS.includes(x));
  const markdownSuperior = fs.existsSync(path.join(DIR, 'Resultados'))
    && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const e = escenarios({ variable: 1, hash: 'a'.repeat(64), dataset: 'b'.repeat(64), archivo: 'local.onnx' });
  const ok = coleccion && !faltantes.length && !inesperados.length && !markdownSuperior
    && e.length === PRESUPUESTO.posts && PRESUPUESTO.total === 44;
  console.log(JSON.stringify({ grupo: 'G052', ok, coleccion, escenarios: e.length,
    faltantes, inesperados, markdownSuperior, presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}
export function preflight(c, env, ensayo = false) {
  const base = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const claves = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_ADMIN_EMAIL',
    'QA_ADMIN_PASSWORD', 'RF71_INTERNAL_KEY'];
  const barreras = claves.filter(k => !String(env[k] ?? '').trim());
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base) : base !== API) barreras.push('API_NO_CANONICA');
  if (c.version > 1 && c.operacion !== 'reevaluar') barreras.push('REEVALUACION_SIN_DECISION');
  return { fase: 'PREFLIGHT_LOCAL', grupo: 'G052', run_id: c.runId, version: c.version,
    ok: !barreras.length, barreras, presupuesto: PRESUPUESTO,
    veterinario_configurado: !!(env.QA_VETERINARIO_EMAIL && env.QA_COMMON_PASSWORD),
    efectos_declarados: ['7_versiones_BD_sujetas_a_rollback', '7_archivos_ONNX_no_revertidos',
      'hasta_4_notas_posibles_revertidas_si_se_acepta_campo_extra',
      '5_avisos_por_destinatario_activo_permiso_43_3_no_revertidos',
      'dos_logins_previos_pueden_dejar_sesion_o_auditoria'] };
}
function errorPublico(data) {
  const d = data?.detail && typeof data.detail === 'object' ? data.detail : data;
  return { codigo: limpio(d?.error_code ?? d?.code ?? d?.codigo),
    mensaje: limpio(d?.message ?? d?.mensaje ?? (typeof data?.detail === 'string' ? data.detail : '')) };
}
async function pedir(api, metodo, ruta, { token, secreto, runId, cuerpo, bitacora } = {}) {
  let http = null, eco = null;
  try {
    const restante = limiteGlobal - Date.now();
    if (restante <= 0) throw Error('LIMITE_1200_SEGUNDOS');
    const x = await fetch(api + ruta, { method: metodo, redirect: 'manual',
      headers: { ...(cuerpo ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(secreto ? { 'X-Sandbox-Secret': secreto } : {}),
        ...(runId ? { 'X-Test-Run-Id': runId, 'X-Zona-Horaria': 'UTC' } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      signal: AbortSignal.timeout(Math.max(1, Math.min(PRESUPUESTO.timeout_ms, restante))) });
    http = x.status; eco = runId ? x.headers.get('x-test-run-id') === runId : null;
    const data = await x.json().catch(() => null);
    return { http, eco, cuerpo: data, error: http >= 400 ? errorPublico(data) : null };
  } finally { bitacora.push({ metodo, ruta, http, eco, en_run: !!runId }); }
}
function extracto(ex, runId) {
  const hs = ex?.response?.header ?? [];
  const eco = hs.find(h => String(h.key).toLowerCase() === 'x-test-run-id')?.value === runId;
  const bytes = Buffer.from(ex?.response?.stream?.data ?? []);
  let cuerpo = null; try { cuerpo = JSON.parse(bytes.toString('utf8')); } catch { /* no JSON */ }
  const http = ex?.response?.code ?? null;
  return { iteracion: ex?.cursor?.iteration ?? null, http, eco, cuerpo,
    error: http >= 400 ? errorPublico(cuerpo) : null };
}
async function ejecutarNewman(c, api, env, escenariosRun, secretos, temporal) {
  const raw = path.join(temporal, 'raw.json'), environment = path.join(temporal, 'environment.json');
  const datos = path.join(temporal, 'iteraciones.json');
  guardar(environment, { values: Object.entries({ autorizado_run: 'SI', ensayo_loopback: c.ensayo ? 'SI' : 'NO',
    base_url: api, run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET,
    rf71_internal_key: env.RF71_INTERNAL_KEY }).map(([key, value]) => ({ key, value, enabled: true })) });
  guardar(datos, escenariosRun.map(x => ({ ...x,
    metricas_validacion: JSON.stringify(x.metricas_validacion),
    compatibilidad_variables: JSON.stringify(x.compatibilidad_variables) })));
  const limiteNewman = Math.max(1, Math.min(1160000, limiteGlobal - Date.now()));
  const inicios = new Map(), duraciones = new Map();
  const salida = await new Promise(resolve => {
    const run = require(paqueteNewman()).run({ collection: JSON.parse(fs.readFileSync(COLECCION, 'utf8')),
      environment: JSON.parse(fs.readFileSync(environment, 'utf8')),
      iterationData: JSON.parse(fs.readFileSync(datos, 'utf8')), reporters: ['json'],
      reporter: { json: { export: raw } }, timeoutRequest: c.ensayo ? 250 : PRESUPUESTO.timeout_post_ms,
      timeout: limiteNewman, color: 'off' }, error => resolve({ code: error ? 1 : 0,
      error: error?.code ?? null, modo: 'API_LOCAL' }));
    run.on('beforeRequest', (_, args) => inicios.set(args.cursor.iteration, performance.now()));
    run.on('request', (_, args) => {
      const i = args.cursor.iteration;
      if (inicios.has(i)) duraciones.set(i, Math.round(performance.now() - inicios.get(i)));
    });
  });
  if (!fs.existsSync(raw)) return { salida, respuestas: [], fallos: [], artefactos: [] };
  const original = JSON.parse(fs.readFileSync(raw, 'utf8'));
  const respuestas = (original.run?.executions ?? []).map(ex => ({ ...extracto(ex, c.runId),
    duracion_ms: duraciones.get(ex?.cursor?.iteration) ?? null }));
  const fallos = (original.run?.failures ?? []).map(f => ({ name: limpio(f.error?.name), mensaje: limpio(f.error?.message) }));
  fs.mkdirSync(path.join(c.directorio, 'newman'), { recursive: true });
  const artefactos = ['newman/newman-G052.json', 'newman/newman-G052.html'];
  guardar(path.join(c.directorio, artefactos[0]), JSON.parse(sanearArtefacto(JSON.stringify({
    info: { nombre: 'Newman G052', generado: true, saneado: true },
    run: { stats: original.run?.stats ?? null, executions: respuestas, failures: fallos } }), secretos)));
  const filas = respuestas.map(x => `<tr><td>${x.iteracion}</td><td>${x.http ?? 'sin respuesta'}</td><td>${x.eco}</td></tr>`).join('');
  fs.writeFileSync(path.join(c.directorio, artefactos[1]),
    `<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G052</title><h1>Newman G052</h1><table><tr><th>Iteración</th><th>HTTP</th><th>Eco RUN</th></tr>${filas}</table></html>`, 'utf8');
  return { salida, respuestas, duraciones, fallos, artefactos };
}

function resultadoInicial(c) {
  return { grupo: 'G052', run_id: c.runId, version: c.version, intento: c.intento ?? null,
    operacion: c.operacion, autorizacion: c.referencia, ambiente: c.ensayo ? 'LOOPBACK_LOCAL' : 'TEST',
    oficial: false, consume_version: false, presupuesto: PRESUPUESTO,
    casos: Object.fromEntries(CASOS.map(x => [x, { estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación' }])),
    comprobaciones: CASOS.map((caso, i) => ({ caso, fuente: 'API', id: IDS[i], tipo: 'ASSERT',
      estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación', evidencia: null })),
    cypress: { total_pruebas: 0 }, preflight_herramientas: {}, evidencias: [],
    bitacora: [], solicitudes: [], listado: null, intentos_estado: [], auditoria: null,
    incidencias: [], problemas_tecnicos: [], observaciones: [],
    detalle_133: { evaluadas: [], excluidas: [], sin_evidencia: [] },
    cierre: { run: { cierre_http: null }, rollback: { verificado: false,
      motivo: 'Sin cierre ni comprobación posterior de BD' } } };
}
function asignar(r, i, estado, motivo) {
  r.casos[CASOS[i]] = { estado, motivo };
  Object.assign(r.comprobaciones[i], { estado, motivo,
    evidencia: r.evidencias.includes('newman/newman-G052.json') ? 'newman/newman-G052.json' : 'resultado.json' });
}
function resumirSolicitudes(casos, posts, gets = []) {
  return casos.map((x, i) => ({ caso: x.caso, dato: x.dato,
    f1: x.metricas_validacion.f1_score_global, recall: x.metricas_validacion.recall_clase_riesgo_alto,
    proceso: x.id_proceso_rf71,
    post: posts[i] && { http: posts[i].http, eco: posts[i].eco,
      duracion_ms: posts[i].duracion_ms, recuperado: !!posts[i].recuperado,
      id: idVersion(posts[i].cuerpo), estado: posts[i].cuerpo?.estado_version,
      detalle: posts[i].cuerpo?.detalle_validacion, error: posts[i].error },
    get: gets[i] && { http: gets[i].http, eco: gets[i].eco,
      id: idVersion(gets[i].cuerpo), estado: gets[i].cuerpo?.estado_version,
      detalle: gets[i].cuerpo?.detalle_validacion } }));
}
function estadoSolicitud(post, get, esperado, httpEsperado) {
  if (!post?.http && !post?.recuperado) return { estado: 'NO_CONCLUYENTE', motivo: 'POST sin respuesta y versión no localizada' };
  if (post.http === 403) return { estado: 'BLOQUEADO', motivo: 'POST HTTP 403: clave interna o acceso no verificable' };
  if (post.http >= 500) return { estado: 'RECHAZADO', motivo: `POST HTTP ${post.http} para métricas válidas` };
  if (post.http && post.http !== httpEsperado) return { estado: 'RECHAZADO', motivo: `POST HTTP ${post.http}; esperado ${httpEsperado}` };
  if ((!post.recuperado && !post.eco) || idVersion(post.cuerpo) == null) return { estado: 'NO_CONCLUYENTE', motivo: 'Sin eco RUN o id de versión en POST' };
  if (!get?.http) return { estado: 'NO_CONCLUYENTE', motivo: 'GET posterior sin respuesta' };
  if (get.http === 403 || get.http >= 500) return { estado: 'BLOQUEADO', motivo: `GET HTTP ${get.http}` };
  if (get.http !== 200 || !get.eco) return { estado: 'NO_CONCLUYENTE', motivo: `GET HTTP ${get.http}; sin eco o datos` };
  if (idVersion(get.cuerpo) !== idVersion(post.cuerpo)) return { estado: 'RECHAZADO', motivo: 'GET no confirma id de versión' };
  if (get.cuerpo?.estado_version !== esperado) return { estado: 'RECHAZADO',
    motivo: `Estado ${get.cuerpo?.estado_version ?? 'ausente'}; esperado ${esperado}` };
  if (esperado === 'APROBADO' && get.cuerpo?.detalle_validacion !== null)
    return { estado: 'RECHAZADO', motivo: 'APROBADO con detalle_validacion no nulo' };
  return { estado: 'APROBADO', motivo: post.recuperado
    ? `Versión localizada por id_proceso_rf71 y GET 200; estado ${esperado}; HTTP de POST no verificable`
    : `POST ${httpEsperado} y GET 200; estado ${esperado}` };
}
function combinar(xs) {
  const orden = ['BLOQUEADO', 'NO_CONCLUYENTE', 'RECHAZADO', 'APROBADO'];
  const estado = orden.find(x => xs.some(y => y.estado === x)) ?? 'NO_CONCLUYENTE';
  return { estado, motivo: xs.filter(x => x.estado !== 'APROBADO').map(x => x.motivo).join('; ')
    || 'Comprobaciones conformes; ver datos de cada solicitud' };
}
export function motivoConDatos(r, caso) {
  const solicitud = dato => r.solicitudes.find(x => x.dato === dato);
  const resumen = dato => {
    const s = solicitud(dato);
    if (!s) return `${dato}: sin solicitud registrada`;
    return `${dato}: f1=${s.f1}, recall=${s.recall}, HTTP ${s.post?.http ?? 'sin respuesta'}, id ${s.post?.id ?? 'sin id'}, ${s.get?.estado ?? 'sin estado'}`;
  };
  if (caso === CASOS[0]) return `${resumen('129')}; auditoría VERSION_REGISTRADA + VERSION_APROBADA de SISTEMA`;
  if (caso === CASOS[1]) return resumen('130');
  if (caso === CASOS[2]) return resumen('131');
  if (caso === CASOS[3]) return ['132-a', '132-b', '132-c', '132-d'].map(resumen).join('; ');
  if (caso === CASOS[4]) return r.detalle_133.evaluadas.map(x => {
    const s = solicitud(x.dato);
    const valores = x.umbrales.map(u => u === 'f1' ? `f1=${s?.f1}<0.80` : `recall=${s?.recall}<0.85`);
    return `${x.dato}/id ${x.version}: ${valores.join(' y ')}`;
  }).join('; ');
  const cambios = r.intentos_estado.filter(x => x.get?.cuerpo?.estado_version !== x.inicial);
  const respuestas = [...new Set(r.intentos_estado.map(x => `${x.metodo}${x.ruta.endsWith('/notas') ? ' /notas' : ''} ${x.respuesta?.http ?? 'sin respuesta'}`))];
  return `${r.intentos_estado.length} intentos; ${respuestas.join(', ')}; ${cambios.length} cambios de estado en GET posterior`;
}
function clasificar(r, escenariosRun, posts, gets, auditoria, veterinario) {
  const evaluados = escenariosRun.map((e, i) => estadoSolicitud(posts[i], gets[i],
    [0, 3].includes(i) ? 'APROBADO' : 'RECHAZADO', [0, 3].includes(i) ? 201 : 200));
  const aud = auditoria;
  const e129 = evaluados[0];
  if (e129.estado === 'APROBADO') {
    if (!aud?.http) asignar(r, 0, 'NO_CONCLUYENTE', 'Auditoría RF-73 sin respuesta');
    else if (aud.http === 403 || aud.http >= 500) asignar(r, 0, 'BLOQUEADO', `Auditoría RF-73 HTTP ${aud.http}`);
    else if (aud.http !== 200 || !aud.eco || !Array.isArray(aud.cuerpo?.items))
      asignar(r, 0, 'NO_CONCLUYENTE', `Auditoría RF-73 HTTP ${aud.http}, sin eco o listado`);
    else assign129();
  } else asignar(r, 0, e129.estado, e129.motivo);
  function assign129() {
    const ok = auditoriaValida(aud.cuerpo.items, idVersion(posts[0].cuerpo), escenariosRun[0].id_proceso_rf71);
    asignar(r, 0, ok ? 'APROBADO' : 'RECHAZADO', ok
      ? 'APROBADO y VERSION_REGISTRADA + VERSION_APROBADA de sistema, fuente RF-71'
      : 'Auditoría no acredita ambos eventos automáticos con fuente RF-71');
  }
  for (const [i, indices] of [[1, [1]], [2, [2]], [3, [3, 4, 5, 6]]]) {
    const x = combinar(indices.map(j => evaluados[j]));
    if (x.estado === 'APROBADO' && (i === 1 || i === 2)) {
      const campo = i === 1 ? 'f1' : 'recall';
      const detalle = gets[indices[0]]?.cuerpo?.detalle_validacion
        ?? posts[indices[0]]?.cuerpo?.detalle_validacion;
      if (!detalleCubre(detalle, [campo])) {
        x.estado = 'RECHAZADO'; x.motivo = `RECHAZADO sin descripción del umbral ${campo} no alcanzado`;
      }
    }
    asignar(r, i, x.estado, x.motivo);
  }
  const detalle133 = r.detalle_133;
  const detalles = [];
  for (const i of [1, 2, 4, 5, 6]) {
    const dato = escenariosRun[i].dato, caso = escenariosRun[i].caso;
    const p = posts[i], g = gets[i];
    const propio = evaluados[i];
    const pendiente = motivo => detalle133.sin_evidencia.push({ dato, caso, motivo });
    const excluir = motivo => detalle133.excluidas.push({ dato, caso,
      version: idVersion(g?.cuerpo) ?? idVersion(p?.cuerpo), motivo,
      incidencia: `INC-M04-G052-${claveIncidencia(r.casos[caso].motivo)}` });
    const defectoAtribuido = propio.estado === 'RECHAZADO' && r.casos[caso].estado === 'RECHAZADO';
    if (!p?.http && !p?.recuperado) { pendiente('POST sin respuesta y versión no conciliada'); continue; }
    if (!p?.recuperado && !p?.eco) { pendiente('POST sin eco RUN'); continue; }
    if (idVersion(p.cuerpo) == null) {
      if (defectoAtribuido) excluir('registro fallido; no se creó versión rechazada consultable');
      else pendiente('sin id de versión y sin defecto atribuido al subcaso');
      continue;
    }
    if (!g?.http) { pendiente('GET de detalle sin respuesta'); continue; }
    if (g.http !== 200 || !g.eco || idVersion(g.cuerpo) !== idVersion(p.cuerpo)) {
      pendiente(`GET de detalle no verificable: HTTP ${g.http}, eco ${g.eco}`); continue;
    }
    if (g.cuerpo?.estado_version !== 'RECHAZADO') {
      if (defectoAtribuido && g.cuerpo?.estado_version)
        excluir(`versión ${g.cuerpo.estado_version}; no quedó RECHAZADO`);
      else pendiente('estado de la versión no verificable');
      continue;
    }
    const faltan = [
      ...(escenariosRun[i].metricas_validacion.f1_score_global < 0.80 ? ['f1'] : []),
      ...(escenariosRun[i].metricas_validacion.recall_clase_riesgo_alto < 0.85 ? ['recall'] : []) ];
    const ok = detalleCubre(g.cuerpo.detalle_validacion, faltan);
    detalle133.evaluadas.push({ dato, caso, version: idVersion(g.cuerpo), umbrales: faltan,
      estado: ok ? 'APROBADO' : 'RECHAZADO' });
    detalles.push(ok ? { estado: 'APROBADO', motivo: `${dato}: ${faltan.join(' y ')}` }
      : { estado: 'RECHAZADO', motivo: `${dato}: detalle no identifica ${faltan.join(' y ')}` });
  }
  const d = detalle133.sin_evidencia.length || !detalles.length
    ? { estado: 'NO_CONCLUYENTE', motivo: `${detalles.length} versiones rechazadas evaluadas; ${detalle133.sin_evidencia.length} sin evidencia; ${detalle133.excluidas.length} excluidas por defecto atribuido` }
    : combinar(detalles);
  asignar(r, 4, d.estado, d.motivo);
  if (!veterinario) asignar(r, 5, 'NO_CONCLUYENTE',
    'No hay cuenta Veterinario verificable; solo se probaron intentos de Administrador');
  else if (r.intentos_estado.length !== PRESUPUESTO.intentos_estado)
    asignar(r, 5, 'NO_CONCLUYENTE', `${r.intentos_estado.length} de 12 intentos; falta una versión o un rol`);
  else {
    const x = combinar(r.intentos_estado.map(t => {
      if (!t.respuesta?.http || !t.get?.http) return { estado: 'NO_CONCLUYENTE', motivo: `${t.rol}/${t.metodo}: sin respuesta` };
      if (t.respuesta.http === 403 || t.get.http === 403 || t.respuesta.http >= 500 || t.get.http >= 500)
        return { estado: 'BLOQUEADO', motivo: `${t.rol}/${t.metodo}: HTTP ${t.respuesta.http}/${t.get.http}` };
      if (t.get.http !== 200 || !t.get.eco) return { estado: 'NO_CONCLUYENTE', motivo: `${t.rol}/${t.metodo}: GET no verificable` };
      if (t.get.cuerpo?.estado_version !== t.inicial)
        return { estado: 'RECHAZADO', motivo: `${t.rol}/${t.metodo}: estado cambió de ${t.inicial} a ${t.get.cuerpo?.estado_version}` };
      if (t.respuesta.http >= 400 || t.respuesta.http < 300)
        return { estado: 'APROBADO', motivo: `${t.rol}/${t.metodo}: estado conservado` };
      return { estado: 'NO_CONCLUYENTE', motivo: `${t.rol}/${t.metodo}: respuesta inusual` };
    }));
    asignar(r, 5, x.estado, x.motivo);
  }
  r.observaciones.push('El correo a Veterinario no tiene traza de entrega por API pública; API-130-01 evalúa HTTP, estado y detalle.');
  for (let i = 0; i < CASOS.length; i++) if (r.casos[CASOS[i]].estado === 'APROBADO')
    asignar(r, i, 'APROBADO', motivoConDatos(r, CASOS[i]));
}
function claveIncidencia(motivo) {
  return /estado cambió/.test(motivo) ? 'ESTADO_ALTERABLE'
    : /detalle no identifica/.test(motivo) ? 'DETALLE'
      : /Auditoría/.test(motivo) ? 'HISTORIAL'
        : /POST HTTP 201; esperado 200/.test(motivo) ? 'HTTP_E3'
          : /Estado/.test(motivo) ? 'UMBRAL' : 'REGISTRO';
}
function agruparIncidencias(r) {
  const rechazados = CASOS.filter(c => r.casos[c].estado === 'RECHAZADO');
  const grupos = new Map();
  for (const caso of rechazados) {
    const motivo = r.casos[caso].motivo;
    const clave = claveIncidencia(motivo);
    if (!grupos.has(clave)) grupos.set(clave, []);
    grupos.get(clave).push(caso);
  }
  return [...grupos].map(([clave, casos], i) => ({ id: `INC-M04-G052-${clave}`,
    titulo: { ESTADO_ALTERABLE: 'Estado definitivo alterable por actor humano',
      DETALLE: 'Detalle de rechazo no identifica el umbral', HISTORIAL: 'Historial automático incompleto',
      HTTP_E3: 'Código HTTP distinto de E3', UMBRAL: 'Evaluación simultánea o frontera incorrecta',
      REGISTRO: 'Registro no cumple el contrato' }[clave], casos_afectados: casos,
    esperado: casos.map(c => `${c}: ${IDS[CASOS.indexOf(c)]}`).join('; '),
    obtenido: casos.map(c => `${c}: ${r.casos[c].motivo}`).join('; '),
    severidad: clave === 'ESTADO_ALTERABLE' || clave === 'UMBRAL' ? 'ALTA'
      : clave === 'HTTP_E3' ? 'BAJA' : 'MEDIA',
    justificacion_severidad: clave === 'ESTADO_ALTERABLE' || clave === 'UMBRAL'
      ? 'Afecta la decisión definitiva de validación sin alternativa en este flujo.'
      : clave === 'HTTP_E3' ? 'El registro persiste; discrepa el código HTTP de E3.'
        : 'Impacto parcial en trazabilidad, detalle o registro del caso.',
    certeza: 'CONFIRMADA', equipo_inicial: 'Desarrollo',
    fundamento_derivacion: 'Primera discrepancia comprobada en API pública de RF-69; causa raíz no determinada.',
    evidencia: ['resultado.json', ...(r.evidencias.includes('newman/newman-G052.json') ? ['newman/newman-G052.json'] : [])] }));
}
function informeDetalle133(r) {
  const detalle = r.detalle_133;
  const evaluadas = detalle.evaluadas.map(x =>
    `| ${x.dato} | ${x.caso} | ${x.version} | ${x.umbrales.join(' y ')} | ${x.estado} |`).join('\n')
    || '| Ninguna | — | — | — | — |';
  const excluidas = detalle.excluidas.map(x =>
    `- ${x.dato} (${x.caso}; versión ${x.version ?? 'no creada'}): no evaluable en 133 por ${x.incidencia} de ${x.caso}; ${celda(x.motivo)}.`).join('\n')
    || '- Ninguna.';
  const pendientes = detalle.sin_evidencia.map(x =>
    `- ${x.dato} (${x.caso}): ${celda(x.motivo)}.`).join('\n') || '- Ninguna.';
  return `## TC-M04-133: detalle de versiones rechazadas\n\n| Dato | Caso de origen | Versión | Umbral exigido | Resultado |\n|---|---|---|---|---|\n${evaluadas}\n\nExcluidas del dominio de 133:\n\n${excluidas}\n\nSin evidencia suficiente:\n\n${pendientes}`;
}
function detallePorCaso(r) {
  const s = r.solicitudes;
  const id = x => x?.get?.id ?? x?.post?.id ?? 'sin id verificable';
  const valores = x => 'f1 ' + (x?.f1 ?? 'sin dato') + ' y recall ' + (x?.recall ?? 'sin dato');
  const observado = x => 'versión ' + id(x) + ': POST ' + (x?.post?.http ? 'HTTP ' + x.post.http : 'sin respuesta')
    + ', GET ' + (x?.get?.http ? 'HTTP ' + x.get.http : 'sin respuesta')
    + ', estado ' + (x?.get?.estado ?? x?.post?.estado ?? 'sin verificar')
    + ', detalle ' + (x?.get?.detalle === null ? 'nulo' : x?.get?.detalle ?? 'sin verificar');
  const cinco = [s[1], s[2], s[4], s[5], s[6]];
  const intentos = r.intentos_estado ?? [];
  const respuestas = [...new Set(intentos.map(x => x.metodo
    + (x.ruta.endsWith('/notas') ? ' de notas' : ' directo')
    + ' HTTP ' + (x.respuesta?.http ?? 'sin respuesta')))].join(', ');
  const sinCambios = intentos.filter(x => x.get?.http === 200
    && x.get.cuerpo?.estado_version === x.inicial).length;
  const cambiados = intentos.filter(x => x.get?.http === 200
    && x.get.cuerpo?.estado_version !== x.inicial)
    .map(x => x.rol + ', versión ' + (x.ruta.match(/\/modelos\/(\d+)/)?.[1] ?? 'sin id')
      + ': GET HTTP 200, estado ' + x.get.cuerpo?.estado_version).join('; ');
  const eventos129 = r.auditoria?.eventos?.filter(x =>
    ['VERSION_REGISTRADA', 'VERSION_APROBADA'].includes(x.tipo_evento)
    && String(x.id_referencia) === String(id(s[0])) && x.tipo_actor === 'SISTEMA').length ?? 0;
  const textos = [
    {
      hizo: s[0] ? 'Se intentó registrar por POST una versión con ' + valores(s[0])
        + '; ' + (s[0].get?.http ? 'se consultó la versión ' + id(s[0]) : 'no hubo GET verificable')
        + ' y se solicitó su auditoría.' : 'No se llegó al registro ni a la consulta de la versión por el impedimento técnico.',
      esperaba: 'RF-69, Fase 3 y CA-4 (líneas 2030-2043 y 2291-2295), exige aprobación automática al cumplir ambos umbrales; Fase 6 (líneas 2089-2099) exige historial automático.',
      observo: observado(s[0]) + '; auditoría ' + (r.auditoria?.http ? 'HTTP ' + r.auditoria.http : 'sin respuesta')
        + ', ' + eventos129 + ' eventos de registro o aprobación atribuidos a SISTEMA.',
      aprobo: 'Ambas métricas superaron los umbrales, el GET confirmó APROBADO y la auditoría registró ambos eventos automáticos.'
    },
    {
      hizo: s[1] ? 'Se intentó registrar por POST una versión con ' + valores(s[1])
        + '; ' + (s[1].get?.http ? 'se consultó la versión ' + id(s[1]) + ' por GET.' : 'no hubo GET verificable.')
        : 'No se llegó al registro ni a la consulta de la versión por el impedimento técnico.',
      esperaba: 'RF-69, E3 (líneas 2169-2175), exige HTTP 200, RECHAZADO, mensaje de umbrales no alcanzados y aviso al Veterinario si f1 es inferior a 0.80; Salida 2 (líneas 2225-2229) exige identificar el umbral.',
      observo: observado(s[1]) + '; duración POST ' + (s[1]?.post?.duracion_ms ?? 'sin medida') + ' ms. No hay traza pública de entrega del aviso.',
      aprobo: 'La comprobación API acreditó HTTP 200, RECHAZADO y el f1 insuficiente. La entrega del aviso no quedó comprobada por esta API; la duración del POST no aísla la validación.'
    },
    {
      hizo: s[2] ? 'Se intentó registrar por POST una versión con ' + valores(s[2])
        + '; ' + (s[2].get?.http ? 'se consultó la versión ' + id(s[2]) + ' por GET.' : 'no hubo GET verificable.')
        : 'No se llegó al registro ni a la consulta de la versión por el impedimento técnico.',
      esperaba: 'RF-69, Fase 3 y CA-4 (líneas 2030-2043 y 2291-2295), exige ambos umbrales a la vez; E3 (líneas 2169-2175) exige rechazar si falla uno.',
      observo: observado(s[2]) + '; duración POST ' + (s[2]?.post?.duracion_ms ?? 'sin medida') + ' ms.',
      aprobo: 'El recall inferior a 0.85 provocó RECHAZADO aunque f1 cumplió 0.80; el GET confirmó el estado y el detalle.'
    },
    {
      hizo: s.length >= 7 ? 'Se intentaron registrar cuatro versiones de frontera: '
        + s.slice(3, 7).map(x => 'versión ' + id(x) + ' con ' + valores(x)
          + (x.get?.http ? ', consultada por GET' : ', sin GET verificable')).join('; ') + '.'
        : 'No se completaron los registros de frontera por el impedimento técnico.',
      esperaba: 'RF-69, Restricción 4 y CA-4 (líneas 1878-1882 y 2291-2295), fija umbrales inclusivos: solo 0.80/0.85 aprueba; las otras tres combinaciones se rechazan.',
      observo: s.slice(3, 7).map(observado).join('; ') + '.',
      aprobo: 'La igualdad exacta aprobó la primera versión y cada valor inferior rechazó la correspondiente; los GET confirmaron los cuatro estados.'
    },
    {
      hizo: cinco.some(x => x?.get?.http) ? 'Se revisaron por GET las versiones disponibles de 130, 131 y 132: '
        + cinco.filter(x => x?.get?.http).map(id).join(', ') + '.'
        : 'No hubo GET verificables de las versiones rechazadas de 130, 131 y 132.',
      esperaba: 'RF-69, Salida 2 (líneas 2225-2229) y Fase 4 (líneas 2045-2059), exige describir el umbral concreto no alcanzado en cada rechazo.',
      observo: cinco.map(x => 'versión ' + id(x) + ': GET '
        + (x?.get?.http ? 'HTTP ' + x.get.http : 'sin respuesta')
        + ', estado ' + (x?.get?.estado ?? 'sin verificar')
        + ', detalle ' + (x?.get?.detalle ?? 'sin detalle verificable')).join('; ')
        + '; ' + (r.detalle_133?.sin_evidencia?.length ?? 0) + ' sin evidencia.',
      aprobo: 'Los cinco detalles identificaron f1, recall o ambos según el valor inferior observado; no quedaron rechazos sin evidencia.'
    },
    {
      hizo: intentos.length ? 'Se hicieron ' + intentos.length + ' intentos con '
        + [...new Set(intentos.map(x => x.rol))].join(' y ')
        + ' sobre las versiones ' + [...new Set(intentos.map(x => x.ruta.match(/\/modelos\/(\d+)/)?.[1] ?? 'sin id'))].join(' y ')
        + ' mediante PATCH de notas, PUT y PATCH directos; se consultó el estado después de cada intento.'
        : 'No se efectuaron intentos de cambio de estado por el impedimento técnico.',
      esperaba: 'RF-69, CA-4 (líneas 2291-2295) y Fase 3 (líneas 2030-2043), exige que ningún usuario cambie el estado; la matriz exige ambos roles y sentidos.',
      observo: (respuestas || 'Sin intentos verificables') + '; ' + sinCambios + ' de ' + intentos.length
        + ' GET posteriores HTTP 200 conservaron el estado inicial'
        + (cambiados ? '; cambios observados: ' + cambiados : '') + '.',
      aprobo: 'Ninguno de los doce intentos cambió el estado; se cubrieron ambos roles y ambos sentidos.'
    }
  ];
  return '## Detalle por caso\n\n' + CASOS.map((caso, i) => {
    const decision = r.casos[caso].estado;
    const x = textos[i];
    const incidencia = r.incidencias.find(y => y.casos_afectados?.includes(caso));
    const porque = decision === 'APROBADO' ? x.aprobo
      : decision === 'RECHAZADO' ? r.casos[caso].motivo + '; incidencia ' + (incidencia?.id ?? 'sin ID registrado') + '.'
        : r.casos[caso].motivo + '; falta resolver el impedimento y repetir las comprobaciones pendientes.';
    return '### ' + caso + ' — ' + decision + '\n'
      + '**Qué se hizo:** ' + x.hizo + '\n'
      + '**Qué se esperaba:** ' + x.esperaba + '\n'
      + '**Qué se observó:** ' + x.observo + '\n'
      + '**Por qué ' + decision + ':** ' + porque;
  }).join('\n\n');
}
export function informe(r) {
  const estados = CASOS.map(c => r.casos[c].estado);
  const decision = estados.includes('BLOQUEADO') ? 'BLOQUEADO TÉCNICO'
    : estados.includes('NO_CONCLUYENTE') ? 'NO_CONCLUYENTE TÉCNICO'
      : estados.includes('RECHAZADO') ? 'RECHAZADO' : 'APROBADO';
  const motivo = r.incidencias.length ? r.incidencias.map(x => x.titulo).join('; ')
    : estados.every(x => x === 'APROBADO')
      ? 'La evaluación automática aplica f1 ≥ 0.80 y recall ≥ 0.85 de forma simultánea e inclusiva, informa el umbral incumplido y ningún usuario puede alterar el estado.'
      : 'Faltan comprobaciones concluyentes.';
  const tabla = CASOS.map((c, i) => `| ${c} | ${IDS[i]} | ${r.casos[c].estado} | ${celda(r.casos[c].motivo)} |`).join('\n');
  const esperado = [
    'APROBADO automático, detalle nulo e historial VERSION_REGISTRADA + VERSION_APROBADA de sistema',
    'HTTP 200, RECHAZADO, umbral f1 identificado; aviso al veterinario',
    'RECHAZADO por recall aunque f1 cumpla',
    'Solo (0.80, 0.85) APROBADO; otras tres RECHAZADO',
    'Cada rechazo identifica f1, recall o ambos umbrales incumplidos',
    'Ningún Administrador ni Veterinario puede alterar el estado en ambos sentidos' ];
  const filas = r.solicitudes.map((s, i) => `| ${s.dato} | ${s.f1} | ${s.recall} | ${[0, 3].includes(i) ? '201 / APROBADO' : '200 / RECHAZADO'} | ${s.post?.http ?? 'sin respuesta'} | ${s.post?.id ?? 'sin id'} | ${celda(s.post?.estado)} | ${s.get?.http ?? 'sin respuesta'} / ${celda(s.get?.estado)} | ${celda(s.get?.detalle)} | ${s.post?.duracion_ms ?? 'sin medida'} |`).join('\n');
  const intentos = r.intentos_estado.map(t => `| ${t.rol} | ${t.ruta.match(/\/modelos\/(\d+)/)?.[1] ?? 'sin id'} (${t.inicial}) | ${t.metodo} ${t.ruta} | ${t.respuesta?.http ?? 'sin respuesta'} | ${t.inicial} → ${celda(t.get?.cuerpo?.estado_version)} (GET ${t.get?.http ?? 'sin respuesta'}) |`).join('\n');
  const incidencias = r.incidencias.length ? r.incidencias.map(x =>
    `### ${x.id}: ${x.titulo}\n\nCasos: ${x.casos_afectados.join(', ')}. Esperado: ${x.esperado}. Observado: ${x.obtenido}. Severidad ${x.severidad}: ${x.justificacion_severidad} Certeza ${x.certeza}. Equipo inicial ${x.equipo_inicial}; ${x.fundamento_derivacion} Causa raíz no determinada. Evidencia: ${x.evidencia.join(', ')}.`).join('\n\n')
    : 'Sin incidencias de producto confirmadas.';
  const falta = estados.every(x => x === 'APROBADO') ? 'nada para este grupo; se deja una observación de rendimiento.'
    : r.incidencias.length ? `Atender ${r.incidencias.map(x => x.id).join(', ')} y reevaluar los casos afectados con autorización explícita.`
      : 'Resolver el impedimento técnico y reintentar V1 con nueva autorización.';
  const oficial = r.oficial && r.ambiente === 'TEST'
    ? `sí (registro QA OFICIAL, intento ${r.intento}; DELETE ${r.cierre.run.cierre_http}, rollback confirmado por sandbox)`
    : r.oficial ? 'solo clasificación local; no es evidencia de TEST' : 'no; faltan comprobaciones o cierre';
  const resumen129 = r.auditoria?.eventos?.filter(x => ['VERSION_REGISTRADA', 'VERSION_APROBADA'].includes(x.tipo_evento))
    .map(x => `${x.tipo_evento} (${x.tipo_actor}, versión ${x.id_referencia})`).join('; ') || 'sin eventos automáticos verificables';
  const observaciones = r.observaciones.map(x => `- ${celda(x)}`).join('\n') || '- Ninguna.';
  return `# TC-M04-G052 — ${decision}\n\n## Decisión del caso\n\nCaso agrupado TC-M04-G052 (RF-69), originales ${CASOS.join(', ')}. **Decisión: ${decision}.** ${motivo}\n\n| Caso | Comprobación | Decisión | Motivo breve |\n|---|---|---|---|\n${tabla}\n\nRUN oficial: ${oficial}. Qué falta: ${falta}\n\n## Identificación\n\nGrupo G052; RF-69 v2.1; V${r.version}; RUN ${r.run_id}; ambiente ${r.ambiente}; autorización ${celda(r.autorizacion)}; código local consultado origin/test daefc3a5 (despliegue no verificado); Newman ${r.preflight_herramientas.newman?.version ?? 'no verificado'}; Cypress no aplica: ${r.cypress?.total_pruebas ?? 0} ejecuciones.\n\n## Esperado vs observado por solicitud\n\n${CASOS.map((c, i) => `- ${c}: esperado ${esperado[i]}. Observado: ${celda(r.casos[c].motivo)}.`).join('\n')}\n\n| Dato | f1 | recall | Esperado HTTP / estado | POST HTTP | ID | Estado POST | GET HTTP / estado | Detalle observado | Duración POST (ms) |\n|---|---:|---:|---|---:|---:|---|---|---|---:|\n${filas || '| Sin solicitudes | — | — | — | — | — | — | — | — | — |'}\n\nListado de conciliación: HTTP ${r.listado?.http ?? 'sin respuesta'}, eco RUN ${r.listado?.eco ?? 'no verificable'}, ${r.listado?.coincidencias ?? 0} coincidencias recuperadas. Auditoría RF-73: HTTP ${r.auditoria?.http ?? 'sin respuesta'}; ${resumen129}.\n\n${informeDetalle133(r)}\n\n## TC-M04-134: intentos de alterar el estado\n\n| Rol | Versión y estado inicial | Operación | HTTP | Estado antes → después |\n|---|---|---|---:|---|\n${intentos || '| Sin intentos verificables | — | — | — | — |'}\n\n## Observaciones\n\n${observaciones}\n\nLos POST rechazados pueden incluir el aviso síncrono por destinatario tras el commit; la lectura local de src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py:183-191, src/prediction/infrastructure/adapters/aviso_version_modelo_email_adapter.py:74-81,101-104 y src/shared/email.py:37,70 muestra timeout SMTP de 8 s. Es hipótesis de latencia, no causa raíz acreditada en TEST. Los POST aprobados observados son inferiores a 0.5 s; RNF-01 exige la validación de métricas en ≤ 5 s y la medida del POST rechazado incluye más pasos, por lo que no acredita un incumplimiento. La entrega del correo no es verificable por API. El sandbox no revierte los ONNX cargados (hasta siete) ni avisos ya emitidos.\n\n## Historial de intentos\n\n${r.intento > 1 ? `Este es el intento ${r.intento} de V${r.version}; consultar el RUN técnico previo para sus resultados.` : 'Primer intento de esta versión.'}\n\n## Incidencias de producto\n\n${incidencias}\n\n## Problemas técnicos y análisis\n\n${r.problemas_tecnicos.length ? r.problemas_tecnicos.map(x => `- ${celda(x)}`).join('\n') : 'Sin problemas técnicos en este RUN.'} No se atribuye causa raíz de producto por lectura de código local.\n\n## Revisión QA\n\n${r.revision_qa ? `${celda(r.revision_qa.fecha)}; ${celda(r.revision_qa.realizada_por)}; ${celda(r.revision_qa.motivo)}.` : 'Pendiente de revisión editorial QA.'}\n\n## Cierre y rollback\n\nDELETE RUN HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. ${r.cierre.rollback.verificado ? 'Sandbox confirmó cierre y rollback; no hubo consulta posterior de BD.' : 'Rollback no confirmado.'} La entrega de avisos y la eliminación de ONNX no se verificaron mediante la API.\n\n## Evidencias\n\n${r.evidencias.map(x => `- ${x}`).join('\n') || 'Sin evidencias registradas.'}\n\n## Conclusión y acción\n\n${decision}. ${falta[0].toUpperCase()}${falta.slice(1)}\n`;
}
function finalizar(c, r, secretos) {
  const nombre = nombreInforme(c.version);
  r.evidencias = [...new Set([...r.evidencias, nombre, 'resultado.json'])];
  r.incidencias = agruparIncidencias(r);
  r.oficial = CASOS.every(x => ['APROBADO', 'RECHAZADO'].includes(r.casos[x].estado))
    && r.cierre.run.cierre_http === 200 && r.cierre.rollback.verificado
    && r.evidencias.includes('newman/newman-G052.json') && r.problemas_tecnicos.length === 0
    && r.evidencias.filter(x => ![nombre, 'resultado.json'].includes(x))
      .every(x => fs.existsSync(path.join(c.directorio, x)));
  r.consume_version = r.oficial;
  const textoInforme = informe(r).replace('## Identificación',
    detallePorCaso(r) + '\n\n## Identificación');
  fs.writeFileSync(path.join(c.directorio, nombre), sanearArtefacto(textoInforme, secretos), 'utf8');
  guardar(path.join(c.directorio, 'resultado.json'), JSON.parse(sanearArtefacto(JSON.stringify(r), secretos)));
}
export async function evaluar(c, { env, ensayo = false }) {
  if (!fs.existsSync(c.directorio)) throw Error('RUN_NO_CREADO_POR_LANZADOR');
  const inicio = Date.now(); limiteGlobal = inicio + (PRESUPUESTO.duracion_segundos - 30) * 1000;
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = resultadoInicial(c);
  const secretos = [env.QA_SANDBOX_SECRET, env.RF71_INTERNAL_KEY, env.QA_ADMIN_EMAIL,
    env.QA_ADMIN_PASSWORD, env.QA_VETERINARIO_EMAIL, env.QA_COMMON_PASSWORD].filter(Boolean);
  let temporal = null, tocado = false;
  try {
    const pre = preflight(c, env, ensayo); guardar(path.join(c.directorio, 'preflight.json'), pre);
    r.evidencias.push('preflight.json');
    if (!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
    r.preflight_herramientas.newman = versionNewman(ensayo);
    if (!r.preflight_herramientas.newman.ok) throw Error('NEWMAN_NO_DISPONIBLE');
    const admin = await pedir(api, 'POST', '/sesiones/', { cuerpo: {
      correo_electronico: env.QA_ADMIN_EMAIL, contrasena: env.QA_ADMIN_PASSWORD }, bitacora: r.bitacora });
    if (admin.http !== 200 || !admin.cuerpo?.token) throw Error(`LOGIN_ADMIN_HTTP_${admin.http}`);
    const tokenAdmin = admin.cuerpo.token; secretos.push(tokenAdmin);
    let tokenVet = null;
    if (pre.veterinario_configurado) {
      const vet = await pedir(api, 'POST', '/sesiones/', { cuerpo: {
        correo_electronico: env.QA_VETERINARIO_EMAIL, contrasena: env.QA_COMMON_PASSWORD }, bitacora: r.bitacora });
      if (vet.http === 200 && vet.cuerpo?.token) { tokenVet = vet.cuerpo.token; secretos.push(tokenVet); }
      else r.observaciones.push(`Login Veterinario no verificable: HTTP ${vet.http}; 134 se limita a Administrador.`);
    } else r.observaciones.push('Sin nombres de credenciales Veterinario completos; 134 se limita a Administrador.');
    tocado = true;
    const catalogo = await pedir(api, 'GET', '/configuracion/variables-ambientales',
      { token: tokenAdmin, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, bitacora: r.bitacora });
    if (catalogo.http !== 200 || !catalogo.eco || !Array.isArray(catalogo.cuerpo?.items))
      throw Error(`CATALOGO_I3P1_NO_VERIFICABLE_HTTP_${catalogo.http}`);
    const ids = catalogo.cuerpo.items.map(x => x.id_variable_ambiental).filter(Number.isSafeInteger);
    if (!ids.length) throw Error('CATALOGO_I3P1_SIN_VARIABLE_ACTIVA');
    temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g052-newman-'));
    const archivo = path.join(temporal, 'g052.onnx'); fs.writeFileSync(archivo, onnxMinimo());
    const casos = escenarios({ variable: ids[0], hash: sha256(fs.readFileSync(archivo)),
      dataset: sha256(Buffer.from('G052 dataset QA RF-71')), archivo });
    const n = await ejecutarNewman(c, api, env, casos, secretos, temporal);
    r.evidencias.push(...n.artefactos);
    if (!n.artefactos.length || n.salida.error || n.fallos.some(f =>
      /SyntaxError|ReferenceError|TypeError/.test(f.name))) throw Error(`NEWMAN_TECNICO:${n.salida.error ?? n.fallos.map(x => x.name).join(',')}`);
    const posts = casos.map((_, i) => n.respuestas.find(x => x.iteracion === i)
      ?? { iteracion: i, http: null, eco: null, cuerpo: null, duracion_ms: n.duraciones?.get(i) ?? null });
    r.solicitudes = resumirSolicitudes(casos, posts);
    for (let i = 0; i < posts.length; i++) if (posts[i].duracion_ms > 5000)
      r.observaciones.push(`${casos[i].dato}: POST ${posts[i].duracion_ms} ms; RF-69 RNF-01 (líneas 2350-2352) exige validación de métricas ≤ 5 s por versión. La medida incluye correo y no aísla Fases 2-3; solo observación de rendimiento.`);
    let consecutivos = 0, sistemico = false;
    for (const p of posts) { consecutivos = p?.http >= 500 ? consecutivos + 1 : 0; if (consecutivos >= 3) sistemico = true; }
    if (posts.some(x => x?.http === 403)) throw Error('POST_403_CLAVE_SIN_REINTENTO');
    if (sistemico) throw Error('POST_5XX_SISTEMICO_SIN_REINTENTO');
    let listado = null;
    try { listado = await pedir(api, 'GET',
      '/prediccion/modelos?tipo_modelo=MODELO_ESPECIES_GRANDES&limit=100&offset=0',
      { token: tokenAdmin, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, bitacora: r.bitacora }); }
    catch { r.problemas_tecnicos.push('LISTADO_SIN_RESPUESTA'); }
    const items = listado?.http === 200 && listado.eco && Array.isArray(listado.cuerpo?.items)
      ? listado.cuerpo.items : [];
    let coincidencias = 0;
    for (let i = 0; i < casos.length; i++) {
      if (posts[i].http) continue;
      const encontrados = items.filter(x => String(x.id_proceso_rf71) === casos[i].id_proceso_rf71);
      if (encontrados.length === 1 && idVersion(encontrados[0]) != null) {
        posts[i] = { ...posts[i], recuperado: true, cuerpo: encontrados[0] };
        coincidencias++;
        r.observaciones.push(`${casos[i].dato}: POST sin respuesta; versión localizada por id_proceso_rf71; código HTTP E3 no verificable para esa solicitud.`);
      } else r.observaciones.push(`${casos[i].dato}: POST sin respuesta; versión no localizada de forma única en listado; sin reintento.`);
    }
    r.listado = { http: listado?.http ?? null, eco: listado?.eco ?? null, coincidencias,
      total_items: items.length };
    const gets = [];
    for (let i = 0; i < casos.length; i++) {
      let g = null;
      if (([200, 201].includes(posts[i]?.http) || posts[i]?.recuperado) && idVersion(posts[i]?.cuerpo) != null) {
        try { g = await pedir(api, 'GET', `/prediccion/modelos/${encodeURIComponent(idVersion(posts[i].cuerpo))}`,
          { token: tokenAdmin, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, bitacora: r.bitacora }); }
        catch { r.problemas_tecnicos.push(`GET_SIN_RESPUESTA_${casos[i].dato}`); }
      }
      gets.push(g);
    }
    let auditoria = null;
    if (idVersion(posts[0]?.cuerpo) != null) try {
      auditoria = await pedir(api, 'GET', `/prediccion/auditoria?id_referencia=${encodeURIComponent(idVersion(posts[0].cuerpo))}&por_pagina=50`,
        { token: tokenAdmin, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, bitacora: r.bitacora });
    } catch { r.problemas_tecnicos.push('AUDITORIA_SIN_RESPUESTA'); }
    r.auditoria = auditoria ? { http: auditoria.http, eco: auditoria.eco,
      eventos: (auditoria.cuerpo?.items ?? []).map(x => ({ tipo_evento: x.tipo_evento,
        tipo_actor: x.tipo_actor, id_usuario: x.id_usuario, id_sistema: x.id_sistema,
        id_referencia: x.id_referencia })) } : null;
    for (const [rol, token] of [['Administrador', tokenAdmin], ['Veterinario', tokenVet]]) {
      if (!token) continue;
       const aprobado = [0, 3].find(i => idVersion(posts[i]?.cuerpo) != null
        && gets[i]?.cuerpo?.estado_version === 'APROBADO');
      const rechazado = [1, 2, 4, 5, 6].find(i => idVersion(posts[i]?.cuerpo) != null
        && gets[i]?.cuerpo?.estado_version === 'RECHAZADO');
      for (const i of [aprobado, rechazado]) {
        if (i === undefined) continue;
        const id = idVersion(posts[i]?.cuerpo), inicial = gets[i]?.cuerpo?.estado_version;
        if (id == null || !['APROBADO', 'RECHAZADO'].includes(inicial)) continue;
        const opuesto = inicial === 'APROBADO' ? 'RECHAZADO' : 'APROBADO';
        const rutaBase = `/prediccion/modelos/${encodeURIComponent(id)}`;
        for (const [metodo, ruta] of [['PATCH', `${rutaBase}/notas`], ['PUT', rutaBase], ['PATCH', rutaBase]]) {
          let respuesta = null, get = null;
          try { respuesta = await pedir(api, metodo, ruta, { token, secreto: env.QA_SANDBOX_SECRET,
            runId: c.runId, cuerpo: { estado_version: opuesto }, bitacora: r.bitacora }); }
          catch { r.problemas_tecnicos.push(`INTENTO_SIN_RESPUESTA_${rol}_${metodo}`); }
          try { get = await pedir(api, 'GET', rutaBase, { token, secreto: env.QA_SANDBOX_SECRET,
            runId: c.runId, bitacora: r.bitacora }); }
          catch { r.problemas_tecnicos.push(`VERIFICACION_SIN_RESPUESTA_${rol}_${metodo}`); }
          r.intentos_estado.push({ rol, metodo, ruta, inicial, opuesto,
            respuesta: respuesta && { http: respuesta.http, eco: respuesta.eco,
              estado: respuesta.cuerpo?.estado_version, error: respuesta.error },
            get: get && { http: get.http, eco: get.eco, cuerpo: { estado_version: get.cuerpo?.estado_version } } });
          if (metodo === 'PATCH' && ruta.endsWith('/notas') && respuesta?.http < 300)
            r.observaciones.push(`PATCH notas aceptó campo extra para ${rol}; posible nota guardada, sujeta a rollback.`);
        }
      }
    }
    r.solicitudes = resumirSolicitudes(casos, posts, gets);
    clasificar(r, casos, posts, gets, auditoria, !!tokenVet);
    r.incidencias = agruparIncidencias(r);
    return r;
  } catch (e) {
    const motivo = limpio(e.message); r.problemas_tecnicos.push(motivo);
    const tipo = /5XX|_5\d\d|403|CATALOGO|LOGIN/.test(motivo) ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
    CASOS.forEach((caso, i) => { if (r.casos[caso].motivo === 'Sin comprobación') asignar(r, i, tipo, motivo); });
    return r;
  } finally {
    limiteGlobal = inicio + PRESUPUESTO.duracion_segundos * 1000;
    if (tocado) try {
      const x = await pedir(api, 'DELETE', `/test-control/runs/${encodeURIComponent(c.runId)}`,
        { secreto: env.QA_SANDBOX_SECRET, bitacora: r.bitacora });
      r.cierre.run.cierre_http = x.http;
      r.cierre.rollback.verificado = x.http === 200 && /rollback|cerrad/i.test(JSON.stringify(x.cuerpo ?? {}));
      r.cierre.rollback.motivo = r.cierre.rollback.verificado
        ? 'Sandbox confirmó cierre, sin consulta posterior de BD' : `DELETE HTTP ${x.http}; rollback no acreditado`;
    } catch { r.problemas_tecnicos.push('CIERRE_SIN_RESPUESTA'); }
    if (temporal) {
      if (!path.resolve(temporal).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
      fs.rmSync(temporal, { recursive: true, force: true });
    }
    finalizar(c, r, secretos);
    limiteGlobal = Infinity;
  }
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
  else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
  else try {
    const c = contextoEjecucion(process.argv.slice(2), { grupo: 'G052', casos: CASOS, directorio: DIR });
    const r = await evaluar(c, { env: leerEnv() });
    console.log(JSON.stringify({ run_id: r.run_id, casos: r.casos, oficial: r.oficial }));
    if (!r.oficial) process.exitCode = 2;
  } catch (e) { console.error(`G052: ${limpio(e.message)}`); process.exitCode = 2; }
}
