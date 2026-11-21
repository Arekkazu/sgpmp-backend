#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';
import { sanearArtefacto, contieneMojibake } from './lib/seguridad.mjs';
import { CASOS, IDS, CAPACIDADES, PRESUPUESTO, ORACULOS, ruta,
  clasificarExportacion, clasificarVolumen } from './lib/g124_escenario.mjs';
import { validarPdf, validarExcel } from './validadores.mjs';

const require = createRequire(import.meta.url);
const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const COLECCION = path.join(DIR, 'G124.postman_collection.json');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const BACKEND = 'origin/test 254deee6f3d3cb68bd14a76aabdac8fa4afae3fd consultado; commit desplegado en TEST no verificado';
const ARCHIVOS = ['g124.mjs', 'G124.postman_collection.json', 'validadores.mjs', 'README.md',
  'lib/contrato_ejecutor.mjs', 'lib/seguridad.mjs', 'lib/g124_escenario.mjs',
  'pruebas/registro_qa.mjs', 'pruebas/fixtures.mjs', 'pruebas/g124_ensayo.mjs', 'pruebas/g124.test.mjs'];
const json = (p, x) => fs.writeFileSync(p, JSON.stringify(x, null, 2), 'utf8');

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
    const entrada = String(process.env.PATH ?? '').split(path.delimiter)
      .map(p => path.join(p, 'node_modules', 'newman', 'package.json')).find(fs.existsSync);
    if (!entrada) throw Error('NEWMAN_NO_RESUELTO');
    return path.dirname(entrada);
  }
}
function validarNewman(ensayo = false) {
  try {
    const paquete = newmanPaquete();
    const manifest = require(path.join(paquete, 'package.json'));
    if (ensayo) return { ok: typeof require(paquete).run === 'function', version: manifest.version,
      error: null, modo: 'paquete en proceso; CLI no disponible en sandbox local' };
    const bin = path.join(paquete, manifest.bin.newman);
    const prueba = spawnSync(process.execPath, [bin, '--version'], { timeout: 30000, encoding: 'utf8' });
    return { ok: prueba.status === 0 && !!prueba.stdout.trim(), version: prueba.stdout.trim(),
      error: prueba.error?.code ?? null };
  } catch (e) { return { ok: false, version: null, error: e.code ?? e.message }; }
}
export function preflight(c, env, ensayo = false) {
  const base = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const barreras = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_PROD_EMAIL', 'QA_PROD_PASSWORD']
    .filter(k => !String(env[k] ?? '').trim());
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base) : base !== API) barreras.push('API_NO_CANONICA');
  if (c.version > 1 && c.operacion !== 'reevaluar') barreras.push('REEVALUACION_SIN_DECISION');
  if (c.operacion === 'recuperar') barreras.push('RECUPERACION_NO_IMPLEMENTADA');
  return { fase: 'PREFLIGHT_LOCAL', grupo: 'G124', run_id: c.runId, version: c.version,
    barreras, presupuesto: PRESUPUESTO, efectos_declarados: [
      'login_productor_fuera_RUN_puede_persistir_sesion_o_auditoria',
      'GET_historial_y_exportaciones_pueden_registrar_auditoria_fuera_RUN',
      'GET_dashboard_puede_registrar_auditoria_y_enviar_correo_sin_umbral',
      'DELETE_RUN_sin_escrituras_de_escenario'], ok: barreras.length === 0 };
}
export function comprobar() {
  let sintaxis = false;
  try {
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const e of col.item.flatMap(i => i.event ?? [])) new vm.Script((e.script?.exec ?? []).join('\n'));
    sintaxis = col.item.length === 3 && col.item.every(x => x.request.method === 'GET')
      && col.item[0].name === 'API-G124-HISTORIAL' && col.item[1].name === 'API-G124-PDF'
      && col.item[2].name === 'API-G124-EXCEL' && !contieneMojibake(JSON.stringify(col));
  } catch { /* comprobación reporta sintaxis=false */ }
  const presentes = fs.readdirSync(DIR).filter(x => !['lib', 'pruebas', 'Resultados', 'EvaluacionV2'].includes(x))
    .concat(...['lib', 'pruebas'].map(d => fs.readdirSync(path.join(DIR, d)).map(x => `${d}/${x}`)));
  const faltantes = ARCHIVOS.filter(x => !fs.existsSync(path.join(DIR, x)));
  const inesperados = presentes.filter(x => !ARCHIVOS.includes(x));
  const markdownSuperior = fs.existsSync(path.join(DIR, 'Resultados'))
    && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const ok = sintaxis && !faltantes.length && !inesperados.length && !markdownSuperior;
  console.log(JSON.stringify({ grupo: 'G124', ok, sintaxis, faltantes, inesperados, markdownSuperior,
    presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}
function errorPublico(bytes) {
  let cuerpo;
  try { cuerpo = JSON.parse(bytes.toString('utf8')); } catch { return { codigo: null, mensaje: null }; }
  const d = cuerpo?.detail && typeof cuerpo.detail === 'object' && !Array.isArray(cuerpo.detail)
    ? cuerpo.detail : cuerpo;
  const seguro = x => typeof x === 'string' ? x.slice(0, 300) : null;
  return { codigo: seguro(d?.error_code ?? d?.code ?? d?.codigo),
    mensaje: seguro(d?.message ?? d?.mensaje ?? d?.error ?? (typeof cuerpo?.detail === 'string' ? cuerpo.detail : null)) };
}
function bytesDe(ex) {
  const stream = ex?.response?.stream;
  return Buffer.from(stream?.data ?? (Array.isArray(stream) ? stream : []));
}
function extracto(ex, runId) {
  if (!ex) return { http: null, eco: false, bytes: Buffer.alloc(0), error: null, contentType: null };
  const headers = ex.response?.header ?? [];
  const campo = n => headers.find(h => String(h.key).toLowerCase() === n)?.value ?? null;
  const bytes = bytesDe(ex), http = ex.response?.code ?? null;
  return { http, eco: campo('x-test-run-id') === runId, bytes,
    error: http >= 400 ? errorPublico(bytes) : null, contentType: campo('content-type') };
}
async function pedir(api, metodo, rutaApi, { cuerpo, token, secreto, runId, bitacora, presupuesto,
  timeout = PRESUPUESTO.timeout_ms, cierre = false } = {}) {
  presupuesto.directas++;
  if (presupuesto.directas > PRESUPUESTO.solicitudes_directas - (cierre ? 0 : PRESUPUESTO.margen_cierre))
    throw Error('PRESUPUESTO_DIRECTO_EXCEDIDO');
  if (!cierre && Date.now() - presupuesto.inicio > (PRESUPUESTO.duracion_segundos - 60) * 1000)
    throw Error('PRESUPUESTO_TIEMPO_EXCEDIDO');
  let http = null, eco = null;
  try {
    const x = await fetch(api + rutaApi, { method: metodo, redirect: 'manual',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(secreto ? { 'X-Sandbox-Secret': secreto } : {}),
        ...(runId ? { 'X-Test-Run-Id': runId, 'X-Zona-Horaria': 'UTC' } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined, signal: AbortSignal.timeout(timeout) });
    http = x.status;
    eco = runId ? x.headers.get('x-test-run-id') === runId : null;
    return { http, eco, cuerpo: await x.json().catch(() => null) };
  } finally { bitacora.push({ metodo, ruta: rutaApi, http, eco, en_run: !!runId }); }
}
const fechaUTC = ms => new Date(ms).toISOString().slice(0, 10);
const rango = (finMs, dias) => ({ inicio: fechaUTC(finMs - dias * 86400000), fin: fechaUTC(finMs) });
export async function seleccionarConsulta(api, token, env, c, r, presupuesto, ahora = Date.now()) {
  const diag = r.diagnostico_seleccion = { modo: 'seleccion_automatica', intentos: [],
    unidades: [], sensores_dashboard: 0, alcance_incompleto: false, seleccion: null };
  const h = { token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, bitacora: r.bitacora,
    presupuesto, timeout: PRESUPUESTO.timeout_seleccion_ms };
  const consultar = async (paso, rutaApi) => {
    const x = await pedir(api, 'GET', rutaApi, h);
    if (x.http !== 200 || !x.eco) throw Error(`ERROR_QA_SELECCION_${paso}_HTTP_${x.http}_ECO_${x.eco}`);
    return x.cuerpo;
  };
  const historial = async (sensorId, fechas, fuente) => {
    const s = { sensorId, ...fechas };
    const cuerpo = await consultar('HISTORIAL', ruta('historial', s));
    if (!Number.isSafeInteger(cuerpo?.total) || cuerpo.total < 0 || !Array.isArray(cuerpo.items))
      throw Error('ERROR_QA_SELECCION_CONTRATO_HISTORIAL');
    const valido = cuerpo.total > 0 && cuerpo.items.some(x => Number(x?.id_sensor) === sensorId);
    diag.intentos.push({ fuente, sensor_id: sensorId, inicio: s.inicio, fin: s.fin,
      total: cuerpo.total, muestra_sensor: valido, http: 200, eco: true });
    if (cuerpo.total > 0 && !valido) throw Error('ERROR_QA_SELECCION_SENSOR_NO_COINCIDE');
    if (valido) diag.seleccion = { fuente, sensor_id: sensorId, inicio: s.inicio, fin: s.fin,
      total: cuerpo.total };
    return valido ? s : null;
  };
  for (const dias of [7, 30]) {
    const s = await historial(6, rango(ahora, dias), `sensor_6_${dias}_dias`);
    if (s) return s;
  }
  const global = await consultar('DASHBOARD_GLOBAL', '/iot/monitoreo/dashboard?pagina=1&por_pagina=50');
  if (!Array.isArray(global?.resumen_unidades) || !Array.isArray(global?.sensores))
    throw Error('ERROR_QA_SELECCION_CONTRATO_DASHBOARD_GLOBAL');
  const visibles = [...global.resumen_unidades, ...global.sensores]
    .map(x => Number(x?.id_infraestructura))
    .filter(x => Number.isSafeInteger(x) && x > 0);
  const unidades = [...new Set([...PRESUPUESTO.unidades_conocidas, ...visibles])];
  if (unidades.length > PRESUPUESTO.unidades_dashboard || global.total > global.sensores.length)
    diag.alcance_incompleto = true;
  const vistos = new Set([6]);
  for (const unidad of unidades.slice(0, PRESUPUESTO.unidades_dashboard)) {
    const rutaDash = `/iot/monitoreo/dashboard/${unidad}?pagina=1&por_pagina=50`;
    const x = await pedir(api, 'GET', rutaDash, h);
    diag.unidades.push({ id_infraestructura: unidad, http: x.http, eco: x.eco,
      sensores: Array.isArray(x.cuerpo?.sensores) ? x.cuerpo.sensores.length : null });
    if (x.http === 404 && x.eco) continue;
    if (x.http !== 200 || !x.eco || !Array.isArray(x.cuerpo?.sensores))
      throw Error(`ERROR_QA_SELECCION_DASHBOARD_HTTP_${x.http}_ECO_${x.eco}`);
    if (x.cuerpo.total > x.cuerpo.sensores.length) diag.alcance_incompleto = true;
    for (const sensor of x.cuerpo.sensores) {
      const id = Number(sensor?.id_sensor);
      if (!Number.isSafeInteger(id) || id <= 0 || vistos.has(id)) continue;
      if (diag.sensores_dashboard >= PRESUPUESTO.historiales_descubrimiento) {
        diag.alcance_incompleto = true; break;
      }
      vistos.add(id); diag.sensores_dashboard++;
      const captura = Date.parse(sensor?.ultimo_timestamp_captura);
      const fin = Number.isFinite(captura) && captura < ahora - 30 * 86400000 ? captura : ahora;
      const s = await historial(id, rango(fin, fin === ahora ? 30 : 7), `dashboard_unidad_${unidad}`);
      if (s) return s;
    }
    if (diag.sensores_dashboard >= PRESUPUESTO.historiales_descubrimiento) break;
  }
  return null;
}
async function ejecutarNewman(c, api, token, env, s, secretos, presupuesto) {
  if (presupuesto.newman + 3 > PRESUPUESTO.solicitudes_newman) throw Error('PRESUPUESTO_NEWMAN_EXCEDIDO');
  const restante = PRESUPUESTO.duracion_segundos * 1000 - (Date.now() - presupuesto.inicio)
    - PRESUPUESTO.timeout_ms;
  if (restante < PRESUPUESTO.timeout_ms) throw Error('PRESUPUESTO_TIEMPO_EXCEDIDO');
  presupuesto.newman += 3;
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'g124-newman-'));
  try {
    const bruto = path.join(temp, 'newman.json');
    const variables = { autorizado_run: 'SI', ensayo_loopback: c.ensayo ? 'SI' : 'NO', base_url: api,
      run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET, token,
      fecha_inicio: s.inicio, fecha_fin: s.fin, sensor_id: String(s.sensorId), semilla_ok: 'NO' };
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    const p = await new Promise(resolve => require(newmanPaquete()).run({ collection: col,
      environment: { values: Object.entries(variables).map(([key, value]) => ({ key, value, enabled: true })) },
      reporters: ['json'], reporter: { json: { export: bruto } }, timeoutRequest: PRESUPUESTO.timeout_ms,
      timeout: restante, color: 'off' },
    (error, summary) => resolve({ error: error?.message ?? null,
      status: error ? null : summary?.run?.failures?.length ? 1 : 0 })));
    if (!fs.existsSync(bruto)) return { proceso: p, error: 'SIN_REPORTE_NEWMAN', artefactos: [],
      respuestas: {}, fallos: [] };
    const original = JSON.parse(fs.readFileSync(bruto, 'utf8'));
    const fallos = (original.run?.failures ?? []).map(f => ({ name: String(f.error?.name ?? ''),
      test: String(f.error?.test ?? ''), source: String(f.source?.name ?? ''),
      mensaje: String(f.error?.message ?? '').slice(0, 150) }));
    const respuestas = {};
    const publicas = (original.run?.executions ?? []).map(ex => {
      const nombre = ex.item?.name ?? 'DESCONOCIDO', x = extracto(ex, c.runId);
      respuestas[nombre] = x;
      return { nombre, metodo: 'GET', http: x.http, eco: x.eco, content_type: x.contentType,
        bytes: x.bytes.length, sha256: x.bytes.length ? createHash('sha256').update(x.bytes).digest('hex') : null,
        error: x.error };
    });
    const salida = path.join(c.directorio, 'newman'); fs.mkdirSync(salida, { recursive: true });
    const artefactos = ['newman/newman-G124.json', 'newman/newman-G124.html'];
    json(path.join(c.directorio, artefactos[0]), JSON.parse(sanearArtefacto(JSON.stringify({
      info: { nombre: 'Newman G124', generado: true, saneado: true },
      run: { stats: original.run?.stats ?? null, timings: original.run?.timings ?? null,
        executions: publicas, failures: fallos },
    }), secretos)));
    const filas = publicas.map(x => `<tr><td>${x.nombre}</td><td>${x.http ?? 'sin respuesta'}</td><td>${x.eco}</td><td>${x.bytes}</td></tr>`).join('');
    fs.writeFileSync(path.join(c.directorio, artefactos[1]),
      `<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G124</title><h1>Newman G124</h1><table><tr><th>GET</th><th>HTTP</th><th>Eco</th><th>Bytes</th></tr>${filas}</table></html>`, 'utf8');
    return { proceso: p, error: null, artefactos, respuestas, fallos };
  } finally {
    if (!path.resolve(temp).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
    fs.rmSync(temp, { recursive: true, force: true });
  }
}

const textoSeguro = x => String(x ?? '').replaceAll('|', '/').replace(/[\r\n]+/g, ' ').slice(0, 500);
export function informe(r) {
  const estados = CASOS.map(c => r.casos[c].estado);
  const decision = estados.includes('RECHAZADO') ? 'RECHAZADO' : estados.every(x => x === 'BLOQUEADO')
    ? 'BLOQUEADO' : estados.every(x => x === 'APROBADO') ? 'APROBADO' : 'NO_CONCLUYENTE';
  const tabla = CASOS.map((caso, i) => `| ${caso} | ${IDS[i]} | API | ${r.casos[caso].estado} | ${textoSeguro(ORACULOS[caso])} | ${textoSeguro(r.casos[caso].motivo)} | ${r.comprobaciones[i].evidencia ?? 'sin evidencia'} |`).join('\n');
  const incidencias = CASOS.filter(caso => r.ambiente === 'TEST' && r.casos[caso].estado === 'RECHAZADO'
    && r.comprobaciones.find(x => x.caso === caso)?.evidencia).map(caso => {
    const c = r.casos[caso], x = r.comprobaciones.find(z => z.caso === caso);
    return `### INC-M03-${caso.slice(-3)}-G124-01\n\n- **Certeza:** CONFIRMADA para la discrepancia pública; causa raíz NO DETERMINADA. Identificador de informe, no ticket definitivo.\n- **Equipo inicial:** Desarrollo. La primera discrepancia comprobada está en la respuesta pública de exportación; no se atribuye causa técnica.\n- **Severidad:** ALTA; falla una exportación relevante sin alternativa demostrada para el formato.\n- **Requisito:** RF-59 CA-10/CA-11 y E5; matriz TC-M03-G124.\n- **Precondiciones y pasos:** Productor autenticado; historial con resultados del sensor y rango acotado; GET exportar ${caso === 'TC-M03-249' ? 'PDF' : 'EXCEL'} dentro del RUN.\n- **Esperado:** ${ORACULOS[caso]}\n- **Observado:** ${textoSeguro(c.motivo)}.\n- **Evidencia:** ${x.evidencia}, resultado.json en este RUN.\n- **Análisis:** origin/test orienta la comprobación; no demuestra el commit desplegado ni la causa raíz.\n- **Cierre:** Desarrollo debe revisar la discrepancia pública; QA repetirá con autorización de reevaluación.`;
  }).join('\n\n') || 'Ninguna discrepancia de producto confirmada en TEST.';
  return `# TC-M03-G124 — ${decision}\n\n## Decisión del caso\n\n${CASOS.map(c => `${c}: **${r.casos[c].estado}**${r.casos[c].subtipo ? ` (${r.casos[c].subtipo})` : ''} — ${textoSeguro(r.casos[c].motivo)}.`).join('\n\n')}\n\n## Identificación\n\nGrupo G124; RF-59/CU04; versión V${r.version}; RUN ${r.run_id}; ambiente ${r.ambiente}; autorización ${r.autorizacion}; commit TEST ${r.commit_test ?? 'no verificado'}; referencia de código ${BACKEND}; Newman ${r.preflight_herramientas.newman?.version ?? 'no verificado'}; Cypress no requerido (API solamente), 0 ejecuciones. Clasificación del registro: ${r.oficial ? 'OFICIAL' : 'TÉCNICO'}; consume versión: ${r.consume_version}.\n\n## Esperado y observado por caso\n\n| Caso | Comprobación | Fuente | Estado | Esperado | Observado | Evidencia |\n| --- | --- | --- | --- | --- | --- | --- |\n${tabla}\n\n## Dependencia M08\n\nRF-59 precondición 8 (Especificacion-Requerimientos-Modulo3.md:5654-5655) requiere generadores funcionales RF-10 de M08. La matriz TC-M03-G124:184-193 anota 503 M08_NO_DISPONIBLE como bloqueo esperado para 249/250 sin alterar los archivos esperados. RF-59 CA-10:6263-6264 y CA-11:6266-6267 conservan el oráculo PDF/Excel. La restricción 13:5703-5716 fija los umbrales y la matriz exige fragmentación. La matriz atribuye esto a CU04 FA-10, pero las anotaciones disponibles cu04_gaps_bd_rf58_rf59.md:92 y curls_m03_cu04_monitoreo_historial.md:317 describen FA-10 como truncado de consultas de 10.000, no fragmentación de exportación; aclaración documental pendiente de QA. FA-11 se refleja en api_reference_m03_telemetria_iot.md:559-567 (400 EXPORTAR_SIN_FILTROS). Si M08 no genera archivos, 254 tampoco puede acreditar los cuatro umbrales. La decisión final de bloqueo corresponde al responsable QA.\n\n## Comprobaciones API/UI y evidencias\n\nConsulta elegida: ${JSON.stringify(r.semilla)}. Diagnóstico saneado de selección: ${JSON.stringify(r.diagnostico_seleccion)}. Respuestas saneadas: ${JSON.stringify(r.respuestas)}. Comprobaciones API: ${r.comprobaciones.map(x => `${x.id}=${x.estado}`).join(', ')}. UI no obligatoria, 0 ejecuciones. Evidencias reales en este RUN: ${r.evidencias.join(', ') || 'ninguna'}.\n\n## Incidencias de producto\n\n${incidencias}\n\n## Incidencias técnicas QA\n\n${r.problemas_tecnicos.join('; ') || 'Ninguna.'}\n\n## Análisis de causas y observaciones\n\nLa referencia origin/test no confirma la versión desplegada. Un fallo de Newman, petición, permisos o transporte se separa de las respuestas públicas. RF-59 E5:6056-6068 exige aviso, sugerencia de reducir rango/filtros, bitácora técnica y datos visibles; API sola no acredita toda la interfaz. No se ejecutaron volúmenes masivos ni exportaciones concurrentes.\n\n## Cierre y rollback\n\nLogin Productor antes del RUN y los GET pueden registrar sesión o auditoría persistente. No hubo escrituras de escenario. DELETE RUN HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. Rollback ${r.cierre.rollback.verificado ? 'verificado por ausencia de escrituras de escenario y cierre 200' : 'NO verificado'}: ${r.cierre.rollback.motivo}.\n\n## Conclusión y próxima acción\n\n${decision}. ${r.oficial ? 'Conservar evidencia y derivar incidencias confirmadas.' : 'Responsable QA debe revisar la dependencia o la incidencia técnica y decidir un intento autorizado cuando M08 esté disponible.'}\n`;
}
function finalizar(c, r, secretos) {
  const nombre = c.version === 1 ? 'TC-M03-G124_resultado.md' : `TC-M03-G124_reevaluacion_V${c.version}.md`;
  r.evidencias = [...new Set([...r.evidencias, 'resultado.json', nombre])];
  const archivosOk = r.evidencias.filter(x => !['resultado.json', nombre].includes(x))
    .every(x => fs.existsSync(path.join(c.directorio, x)));
  r.oficial = Object.values(r.casos).every(x => ['APROBADO', 'RECHAZADO'].includes(x.estado))
    && r.comprobaciones.every(x => ['APROBADO', 'RECHAZADO'].includes(x.estado) && !!x.evidencia)
    && r.cierre.run.cierre_http === 200 && r.cierre.rollback.verificado && archivosOk
    && r.problemas_tecnicos.length === 0;
  r.consume_version = r.oficial;
  fs.writeFileSync(path.join(c.directorio, nombre), sanearArtefacto(informe(r), secretos), 'utf8');
  json(path.join(c.directorio, 'resultado.json'), JSON.parse(sanearArtefacto(JSON.stringify(r), secretos)));
}

export async function evaluar(c, { env, ensayo = false }) {
  if (!fs.existsSync(c.directorio)) throw Error('RUN_NO_CREADO_POR_LANZADOR');
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G124', run_id: c.runId, version: c.version, operacion: c.operacion,
    autorizacion: c.referencia, ambiente: ensayo ? 'LOOPBACK_LOCAL' : 'TEST', oficial: false,
    consume_version: false, casos: Object.fromEntries(CASOS.map(x => [x, { estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación' }])),
    comprobaciones: CASOS.map((caso, i) => ({ caso, fuente: 'API', id: IDS[i], tipo: 'ASSERT',
      estado: 'NO_CONCLUYENTE', motivo: 'Sin respuesta', evidencia: null })),
    cypress: { total_pruebas: 0 }, preflight_herramientas: {}, evidencias: [], bitacora: [],
    semilla: null, diagnostico_seleccion: null, respuestas: {}, problemas_tecnicos: [],
    cierre: { run: { cierre_http: null }, rollback: { verificado: false, motivo: 'Sin cierre' } },
    inicio: new Date().toISOString() };
  const secretos = [env.QA_SANDBOX_SECRET, env.QA_PROD_EMAIL, env.QA_PROD_PASSWORD].filter(Boolean);
  const presupuesto = { directas: 0, newman: 0, inicio: Date.now() };
  let tocado = false;
  try {
    const pre = preflight(c, env, ensayo); json(path.join(c.directorio, 'preflight.json'), pre);
    r.evidencias.push('preflight.json');
    if (!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
    tocado = true;
    r.preflight_herramientas.newman = validarNewman(ensayo);
    if (!r.preflight_herramientas.newman.ok) throw Error('NEWMAN_NO_DISPONIBLE');
    const login = await pedir(api, 'POST', '/sesiones/', { cuerpo: { correo_electronico: env.QA_PROD_EMAIL,
      contrasena: env.QA_PROD_PASSWORD }, bitacora: r.bitacora, presupuesto });
    if (login.http !== 200 || !login.cuerpo?.token) throw Error(`LOGIN_PRODUCTOR_HTTP_${login.http}`);
    const token = login.cuerpo.token; secretos.push(token);
    const s = await seleccionarConsulta(api, token, env, c, r, presupuesto);
    if (!s) {
      const motivo = 'Datos imprescindibles no disponibles: ninguna consulta acotada del historial devolvió resultados con eco; ver diagnóstico de selección';
      for (let i = 0; i < CASOS.length; i++) {
        r.casos[CASOS[i]] = { estado: 'BLOQUEADO', motivo };
        r.comprobaciones[i] = { ...r.comprobaciones[i], estado: 'BLOQUEADO', motivo,
          evidencia: 'resultado.json' };
      }
      return r;
    }
    r.semilla = s;
    const n = await ejecutarNewman(c, api, token, env, s, secretos, presupuesto);
    r.evidencias.push(...n.artefactos);
    const falloTecnico = n.error || n.proceso?.error || (n.proceso?.status !== 0 && n.fallos.length === 0)
      || n.fallos.some(f => f.name !== 'AssertionError'
      || !['API-G124-PDF', 'API-G124-EXCEL'].includes(f.source)
      || !IDS.slice(0, 2).some(id => f.test.includes(`[${id}]`)));
    if (falloTecnico) r.problemas_tecnicos.push(`NEWMAN_ERROR_SCRIPT_O_TRANSPORTE:${textoSeguro(n.error ?? n.proceso?.error ?? JSON.stringify(n.fallos))}`);
    const hist = n.respuestas['API-G124-HISTORIAL'];
    let h = null;
    try { h = JSON.parse(hist?.bytes.toString('utf8') ?? 'null'); } catch { /* respuesta no JSON */ }
    const valida = hist?.http === 200 && hist.eco && Array.isArray(h?.items)
      && Number.isSafeInteger(h.total) && h.total > 0
      && h.items.some(x => Number(x.id_sensor) === s.sensorId);
    r.respuestas.historial = { http: hist?.http ?? null, eco: hist?.eco ?? false,
      total: Number.isSafeInteger(h?.total) ? h.total : null, error: hist?.error ?? null };
    for (let i = 0; i < 2; i++) {
      const caso = CASOS[i], formato = i === 0 ? 'PDF' : 'EXCEL', ex = n.respuestas[`API-G124-${formato}`];
      let evaluado;
      if (!valida) evaluado = hist?.http === 200 && hist.eco && h?.total === 0
        ? { estado: 'BLOQUEADO', motivo: 'Datos imprescindibles no disponibles: historial público sin resultados para sensor y rango' }
        : { estado: 'NO_CONCLUYENTE', motivo: `Historial semilla no acreditado; HTTP ${hist?.http ?? 'sin respuesta'}, eco ${hist?.eco ?? false}` };
      else {
        const meta = { inicio: s.inicio, fin: s.fin, sensorId: s.sensorId,
          campos: Object.keys(h.items[0] ?? {}), muestra: h.items[0] ?? {} };
        const bytes = ex?.bytes ?? Buffer.alloc(0);
        const validacion = ex?.http === 200 && bytes.length <= PRESUPUESTO.max_bytes_respuesta
          ? formato === 'PDF' ? validarPdf(bytes, meta) : validarExcel(bytes, meta) : null;
        evaluado = bytes.length > PRESUPUESTO.max_bytes_respuesta
          ? { estado: 'NO_CONCLUYENTE', motivo: `${formato} supera el límite de inspección QA` }
          : clasificarExportacion({ ...ex, validacion }, formato);
        r.respuestas[formato] = { http: ex?.http ?? null, eco: ex?.eco ?? false,
          bytes: bytes.length, sha256: bytes.length ? createHash('sha256').update(bytes).digest('hex') : null,
          error: ex?.error ?? null, validacion };
      }
      r.casos[caso] = evaluado;
      if (ex?.http >= 400 && ex.http < 500 && evaluado.estado !== 'RECHAZADO')
        r.problemas_tecnicos.push(`ERROR_QA_PETICION_${formato}:HTTP_${ex.http}`);
      r.comprobaciones[i] = { ...r.comprobaciones[i], estado: evaluado.estado, motivo: evaluado.motivo,
        evidencia: n.artefactos[0] ?? null };
    }
    const v = valida ? clasificarVolumen(r.casos[CASOS[0]], r.casos[CASOS[1]], h.total)
      : { estado: r.casos[CASOS[0]].estado === 'BLOQUEADO' ? 'BLOQUEADO' : 'NO_CONCLUYENTE',
        motivo: 'Sin historial válido y archivos, no se pueden comprobar los límites por formato' };
    r.casos[CASOS[2]] = v;
    r.comprobaciones[2] = { ...r.comprobaciones[2], estado: v.estado, motivo: v.motivo,
      evidencia: n.artefactos[0] ?? null };
    for (const [tipo, nombre] of [['historial', 'API-G124-HISTORIAL'], ['PDF', 'API-G124-PDF'], ['EXCEL', 'API-G124-EXCEL']]) {
      const ex = n.respuestas[nombre];
      r.bitacora.push({ metodo: 'GET', ruta: ruta(tipo, s), http: ex?.http ?? null, eco: ex?.eco ?? false,
        en_run: true, error: ex?.error ?? null });
    }
  } catch (e) {
    const motivo = textoSeguro(e.message);
    r.problemas_tecnicos.push(motivo);
    for (let i = 0; i < CASOS.length; i++) if (r.casos[CASOS[i]].motivo === 'Sin comprobación') {
      r.casos[CASOS[i]] = { estado: 'NO_CONCLUYENTE', motivo };
      r.comprobaciones[i].motivo = motivo;
    }
  } finally {
    if (tocado) try {
      const x = await pedir(api, 'DELETE', `/test-control/runs/${c.runId}`,
        { secreto: env.QA_SANDBOX_SECRET, bitacora: r.bitacora, presupuesto, cierre: true });
      r.cierre.run.cierre_http = x.http;
      r.cierre.rollback.verificado = x.http === 200;
      r.cierre.rollback.motivo = x.http === 200
        ? 'Sin escrituras de escenario; DELETE 200. No acredita reversión de sesión, auditoría ni correos del dashboard'
        : `DELETE HTTP ${x.http}`;
    } catch (e) { r.cierre.rollback.motivo = `Cierre sin respuesta: ${textoSeguro(e.message)}`;
      r.problemas_tecnicos.push('CIERRE_NO_ACREDITADO'); }
    finalizar(c, r, secretos);
  }
  return r;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
  else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
  else try {
    const ensayo = process.argv.includes('--ensayo-loopback');
    const c = contextoEjecucion(process.argv.slice(2), { grupo: 'G124', casos: CASOS, directorio: DIR, modoEnsayo: ensayo });
    const env = ensayo ? { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: process.env.G124_ENSAYO_BASE,
      QA_SANDBOX_SECRET: 'ENSAYO_SECRET', QA_PROD_EMAIL: 'productor@example.test',
      QA_PROD_PASSWORD: 'ENSAYO_PASS' } : leerEnv();
    const r = await evaluar(c, { env, ensayo });
    console.log(JSON.stringify({ run_id: r.run_id, casos: r.casos, oficial: r.oficial }));
    if (!r.oficial) process.exitCode = 2;
  } catch (e) { console.error(`G124: ${e.message}`); process.exitCode = 2; }
}
