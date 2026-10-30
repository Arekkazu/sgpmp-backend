#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { spawnSync, spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';
import { sanearArtefacto, contieneMojibake } from './lib/seguridad.mjs';
import { CASOS, IDS, CAPACIDADES, PRESUPUESTO, onnxMinimo, sha256, uuid, METRICAS,
  esUuid, idVersion, estado, metadatosIguales, evaluarAuditoria } from './lib/g049_escenario.mjs';

const require = createRequire(import.meta.url);
const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION = path.join(DIR, 'G049.postman_collection.json');
const ARCHIVOS = ['.gitkeep', 'g049.mjs', 'G049.postman_collection.json', 'README.md',
  'lib/contrato_ejecutor.mjs', 'lib/seguridad.mjs', 'lib/g049_escenario.mjs',
  'pruebas/registro_qa.mjs', 'pruebas/g049_ensayo.mjs', 'pruebas/g049.test.mjs'];
const limpio = x => String(x ?? '').replaceAll('|', '/').replace(/[\r\n]+/g, ' ').slice(0, 300);
const guardar = (p, x) => fs.writeFileSync(p, JSON.stringify(x, null, 2), 'utf8');

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
function newmanPaquete() {
  try { return path.dirname(require.resolve('newman/package.json', { paths: [RAIZ] })); }
  catch {
    const p = String(process.env.PATH ?? '').split(path.delimiter)
      .map(x => path.join(x, 'node_modules', 'newman', 'package.json')).find(fs.existsSync);
    if (!p) throw Error('NEWMAN_NO_RESUELTO');
    return path.dirname(p);
  }
}
function newmanBin() { const p = newmanPaquete(); return path.join(p, require(path.join(p, 'package.json')).bin.newman); }
function versionNewman(ensayo = false) {
  try {
    const p = newmanPaquete();
    if (ensayo) return { ok: true, version: require(path.join(p, 'package.json')).version, modo: 'paquete local' };
    const x = spawnSync(process.execPath, [newmanBin(), '--version'], { timeout: 30000, encoding: 'utf8' });
    return { ok: x.status === 0 && !!x.stdout.trim(), version: x.stdout.trim(), error: x.error?.code ?? null };
  } catch (e) { return { ok: false, version: null, error: e.code ?? e.message }; }
}
export function preflight(c, env, ensayo = false) {
  const base = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const claves = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_ADMIN_EMAIL',
    'QA_ADMIN_PASSWORD', 'RF71_INTERNAL_KEY'];
  const barreras = claves.filter(k => !String(env[k] ?? '').trim());
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base) : base !== API) barreras.push('API_NO_CANONICA');
  if (c.version > 1 && c.operacion !== 'reevaluar') barreras.push('REEVALUACION_SIN_DECISION');
  return { fase: 'PREFLIGHT_LOCAL', grupo: 'G049', run_id: c.runId, version: c.version,
    ok: barreras.length === 0, barreras, presupuesto: PRESUPUESTO,
    efectos_declarados: ['3_versiones_BD_sujetas_a_rollback_externo',
      '3_archivos_ONNX_en_MODELOS_STORAGE_PATH_no_revertidos',
      'eventos_RF73_en_sesion_sandbox_sujetos_a_rollback_salvo_respaldo_local',
      'login_fuera_RUN_puede_persistir_sesion_o_auditoria', 'ningun_correo_esperado'] };
}
export function comprobar() {
  let coleccion = false;
  try {
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const i of col.item) for (const e of i.event ?? []) new vm.Script((e.script?.exec ?? []).join('\n'));
    coleccion = col.item.length === 7
      && col.item.map(i => i.request.method).join(',') === 'POST,GET,GET,POST,GET,POST,GET'
      && col.item.map(i => i.name).join(',') === 'API-G049-POST-V1,API-G049-GET-V1,API-G049-AUDITORIA-V1,API-G049-POST-V2,API-G049-GET-V2,API-G049-POST-V3,API-G049-GET-V3'
      && !contieneMojibake(JSON.stringify(col));
  } catch { /* se informa coleccion=false */ }
  const presentes = fs.readdirSync(DIR).filter(x => !['lib', 'pruebas', 'Resultados', 'EvaluacionV2'].includes(x))
    .concat(...['lib', 'pruebas'].map(d => fs.readdirSync(path.join(DIR, d)).map(x => `${d}/${x}`)));
  const faltantes = ARCHIVOS.filter(x => !fs.existsSync(path.join(DIR, x)));
  const inesperados = presentes.filter(x => !ARCHIVOS.includes(x));
  const markdownSuperior = fs.existsSync(path.join(DIR, 'Resultados'))
    && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const ok = coleccion && !faltantes.length && !inesperados.length && !markdownSuperior;
  console.log(JSON.stringify({ grupo: 'G049', ok, coleccion, faltantes, inesperados,
    markdownSuperior, presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}
function cuerpoPublico(x) {
  const d = x?.detail && typeof x.detail === 'object' ? x.detail : x;
  return { codigo: limpio(d?.error_code ?? d?.code ?? d?.codigo),
    mensaje: limpio(d?.message ?? d?.mensaje ?? (typeof x?.detail === 'string' ? x.detail : '')) };
}
async function pedir(api, metodo, ruta, { token, secreto, runId, cuerpo, bitacora, timeout = PRESUPUESTO.timeout_ms } = {}) {
  let http = null, eco = null;
  try {
    const x = await fetch(api + ruta, { method: metodo, redirect: 'manual',
      headers: { ...(cuerpo ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(secreto ? { 'X-Sandbox-Secret': secreto } : {}),
        ...(runId ? { 'X-Test-Run-Id': runId, 'X-Zona-Horaria': 'UTC' } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined, signal: AbortSignal.timeout(timeout) });
    http = x.status; eco = runId ? x.headers.get('x-test-run-id') === runId : null;
    const data = await x.json().catch(() => null);
    return { http, eco, cuerpo: data, error: http >= 400 ? cuerpoPublico(data) : null };
  } finally { bitacora.push({ metodo, ruta, http, eco, en_run: !!runId }); }
}
function extracto(ex, runId) {
  const hs = ex?.response?.header ?? [];
  const cab = n => hs.find(h => String(h.key).toLowerCase() === n)?.value ?? null;
  const stream = ex?.response?.stream;
  const bytes = Buffer.from(stream?.data ?? (Array.isArray(stream) ? stream : []));
  let cuerpo = null; try { cuerpo = JSON.parse(bytes.toString('utf8')); } catch { /* vacío */ }
  const http = ex?.response?.code ?? null;
  return { http, eco: cab('x-test-run-id') === runId, cuerpo,
    error: http >= 400 ? cuerpoPublico(cuerpo) : null };
}
async function ejecutarNewman(c, api, env, datos, onnxPath, secretos, r, temporal) {
  const raw = path.join(temporal, 'raw.json'), environment = path.join(temporal, 'environment.json');
  const vars = { autorizado_run: 'SI', ensayo_loopback: c.ensayo ? 'SI' : 'NO',
    base_url: api, run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET,
    rf71_internal_key: env.RF71_INTERNAL_KEY, token_admin: datos.token_admin,
    tipo_modelo: datos.tipo_modelo,
    hash_artefacto_sha256: datos.hash_artefacto_sha256,
    dataset_entrenamiento_hash: datos.dataset_entrenamiento_hash,
    metricas_validacion: JSON.stringify(datos.metricas_validacion),
    fecha_entrenamiento: datos.fecha_entrenamiento,
    compatibilidad_variables: JSON.stringify(datos.compatibilidad_variables),
    onnx_path: onnxPath, proceso_1: datos.procesos[0], proceso_2: datos.procesos[1],
    proceso_3: datos.procesos[2] };
  guardar(environment, { values: Object.entries(vars).map(([key, value]) => ({ key, value, enabled: true })) });
  const args = [newmanBin(), 'run', COLECCION, '--environment', environment, '--reporters', 'json',
    '--reporter-json-export', raw, '--working-dir', temporal, '--timeout-request', String(PRESUPUESTO.timeout_ms),
    '--timeout', String((PRESUPUESTO.duracion_segundos - 300) * 1000), '--color', 'off'];
  let salida = await new Promise(resolve => {
    let p;
    try { p = spawn(process.execPath, args, { stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true }); }
    catch (e) { resolve({ code: null, error: e.code ?? 'NEWMAN_SPAWN' }); return; }
    p.stdout.on('data', () => {});
    p.stderr.on('data', () => {});
    p.on('error', e => resolve({ code: null, error: e.code ?? 'NEWMAN_SPAWN' }));
    p.on('close', code => resolve({ code, error: null }));
  });
  // El sandbox local puede prohibir spawn; solo el ensayo usa la API del mismo paquete.
  if (c.ensayo && salida.error === 'EPERM') {
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    const e = JSON.parse(fs.readFileSync(environment, 'utf8'));
    salida = await new Promise(resolve => require(newmanPaquete()).run({ collection: col,
      environment: e, reporters: ['json'], reporter: { json: { export: raw } },
      timeoutRequest: PRESUPUESTO.timeout_ms, timeout: (PRESUPUESTO.duracion_segundos - 300) * 1000,
      color: 'off' }, (error, summary) => resolve({ code: error ? 1 : 0,
        error: error?.message ?? null, fallos: summary?.run?.failures?.length ?? 0,
        modo: 'API_LOCAL_POR_SPAWN_EPERM' })));
  }
  if (!fs.existsSync(raw)) return { salida, respuestas: [], fallos: [], artefactos: [] };
  const original = JSON.parse(fs.readFileSync(raw, 'utf8'));
  const ejecuciones = (original.run?.executions ?? []).map(ex => ({ nombre: ex.item?.name ?? 'DESCONOCIDO',
    ...extracto(ex, c.runId) }));
  const fallos = (original.run?.failures ?? []).map(f => ({ name: limpio(f.error?.name),
    test: limpio(f.error?.test), source: limpio(f.source?.name), mensaje: limpio(f.error?.message) }));
  const salidaDir = path.join(c.directorio, 'newman'); fs.mkdirSync(salidaDir, { recursive: true });
  const artefactos = ['newman/newman-G049.json', 'newman/newman-G049.html'];
  guardar(path.join(c.directorio, artefactos[0]), JSON.parse(sanearArtefacto(JSON.stringify({
    info: { nombre: 'Newman G049', generado: true, saneado: true },
    run: { stats: original.run?.stats ?? null, executions: ejecuciones, failures: fallos } }), secretos)));
  const filas = ejecuciones.map(x => `<tr><td>${x.nombre}</td><td>${x.http ?? 'sin respuesta'}</td><td>${x.eco}</td></tr>`).join('');
  fs.writeFileSync(path.join(c.directorio, artefactos[1]),
    `<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G049</title><h1>Newman G049</h1><table><tr><th>Solicitud</th><th>HTTP</th><th>Eco RUN</th></tr>${filas}</table></html>`, 'utf8');
  return { salida, respuestas: ejecuciones, fallos, artefactos };
}

function asignar(r, i, estadoCaso, motivo, evidencia = null, observado = null) {
  const caso = CASOS[i]; r.casos[caso] = { estado: estadoCaso, motivo };
  Object.assign(r.comprobaciones[i], { estado: estadoCaso, motivo, evidencia, observado });
}
function resultadoInicial(c) {
  return { grupo: 'G049', run_id: c.runId, version: c.version, operacion: c.operacion,
    autorizacion: c.referencia, ambiente: c.ensayo ? 'LOOPBACK_LOCAL' : 'TEST', oficial: false,
    consume_version: false, casos: Object.fromEntries(CASOS.map(x => [x,
      { estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación' }])),
    comprobaciones: CASOS.map((caso, i) => ({ caso, fuente: 'API', id: IDS[i], tipo: 'ASSERT',
      estado: 'NO_CONCLUYENTE', motivo: 'Sin respuesta', evidencia: null })),
    cypress: { total_pruebas: 0 }, preflight_herramientas: {}, evidencias: [], bitacora: [],
    datos: null, respuestas: {}, incidencias: [], problemas_tecnicos: [],
    cierre: { run: { cierre_http: null }, rollback: { verificado: false,
      motivo: 'Sin cierre ni comprobación de reversión de BD' } } };
}
function incidencia(caso, id, titulo, requisito, linea, esperado, obtenido, evidencia, severidad) {
  return { id, titulo, equipo: 'Desarrollo', derivacion: 'Primera discrepancia comprobada en API pública; causa raíz no determinada',
    severidad, sustento_severidad: severidad === 'ALTA' ? 'Impide una función central de RF-69 sin alternativa equivalente'
      : 'Afecta trazabilidad de una versión; el registro puede continuar', certeza: 'CONFIRMADA',
    requisito, linea, caso, precondiciones: 'RUN autorizado, clave interna válida, artefacto ONNX y metadatos completos',
    pasos: 'POST interno; GET de versión y auditoría por API pública dentro del RUN', esperado,
    obtenido, evidencia, analisis: 'La observación acredita la discrepancia, no su causa técnica',
    impacto: titulo, cierre: 'Pendiente de corrección y reevaluación autorizada' };
}
export function incidencia115(r) {
  const ids = r.respuestas.posts?.map(x => x?.id) ?? [];
  const id = ids[0];
  const get = r.respuestas.gets?.[0];
  const ref = r.respuestas.gets?.[2]?.cuerpo?.version_referencia;
  return {
    id: 'INC-M04-G049-115', caso: CASOS[1],
    titulo: 'El identificador de versión de modelo es un entero secuencial y no un UUID',
    equipo: 'Desarrollo', derivacion: 'La primera discrepancia comprobada está en la respuesta del API público; se deriva a Desarrollo sin atribuir causa raíz.',
    severidad: 'MEDIA',
    sustento_severidad: 'El registro, la unicidad local y las consultas funcionan; la desviación del contrato afecta trazabilidad e interoperabilidad: identificadores secuenciales predecibles y enumerables, no únicos fuera de la base de datos. No bloquea el flujo.',
    certeza: 'CONFIRMADA',
    requisito: ['RF-69 línea 1794: “identificado de forma única mediante un id_version (UUID)”',
      'Salida 1, línea 2207: “id_version (UUID)”',
      'Entradas, línea 1965: “version_referencia | UUID (opcional)”'],
    precondiciones: 'RUN autorizado, clave interna RF-71 válida, artefacto ONNX válido, metadatos completos y tipo MODELO_ESPECIES_GRANDES.',
    pasos: ['Enviar tres POST /prediccion/modelos multipart con X-RF71-Internal-Key y procesos RF-71 distintos.',
      'Registrar los tres identificadores devueltos y usar el segundo como version_referencia del tercero.',
      'Consultar GET /prediccion/modelos/{id} para la primera y la tercera versión; contrastar id y version_referencia.'],
    esperado: 'Tres UUID distintos para id_version; version_referencia de V3 es el UUID de V2.',
    obtenido: `POST ${r.respuestas.posts?.map(x => `HTTP ${x?.http ?? 'sin respuesta'}: id_version_modelo ${x?.id ?? 'sin id'}`).join('; ') ?? 'sin respuestas'}; GET /prediccion/modelos/${id} HTTP ${get?.http ?? 'sin respuesta'} devuelve id_version_modelo ${get?.cuerpo?.id_version_modelo ?? get?.cuerpo?.id_version ?? 'sin id'}; V3 version_referencia ${ref ?? 'sin referencia'} (${typeof ref}).`,
    evidencia: ['newman/newman-G049.json', 'resultado.json', r.run_id],
    analisis: 'El DTO y el schema tipan el identificador como entero (registrar_version_modelo_dto.py:48; version_modelo_schema.py:14,26). Clave autoincremental probable; causa raíz no confirmada.',
    impacto: 'Los consumidores que esperan UUID en version_referencia, correlación con RF-71/RF-73 y distribución RF-70 pueden recibir enteros; los identificadores expuestos son enumerables.',
    cierre: 'Exponer id_version y version_referencia como UUID en respuesta, ruta GET y entrada; reevaluar TC-M04-115 en V2 autorizada.'
  };
}
function detallePorCaso(r) {
  const dato = x => x === undefined || x === null ? 'sin dato verificable' : limpio(x);
  const posts = r.respuestas.posts ?? [];
  const gets = r.respuestas.gets ?? [];
  const procesos = r.datos?.procesos ?? [];
  const metricas = r.datos?.metricas_validacion ?? {};
  const auditoria = r.respuestas.auditoria;
  const eventos = (auditoria?.items ?? []).filter(x =>
    ['VERSION_REGISTRADA', 'VERSION_APROBADA', 'VERSION_RECHAZADA'].includes(x.tipo_evento));
  const incidencias = Object.fromEntries(r.incidencias.map(x => [x.caso, x.id]));
  const estado = i => r.casos[CASOS[i]]?.estado ?? 'NO_CONCLUYENTE';
  const motivo = i => dato(r.casos[CASOS[i]]?.motivo);
  const porQue = (i, aprobado) => estado(i) === 'APROBADO' ? aprobado
    : estado(i) === 'RECHAZADO'
      ? `Se incumplió el criterio: ${motivo(i)}. Incidencia ${incidencias[CASOS[i]] ?? 'pendiente de identificar'}.`
      : `No se pudo comprobar el criterio: ${motivo(i)}. Hace falta completar las respuestas y lecturas del API en una evaluación autorizada.`;
  const encabezado = (i, lineas) => `### ${CASOS[i]} — ${estado(i)}\n\n${lineas.join('\n')}`;
  const registro = posts[0]
    ? `Se envió un modelo ${dato(r.datos?.tipo_modelo)} por POST /prediccion/modelos como invocación interna de RF-71, con proceso ${dato(procesos[0])}, F1 ${dato(metricas.f1_score_global)} y recall de riesgo alto ${dato(metricas.recall_clase_riesgo_alto)}; se consultó su auditoría.`
    : 'Se intentó registrar una versión mediante la invocación interna de RF-71; no quedó una respuesta de registro verificable.';
  const observacion114 = eventos.length
    ? `POST HTTP ${dato(posts[0]?.http)} registró la versión ${dato(posts[0]?.id)}; auditoría HTTP ${dato(auditoria?.http)} mostró ${eventos.map(x => `${x.tipo_evento} por ${dato(x.tipo_actor)}, fuente ${dato(x.id_sistema)}, estado ${dato(x.estado)}`).join(' y ')}.`
    : `No se obtuvieron eventos automáticos verificables; ${auditoria?.http ? `auditoría HTTP ${auditoria.http}` : 'auditoría sin respuesta registrada'}.`;
  const ids = posts.map(x => x?.id);
  const observacion115 = posts.length
    ? `Los registros devolvieron ${posts.map(x => `HTTP ${dato(x?.http)} e identificador ${dato(x?.id)}`).join('; ')}; la consulta de la primera versión devolvió HTTP ${dato(gets[0]?.http)} e identificador ${dato(gets[0]?.cuerpo?.id_version_modelo)}.`
    : 'No se registraron tres respuestas de creación ni una consulta verificable.';
  const observado116 = r.comprobaciones[2]?.observado;
  const resumen116 = observado116
    ? `GET /prediccion/modelos/${dato(posts[0]?.id)} respondió HTTP ${dato(gets[0]?.http)}: estado ${dato(observado116.estado)}, F1 ${dato(observado116.f1_score_global)}, recall alto ${dato(observado116.recall_clase_riesgo_alto)}, precisión ${dato(observado116.precision_global)}, accuracy ${dato(observado116.accuracy)}, ROC AUC ${dato(observado116.roc_auc_score)}, notas de validación ${observado116.notas_validacion === null ? 'nulas' : dato(observado116.notas_validacion)}; demás campos y valores en la tabla de Salida 1.`
    : `No hubo lectura completa de metadatos verificable; GET HTTP ${dato(gets[0]?.http)}.`;
  const ref = r.comprobaciones[3]?.observado;
  const observacion117 = ref
    ? `V1 ${dato(posts[0]?.id)} se registró sin referencia; V2 ${dato(ref.v2_id)} y V3 ${dato(posts[2]?.id)} devolvieron HTTP ${dato(posts[1]?.http)} y ${dato(posts[2]?.http)}; GET V3 HTTP ${dato(gets[2]?.http)} devolvió referencia ${dato(ref.v3_referencia)}.`
    : `No se acreditó la relación en la consulta de V3; POST V3 HTTP ${dato(posts[2]?.http)}, GET V3 HTTP ${dato(gets[2]?.http)}.`;
  return [
    encabezado(0, [
      `**Qué se hizo:** ${registro}`,
      '**Qué se esperaba:** Registro automático sin intervención humana, primero en EN_VALIDACION y luego con resultado automático; auditoría con VERSION_REGISTRADA y VERSION_APROBADA o VERSION_RECHAZADA, originadas por RF-71 (RF-69, líneas 1790, 2001-2004 y 2089-2095).',
      `**Qué se observó:** ${observacion114}`,
      `**Por qué ${estado(0)}:** ${porQue(0, 'Los dos eventos de sistema están vinculados al proceso RF-71 y acreditan registro y aprobación automáticos; el estado APROBADO del evento de registro es una foto final, no prueba de una transición omitida.')}`
    ]),
    encabezado(1, [
      `**Qué se hizo:** ${posts.length ? `Se enviaron ${posts.length} versiones ${dato(r.datos?.tipo_modelo)} desde procesos RF-71 ${procesos.slice(0, posts.length).map(dato).join(', ')}, se compararon sus identificadores y se consultó la primera por GET.` : 'Se intentó iniciar el registro de tres versiones; no hay respuestas de creación verificables.'}`,
      '**Qué se esperaba:** Tres identificadores UUID distintos para las tres versiones (RF-69, líneas 1794, 2001 y 2207).',
      `**Qué se observó:** ${observacion115}`,
      `**Por qué ${estado(1)}:** ${porQue(1, 'Los tres identificadores observados son UUID distintos y la primera versión se puede consultar con el identificador recibido.')}`
    ]),
    encabezado(2, [
      `**Qué se hizo:** ${posts[0] ? `Se envió el modelo ${dato(r.datos?.tipo_modelo)} con proceso ${dato(procesos[0])}, F1 ${dato(metricas.f1_score_global)}, recall alto ${dato(metricas.recall_clase_riesgo_alto)}, precisión ${dato(metricas.precision_global)}, accuracy ${dato(metricas.accuracy)}, ROC AUC ${dato(metricas.roc_auc_score)}, hashes de dataset ${dato(r.datos?.dataset_entrenamiento_hash)} y artefacto ${dato(r.datos?.hash_artefacto_sha256)}, fecha ${dato(r.datos?.fecha_entrenamiento)}; se leyó la versión ${dato(posts[0]?.id)} por GET.` : 'Se intentó registrar el modelo para consultar sus metadatos; no hay versión verificable.'}`,
      '**Qué se esperaba:** Persistencia fiel de todos los campos de Salida 1, incluidas métricas, hashes, fechas, origen RF-71 y notas de validación nulas hasta la revisión clínica (RF-69, líneas 2204-2223; formato UUID evaluado en TC-M04-115).',
      `**Qué se observó:** ${resumen116}`,
      `**Por qué ${estado(2)}:** ${porQue(2, 'Los campos de Salida 1 y sus valores coinciden con lo enviado, las fechas están presentes y las notas siguen nulas; el formato del identificador se decide en TC-M04-115.')}`
    ]),
    encabezado(3, [
      `**Qué se hizo:** ${posts[2] ? `Se registró V1 sin referencia, después V2 ${dato(posts[1]?.id)} y V3 con referencia a V2; se consultaron V1 y V3 por GET usando los procesos RF-71 ${dato(procesos[0])} y ${dato(procesos[2])}.` : 'Se intentó registrar una versión sin referencia y otra con referencia a la anterior; no hay tres respuestas de creación verificables.'}`,
      '**Qué se esperaba:** El registro sin version_referencia procede; cuando se envía, la versión anterior existe y la relación queda consultable (RF-69, línea 1965 y fase de recepción, líneas 1972-1985).',
      `**Qué se observó:** ${observacion117}`,
      `**Por qué ${estado(3)}:** ${porQue(3, 'V1 se registró sin referencia y V3 expone en GET la misma referencia enviada para V2; el formato UUID de esa referencia se decide en TC-M04-115.')}`
    ])
  ].join('\n\n');
}
export function informe(r) {
  const estados = Object.values(r.casos).map(x => x.estado);
  const decision = estados.every(x => x === 'APROBADO') ? 'APROBADO'
    : estados.includes('RECHAZADO') ? 'RECHAZADO'
      : estados.includes('BLOQUEADO') ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
  const celda = x => limpio(x === undefined || x === null ? 'nulo' : typeof x === 'object' ? JSON.stringify(x) : x);
  const tabla = r.comprobaciones.map(x => `| ${x.caso} | ${x.id} | ${x.estado} | ${celda(x.motivo)} |`).join('\n');
  const ids = r.respuestas.posts?.map(x => x?.id) ?? [];
  const auditoria = r.respuestas.auditoria?.items ?? [];
  const eventos = auditoria.filter(x => ['VERSION_REGISTRADA', 'VERSION_APROBADA', 'VERSION_RECHAZADA'].includes(x.tipo_evento));
  const meta = r.comprobaciones.find(x => x.id === 'API-116-01')?.observado ?? {};
  const enviado = r.datos ?? {};
  const metricas = enviado.metricas_validacion ?? {};
  const campos = ['id_version', 'tipo_modelo', 'estado', 'f1_score_global', 'recall_clase_riesgo_alto',
    'precision_global', 'accuracy', 'roc_auc_score', 'recall_por_clase', 'matriz_confusion',
    'dataset_entrenamiento_hash', 'hash_artefacto_modelo', 'fecha_entrenamiento',
    'timestamp_registro', 'id_proceso_rf71', 'notas_validacion'];
  const esperado = k => k === 'id_version' ? 'UUID (formato evaluado en TC-M04-115)'
    : k === 'estado' ? 'APROBADO automático'
      : k === 'timestamp_registro' ? 'fecha válida'
        : k === 'id_proceso_rf71' ? enviado.procesos?.[0]
          : k === 'notas_validacion' ? 'nulo'
            : k === 'hash_artefacto_modelo' ? enviado.hash_artefacto_sha256
              : k in metricas ? metricas[k] : enviado[k];
  const tablaMeta = campos.map(k => `| ${k} | ${celda(esperado(k))} | ${celda(meta[k])} |`).join('\n');
  const tablaEventos = eventos.map(x => `| ${celda(x.tipo_evento)} | ${celda(x.tipo_actor)} | ${celda(x.id_usuario)} | ${celda(x.id_sistema)} | ${celda(x.estado)} |`).join('\n');
  const lista = x => Array.isArray(x) ? x.map((v, i) => `${i + 1}. ${v}`).join('\n') : x;
  const incidencias = r.incidencias.length ? r.incidencias.map(x =>
    `### ${x.id} — ${x.titulo}\n\n- **Caso y equipo inicial:** ${x.caso}; ${x.equipo}. ${x.derivacion}\n- **Severidad y certeza:** ${x.severidad}, ${x.certeza}. ${x.sustento_severidad}\n- **Requisito:** ${Array.isArray(x.requisito) ? x.requisito.join('; ') : `“${x.requisito}” (${x.linea})`}\n- **Precondiciones:** ${x.precondiciones}\n- **Pasos reproducibles:**\n\n${lista(x.pasos)}\n\n- **Esperado:** ${x.esperado}\n- **Obtenido:** ${x.obtenido}\n- **Evidencia:** ${Array.isArray(x.evidencia) ? x.evidencia.join('; ') : x.evidencia}\n- **Análisis e hipótesis:** ${x.analisis}\n- **Impacto:** ${x.impacto}\n- **Para cerrarla:** ${x.cierre}`).join('\n\n')
    : 'Sin incidencias de producto confirmadas.';
  const motivo = decision === 'RECHAZADO' && r.casos['TC-M04-115']?.estado === 'RECHAZADO'
    && estados.filter(x => x === 'APROBADO').length === 3
    ? 'TC-M04-115 incumple el formato UUID; los otros tres casos aprobaron.'
    : `Estados: ${estados.join(', ')}.`;
  const oficial = r.oficial
    ? `RUN oficial: sí (registro QA OFICIAL, DELETE ${r.cierre.run.cierre_http}, rollback confirmado).`
    : 'RUN oficial: no; falta completar las comprobaciones y el cierre requeridos por registro QA.';
  const falta = r.casos['TC-M04-115']?.estado === 'RECHAZADO' && r.oficial
    ? 'Qué falta: corrección de INC-M04-G049-115 por Desarrollo y reevaluación V2 autorizada de TC-M04-115.'
    : 'Qué falta: resolver los casos o impedimentos indicados y completar una evaluación autorizada.';
  const observaciones = [
    r.comprobaciones[0]?.observacion ? `VERSION_REGISTRADA: ${r.comprobaciones[0].observacion}` : null,
    r.respuestas.gets?.length && !r.comprobaciones[0]?.observacion
      ? 'El historial de transiciones no se expone por API pública; los eventos RF-73 acreditan registro y resultado automáticos.' : null,
    r.respuestas.posts?.every(x => [200, 201].includes(x?.http)) ? `El tipo ${celda(enviado.tipo_modelo)} fue aceptado en los tres POST.` : null,
    r.respuestas.gets?.length === 3 && r.respuestas.gets.every(x => x?.cuerpo?.tamanio_artefacto_bytes === 84)
      ? 'Tres artefactos ONNX de 84 bytes quedaron fuera del rollback de BD.' : null
  ].filter(Boolean).map(x => `- ${x}`).join('\n') || 'Sin observaciones adicionales.';
  const revision = r.revision_qa
    ? `Fecha ${r.revision_qa.fecha}; realizada por ${r.revision_qa.realizada_por}; autorizada por ${r.revision_qa.autorizada_por}. ${r.revision_qa.motivo} Cambios: ${r.revision_qa.cambios.join('; ')}.`
    : 'Informe generado con los criterios vigentes del ejecutor; sin revisión QA posterior registrada.';
  return `# TC-M04-G049 — ${decision}\n\n## Decisión del caso\n\nCaso agrupado TC-M04-G049 (RF-69); originales TC-M04-114, TC-M04-115, TC-M04-116 y TC-M04-117. Decisión: ${decision}. Motivo: ${motivo}\n\n| Caso | Comprobación | Decisión | Motivo breve |\n|---|---|---|---|\n${tabla}\n\n${oficial}\n\n${falta}\n\n## Detalle por caso\n\n${detallePorCaso(r)}\n\n## Identificación\n\nRF-69 v2.1; versión V${r.version}; RUN ${r.run_id}; ambiente ${r.ambiente}; autorización ${celda(r.autorizacion)}; código de referencia origin/test daefc3a5 (despliegue no verificado); Newman ${r.preflight_herramientas.newman?.version ?? 'no verificado'}; Cypress no requerido, ${r.cypress?.total_pruebas ?? 0} ejecuciones.\n\n## Esperado vs observado por caso\n\n### TC-M04-114 · API-114-01\n\nEsperado: VERSION_REGISTRADA (Fase 1, sistema, fuente id_proceso_rf71) y VERSION_APROBADA o VERSION_RECHAZADA (Fase 3, sistema). Observado para id_referencia ${celda(ids[0])}:\n\n| Evento | Actor | id_usuario | id_sistema | Estado del payload |\n|---|---|---|---|---|\n${tablaEventos || '| Sin evento verificable | — | — | — | — |'}\n\nDecisión: ${r.casos['TC-M04-114']?.estado}. ${celda(r.casos['TC-M04-114']?.motivo)}\n\n### TC-M04-115 · API-115-01\n\nEsperado: tres UUID distintos. Observado: POST ${r.respuestas.posts?.map(x => `${x?.http ?? 'sin respuesta'} → ${celda(x?.id)}`).join('; ') ?? 'sin respuestas'}; GET /prediccion/modelos/${celda(ids[0])} HTTP ${r.respuestas.gets?.[0]?.http ?? 'sin respuesta'} devuelve id_version_modelo ${celda(r.respuestas.gets?.[0]?.cuerpo?.id_version_modelo ?? r.respuestas.gets?.[0]?.cuerpo?.id_version)}. Decisión: ${r.casos['TC-M04-115']?.estado}.\n\n### TC-M04-116 · API-116-01\n\nEsperado: campos de Salida 1 presentes y fieles, con notas_validacion nulo. La comprobación de formato UUID corresponde a TC-M04-115.\n\n| Campo | Enviado / exigido | GET V1 observado |\n|---|---|---|\n${tablaMeta}\n\nDecisión: ${r.casos['TC-M04-116']?.estado}. ${celda(r.casos['TC-M04-116']?.motivo)}\n\n### TC-M04-117 · API-117-01\n\nEsperado: V1 sin referencia y V3 con version_referencia de V2, consultable. Observado: V1 sin referencia ${celda(r.comprobaciones[3]?.observado?.v1_sin_referencia)}; V2 id ${celda(r.comprobaciones[3]?.observado?.v2_id)}; V3 version_referencia ${celda(r.comprobaciones[3]?.observado?.v3_referencia)}. Decisión: ${r.casos['TC-M04-117']?.estado}.\n\n## Observaciones\n\n${observaciones}\n\n## Incidencias de producto\n\n${incidencias}\n\n## Problemas técnicos y análisis\n\n${r.problemas_tecnicos.length ? r.problemas_tecnicos.map(x => `- ${celda(x)}`).join('\n') : 'Sin problemas técnicos observados.'} La causa raíz de las incidencias de producto no está confirmada.\n\n## Cierre y rollback\n\nDELETE RUN HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. ${r.cierre.rollback.verificado ? 'Cierre de la transacción externa del sandbox confirmado' : 'Rollback de BD no confirmado'}: ${celda(r.cierre.rollback.motivo)}. Los artefactos en disco, posibles respaldos RF-73 y sesiones de login no se verificaron como eliminados.\n\n## Revisión QA\n\n${revision}\n\n## Evidencias\n\n${r.evidencias.map(x => `- ${x}`).join('\n') || 'Sin evidencias registradas.'}\n\n## Conclusión y acción\n\n${decision}. ${falta}\n`;
}
function finalizar(c, r, secretos) {
  const nombre = r.version === 1 ? 'TC-M04-G049_resultado.md' : `TC-M04-G049_reevaluacion_V${r.version}.md`;
  r.evidencias = [...new Set([...r.evidencias, nombre, 'resultado.json'])];
  const completos = r.comprobaciones.every(x => ['APROBADO', 'RECHAZADO'].includes(x.estado)
    && x.evidencia && r.evidencias.includes(x.evidencia));
  r.oficial = completos && r.cierre.run.cierre_http === 200 && r.cierre.rollback.verificado
    && r.problemas_tecnicos.length === 0 && r.evidencias.filter(x => ![nombre, 'resultado.json'].includes(x))
      .every(x => fs.existsSync(path.join(c.directorio, x)));
  r.consume_version = r.oficial;
  const md = sanearArtefacto(informe(r), secretos);
  fs.writeFileSync(path.join(c.directorio, nombre), md, 'utf8');
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
    const variable = catalogo.cuerpo.items.find(x => Number.isSafeInteger(x.id_variable_ambiental));
    if (!variable) throw Error('CATALOGO_I3P1_SIN_VARIABLE_ACTIVA');
    temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g049-newman-'));
    const onnx = onnxMinimo(), onnxPath = path.join(temporal, 'g049.onnx');
    fs.writeFileSync(onnxPath, onnx);
    const datos = { tipo_modelo: 'MODELO_ESPECIES_GRANDES', hash_artefacto_sha256: sha256(onnx),
      dataset_entrenamiento_hash: sha256(Buffer.from('G049 dataset QA RF-71')),
      metricas_validacion: METRICAS, fecha_entrenamiento: new Date(Date.now() - 86400000).toISOString(),
      compatibilidad_variables: [variable.id_variable_ambiental], procesos: [uuid(), uuid(), uuid()] };
    r.datos = { ...datos };
    datos.token_admin = token;
    const n = await ejecutarNewman(c, api, env, datos, onnxPath, secretos, r, temporal);
    r.evidencias.push(...n.artefactos);
    const fallosScript = n.fallos.filter(f => !/AssertionError/.test(f.name));
    if (fallosScript.length || n.salida.error || !n.artefactos.length)
      throw Error(`NEWMAN_TECNICO:${JSON.stringify({ fallos: fallosScript, salida: n.salida })}`);
    const posts = [1, 2, 3].map(i => n.respuestas.find(x => x.nombre === `API-G049-POST-V${i}`));
    const primero = posts[0];
    if (!primero?.http) throw Error('POST_V1_SIN_RESPUESTA');
    if (primero.http === 403) {
      CASOS.forEach((_, i) => asignar(r, i, 'BLOQUEADO', 'Clave interna rechazada 403; sin reintentos',
        'newman/newman-G049.json'));
      r.problemas_tecnicos.push('CREDENCIAL_RF71_403');
      return r;
    }
    if (primero.http >= 500) throw Error(`POST_V1_5XX_${primero.http}`);
    if (![200, 201].includes(primero.http) || !primero.eco || !idVersion(primero.cuerpo))
      throw Error(`POST_V1_PRECONDICION_HTTP_${primero.http}_ECO_${primero.eco}`);
    const gets = [1, 2, 3].map(i => n.respuestas.find(x => x.nombre === `API-G049-GET-V${i}`));
    const auditorias = [n.respuestas.find(x => x.nombre === 'API-G049-AUDITORIA-V1')];
    r.respuestas = { posts: posts.map(x => x ? { http: x.http, eco: x.eco, id: idVersion(x.cuerpo),
      estado: estado(x.cuerpo), error: x.error } : null),
    gets: gets.map(x => x ? { http: x.http, eco: x.eco, cuerpo: x.cuerpo } : null),
    auditoria: auditorias[0] ? { http: auditorias[0].http, eco: auditorias[0].eco,
      total: auditorias[0].cuerpo?.total, items: (auditorias[0].cuerpo?.items ?? []).map(e => ({
        tipo_evento: e.tipo_evento, tipo_actor: e.tipo_actor, id_usuario: e.id_usuario,
        id_sistema: e.id_sistema, id_referencia: e.id_referencia,
        estado: e.payload_evento?.estado_version ?? e.payload_evento?.estado })) } : null };
    const g1 = gets[0], a1 = auditorias[0];
    if (!g1?.http || !a1?.http) throw Error('LECTURA_V1_SIN_RESPUESTA');
    if (g1.http >= 500 || a1.http >= 500) throw Error('LECTURA_V1_5XX');
    if (g1.http === 403 || a1.http === 403) throw Error('LECTURA_V1_403');
    if (a1.http !== 200 || !a1.eco || !Array.isArray(a1.cuerpo?.items))
      throw Error(`AUDITORIA_NO_VERIFICABLE_HTTP_${a1.http}`);
    const auditoria = evaluarAuditoria(a1.cuerpo.items, idVersion(primero.cuerpo), datos.procesos[0]);
    asignar(r, 0, auditoria.ok ? 'APROBADO' : 'RECHAZADO', auditoria.ok
      ? 'VERSION_REGISTRADA y VERSION_APROBADA de sistema con fuente id_proceso_rf71 (RF-69 Fase 6)'
      : 'No se acreditan ambas transiciones automáticas con fuente RF-71',
    'resultado.json', { eventos: a1.cuerpo.items.map(e => ({ tipo_evento: e.tipo_evento,
      tipo_actor: e.tipo_actor, id_usuario: e.id_usuario, id_sistema: e.id_sistema,
      id_referencia: e.id_referencia, estado: e.payload_evento?.estado_version })) });
    if (auditoria.observacion) {
      r.comprobaciones[0].observacion = auditoria.observacion;
      r.casos[CASOS[0]].observacion = auditoria.observacion;
    }
    const ids = posts.map(x => idVersion(x?.cuerpo));
    const identidadOk = ids.every(esUuid) && new Set(ids).size === 3;
    if (ids.every(x => x !== null && x !== undefined)) asignar(r, 1,
      identidadOk ? 'APROBADO' : 'RECHAZADO', identidadOk ? 'Tres UUID RFC 4122 distintos'
        : `Identificadores observados: ${JSON.stringify(ids)}; se exigen UUID distintos`,
    'newman/newman-G049.json', ids);
    else asignar(r, 1, 'NO_CONCLUYENTE', 'No se obtuvieron tres versiones registradas');
    if (g1.http !== 200 || !g1.eco || !g1.cuerpo) throw Error(`GET_V1_NO_VERIFICABLE_HTTP_${g1.http}`);
    const meta = metadatosIguales(g1.cuerpo, { ...datos, id_proceso_rf71: datos.procesos[0] });
    const idLeido = idVersion(g1.cuerpo);
    const idOk = idLeido !== null && idLeido !== undefined && idLeido === ids[0];
    const metaOk = !meta.faltantes.length && idOk;
    asignar(r, 2, metaOk ? 'APROBADO' : 'RECHAZADO', metaOk ? 'Salida 1 completa e igual a la enviada'
      : `Campos divergentes: ${[...meta.faltantes, ...(!idOk ? ['id_version'] : [])].join(', ')}`,
    'resultado.json', { id_version: idLeido, ...meta.observados });
    if (idLeido !== null && idLeido !== undefined && !esUuid(idLeido))
      r.comprobaciones[2].observacion =
      'Formato de id_version evaluado en TC-M04-115 (INC-M04-G049-115)';
    const p3 = posts[2], g3 = gets[2];
    if (p3?.http && p3.http >= 500) throw Error(`POST_V3_5XX_${p3.http}`);
    if (p3?.http === 422 && ids[1] && esUuid(ids[1])) {
      asignar(r, 3, 'RECHAZADO', 'POST V3 rechaza version_referencia UUID con 422',
        'newman/newman-G049.json', { http: 422, error: p3.error, referencia: ids[1] });
    } else if (p3?.http && [200, 201].includes(p3.http) && g3?.http === 200 && g3.eco) {
      const ref = g3.cuerpo?.version_referencia;
      const sinRef = posts[0]?.http && [200, 201].includes(posts[0].http);
      const ok = sinRef && String(ref ?? '') === String(ids[1]);
      asignar(r, 3, ok ? 'APROBADO' : 'RECHAZADO', ok ? 'V3 refiere V2 y V1 se registró sin referencia'
        : 'V3 no expone la referencia a V2 por GET', 'resultado.json',
      { v1_sin_referencia: sinRef, v2_id: ids[1], v3_referencia: ref });
    } else assignarPendiente();
    function assignarPendiente() { asignar(r, 3, 'NO_CONCLUYENTE',
      `V3 o GET no verificable: POST ${p3?.http ?? 'sin respuesta'}, GET ${g3?.http ?? 'sin respuesta'}`); }
    if (n.fallos.some(f => f.name === 'AssertionError' && f.test === 'ID_UUID')
      && r.comprobaciones[1].estado === 'APROBADO')
      asignar(r, 1, 'RECHAZADO', 'Aserción Newman ID_UUID fallida', 'newman/newman-G049.json', ids);
    const secundario = posts.slice(1).find(p => p?.http === 403 || p?.http >= 500);
    if (secundario) {
      r.problemas_tecnicos.push(`POST_SECUNDARIO_HTTP_${secundario.http}`);
      for (const i of [1, 3]) if (r.comprobaciones[i].estado === 'NO_CONCLUYENTE')
        asignar(r, i, 'BLOQUEADO', `POST secundario HTTP ${secundario.http}; no se completaron tres versiones`,
          'newman/newman-G049.json');
    }
    if (r.comprobaciones[0].estado === 'RECHAZADO') r.incidencias.push(incidencia(CASOS[0], 'INC-M04-G049-114',
      'Historial automático incompleto', 'Se registra en historial inmutable: VERSION_REGISTRADA ... VERSION_APROBADA o VERSION_RECHAZADA',
      'RF-69 líneas 2089-2095', 'Dos eventos de sistema vinculados a id_proceso_rf71',
      r.comprobaciones[0].motivo, 'resultado.json', 'ALTA'));
    if (r.comprobaciones[1].estado === 'RECHAZADO') r.incidencias.push(incidencia115(r));
    if (r.comprobaciones[2].estado === 'RECHAZADO') r.incidencias.push(incidencia(CASOS[2], 'INC-M04-G049-116',
      'Metadatos de trazabilidad incompletos', 'Persiste un objeto con: id_version (UUID) ... notas_validacion (Text; nulo hasta Fase 4)',
      'RF-69 líneas 2204-2223', 'Salida 1 completa e igual a la enviada',
      r.comprobaciones[2].motivo, 'resultado.json', 'MEDIA'));
    if (r.comprobaciones[3].estado === 'RECHAZADO') r.incidencias.push(incidencia(CASOS[3], 'INC-M04-G049-117',
      'Relación con versión anterior no consultable', 'version_referencia | UUID (opcional)',
      'RF-69 línea 1965', 'V3 refiere V2 por GET; V1 se registra sin referencia',
      r.comprobaciones[3].motivo, r.comprobaciones[3].evidencia, 'MEDIA'));
    return r;
  } catch (e) {
    const motivo = limpio(e.message);
    r.problemas_tecnicos.push(motivo);
    const tipo = /5XX|_5\d\d|403|SIN_PERMISO|CATALOGO|LOGIN/.test(motivo) ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
    CASOS.forEach((_, i) => { if (r.casos[CASOS[i]].motivo === 'Sin comprobación')
      asignar(r, i, tipo, motivo); });
    return r;
  } finally {
    if (tocado) try {
      const x = await pedir(api, 'DELETE', `/test-control/runs/${encodeURIComponent(c.runId)}`,
        { secreto: env.QA_SANDBOX_SECRET, bitacora: r.bitacora });
      r.cierre.run.cierre_http = x.http;
      r.cierre.rollback.verificado = x.http === 200;
      r.cierre.rollback.motivo = x.http === 200
        ? 'Transacción externa del sandbox cerrada; artefactos en disco y posible respaldo local fuera de alcance'
        : `DELETE HTTP ${x.http}`;
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
    const c = contextoEjecucion(process.argv.slice(2), { grupo: 'G049', casos: CASOS, directorio: DIR });
    const r = await evaluar(c, { env: leerEnv() });
    console.log(JSON.stringify({ run_id: r.run_id, casos: r.casos, oficial: r.oficial }));
    if (!r.oficial) process.exitCode = 2;
  } catch (e) { console.error(`G049: ${limpio(e.message)}`); process.exitCode = 2; }
}
