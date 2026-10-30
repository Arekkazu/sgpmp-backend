#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import crypto from 'node:crypto';
import { spawn, spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';
import { sanearArtefacto, contieneMojibake } from './lib/seguridad.mjs';
import { onnxMinimo, savedModelMinimo, validarSavedModel, sha256 } from './lib/artefactos.mjs';
import { CASOS, IDS, TIPOS, INDIVIDUAL, POBLACIONAL, PRESUPUESTO, CAPACIDADES,
  idVersion, estado } from './lib/g050_escenario.mjs';

const require = createRequire(import.meta.url);
const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION = path.join(DIR, 'G050.postman_collection.json');
const ARCHIVOS = ['.gitkeep', 'g050.mjs', 'G050.postman_collection.json', 'README.md',
  'lib/contrato_ejecutor.mjs', 'lib/seguridad.mjs', 'lib/artefactos.mjs',
  'lib/g050_escenario.mjs', 'pruebas/registro_qa.mjs', 'pruebas/g050_ensayo.mjs',
  'pruebas/g050.test.mjs', 'artefactos/g050.onnx', 'artefactos/saved_model.pb'];
const limpio = x => String(x ?? '').replaceAll('|', '/').replace(/[\r\n]+/g, ' ').slice(0, 250);
const guardar = (p, x) => fs.writeFileSync(p, JSON.stringify(x, null, 2), 'utf8');
const celda = x => limpio(x === null || x === undefined ? 'nulo' : typeof x === 'object' ? JSON.stringify(x) : x);

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
    const p = paqueteNewman();
    if (ensayo) return { ok: true, version: require(path.join(p, 'package.json')).version, modo: 'paquete local' };
    const x = spawnSync(process.execPath, [binNewman(), '--version'],
      { timeout: 30000, encoding: 'utf8', windowsHide: true });
    return { ok: x.status === 0 && !!x.stdout.trim(), version: x.stdout.trim(), error: x.error?.code ?? null };
  } catch (e) { return { ok: false, error: e.code ?? e.message }; }
}
export function preflight(c, env, ensayo = false) {
  const base = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const claves = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_ADMIN_EMAIL',
    'QA_ADMIN_PASSWORD', 'RF71_INTERNAL_KEY'];
  const barreras = claves.filter(k => !String(env[k] ?? '').trim());
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base) : base !== API) barreras.push('API_NO_CANONICA');
  if (c.version > 1 && c.operacion !== 'reevaluar') barreras.push('REEVALUACION_SIN_DECISION');
  return { fase: 'PREFLIGHT_LOCAL', grupo: 'G050', run_id: c.runId, version: c.version,
    ok: !barreras.length, barreras, presupuesto: PRESUPUESTO,
    efectos_declarados: ['hasta_7_versiones_BD_sujetas_a_rollback_externo',
      'hasta_7_archivos_ONNX_o_PB_en_MODELOS_STORAGE_PATH_no_revertidos',
      'posible_respaldo_local_RF73_no_revertido', 'login_fuera_RUN_puede_persistir',
      'ningun_correo_esperado_con_metricas_aprobatorias'] };
}
export function comprobar() {
  let coleccion = false;
  try {
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const i of col.item) for (const e of i.event ?? []) new vm.Script((e.script?.exec ?? []).join('\n'));
    const nombres = ['V1', 'V2', 'V2b', 'V3', 'V4', 'V5', 'V6'];
    coleccion = col.item.length === 14 && col.item.every((i, n) => i.name ===
      `API-G050-${n % 2 ? 'GET' : 'POST'}-${nombres[Math.floor(n / 2)]}`
      && i.request.method === (n % 2 ? 'GET' : 'POST')) && !contieneMojibake(JSON.stringify(col));
  } catch { /* se informa */ }
  const faltantes = ARCHIVOS.filter(x => !fs.existsSync(path.join(DIR, x)));
  const presentes = fs.readdirSync(DIR).filter(x => !['lib', 'pruebas', 'artefactos', 'Resultados', 'EvaluacionV2'].includes(x))
    .concat(...['lib', 'pruebas', 'artefactos'].map(d => fs.readdirSync(path.join(DIR, d)).map(x => `${d}/${x}`)));
  const inesperados = presentes.filter(x => !ARCHIVOS.includes(x));
  const artefactos = fs.existsSync(path.join(DIR, 'artefactos/g050.onnx'))
    && fs.readFileSync(path.join(DIR, 'artefactos/g050.onnx')).equals(onnxMinimo())
    && fs.existsSync(path.join(DIR, 'artefactos/saved_model.pb'))
    && fs.readFileSync(path.join(DIR, 'artefactos/saved_model.pb')).equals(savedModelMinimo())
    && validarSavedModel(savedModelMinimo());
  const markdownSuperior = fs.existsSync(path.join(DIR, 'Resultados'))
    && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const ok = coleccion && artefactos && !faltantes.length && !inesperados.length && !markdownSuperior;
  console.log(JSON.stringify({ grupo: 'G050', ok, coleccion, artefactos,
    faltantes, inesperados, markdownSuperior, presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}
function cuerpoPublico(x) { const d = x?.detail && typeof x.detail === 'object' ? x.detail : x;
  return { codigo: limpio(d?.error_code ?? d?.code ?? d?.codigo),
    mensaje: limpio(d?.message ?? d?.mensaje ?? (typeof x?.detail === 'string' ? x.detail : '')) }; }
async function pedir(api, metodo, ruta, { token, secreto, runId, cuerpo, bitacora } = {}) {
  let http = null, eco = null;
  try {
    const x = await fetch(api + ruta, { method: metodo, redirect: 'manual',
      headers: { ...(cuerpo ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(secreto ? { 'X-Sandbox-Secret': secreto } : {}),
        ...(runId ? { 'X-Test-Run-Id': runId, 'X-Zona-Horaria': 'UTC' } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      signal: AbortSignal.timeout(PRESUPUESTO.timeout_ms) });
    http = x.status; eco = runId ? x.headers.get('x-test-run-id') === runId : null;
    const data = await x.json().catch(() => null);
    return { http, eco, cuerpo: data, error: http >= 400 ? cuerpoPublico(data) : null };
  } finally { bitacora.push({ metodo, ruta, http, eco, en_run: !!runId }); }
}
function extracto(ex, runId) {
  const hs = ex?.response?.header ?? [];
  const eco = hs.find(h => String(h.key).toLowerCase() === 'x-test-run-id')?.value === runId;
  const stream = ex?.response?.stream;
  const bytes = Buffer.from(stream?.data ?? (Array.isArray(stream) ? stream : []));
  let cuerpo = null; try { cuerpo = JSON.parse(bytes.toString('utf8')); } catch { /* vacío */ }
  const http = ex?.response?.code ?? null;
  return { http, eco, cuerpo, error: http >= 400 ? cuerpoPublico(cuerpo) : null };
}
async function ejecutarNewman(c, api, env, datos, secretos, temporal) {
  const raw = path.join(temporal, 'raw.json'), environment = path.join(temporal, 'environment.json');
  const vars = { autorizado_run: 'SI', ensayo_loopback: c.ensayo ? 'SI' : 'NO',
    base_url: api, run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET,
    rf71_internal_key: env.RF71_INTERNAL_KEY, token_admin: datos.token,
    dataset_hash: datos.datasetHash, fecha_entrenamiento: datos.fecha,
    compatibilidad_variables: JSON.stringify(datos.variables) };
  datos.versiones.forEach((d, i) => { const n = i + 1;
    Object.assign(vars, { [`tipo_${n}`]: d.tipo, [`hash_${n}`]: d.hash,
      [`metricas_${n}`]: JSON.stringify(d.metricas), [`proceso_${n}`]: d.proceso,
      [`archivo_${n}`]: d.archivo });
    if (d.componente) vars[`componente_${n}`] = d.componente;
  });
  const v2b = datos.version2b;
  Object.assign(vars, { tipo_2b: v2b.tipo, hash_2b: v2b.hash,
    metricas_2b: JSON.stringify(v2b.metricas), proceso_2b: v2b.proceso,
    archivo_2b: v2b.archivo });
  guardar(environment, { values: Object.entries(vars).map(([key, value]) => ({ key, value, enabled: true })) });
  const args = [binNewman(), 'run', COLECCION, '--environment', environment, '--reporters', 'json',
    '--reporter-json-export', raw, '--working-dir', temporal,
    '--timeout-request', String(PRESUPUESTO.timeout_ms), '--timeout', '600000', '--color', 'off'];
  let salida = await new Promise(resolve => {
    let p; try { p = spawn(process.execPath, args, { stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true }); }
    catch (e) { resolve({ code: null, error: e.code ?? 'NEWMAN_SPAWN' }); return; }
    p.stdout.on('data', () => {}); p.stderr.on('data', () => {});
    p.on('error', e => resolve({ code: null, error: e.code ?? 'NEWMAN_SPAWN' }));
    p.on('close', code => resolve({ code, error: null }));
  });
  if (c.ensayo && salida.error === 'EPERM') {
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    const e = JSON.parse(fs.readFileSync(environment, 'utf8'));
    salida = await new Promise(resolve => require(paqueteNewman()).run({ collection: col,
      environment: e, reporters: ['json'], reporter: { json: { export: raw } },
      timeoutRequest: PRESUPUESTO.timeout_ms, timeout: 600000, color: 'off' },
    error => resolve({ code: error ? 1 : 0, error: error?.message ?? null, modo: 'API_LOCAL_POR_SPAWN_EPERM' })));
  }
  if (!fs.existsSync(raw)) return { salida, respuestas: [], fallos: [], artefactos: [] };
  const original = JSON.parse(fs.readFileSync(raw, 'utf8'));
  const ejecuciones = (original.run?.executions ?? []).map(ex => ({ nombre: ex.item?.name ?? 'DESCONOCIDO',
    ...extracto(ex, c.runId) }));
  const fallos = (original.run?.failures ?? []).map(f => ({ name: limpio(f.error?.name),
    test: limpio(f.error?.test), source: limpio(f.source?.name), mensaje: limpio(f.error?.message) }));
  fs.mkdirSync(path.join(c.directorio, 'newman'), { recursive: true });
  const artefactos = ['newman/newman-G050.json', 'newman/newman-G050.html'];
  guardar(path.join(c.directorio, artefactos[0]), JSON.parse(sanearArtefacto(JSON.stringify({
    info: { nombre: 'Newman G050', generado: true, saneado: true },
    run: { stats: original.run?.stats ?? null, executions: ejecuciones, failures: fallos } }), secretos)));
  const filas = ejecuciones.map(x => `<tr><td>${x.nombre}</td><td>${x.http ?? 'sin respuesta'}</td><td>${x.eco}</td></tr>`).join('');
  fs.writeFileSync(path.join(c.directorio, artefactos[1]),
    `<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G050</title><h1>Newman G050</h1><table><tr><th>Solicitud</th><th>HTTP</th><th>Eco RUN</th></tr>${filas}</table></html>`, 'utf8');
  return { salida, respuestas: ejecuciones, fallos, artefactos };
}

function resultadoInicial(c) {
  return { grupo: 'G050', run_id: c.runId, version: c.version, operacion: c.operacion,
    autorizacion: c.referencia, ambiente: c.ensayo ? 'LOOPBACK_LOCAL' : 'TEST',
    oficial: false, consume_version: false,
    casos: Object.fromEntries(CASOS.map(x => [x, { estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación' }])),
    comprobaciones: CASOS.map((caso, i) => ({ caso, fuente: 'API', id: IDS[i],
      tipo: 'ASSERT', estado: 'NO_CONCLUYENTE', motivo: 'Sin respuesta', evidencia: null })),
    cypress: { total_pruebas: 0 }, preflight_herramientas: {}, evidencias: [],
    bitacora: [], datos: null, respuestas: { posts: [], gets: [], v2b: null },
    incidencias: [], problemas_tecnicos: [],
    cierre: { run: { cierre_http: null }, rollback: { verificado: false,
      motivo: 'Sin cierre ni comprobación de reversión de BD' } } };
}
function asignar(r, i, estadoCaso, motivo, observado = null, evidencia = null) {
  const caso = CASOS[i]; r.casos[caso] = { estado: estadoCaso, motivo };
  Object.assign(r.comprobaciones[i], { estado: estadoCaso, motivo, observado, evidencia });
}
function incidencia(caso, id, titulo, esperado, obtenido, evidencia, severidad = 'MEDIA') {
  return { id, caso, titulo, equipo: 'Desarrollo',
    derivacion: 'Primera discrepancia comprobada en la API pública; causa raíz no determinada.',
    severidad, certeza: 'CONFIRMADA',
    sustento_severidad: severidad === 'ALTA'
      ? 'El tipo o formato exigido no se puede registrar sin alternativa equivalente en RF-69.'
      : 'El registro puede continuar, pero el formato o metadato consultable es incorrecto.',
    requisito: 'Matriz vigente G050; RF-69 Restricción 2, RFC-009 y RF-65.',
    precondiciones: 'RUN autorizado; clave RF-71 válida; catálogo I3P-1; artefactos y hashes deterministas.',
    pasos: ['Enviar POST multipart de los seis tipos dentro del RUN; usar V2b ONNX si V2 se rechaza por formato.',
      'Consultar por GET cada id devuelto y comparar formato, tipo, paradigma, componente y métricas.'],
    esperado, obtenido, evidencia,
    analisis: 'La API demuestra la discrepancia; el código local sugiere una hipótesis, no acredita la causa raíz en TEST.',
    impacto: titulo, cierre: 'Corregir y reevaluar en un RUN autorizado.' };
}
export function incidencia119(r, post, get, hashEnviado, v2bCreado) {
  const identificadoComoOnnx = post?.http === 201 && get?.http === 200
    && get?.formato_artefacto === 'ONNX' && get?.hash_artefacto_sha256 === hashEnviado;
  const hash = hashEnviado ?? 'no disponible';
  const base = incidencia(CASOS[1], 'INC-M04-G050-119',
    identificadoComoOnnx ? 'Un TensorFlow SavedModel válido se registra con formato ONNX'
      : 'Un TensorFlow SavedModel válido no se registra con el formato exigido',
    'POST 201 y GET 200 con formato_artefacto TENSORFLOW_SAVED_MODEL y hash SHA-256 igual al enviado',
    identificadoComoOnnx
      ? `POST 201, id ${post.id}, estado ${post.estado}; GET 200, formato_artefacto ONNX, hash ${get.hash_artefacto_sha256} igual al enviado ${hash}; primeros bytes 08 01 12 96.`
      : `POST HTTP ${post?.http ?? 'sin respuesta'}; GET HTTP ${get?.http ?? 'no ejecutado'}; formato_artefacto ${get?.formato_artefacto ?? 'no disponible'}; hash enviado ${hash}.`,
    ['newman/newman-G050.json', 'resultado.json'], identificadoComoOnnx ? 'MEDIA' : 'ALTA');
  return { ...base, run_id: r.run_id,
    derivacion: 'La primera discrepancia está comprobada en POST/GET de la API pública; Desarrollo es el primer equipo de atención. La causa raíz en TEST no está demostrada.',
    sustento_severidad: identificadoComoOnnx
      ? 'El registro se completa y el hash es fiel, pero el metadato de formato es incorrecto. Los consumidores que dependan del formato (RF-66 al ejecutar y RF-70 al distribuir al Edge) podrían cargar el artefacto con el runtime equivocado; no bloquea el registro.'
      : 'El formato exigido no quedó disponible para el caso; sin alternativa equivalente para el artefacto SavedModel en RF-69.',
    requisito: 'RF-69, Restricción 2, línea 1873: “Solo se aceptan artefactos en formato ONNX o TensorFlow SavedModel.” Fase 1, líneas 1993-1995: “El sistema verifica que el formato del artefacto sea ONNX o TensorFlow SavedModel. Si el formato es inválido → E1.” RNF-09, línea 2391: “Solo ONNX y TensorFlow SavedModel.” Matriz G050, nota de TC-M04-119: “la detección se basa en la firma binaria del archivo, no en su extensión”.',
    precondiciones: `RUN ${r.run_id} autorizado; clave RF-71 válida; catálogo I3P-1; saved_model.pb de 155 bytes construido según tensorflow/core/protobuf/saved_model.proto, con saved_model_schema_version=1 y MetaGraph “serve”; hash SHA-256 ${hash}.`,
    pasos: [
      `En el RUN autorizado, enviar POST /prediccion/modelos multipart con archivo_modelo=saved_model.pb, tipo_modelo=MODELO_ESPECIES_MEDIANAS, hash_artefacto_sha256=${hash} y cabecera X-RF71-Internal-Key.`,
      `Consultar GET /prediccion/modelos/${post?.id ?? '<id devuelto>'} y comparar formato_artefacto y hash_artefacto_sha256 con el archivo enviado.`,
      ...(v2bCreado ? ['Registrar V2b ONNX para el subcaso independiente TC-M04-120; no usarlo para decidir TC-M04-119.'] : [])
    ],
    analisis: 'La API demuestra la discrepancia de formato. Hipótesis a comprobar: en origin/test, registrar_version_modelo_use_case.py:250-270 decide por el primer byte (0x08 → ONNX; 0x0a → TensorFlow). Un SavedModel real empieza con 0x08 porque el campo 1 saved_model_schema_version es varint, igual que el campo inicial de ModelProto ONNX. Esa lectura local no confirma la causa raíz en TEST.',
    impacto: identificadoComoOnnx
      ? 'Los consumidores que seleccionan runtime por formato (RF-66 y RF-70) podrían elegir ONNX para un SavedModel; además, un SavedModel podría guardarse con extensión .onnx. Impacto potencial, no observado en este RUN.'
      : 'El artefacto SavedModel exigido no queda disponible con el formato correcto.',
    cierre: 'Identificar el formato por la estructura del mensaje y no por el primer byte, o recibir el formato declarado y validarlo contra la estructura; después, reevaluación V2 autorizada de TC-M04-119.' };
}
function evaluarRegistro(post, get, d) {
  if (!post?.http) return { estado: 'NO_CONCLUYENTE', motivo: 'POST sin respuesta' };
  if (post.http === 403 || post.http >= 500) return { estado: 'BLOQUEADO', motivo: `POST HTTP ${post.http}; impedimento técnico` };
  if (post.http === 422) return { estado: 'RECHAZADO', motivo: `POST HTTP 422: ${post.error?.codigo ?? 'error de validación'}` };
  if (![200, 201].includes(post.http)) return { estado: 'NO_CONCLUYENTE', motivo: `POST HTTP ${post.http} no verificable` };
  if (!post.eco || idVersion(post.cuerpo) === null) return { estado: 'NO_CONCLUYENTE', motivo: 'POST sin eco o identificador' };
  if (!get?.http) return { estado: 'NO_CONCLUYENTE', motivo: 'GET sin respuesta' };
  if (get.http === 403 || get.http >= 500) return { estado: 'BLOQUEADO', motivo: `GET HTTP ${get.http}; impedimento técnico` };
  if (get.http !== 200 || !get.eco || !get.cuerpo) return { estado: 'NO_CONCLUYENTE', motivo: `GET HTTP ${get.http} o eco inválido` };
  const observado = get.cuerpo;
  const comunes = idVersion(observado) === idVersion(post.cuerpo)
    && observado.tipo_modelo === d.tipo && observado.paradigma === d.paradigma
    && estado(observado) === 'APROBADO';
  if (!comunes || post.http !== 201) return { estado: 'RECHAZADO', motivo: 'Registro o GET difiere en id, tipo, paradigma o estado APROBADO' };
  return { estado: 'APROBADO', motivo: 'Registro 201 y GET coherentes con tipo y paradigma' };
}
function metricasIguales(observado, d) {
  if (d.paradigma === 'POBLACIONAL') {
    const m = observado.metricas_poblacionales;
    return observado.componente === d.componente && m?.calibracion_completada === true
      && Number(m.tasa_falsos_positivos_rutina) === POBLACIONAL.tasa_falsos_positivos_rutina
      && Number(m.tasa_deteccion_eventos_clinicos) === POBLACIONAL.tasa_deteccion_eventos_clinicos;
  }
  return observado.componente == null && Number(observado.f1_score) === INDIVIDUAL.f1_score_global
    && Number(observado.recall_clase_riesgo_alto) === INDIVIDUAL.recall_clase_riesgo_alto
    && Number(observado.precision_modelo) === INDIVIDUAL.precision_global
    && Number(observado.accuracy) === INDIVIDUAL.accuracy
    && Number(observado.roc_auc_score) === INDIVIDUAL.roc_auc_score
    && JSON.stringify(observado.recall_por_clase) === JSON.stringify(INDIVIDUAL.recall_por_clase)
    && JSON.stringify(observado.matriz_confusion) === JSON.stringify(INDIVIDUAL.matriz_confusion);
}
function resumir(x) {
  if (!x) return null;
  const c = x.cuerpo ?? {};
  return { http: x.http, eco: x.eco, id: idVersion(c),
    tipo_modelo: c.tipo_modelo, paradigma: c.paradigma,
    formato_artefacto: c.formato_artefacto, hash_artefacto_sha256: c.hash_artefacto_sha256,
    componente: c.componente, metricas_poblacionales: c.metricas_poblacionales,
    f1_score: c.f1_score, recall_clase_riesgo_alto: c.recall_clase_riesgo_alto,
    precision_modelo: c.precision_modelo, accuracy: c.accuracy,
    roc_auc_score: c.roc_auc_score, recall_por_clase: c.recall_por_clase,
    matriz_confusion: c.matriz_confusion,
    estado: estado(c), error: x.error };
}
function detallePorCaso(r) {
  const posts = r.respuestas.posts, gets = r.respuestas.gets, datos = r.datos?.versiones ?? [];
  const numero = x => x == null ? 'sin respuesta' : String(x);
  const http = x => 'HTTP ' + numero(x?.http);
  const id = x => x?.id == null ? 'sin ID' : 'ID ' + x.id;
  const nombre = x => String(x ?? 'sin tipo').replace(/^MODELO_/, '').replaceAll('_', ' ').toLowerCase();
  const fiel = (g, d) => !!g?.hash_artefacto_sha256 && g.hash_artefacto_sha256 === d?.hash;
  const incidencia = caso => r.incidencias.find(x => x.caso === caso)?.id ?? 'sin incidencia registrada';
  const apartado = (caso, hecho, esperado, observado, motivo) =>
    '### ' + caso + ' — ' + r.casos[caso].estado + '\n\n'
    + '**Qué se hizo:** ' + hecho + '  \n'
    + '**Qué se esperaba:** ' + esperado + '  \n'
    + '**Qué se observó:** ' + observado + '  \n'
    + '**Por qué ' + r.casos[caso].estado + ':** ' + motivo;
  const sinCierre = caso => 'La comprobación quedó sin cerrar: ' + limpio(r.casos[caso].motivo)
    + '. Hace falta resolver el impedimento y obtener respuestas de registro y consulta verificables en una ejecución autorizada.';
  const p0 = posts[0], g0 = gets[0], d0 = datos[0] ?? {};
  const p1 = posts[1], g1 = gets[1], d1 = datos[1] ?? {};
  const paso = (p, g, d, archivo, tipo) =>
    'Como servicio interno RF-71, sin actor humano, ' + (p ? 'se envió POST' : 'no consta envío POST')
    + ' /prediccion/modelos con ' + archivo
    + ', tipo ' + tipo + ', paradigma individual, hash SHA-256 ' + (d.hash ?? 'sin registro')
    + ', F1 ' + (d.metricas?.f1_score_global ?? 'sin registro')
    + ' y recall ' + (d.metricas?.recall_clase_riesgo_alto ?? 'sin registro')
    + '; ' + (g ? 'se consultó GET /prediccion/modelos/' + (g.id ?? 'ID no recibido') : 'no consta consulta GET') + ' (' + id(g ?? p) + ').';
  const respuesta = (p, g, d) => 'POST ' + http(p) + ', ' + id(p) + ' y estado '
    + (p?.estado ?? 'sin estado') + '; GET ' + http(g) + ', formato '
    + (g?.formato_artefacto ?? 'sin formato observado') + ', hash '
    + (g?.hash_artefacto_sha256 ?? 'sin valor') + ' (' + (fiel(g, d) ? 'igual al enviado' : 'sin coincidencia confirmada') + ').';
  const fallo120 = posts.map((p, i) => ({ p, g: gets[i], d: datos[i] ?? {} }))
    .find(x => x.p?.http !== 201 || x.g?.http !== 200 || x.g?.tipo_modelo !== x.d.tipo
      || x.g?.paradigma !== x.d.paradigma || (x.g?.componente ?? null) !== (x.d.componente ?? null));
  const por118 = r.casos[CASOS[0]].estado === 'APROBADO'
    ? 'El registro y la consulta se completaron; el formato fue ONNX y el hash coincidió con el archivo enviado.'
    : r.casos[CASOS[0]].estado === 'RECHAZADO'
      ? 'El criterio ONNX falló: POST ' + http(p0) + ', GET ' + http(g0) + ', formato '
        + (g0?.formato_artefacto ?? 'sin valor') + '. Incidencia ' + incidencia(CASOS[0]) + '.'
      : sinCierre(CASOS[0]);
  const por119 = r.casos[CASOS[1]].estado === 'APROBADO'
    ? 'El registro y la consulta se completaron; el formato fue TensorFlow SavedModel y el hash coincidió con el archivo enviado.'
    : r.casos[CASOS[1]].estado === 'RECHAZADO'
      ? 'Se exigía TensorFlow SavedModel y se obtuvo ' + (g1?.formato_artefacto ?? 'sin formato observado')
        + ' en GET ' + http(g1) + ' tras POST ' + http(p1) + '; el hash '
        + (fiel(g1, d1) ? 'sí coincidió' : 'no quedó confirmado') + '. Incidencia ' + incidencia(CASOS[1]) + '.'
      : sinCierre(CASOS[1]);
  const por120 = r.casos[CASOS[2]].estado === 'APROBADO'
    ? 'Los seis tipos tuvieron POST 201 y GET 200 con IDs propios; coincidieron tipo, paradigma, componente y métricas de cada registro.'
    : r.casos[CASOS[2]].estado === 'RECHAZADO'
      ? 'No se completó el criterio para ' + nombre(fallo120?.d.tipo) + ': POST ' + http(fallo120?.p)
        + ', GET ' + http(fallo120?.g) + ', paradigma ' + (fallo120?.g?.paradigma ?? 'sin valor')
        + ' y componente ' + (fallo120?.g?.componente ?? 'sin valor') + '. Incidencia ' + incidencia(CASOS[2]) + '.'
      : sinCierre(CASOS[2]);
  const enviados = posts.map((p, i) => nombre(datos[i]?.tipo) + ' en '
    + (datos[i]?.formato === 'TENSORFLOW_SAVED_MODEL' ? 'TensorFlow SavedModel' : 'ONNX')
    + ' (' + id(p) + ')').join(', ') || 'ningún modelo';
  const observados = posts.map((p, i) => nombre(datos[i]?.tipo) + ': POST ' + http(p)
    + ', GET ' + http(gets[i]) + ', ' + id(gets[i] ?? p)
    + ', estado ' + (gets[i]?.estado ?? p?.estado ?? 'sin estado')
    + ', paradigma ' + (gets[i]?.paradigma ?? 'sin valor')
    + ', componente ' + (gets[i]?.componente ?? 'ninguno')).join('; ') || 'no constan respuestas de modelos';
  const poblacionales = datos.slice(3, 6).map(x => nombre(x.tipo) + ' con componente '
    + String(x.componente ?? 'sin componente').toLowerCase()).join(', ') || 'sin datos poblacionales';
  return '## Detalle por caso\n\n'
    + apartado(CASOS[0], paso(p0, g0, d0, 'archivo ONNX', 'especies grandes'),
      '“Registro completo con formato identificado como ONNX” (matriz G050, TC-M04-118; RF-69, restricción 2, línea 1873, y fase 1, líneas 1993-1995).',
      respuesta(p0, g0, d0), por118) + '\n\n'
    + apartado(CASOS[1], paso(p1, g1, d1, 'saved_model.pb', 'especies medianas'),
      '“Registro completo con formato identificado como TensorFlow SavedModel” (matriz G050, TC-M04-119; RF-69, restricción 2, línea 1873, y fase 1, líneas 1993-1995; la matriz exige identificar la firma binaria, no la extensión).',
      respuesta(p1, g1, d1), por119) + '\n\n'
    + apartado(CASOS[2], 'Como servicio interno RF-71, sin actor humano, se enviaron ' + (posts.filter(Boolean).length + (r.respuestas.v2b?.post ? 1 : 0))
        + ' POST para ' + enviados + '; los tipos individual y meta llevaron F1 0,91 y recall 0,93, y '
        + poblacionales + ' llevaron calibración completa, falsos positivos 0,02 y detección 0,96; '
        + (r.respuestas.v2b?.post ? 'tras el rechazo inicial de especies medianas, se registró un reemplazo ONNX con '
          + id(r.respuestas.v2b.post) + '; ' : '')
        + (gets.some(Boolean) ? 'se consultaron los IDs recibidos por GET.' : 'no constan consultas GET.'),
      '“Los seis registros se completan y cada tipo se gestiona de forma independiente” (matriz G050, TC-M04-120; RF-69, actualización RFC-009, línea 1784, y enumerado de seis tipos, líneas 383-389).',
      observados + (r.respuestas.v2b?.post ? '; reemplazo de especies medianas: POST '
        + http(r.respuestas.v2b.post) + ', GET ' + http(r.respuestas.v2b.get)
        + ', ' + id(r.respuestas.v2b.get ?? r.respuestas.v2b.post) : '')
        + '. En los GET poblacionales constan calibración '
        + (gets[3]?.metricas_poblacionales?.calibracion_completada === true ? 'completa' : 'sin confirmar') + ', falsos positivos '
        + (gets[3]?.metricas_poblacionales?.tasa_falsos_positivos_rutina ?? 'sin valor') + ' y detección '
        + (gets[3]?.metricas_poblacionales?.tasa_deteccion_eventos_clinicos ?? 'sin valor') + '.', por120);
}
export function informe(r) {
  const estados = Object.values(r.casos).map(x => x.estado);
  const decision = estados.every(x => x === 'APROBADO') ? 'APROBADO'
    : estados.includes('RECHAZADO') ? 'RECHAZADO'
      : estados.includes('BLOQUEADO') ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
  const tabla = r.comprobaciones.map(x => `| ${x.caso} | ${x.id} | ${x.estado} | ${celda(x.motivo)} |`).join('\n');
  const observados = TIPOS.map((d, i) => {
    const p = r.respuestas.posts[i], g = r.respuestas.gets[i];
    const metricas = d.paradigma === 'POBLACIONAL'
      ? `calibración ${celda(g?.metricas_poblacionales?.calibracion_completada)}, FP ${celda(g?.metricas_poblacionales?.tasa_falsos_positivos_rutina)}, detección ${celda(g?.metricas_poblacionales?.tasa_deteccion_eventos_clinicos)}`
      : `f1 ${celda(g?.f1_score)}, recall ${celda(g?.recall_clase_riesgo_alto)}`;
    return `| V${i + 1} ${d.tipo} | ${celda(g?.id ?? p?.id)} | ${d.formato}; ${d.paradigma}; ${d.componente ?? 'sin componente'} | `
      + `${p?.http ?? 'sin respuesta'} / ${g?.http ?? 'sin GET'} | ${celda(g?.formato_artefacto)}; ${celda(g?.paradigma)}; `
      + `${celda(g?.componente)}; ${celda(g?.estado)} | ${celda(g?.hash_artefacto_sha256)} | ${metricas} |`;
  }).concat(r.respuestas.v2b?.post?.http ? (() => {
    const p = r.respuestas.v2b.post, g = r.respuestas.v2b.get;
    return `| V2b ${TIPOS[1].tipo} | ${celda(g?.id ?? p?.id)} | ONNX; INDIVIDUAL; sin componente | `
      + `${p.http} / ${g?.http ?? 'sin GET'} | ${celda(g?.formato_artefacto)}; ${celda(g?.paradigma)}; `
      + `${celda(g?.componente)}; ${celda(g?.estado)} | ${celda(g?.hash_artefacto_sha256)} | `
      + `f1 ${celda(g?.f1_score)}, recall ${celda(g?.recall_clase_riesgo_alto)} |`;
  })() : []).join('\n');
  const incidencias = r.incidencias.length ? r.incidencias.map(x =>
    `### ${x.id} — ${x.titulo}\n\n- **Caso y equipo inicial:** ${x.caso}; ${x.equipo}. ${x.derivacion}\n`
    + `- **Severidad y certeza:** ${x.severidad}, ${x.certeza}. ${x.sustento_severidad}\n`
    + `- **Requisito:** ${x.requisito}\n- **Precondiciones:** ${x.precondiciones}\n`
    + `- **Pasos:**\n${x.pasos.map((p, i) => `  ${i + 1}. ${p}`).join('\n')}\n- **Esperado:** ${x.esperado}\n`
    + `- **Obtenido:** ${x.obtenido}\n- **Evidencia:** ${x.evidencia.join('; ')}${x.run_id ? `; RUN ${x.run_id}` : ''}\n`
    + `- **Análisis:** ${x.analisis}\n- **Impacto:** ${x.impacto}\n- **Cierre:** ${x.cierre}`).join('\n\n')
    : 'Sin incidencias de producto confirmadas.';
  const solo119 = r.casos[CASOS[0]].estado === 'APROBADO'
    && r.casos[CASOS[1]].estado === 'RECHAZADO'
    && r.casos[CASOS[2]].estado === 'APROBADO'
    && r.respuestas.gets[1]?.formato_artefacto === 'ONNX'
    && r.respuestas.gets[1]?.hash_artefacto_sha256 === r.datos?.versiones?.[1]?.hash;
  const motivoDecision = solo119
    ? 'TC-M04-119: el SavedModel válido se registra con formato ONNX; ONNX y los seis tipos de RFC-009 se registran correctamente'
    : decision === 'APROBADO'
      ? 'Los tres casos cumplen sus oráculos de formato y tipos por API'
      : r.comprobaciones.filter(x => x.estado !== 'APROBADO')
        .map(x => `${x.caso}: ${x.motivo}`).join('; ') || 'Quedan comprobaciones sin resultado';
  const falta = decision === 'APROBADO' ? 'Ninguna comprobación pendiente en este RUN.'
    : solo119 ? 'corrección de INC-M04-G050-119 por Desarrollo y reevaluación V2 autorizada de TC-M04-119.'
      : decision === 'RECHAZADO' ? 'Corregir las incidencias descritas y reevaluar los casos afectados con autorización específica.'
      : 'Resolver el impedimento técnico y repetir con autorización específica.';
  const p119 = r.respuestas.posts[1], g119 = r.respuestas.gets[1];
  const hashFiel119 = !!g119?.hash_artefacto_sha256
    && g119.hash_artefacto_sha256 === r.datos?.versiones?.[1]?.hash;
  const revision = r.revision_qa
    ? `Fecha ${r.revision_qa.fecha}; realizada por ${r.revision_qa.realizada_por}. Motivo: ${r.revision_qa.motivo}. Se corrigió la descripción de formato y hash de TC-M04-119 y se completó la incidencia con requisito, datos observados e hipótesis; no se modificaron veredictos ni evidencias.`
    : 'Informe generado desde las comprobaciones y respuestas de este RUN; sin revisión posterior registrada.';
  return `# TC-M04-G050 — ${decision}\n\n## Decisión del caso\n\nCaso agrupado TC-M04-G050 (RF-69); originales TC-M04-118, TC-M04-119 y TC-M04-120. Decisión: ${decision}. Motivo: ${motivoDecision}.\n\n| Caso | Comprobación | Decisión | Motivo breve |\n|---|---|---|---|\n${tabla}\n\nRUN oficial: ${r.oficial ? `sí (registro QA OFICIAL, DELETE ${r.cierre.run.cierre_http ?? 'sin respuesta'}, rollback ${r.cierre.rollback.verificado ? 'confirmado' : 'no confirmado'})` : 'no; faltan comprobaciones o cierre'}.\n\nQué falta: ${falta}\n\n${detallePorCaso(r)}\n\n## Identificación\n\nGrupo G050; casos TC-M04-118, TC-M04-119 y TC-M04-120; RF-69 v2.1; versión V${r.version}; RUN ${r.run_id}; ambiente ${r.ambiente}; autorización ${celda(r.autorizacion)}; referencia de código origin/test daefc3a5 (despliegue no verificado); Newman ${r.preflight_herramientas.newman?.version ?? 'no verificado'}; Cypress no requerido (solo API).\n\n## Esperado vs observado por caso\n\n- **TC-M04-118 / API-118-01:** Esperado de matriz: “Registro completo con formato identificado como ONNX”. Observado: POST ${r.respuestas.posts[0]?.http ?? 'sin respuesta'}, GET ${r.respuestas.gets[0]?.http ?? 'sin GET'}, formato_artefacto ${celda(r.respuestas.gets[0]?.formato_artefacto)}, hash ${r.respuestas.gets[0]?.hash_artefacto_sha256 === r.datos?.versiones?.[0]?.hash ? 'fiel' : 'no confirmado'}. Decisión ${r.casos[CASOS[0]].estado}.\n- **TC-M04-119 / API-119-01:** Esperado de matriz: “Registro completo con formato identificado como TensorFlow SavedModel”. Observado: POST ${p119?.http ?? 'sin respuesta'}, id ${celda(p119?.id)}, estado ${celda(p119?.estado)}; GET ${g119?.http ?? 'sin GET'}, formato_artefacto ${celda(g119?.formato_artefacto)}, hash ${hashFiel119 ? 'fiel al enviado' : 'no confirmado'}. Decisión ${r.casos[CASOS[1]].estado}.\n- **TC-M04-120 / API-120-01:** Esperado de matriz: “Los seis registros se completan y cada tipo se gestiona de forma independiente”. Observado: ${r.respuestas.posts.filter(x => x?.http === 201).length} POST 201 y ${r.respuestas.gets.filter(x => x?.http === 200).length} GET 200 de los seis tipos; paradigmas, componentes y métricas detallados abajo. Decisión ${r.casos[CASOS[2]].estado}.\n\n| Versión y tipo | ID | Esperado | HTTP POST / GET | GET observado: formato; paradigma; componente; estado | Hash GET | Métricas GET |\n|---|---|---|---|---|---|---|\n${observados}\n\n## Observaciones\n\nSe envió saved_model.pb como binario único porque el API admite un único archivo_modelo; no se comprobó la carga del directorio SavedModel en un runtime TensorFlow. Los hashes enviados y consultados constan en resultado.json y Newman JSON. ${r.respuestas.v2b?.post?.http ? 'V2b se creó con ONNX y un nuevo id_proceso_rf71 porque V2 fue rechazado por el artefacto; API-120-01 usa V2b para MEDIANAS.' : 'V2b no fue necesario porque V2 se registró; API-120-01 usa V2 para MEDIANAS.'} Para POBLACIONAL, el código origin/test consultado solo usa calibracion_completada para aprobar; no define umbral de aprobación para las tasas 0.02 y 0.96.\n\n## Incidencias de producto\n\n${incidencias}\n\n## Problemas técnicos y análisis\n\n${r.problemas_tecnicos.length ? r.problemas_tecnicos.map(x => `- ${celda(x)}`).join('\n') : 'Sin problemas técnicos observados.'} La hipótesis de código local no demuestra la causa raíz en TEST.\n\n## Cierre y rollback\n\nDELETE RUN HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. ${r.cierre.rollback.verificado ? 'Cierre de la transacción externa confirmado' : 'Rollback de BD no confirmado'}: ${celda(r.cierre.rollback.motivo)}. La eliminación de archivos en MODELOS_STORAGE_PATH y de posibles respaldos RF-73 no se verificó.\n\n## Revisión QA\n\n${revision}\n\n## Evidencias\n\n${r.evidencias.map(x => `- ${x}`).join('\n') || 'Sin evidencias registradas.'}\n\n## Conclusión y acción\n\n${decision}. Acción pendiente: ${falta}\n`;
}
function finalizar(c, r, secretos) {
  const nombre = r.version === 1 ? 'TC-M04-G050_resultado.md' : `TC-M04-G050_reevaluacion_V${r.version}.md`;
  r.evidencias = [...new Set([...r.evidencias, nombre, 'resultado.json'])];
  const completos = r.comprobaciones.every(x => ['APROBADO', 'RECHAZADO'].includes(x.estado)
    && x.evidencia && r.evidencias.includes(x.evidencia));
  r.oficial = completos && r.cierre.run.cierre_http === 200 && r.cierre.rollback.verificado
    && r.problemas_tecnicos.length === 0 && r.evidencias.filter(x => ![nombre, 'resultado.json'].includes(x))
      .every(x => fs.existsSync(path.join(c.directorio, x)));
  r.consume_version = r.oficial;
  fs.writeFileSync(path.join(c.directorio, nombre), sanearArtefacto(informe(r), secretos), 'utf8');
  guardar(path.join(c.directorio, 'resultado.json'),
    JSON.parse(sanearArtefacto(JSON.stringify(r), secretos)));
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
    temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g050-newman-'));
    const archivos = [path.join(DIR, 'artefactos/g050.onnx'), path.join(DIR, 'artefactos/saved_model.pb')];
    const hashes = archivos.map(x => sha256(fs.readFileSync(x)));
    const versiones = TIPOS.map((d, i) => ({ ...d, archivo: archivos[i === 1 ? 1 : 0],
      hash: hashes[i === 1 ? 1 : 0], proceso: crypto.randomUUID(),
      metricas: d.paradigma === 'POBLACIONAL' ? POBLACIONAL : INDIVIDUAL }));
    const version2b = { ...TIPOS[1], formato: 'ONNX', archivo: archivos[0],
      hash: hashes[0], proceso: crypto.randomUUID(), metricas: INDIVIDUAL };
    const datos = { token, versiones, version2b, datasetHash: sha256(Buffer.from('G050 dataset QA RF-71')),
      fecha: new Date(Date.now() - 86400000).toISOString(), variables: [variable.id_variable_ambiental] };
    r.datos = { versiones: versiones.map(({ tipo, paradigma, formato, componente, hash, proceso, metricas }) =>
      ({ tipo, paradigma, formato, componente, hash, proceso, metricas })),
    version2b: { tipo: version2b.tipo, paradigma: version2b.paradigma,
      formato: version2b.formato, hash: version2b.hash, proceso: version2b.proceso,
      metricas: version2b.metricas },
    dataset_hash: datos.datasetHash, fecha_entrenamiento: datos.fecha,
    compatibilidad_variables: datos.variables };
    const n = await ejecutarNewman(c, api, env, datos, secretos, temporal);
    r.evidencias.push(...n.artefactos);
    if (!n.artefactos.length || n.salida.error || n.fallos.some(f =>
      /SyntaxError|ReferenceError|TypeError|AssertionError/.test(f.name)))
      throw Error(`NEWMAN_TECNICO:${n.salida.error ?? n.fallos.map(x => x.name).join(',')}`);
    const posts = TIPOS.map((_, i) => n.respuestas.find(x => x.nombre === `API-G050-POST-V${i + 1}`));
    const gets = TIPOS.map((_, i) => n.respuestas.find(x => x.nombre === `API-G050-GET-V${i + 1}`));
    const post2b = n.respuestas.find(x => x.nombre === 'API-G050-POST-V2b');
    const get2b = n.respuestas.find(x => x.nombre === 'API-G050-GET-V2b');
    r.respuestas = { posts: posts.map(resumir), gets: gets.map(resumir),
      v2b: post2b?.http ? { post: resumir(post2b), get: resumir(get2b) } : null };
    const primerBloqueo = posts.findIndex(x => x?.http === 403 || x?.http >= 500);
    const evals = TIPOS.map((d, i) => !posts[i]?.http && primerBloqueo >= 0 && i > primerBloqueo
      ? { estado: 'BLOQUEADO', motivo: `Escenario detenido tras POST V${primerBloqueo + 1} HTTP ${posts[primerBloqueo].http}` }
      : evaluarRegistro(posts[i], gets[i], d));
    const formato = i => {
      const e = evals[i], p = posts[i], g = gets[i], d = versiones[i];
      if (e.estado !== 'APROBADO') return e;
      if (g.cuerpo.formato_artefacto !== d.formato || g.cuerpo.hash_artefacto_sha256 !== d.hash) {
        const partes = [];
        if (g.cuerpo.formato_artefacto !== d.formato)
          partes.push(`formato_artefacto ${g.cuerpo.formato_artefacto ?? 'nulo'} en lugar de ${d.formato}`);
        partes.push(g.cuerpo.hash_artefacto_sha256 === d.hash ? 'hash fiel' : 'hash divergente');
        return { estado: 'RECHAZADO', motivo: partes.join('; ') };
      }
      return { estado: 'APROBADO', motivo: `POST 201; GET ${d.formato} y hash SHA-256 fiel` };
    };
    for (const [k, idx] of [0, 1].entries()) {
      const x = formato(idx); asignar(r, k, x.estado, x.motivo,
        { post: r.respuestas.posts[idx], get: r.respuestas.gets[idx], hash_enviado: versiones[idx].hash },
        n.artefactos.length ? 'newman/newman-G050.json' : null);
    }
    const rechazoArtefactoV2 = posts[1]?.http >= 400 && posts[1]?.http < 500
      && idVersion(posts[1]?.cuerpo) == null
      && /FORMATO|ARTEFACTO/i.test(JSON.stringify(posts[1]?.error ?? {}));
    const usadosGet = [...gets], usadosDatos = [...versiones];
    if (rechazoArtefactoV2) {
      usadosGet[1] = get2b;
      usadosDatos[1] = version2b;
    }
    const evals120 = TIPOS.map((d, i) => rechazoArtefactoV2 && i === 1 && !post2b?.http
      ? { estado: 'NO_CONCLUYENTE', motivo: 'V2b ONNX no se ejecutó tras rechazo de formato V2' }
      : i === 1 && rechazoArtefactoV2 ? evaluarRegistro(post2b, get2b, version2b) : evals[i]);
    const tecnico = evals120.find(x => ['BLOQUEADO', 'NO_CONCLUYENTE'].includes(x.estado));
    const defectos = evals120.map((x, i) => ({ ...x, i })).filter(x => x.estado === 'RECHAZADO'
      || (x.estado === 'APROBADO' && !metricasIguales(usadosGet[x.i].cuerpo, usadosDatos[x.i])));
    let estado120, motivo120;
    if (tecnico) { estado120 = tecnico.estado; motivo120 = `No se verificaron seis registros: ${tecnico.motivo}`; }
    else if (defectos.length) { estado120 = 'RECHAZADO';
      motivo120 = `Tipos/metricas divergentes en V${defectos.map(x => x.i + 1).join(', V')}`; }
    else { estado120 = 'APROBADO'; motivo120 = 'Seis tipos con POST 201 y GET, paradigmas, componentes y métricas independientes'; }
    asignar(r, 2, estado120, motivo120,
      usadosGet.map((x, i) => { const g = resumir(x); return { version: i === 1 && rechazoArtefactoV2 ? '2b' : i + 1, tipo: g?.tipo_modelo,
        paradigma: g?.paradigma, componente: g?.componente, metricas_poblacionales: g?.metricas_poblacionales }; }),
      n.artefactos.length ? 'newman/newman-G050.json' : null);
    const t119 = r.casos[CASOS[1]].estado === 'RECHAZADO';
    if (r.casos[CASOS[0]].estado === 'RECHAZADO') r.incidencias.push(incidencia(CASOS[0],
      'INC-M04-G050-118', 'ONNX no registrado o formato/hash divergente',
      'POST 201 y GET ONNX con hash fiel', r.casos[CASOS[0]].motivo,
      ['newman/newman-G050.json', 'resultado.json']));
    if (t119) r.incidencias.push(incidencia119(r, r.respuestas.posts[1],
      r.respuestas.gets[1], versiones[1].hash, !!r.respuestas.v2b?.post?.http));
    if (estado120 === 'RECHAZADO') {
      if (defectos.length) r.incidencias.push(incidencia(CASOS[2], 'INC-M04-G050-120',
        'Tipo, paradigma, componente o métricas de modelo divergentes',
        'Seis tipos independientes con métricas de su paradigma', motivo120,
        ['newman/newman-G050.json', 'resultado.json'], defectos.some(x => x.estado === 'RECHAZADO') ? 'ALTA' : 'MEDIA'));
    }
    if ([...posts, post2b, ...gets, get2b].some(x => x?.http === 403))
      r.problemas_tecnicos.push('HTTP_403_CLAVE_O_PERMISO_SIN_REINTENTO');
    if ([...posts, post2b, ...gets, get2b].some(x => x?.http >= 500))
      r.problemas_tecnicos.push('HTTP_5XX_ENTORNO');
    if (posts.some(x => !x?.http) || gets.some((x, i) => posts[i]?.http === 201 && !x?.http)
      || (post2b?.http === 201 && !get2b?.http))
      r.problemas_tecnicos.push('SIN_RESPUESTA_O_GET_OMITIDO');
    return r;
  } catch (e) {
    const motivo = limpio(e.message); r.problemas_tecnicos.push(motivo);
    const tipo = /5XX|_5\d\d|403|CATALOGO|LOGIN/.test(motivo) ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
    CASOS.forEach((caso, i) => { if (r.casos[caso].motivo === 'Sin comprobación') asignar(r, i, tipo, motivo); });
    return r;
  } finally {
    if (tocado) try {
      const x = await pedir(api, 'DELETE', `/test-control/runs/${encodeURIComponent(c.runId)}`,
        { secreto: env.QA_SANDBOX_SECRET, bitacora: r.bitacora });
      r.cierre.run.cierre_http = x.http; r.cierre.rollback.verificado = x.http === 200;
      r.cierre.rollback.motivo = x.http === 200
        ? 'Transacción externa cerrada; archivos y respaldo local fuera de rollback'
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
    const c = contextoEjecucion(process.argv.slice(2), { grupo: 'G050', casos: CASOS, directorio: DIR });
    const r = await evaluar(c, { env: leerEnv() });
    console.log(JSON.stringify({ run_id: r.run_id, casos: r.casos, oficial: r.oficial }));
    if (!r.oficial) process.exitCode = 2;
  } catch (e) { console.error(`G050: ${limpio(e.message)}`); process.exitCode = 2; }
}
