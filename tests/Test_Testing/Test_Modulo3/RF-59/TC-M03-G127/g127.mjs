#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';
import { sanearArtefacto, contieneMojibake } from './lib/seguridad.mjs';
import { CASOS, ID, CAPACIDADES, PRESUPUESTO, rango, rutaHistorial, rutaAuditoria,
  identidadJwt, evaluarEvento } from './lib/g127_escenario.mjs';

const require = createRequire(import.meta.url);
const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const COLECCION = path.join(DIR, 'G127.postman_collection.json');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const ARCHIVOS = ['g127.mjs', 'G127.postman_collection.json', 'README.md',
  'lib/contrato_ejecutor.mjs', 'lib/seguridad.mjs', 'lib/g127_escenario.mjs',
  'pruebas/registro_qa.mjs', 'pruebas/g127_ensayo.mjs', 'pruebas/g127.test.mjs'];
const json = (p, x) => fs.writeFileSync(p, JSON.stringify(x, null, 2), 'utf8');
const seguro = x => String(x ?? '').replaceAll('|', '/').replace(/[\r\n]+/g, ' ').slice(0, 400);

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
    const paquete = newmanPaquete(), manifest = require(path.join(paquete, 'package.json'));
    if (ensayo) return { ok: typeof require(paquete).run === 'function', version: manifest.version,
      modo: 'paquete local; CLI no lanzada durante ensayo' };
    const bin = path.join(paquete, manifest.bin.newman);
    const prueba = require('node:child_process').spawnSync(process.execPath, [bin, '--version'],
      { timeout: 30000, encoding: 'utf8' });
    return { ok: prueba.status === 0 && !!prueba.stdout.trim(), version: prueba.stdout.trim(),
      error: prueba.error?.code ?? null };
  } catch (e) { return { ok: false, version: null, error: e.code ?? e.message }; }
}
export function preflight(c, env, ensayo = false) {
  const base = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const claves = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_PROD_EMAIL',
    'QA_PROD_PASSWORD', 'QA_ADMIN_EMAIL', 'QA_ADMIN_PASSWORD'];
  const barreras = claves.filter(k => !String(env[k] ?? '').trim());
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base) : base !== API)
    barreras.push('API_NO_CANONICA');
  if (c.version > 1 && c.operacion !== 'reevaluar') barreras.push('REEVALUACION_SIN_DECISION');
  if (c.operacion === 'recuperar') barreras.push('RECUPERACION_NO_IMPLEMENTADA');
  return { fase: 'PREFLIGHT_LOCAL', grupo: 'G127', run_id: c.runId, version: c.version,
    barreras, ok: barreras.length === 0, presupuesto: PRESUPUESTO,
    efectos_declarados: ['logins_fuera_RUN_pueden_persistir_sesion_o_auditoria',
      'GET_historial_y_exportacion_pueden_persistir_auditoria_RF63_por_commit_en_misma_sesion',
      'GET_bitacora_RF63_es_lectura', 'DELETE_RUN_sin_escrituras_de_negocio'] };
}
export function comprobar() {
  let sintaxis = false;
  try {
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const e of col.item.flatMap(i => i.event ?? [])) new vm.Script((e.script?.exec ?? []).join('\n'));
    sintaxis = col.item.length === 3 && col.item.every(x => x.request.method === 'GET')
      && col.item.map(x => x.name).join(',') === 'API-G127-HISTORIAL,API-G127-AUDITORIA,API-G127-EXPORTACION'
      && !contieneMojibake(JSON.stringify(col));
  } catch { /* se informa sintaxis=false */ }
  const presentes = fs.readdirSync(DIR).filter(x => !['lib', 'pruebas', 'Resultados', 'EvaluacionV2'].includes(x))
    .concat(...['lib', 'pruebas'].map(d => fs.readdirSync(path.join(DIR, d)).map(x => `${d}/${x}`)));
  const faltantes = ARCHIVOS.filter(x => !fs.existsSync(path.join(DIR, x)));
  const inesperados = presentes.filter(x => !ARCHIVOS.includes(x));
  const markdownSuperior = fs.existsSync(path.join(DIR, 'Resultados'))
    && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const ok = sintaxis && !faltantes.length && !inesperados.length && !markdownSuperior;
  console.log(JSON.stringify({ grupo: 'G127', ok, sintaxis, faltantes, inesperados,
    markdownSuperior, presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}
function errorPublico(cuerpo) {
  const d = cuerpo?.detail && typeof cuerpo.detail === 'object' ? cuerpo.detail : cuerpo;
  const valor = x => typeof x === 'string' ? x.slice(0, 200) : null;
  return { codigo: valor(d?.error_code ?? d?.code ?? d?.codigo),
    mensaje: valor(d?.message ?? d?.mensaje ?? d?.error ?? (typeof cuerpo?.detail === 'string' ? cuerpo.detail : null)) };
}
async function pedir(api, metodo, ruta, { token, secreto, runId, cuerpo, bitacora, presupuesto,
  cierre = false, timeout = PRESUPUESTO.timeout_ms } = {}) {
  presupuesto.directas++;
  if (presupuesto.directas > PRESUPUESTO.solicitudes_directas - (cierre ? 0 : PRESUPUESTO.margen_cierre))
    throw Error('PRESUPUESTO_DIRECTO_EXCEDIDO');
  if (!cierre && Date.now() - presupuesto.inicio > (PRESUPUESTO.duracion_segundos - 60) * 1000)
    throw Error('PRESUPUESTO_TIEMPO_EXCEDIDO');
  let http = null, eco = null;
  try {
    const x = await fetch(api + ruta, { method: metodo, redirect: 'manual',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(secreto ? { 'X-Sandbox-Secret': secreto } : {}),
        ...(runId ? { 'X-Test-Run-Id': runId, 'X-Zona-Horaria': 'UTC' } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined, signal: AbortSignal.timeout(timeout) });
    http = x.status; eco = runId ? x.headers.get('x-test-run-id') === runId : null;
    const data = await x.json().catch(() => null);
    return { http, eco, cuerpo: data, error: http >= 400 ? errorPublico(data) : null };
  } finally { bitacora.push({ metodo, ruta, http, eco, en_run: !!runId }); }
}
async function seleccionar(api, token, env, c, r, presupuesto) {
  const diagnostico = r.diagnostico_seleccion = [];
  const ahora = Date.now();
  const candidatos = [rango(ahora, 7), rango(ahora, 30),
    { inicio: '2026-10-20', fin: '2026-10-27' }];
  for (const fechas of candidatos) {
    const s = { ...fechas, sensorId: 6 };
    const x = await pedir(api, 'GET', rutaHistorial(s), { token, secreto: env.QA_SANDBOX_SECRET,
      runId: c.runId, bitacora: r.bitacora, presupuesto, timeout: PRESUPUESTO.timeout_seleccion_ms });
    if (x.http !== 200 || !x.eco) throw Error(`SELECCION_HTTP_${x.http}_ECO_${x.eco}`);
    if (!Number.isSafeInteger(x.cuerpo?.total) || !Array.isArray(x.cuerpo?.items))
      throw Error('SELECCION_CONTRATO_HISTORIAL');
    const valido = x.cuerpo.total > 0 && x.cuerpo.items.some(v => Number(v?.id_sensor) === 6);
    diagnostico.push({ sensor_id: 6, ...fechas, total: x.cuerpo.total, muestra_sensor: valido,
      http: x.http, eco: x.eco });
    if (x.cuerpo.total > 0 && !valido) throw Error('SELECCION_SENSOR_NO_COINCIDE');
    if (valido) return s;
  }
  return null;
}
function extracto(ex, runId) {
  const hs = ex?.response?.header ?? [];
  const campo = n => hs.find(h => String(h.key).toLowerCase() === n)?.value ?? null;
  const stream = ex?.response?.stream;
  const bytes = Buffer.from(stream?.data ?? (Array.isArray(stream) ? stream : []));
  const http = ex?.response?.code ?? null;
  let cuerpo = null;
  try { cuerpo = JSON.parse(bytes.toString('utf8')); } catch { /* binario o vacío */ }
  return { http, eco: campo('x-test-run-id') === runId, cuerpo,
    error: http >= 400 ? errorPublico(cuerpo) : null, bytes: bytes.length,
    content_type: campo('content-type') };
}
async function ejecutarNewman(c, api, tokens, env, s, idUsuario, presupuesto, secretos) {
  presupuesto.newman += 3;
  if (presupuesto.newman > PRESUPUESTO.solicitudes_newman) throw Error('PRESUPUESTO_NEWMAN_EXCEDIDO');
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'g127-newman-'));
  try {
    const bruto = path.join(temp, 'newman.json');
    const desde = new Date(Date.now() - 10000).toISOString();
    const hasta = new Date(Date.now() + 120000).toISOString();
    const vars = { autorizado_run: 'SI', ensayo_loopback: c.ensayo ? 'SI' : 'NO', base_url: api,
      run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET, token_prod: tokens.prod,
      token_admin: tokens.admin, fecha_inicio: s.inicio, fecha_fin: s.fin,
      sensor_id: String(s.sensorId), id_usuario: String(idUsuario), fecha_desde: desde,
      fecha_hasta: hasta, consulta_ok: 'NO' };
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    const p = await new Promise(resolve => require(newmanPaquete()).run({ collection: col,
      environment: { values: Object.entries(vars).map(([key, value]) => ({ key, value, enabled: true })) },
      reporters: ['json'], reporter: { json: { export: bruto } },
      timeoutRequest: PRESUPUESTO.timeout_ms, timeout: PRESUPUESTO.duracion_segundos * 1000,
      color: 'off' }, (error, summary) => resolve({ error: error?.message ?? null,
        fallos: summary?.run?.failures?.length ?? 0 })));
    if (!fs.existsSync(bruto)) return { error: p.error ?? 'SIN_REPORTE_NEWMAN', p, respuestas: {},
      artefactos: [], fallos: [] };
    const original = JSON.parse(fs.readFileSync(bruto, 'utf8'));
    const respuestas = {}, ejecuciones = [];
    for (const ex of original.run?.executions ?? []) {
      const nombre = ex.item?.name ?? 'DESCONOCIDO', x = extracto(ex, c.runId);
      respuestas[nombre] = x;
      ejecuciones.push({ nombre, metodo: 'GET', http: x.http, eco: x.eco,
        bytes: x.bytes, content_type: x.content_type, error: x.error });
    }
    const fallos = (original.run?.failures ?? []).map(f => ({ name: seguro(f.error?.name),
      test: seguro(f.error?.test), source: seguro(f.source?.name), mensaje: seguro(f.error?.message) }));
    const salida = path.join(c.directorio, 'newman'); fs.mkdirSync(salida, { recursive: true });
    const artefactos = ['newman/newman-G127.json', 'newman/newman-G127.html'];
    json(path.join(c.directorio, artefactos[0]), JSON.parse(sanearArtefacto(JSON.stringify({
      info: { nombre: 'Newman G127', generado: true, saneado: true },
      run: { stats: original.run?.stats ?? null, timings: original.run?.timings ?? null,
        executions: ejecuciones, failures: fallos } }), secretos)));
    const filas = ejecuciones.map(x => `<tr><td>${x.nombre}</td><td>${x.http ?? 'sin respuesta'}</td><td>${x.eco}</td><td>${x.bytes}</td></tr>`).join('');
    fs.writeFileSync(path.join(c.directorio, artefactos[1]),
      `<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G127</title><h1>Newman G127</h1><table><tr><th>GET</th><th>HTTP</th><th>Eco</th><th>Bytes</th></tr>${filas}</table></html>`, 'utf8');
    return { error: p.error, p, respuestas, artefactos, fallos, desde, hasta,
      fin: new Date().toISOString() };
  } finally {
    if (!path.resolve(temp).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
    fs.rmSync(temp, { recursive: true, force: true });
  }
}

function resumenConsulta(r) {
  const x = r.comprobaciones[0];
  return `${x.estado}: ${seguro(x.motivo)}. Valores observados: ${seguro(JSON.stringify(r.auditoria?.valores ?? null))}`;
}
export function informe(r) {
  const caso = r.casos['TC-M03-256'];
  const decision = caso.estado;
  const severidad = r.auditoria?.faltantes?.includes('evento') ? 'ALTA' : 'MEDIA';
  const impacto = severidad === 'ALTA'
    ? 'No se encontró constancia de acceso para la consulta y no se demostró una trazabilidad alternativa.'
    : 'La constancia existe, pero faltan datos exigidos para reconstruir completamente la consulta.';
  const incidencia = decision !== 'RECHAZADO' || r.ambiente !== 'TEST' ?
    'Ninguna discrepancia de producto confirmada en TEST.' :
    `### INC-M03-256-G127-01 — Auditoría de consulta histórica incompleta\n\n` +
    `- **Equipo inicial:** Desarrollo. La primera discrepancia se observó por API pública RF-63; esta derivación no atribuye causa raíz.\n` +
    `- **Severidad:** ${severidad}; ${impacto}\n` +
    `- **Certeza:** CONFIRMADA para la discrepancia pública; causa raíz NO DETERMINADA. Identificador de informe, no ticket definitivo.\n` +
    `- **Requisito:** RF-59 CA-16, Especificacion-Requerimientos-Modulo3.md:6281-6284: “Dado cualquier consulta al historial realizada por cualquier usuario, cuando sea procesada, entonces el sistema debe registrar en la bitácora: Timestamp, usuario, rol, filtros aplicados, número de registros devueltos y si se exportó.” Fase 8:5982-5990; Postcondición 6:6224-6226.\n` +
    `- **Precondiciones:** Productor y Administrador autenticados; consulta con resultados y eco del RUN; lectura RF-63 con permiso (39,2) y filtro de usuario/ventana.\n` +
    `- **Pasos:** GET historial con sensor ${r.semilla?.sensorId ?? '?'}, periodo ${r.semilla?.inicio ?? '?'}..${r.semilla?.fin ?? '?'} y por_pagina=37; GET /iot/auditoria filtrado; correlación de evento y valores.\n` +
    `- **Esperado:** Evento con usuario, rol, filtros y rango, cantidad devuelta, timestamp y si se exportó.\n` +
    `- **Obtenido:** ${seguro(caso.motivo)}; ${seguro(JSON.stringify(r.auditoria?.valores ?? null))}.\n` +
    `- **Evidencia:** resultado.json y newman/newman-G127.json del RUN; ${r.auditoria?.busquedas ?? 0} búsquedas RF-63.\n` +
    `- **Análisis:** origin/test orienta la comprobación, pero el commit desplegado y la causa raíz no se acreditan aquí.\n` +
    `- **Impacto y cierre:** ${impacto} Desarrollo debe revisar la discrepancia y QA reevaluará con autorización específica.`;
  return `# TC-M03-G127 — ${decision}\n\n## Decisión del caso\n\n` +
    `TC-M03-256: **${decision}** — ${seguro(caso.motivo)}.\n\n` +
    `## Identificación\n\nGrupo G127; caso TC-M03-256; RF-59/CU04; versión V${r.version}; RUN ${r.run_id}; ambiente ${r.ambiente}; autorización ${seguro(r.autorizacion)}; commit TEST no verificado; referencia de código origin/test leída, no acredita despliegue. Newman ${r.preflight_herramientas.newman?.version ?? 'no verificado'}; Cypress no requerido, 0 ejecuciones. Clasificación ${r.oficial ? 'OFICIAL' : 'TÉCNICO'}; consume versión ${r.consume_version}.\n\n` +
    `## Esperado y observado por caso\n\nLa matriz TC-M03-G127:194-195 espera un registro con usuario, filtros aplicados, rango temporal, cantidad de registros y timestamp; el formato se comprueba solo cuando exista exportación. RF-59 Fase 8:5982-5990, Postcondición 6:6224-6226 y CA-16:6281-6284.\n\n` +
    `| Caso | Comprobación | Estado | Esperado | Observado | Evidencia |\n| --- | --- | --- | --- | --- | --- |\n` +
    `| TC-M03-256 | API-256-01 | ${r.comprobaciones[0].estado} | Evento RF-63 completo de la consulta del RUN | ${seguro(resumenConsulta(r))} | ${r.comprobaciones[0].evidencia ?? 'sin evidencia'} |\n\n` +
    `## Comprobaciones API/UI y evidencias\n\nConsulta elegida: ${seguro(JSON.stringify(r.semilla))}. Selección saneada: ${seguro(JSON.stringify(r.diagnostico_seleccion))}. Respuesta del historial: ${seguro(JSON.stringify(r.respuestas.historial ?? null))}. Auditoría: ${seguro(JSON.stringify(r.auditoria ?? null))}. Exportación informativa: ${seguro(JSON.stringify(r.exportacion ?? null))}. UI no obligatoria, cero ejecuciones. Evidencias reales: ${r.evidencias.join(', ') || 'ninguna'}.\n\n` +
    `## Incidencias de producto\n\n${incidencia}\n\n## Incidencias técnicas QA\n\n${r.problemas_tecnicos.join('; ') || 'Ninguna.'}\n\n` +
    `## Análisis de causas y observaciones\n\nLa primera lectura de RF-63 se hizo después de la consulta. Se correlacionó con usuario, sensor, por_pagina=37 y ventana temporal; el resultado de una selección previa no se usa como evento del caso. CA-16 también exige “si se exportó” para cualquier consulta; por eso falta de exportado=false rechaza la consulta normal. ${r.exportacion?.estado === 'NO_APLICA' ? 'M08 respondió 503 M08_NO_DISPONIBLE: el formato de exportación NO APLICA; esto no bloquea la consulta.' : 'El formato de exportación se evalúa solo si hubo una exportación disponible.'} La bitácora RF-63 usa commit en la sesión de la petición; el evento puede persistir fuera del rollback del RUN.\n\n` +
    `## Cierre y rollback\n\nLogin Productor y Administrador anteriores a las peticiones del RUN pueden persistir sesión o auditoría. No hubo escrituras de negocio. DELETE RUN HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. Rollback ${r.cierre.rollback.verificado ? 'verificado solo para ausencia de escrituras de escenario y cierre' : 'NO verificado'}: ${seguro(r.cierre.rollback.motivo)}. La persistencia de auditoría y sesiones no se considera revertida.\n\n` +
    `## Conclusión y acción\n\n${decision}. ${r.oficial ? 'Conservar evidencia y derivar la discrepancia confirmada si aplica.' : 'Responsable QA debe resolver el impedimento documentado antes de otro intento autorizado.'}\n`;
}
function finalizar(c, r, secretos) {
  const nombre = c.version === 1 ? 'TC-M03-G127_resultado.md' : `TC-M03-G127_reevaluacion_V${c.version}.md`;
  r.evidencias = [...new Set([...r.evidencias, 'resultado.json', nombre])];
  const archivosOk = r.evidencias.filter(x => !['resultado.json', nombre].includes(x))
    .every(x => fs.existsSync(path.join(c.directorio, x)));
  r.oficial = ['APROBADO', 'RECHAZADO'].includes(r.casos['TC-M03-256'].estado)
    && r.comprobaciones[0].estado === r.casos['TC-M03-256'].estado
    && !!r.comprobaciones[0].evidencia && r.cierre.run.cierre_http === 200
    && r.cierre.rollback.verificado && archivosOk && r.problemas_tecnicos.length === 0;
  r.consume_version = r.oficial;
  fs.writeFileSync(path.join(c.directorio, nombre), sanearArtefacto(informe(r), secretos), 'utf8');
  json(path.join(c.directorio, 'resultado.json'), JSON.parse(sanearArtefacto(JSON.stringify(r), secretos)));
}
export async function evaluar(c, { env, ensayo = false }) {
  if (!fs.existsSync(c.directorio)) throw Error('RUN_NO_CREADO_POR_LANZADOR');
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G127', run_id: c.runId, version: c.version, operacion: c.operacion,
    autorizacion: c.referencia, ambiente: ensayo ? 'LOOPBACK_LOCAL' : 'TEST', oficial: false,
    consume_version: false, casos: { 'TC-M03-256': { estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación' } },
    comprobaciones: [{ caso: 'TC-M03-256', fuente: 'API', id: ID, tipo: 'ASSERT',
      estado: 'NO_CONCLUYENTE', motivo: 'Sin respuesta', evidencia: null }],
    cypress: { total_pruebas: 0 }, preflight_herramientas: {}, evidencias: [], bitacora: [],
    semilla: null, diagnostico_seleccion: null, respuestas: {}, auditoria: null,
    exportacion: { estado: 'NO_EJECUTADA' }, problemas_tecnicos: [],
    cierre: { run: { cierre_http: null }, rollback: { verificado: false, motivo: 'Sin cierre' } } };
  const secretos = [env.QA_SANDBOX_SECRET, env.QA_PROD_EMAIL, env.QA_PROD_PASSWORD,
    env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD].filter(Boolean);
  const presupuesto = { directas: 0, newman: 0, inicio: Date.now() };
  let tocado = false;
  const asignar = (estado, motivo, evidencia = null) => {
    r.casos['TC-M03-256'] = { estado, motivo };
    Object.assign(r.comprobaciones[0], { estado, motivo, evidencia });
  };
  try {
    const pre = preflight(c, env, ensayo); json(path.join(c.directorio, 'preflight.json'), pre);
    r.evidencias.push('preflight.json');
    if (!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
    tocado = true;
    r.preflight_herramientas.newman = validarNewman(ensayo);
    if (!r.preflight_herramientas.newman.ok) throw Error('NEWMAN_NO_DISPONIBLE');
    const login = async (correo, contrasena, rol) => {
      const x = await pedir(api, 'POST', '/sesiones/', { cuerpo: { correo_electronico: correo,
        contrasena }, bitacora: r.bitacora, presupuesto });
      if (x.http !== 200 || !x.cuerpo?.token) throw Error(`LOGIN_${rol}_HTTP_${x.http}`);
      secretos.push(x.cuerpo.token); return x.cuerpo.token;
    };
    const prod = await login(env.QA_PROD_EMAIL, env.QA_PROD_PASSWORD, 'PRODUCTOR');
    const admin = await login(env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD, 'ADMIN');
    const usuario = identidadJwt(prod);
    if (!usuario.id || !usuario.rol) throw Error('IDENTIDAD_PRODUCTOR_NO_VERIFICABLE_EN_JWT');
    const s = await seleccionar(api, prod, env, c, r, presupuesto);
    if (!s) {
      asignar('BLOQUEADO', 'Datos imprescindibles no disponibles: sensor 6 sin lecturas en rangos acotados de 7/30 días ni 2026-10-20..27', 'resultado.json');
      return r;
    }
    r.semilla = s;
    const n = await ejecutarNewman(c, api, { prod, admin }, env, s, usuario.id, presupuesto, secretos);
    r.evidencias.push(...n.artefactos);
    if (n.error || n.fallos.length) throw Error(`NEWMAN_SCRIPT_O_TRANSPORTE:${seguro(n.error ?? JSON.stringify(n.fallos))}`);
    const h = n.respuestas['API-G127-HISTORIAL'];
    const a = n.respuestas['API-G127-AUDITORIA'];
    const e = n.respuestas['API-G127-EXPORTACION'];
    r.respuestas.historial = { http: h?.http ?? null, eco: h?.eco ?? false,
      total: h?.cuerpo?.total ?? null, registros_devueltos: h?.cuerpo?.items?.length ?? null };
    if (!h?.http || !h.eco || h.http !== 200 || !Array.isArray(h.cuerpo?.items))
      throw Error(`HISTORIAL_CONSULTA_NO_VERIFICABLE_HTTP_${h?.http ?? 'SIN_RESPUESTA'}`);
    if (!h.cuerpo.items.length || !h.cuerpo.items.every(x => Number(x?.id_sensor) === s.sensorId))
      throw Error('HISTORIAL_CONSULTA_SIN_DATOS_DEL_SENSOR');
    if (!a?.http) { asignar('NO_CONCLUYENTE', 'Bitácora RF-63 sin respuesta; no se puede interpretar la ausencia de evento'); }
    else if (!a.eco) { asignar('NO_CONCLUYENTE', 'Bitácora RF-63 sin eco del RUN'); }
    else if (a.http === 403) { asignar('BLOQUEADO', 'Bitácora RF-63 no accesible: Administrador sin permiso (39,2)'); }
    else if (a.http >= 500) { asignar('BLOQUEADO', `Bitácora RF-63 HTTP ${a.http}; búsqueda no verificable`); }
    else if (a.http !== 200 || !Array.isArray(a.cuerpo?.items)) {
      asignar('NO_CONCLUYENTE', `Bitácora RF-63 respuesta inesperada HTTP ${a.http}`);
    } else {
      let eventos = a.cuerpo.items, busquedas = 1;
      const op = { idUsuario: usuario.id, idRol: usuario.rol, sensorId: s.sensorId, porPagina: 37,
        inicio: s.inicio, fin: s.fin, registros: h.cuerpo.items.length,
        desde: n.desde, hasta: n.fin };
      let evaluacion = evaluarEvento(eventos, op);
      if (a.cuerpo.total > eventos.length && evaluacion.faltantes?.includes('evento')) {
        asignar('NO_CONCLUYENTE', 'Búsqueda RF-63 paginada: la primera página no cubre todos los eventos');
      }
      for (let i = 0; i < 2 && r.casos['TC-M03-256'].motivo === 'Sin comprobación'
        && evaluacion.faltantes?.includes('evento'); i++) {
        await new Promise(resolve => setTimeout(resolve, ensayo ? 10 : 5000));
        const x = await pedir(api, 'GET', rutaAuditoria(usuario.id, n.desde, n.hasta),
          { token: admin, secreto: env.QA_SANDBOX_SECRET, runId: c.runId,
            bitacora: r.bitacora, presupuesto });
        busquedas++;
        if (!x.http || !x.eco) { asignar('NO_CONCLUYENTE', 'Reintento RF-63 sin respuesta o eco'); break; }
        if (x.http === 403 || x.http >= 500) {
          asignar('BLOQUEADO', `Reintento RF-63 HTTP ${x.http}; auditoría no accesible`); break;
        }
        if (x.http !== 200 || !Array.isArray(x.cuerpo?.items)) {
          asignar('NO_CONCLUYENTE', `Reintento RF-63 inesperado HTTP ${x.http}`); break;
        }
        eventos = x.cuerpo.items; evaluacion = evaluarEvento(eventos, op);
        if (x.cuerpo.total > eventos.length && evaluacion.faltantes?.includes('evento')) {
          asignar('NO_CONCLUYENTE', 'Reintento RF-63 paginado: no cubre todos los eventos'); break;
        }
      }
      r.auditoria = { busquedas, filtro: { tipo_evento: 'HISTORIAL_CONSULTADO', rf_origen: 'RF59',
        id_usuario: usuario.id, fecha_desde: n.desde, fecha_hasta: n.hasta },
        total_ultimo: eventos.length, ...evaluacion };
      if (r.casos['TC-M03-256'].motivo === 'Sin comprobación')
        asignar(evaluacion.estado, evaluacion.motivo, 'newman/newman-G127.json');
    }
    r.exportacion = { estado: 'INFO', http: e?.http ?? null, eco: e?.eco ?? false,
      error: e?.error ?? null, formato_solicitado: 'PDF' };
    if (e?.http === 503 && e.eco && e.error?.codigo === 'M08_NO_DISPONIBLE') {
      r.exportacion.estado = 'NO_APLICA';
      const x = await pedir(api, 'GET', rutaAuditoria(usuario.id, n.desde, n.hasta, 'EXPORTACION_FALLIDA'),
        { token: admin, secreto: env.QA_SANDBOX_SECRET, runId: c.runId,
          bitacora: r.bitacora, presupuesto });
      r.exportacion.eventos_fallida = x.http === 200 && x.eco ? x.cuerpo?.items?.length ?? null : null;
    } else if (e?.http === 200 && e.eco) {
      let evento = null, consultaValida = true, exhaustiva = true;
      for (let i = 0; i < 3 && !evento; i++) {
        if (i) await new Promise(resolve => setTimeout(resolve, ensayo ? 10 : 5000));
        const x = await pedir(api, 'GET', rutaAuditoria(usuario.id, n.desde, n.hasta, 'EXPORTACION_GENERADA'),
          { token: admin, secreto: env.QA_SANDBOX_SECRET, runId: c.runId,
            bitacora: r.bitacora, presupuesto });
        if (x.http !== 200 || !x.eco || !Array.isArray(x.cuerpo?.items)) {
          consultaValida = false; r.exportacion.http_auditoria = x.http; break;
        }
        if (x.cuerpo.total > x.cuerpo.items.length) exhaustiva = false;
        evento = x.cuerpo.items.find(v =>
          String(v?.accion_detallada?.formato ?? v?.accion_detallada?.formato_exportacion
            ?? v?.formato ?? '').toUpperCase() === 'PDF');
      }
      r.exportacion.estado = evento ? 'FORMATO_ACREDITADO'
        : consultaValida && exhaustiva ? 'FORMATO_NO_ACREDITADO' : 'FORMATO_NO_CONCLUYENTE';
      r.exportacion.id_evento = evento?.id_evento ?? null;
      if (!evento && r.casos['TC-M03-256'].estado === 'APROBADO') {
        const estado = consultaValida && exhaustiva ? 'RECHAZADO' : 'NO_CONCLUYENTE';
        asignar(estado, estado === 'RECHAZADO'
          ? 'Exportación PDF disponible sin evento RF-63 con formato PDF tras búsqueda correcta'
          : 'No se pudo consultar exhaustivamente el formato de exportación en RF-63',
        estado === 'RECHAZADO' ? 'resultado.json' : null);
      }
    }
  } catch (e) {
    const motivo = seguro(e.message);
    r.problemas_tecnicos.push(motivo);
    if (r.casos['TC-M03-256'].motivo === 'Sin comprobación') asignar('NO_CONCLUYENTE', motivo);
  } finally {
    if (tocado) try {
      const x = await pedir(api, 'DELETE', `/test-control/runs/${c.runId}`,
        { secreto: env.QA_SANDBOX_SECRET, bitacora: r.bitacora, presupuesto, cierre: true });
      r.cierre.run.cierre_http = x.http;
      r.cierre.rollback.verificado = x.http === 200;
      r.cierre.rollback.motivo = x.http === 200
        ? 'Sin escrituras de negocio del escenario; DELETE 200. Auditoría RF-63 y sesiones pueden persistir'
        : `DELETE HTTP ${x.http}`;
    } catch (e) { r.cierre.rollback.motivo = `Cierre sin respuesta: ${seguro(e.message)}`;
      r.problemas_tecnicos.push('CIERRE_NO_ACREDITADO'); }
    finalizar(c, r, secretos);
  }
  return r;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
  else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
  else try {
    const c = contextoEjecucion(process.argv.slice(2),
      { grupo: 'G127', casos: CASOS, directorio: DIR });
    const r = await evaluar(c, { env: leerEnv() });
    console.log(JSON.stringify({ run_id: r.run_id, casos: r.casos, oficial: r.oficial }));
    if (!r.oficial) process.exitCode = 2;
  } catch (e) { console.error(`G127: ${e.message}`); process.exitCode = 2; }
}
