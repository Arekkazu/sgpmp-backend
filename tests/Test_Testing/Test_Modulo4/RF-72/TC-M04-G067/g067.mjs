#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { CASOS, IDS, REGISTROS, PRESUPUESTO, CAPACIDADES,
  usuarioDelToken, tipoModelo, diagnosticar, seleccionar, patologiasActivasPara, verificarRegistro } from './lib/g067_core.mjs';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION_RUTA = path.join(DIR, 'G067.postman_collection.json');
const COLECCION = (() => { try { return JSON.parse(fs.readFileSync(COLECCION_RUTA, 'utf8')); }
  catch { return null; } })();
const POST_RUTA = '/prediccion/retroalimentacion';
const INFORME = v => v === 1 ? 'TC-M04-G067_resultado.md' : `TC-M04-G067_reevaluacion_V${v}.md`;
const corto = x => String(x ?? '').replace(/[\r\n|]/g, ' ').slice(0, 180);
const textoInforme = x => String(x ?? '').replace(/[\r\n|]/g, ' ');
const fecha = d => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota',
  year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(d));
const rutaHistorial = (id, inicio, fin, cursor) => `/prediccion/historial/${id}?fecha_inicio=${inicio}&fecha_fin=${fin}${cursor ? `&cursor_paginacion=${encodeURIComponent(cursor)}` : ''}`;
const guardar = (f, x) => fs.writeFileSync(f, JSON.stringify(x, null, 2), 'utf8');
const coleccionValida = c => c?.item?.length === 1 && c.item[0].request?.method === 'POST'
  && c.item[0].request.url?.path?.join('/') === 'prediccion/retroalimentacion'
  && c.item[0].request.body?.raw === '{{cuerpo_retroalimentacion}}'
  && ['Authorization','X-Test-Run-Id','X-Sandbox-Secret'].every(k =>
    c.item[0].request.header?.some(h => h.key === k))
  && c.item[0].event?.some(e => e.listen === 'test'
    && e.script?.exec?.some(linea => linea.includes('http_permitidos'))
    && e.script?.exec?.some(linea => linea.includes('Eco de X-Test-Run-Id')));
function paqueteNewman() {
  try { return path.dirname(require.resolve('newman/package.json', { paths: [RAIZ] })); }
  catch {
    const rutas = [process.execPath, ...String(process.env.PATH ?? '').split(path.delimiter)];
    return rutas.map(x => path.join(path.dirname(x), 'node_modules', 'newman', 'package.json'))
      .find(fs.existsSync)?.replace(/[\\/]package\.json$/, '') ?? null;
  }
}
function versionNewman() {
  const inicio = Date.now();
  try {
    const dir = paqueteNewman();
    const version = require(path.join(dir, 'package.json')).version;
    if (!/^\d+\.\d+\.\d+/.test(version) || Date.now() - inicio > 30000) throw Error('VERSION_INVALIDA');
    return { ok: true, version, duracion_ms: Date.now() - inicio, limite_ms: 30000 };
  } catch { return { ok: false, error: 'NEWMAN_NO_DISPONIBLE', limite_ms: 30000 }; }
}
const sanear = (valor, secretos) => {
  let texto = String(valor);
  for (const secreto of secretos.filter(x => typeof x === 'string' && x.length >= 4))
    texto = texto.split(secreto).join('[REDACTADO]');
  return texto.replace(/eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}/g, '[JWT_REDACTADO]')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[CORREO_REDACTADO]');
};
const escaparHtml = x => String(x).replace(/[&<>"']/g, y =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[y]);

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
export function comprobar() {
  const archivos = ['g067.mjs', 'lib/g067_core.mjs', 'G067.postman_collection.json',
    'pruebas/g067_ensayo.mjs', 'pruebas/g067_env.test.mjs', 'pruebas/registro_qa.mjs', 'README.md'];
  const faltantes = archivos.filter(x => !fs.existsSync(path.join(DIR, x)));
  let coleccion = false;
  try { const c = JSON.parse(fs.readFileSync(path.join(DIR, 'G067.postman_collection.json'), 'utf8'));
    coleccion = coleccionValida(c); } catch { /* estructural */ }
  const markdownSuperior = fs.existsSync(path.join(DIR, 'Resultados'))
    && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const newman = versionNewman();
  const ok = !faltantes.length && coleccion && !markdownSuperior && newman.ok;
  console.log(JSON.stringify({ grupo: 'G067', ok, faltantes, coleccion, markdownSuperior,
    presupuesto: PRESUPUESTO, newman }));
  return ok ? 0 : 2;
}
function contexto(args) {
  const v = k => args.includes(k) ? args[args.indexOf(k) + 1] : undefined;
  const operacion = v('--operacion'), version = Number(v('--version')),
    intento = Number(v('--intento')), runId = v('--run-id'), referencia = v('--autorizacion'), archivo = v('--contexto');
  if (!CAPACIDADES.operaciones.includes(operacion) || !Number.isInteger(version) || version < 1
    || !Number.isInteger(intento) || intento < 1 || !referencia || !archivo
    || !new RegExp(`^RUN-G067-V${version}-\\d{8}-\\d{6}$`).test(runId ?? ''))
    throw Error('Contexto de ejecución incompleto');
  const destino = path.join(DIR, ...(version === 1
    ? ['Resultados', runId] : [`EvaluacionV${version}`, 'Resultados', runId]));
  const ruta = path.resolve(archivo);
  if (path.dirname(ruta) !== destino || !(operacion === 'recuperar'
    ? /^recuperacion-\d{14}\.contexto\.json$/.test(path.basename(ruta))
    : path.basename(ruta) === 'contexto_operacion.json')) throw Error('Contexto fuera del RUN canónico');
  const c = JSON.parse(fs.readFileSync(ruta, 'utf8'));
  if (c.grupo !== 'G067' || c.run_id !== runId || c.version !== version || c.intento !== intento
    || c.operacion !== operacion.toUpperCase() || c.referencia !== referencia
    || JSON.stringify(c.casos) !== JSON.stringify(CASOS)
    || (operacion === 'reevaluar' && (version < 2 || c.version_anterior !== version - 1
      || !c.alcance_reevaluacion)) || (operacion === 'recuperar' && v('--run-objetivo') !== runId))
    throw Error('Contexto incoherente');
  return { operacion, version, intento, runId, referencia, directorio: destino, ensayo: false };
}
function preflight(c, env, newman = versionNewman()) {
  const base = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const barreras = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_VETERINARIO_EMAIL',
    'QA_COMMON_PASSWORD'].filter(k => !String(env[k] ?? '').trim());
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (!coleccionValida(COLECCION)) barreras.push('COLECCION_INVALIDA');
  if (!newman.ok) barreras.push('NEWMAN_NO_DISPONIBLE');
  if (c.ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base) : base !== API)
    barreras.push('API_NO_CANONICA');
  return { grupo: 'G067', run_id: c.runId, ok: !barreras.length, barreras,
    presupuesto: PRESUPUESTO, herramientas: { newman }, efectos: ['login Veterinario',
      'lecturas descubrimiento, catálogo, historial y auditoría',
      '4 retroalimentaciones válidas y sus auditorías', '9 intentos de rechazo; posibles registros indebidos',
      'DELETE sandbox siempre', 'lecturas poscierre con HISTORIAL_CONSULTADO fuera del sandbox'] };
}
function resumenCuerpo(p, b) {
  if (!b || typeof b !== 'object') return null;
  if (p.startsWith('/sesiones/')) return { token_recibido: !!b.token };
  if (p === POST_RUTA) return { id_retroalimentacion: b.id_retroalimentacion ?? null,
    id_resultado_inferencia: b.id_resultado_inferencia ?? null,
    estado_retroalimentacion: b.estado_retroalimentacion ?? null,
    diagnosticos_reales: b.diagnosticos_reales ?? null,
    error_code: b.error_code ?? null, field: b.fields?.[0]?.field ?? null,
    mensaje: corto(b.message ?? ''), detalle_campo: corto(b.fields?.[0]?.message ?? '') };
  return { total: b.total ?? b.total_registros ?? b.total_pagina ?? null,
    registros: b.registros?.length ?? null, eventos: b.eventos?.length ?? null,
    items: b.items?.length ?? null, error_code: b.error_code ?? null };
}
async function pedir(r, api, metodo, endpoint, { token, secreto, runId, cuerpo, caso,
  timeout = PRESUPUESTO.timeout_ms } = {}) {
  if (r.solicitudes.length >= PRESUPUESTO.solicitudes_totales && metodo !== 'DELETE')
    throw Error('PRESUPUESTO_AGOTADO');
  const fila = { caso: caso ?? null, metodo, ruta: endpoint.split('?')[0], http: null };
  r.solicitudes.push(fila);
  const inicio = Date.now();
  try {
    if (inicio >= r._limite && metodo !== 'DELETE') throw Error('DURACION_EXCEDIDA');
    const x = await fetch(api + endpoint, { method: metodo, redirect: 'manual',
      headers: { ...(cuerpo ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(secreto ? { 'X-Sandbox-Secret': secreto } : {}),
        ...(runId ? { 'X-Test-Run-Id': runId, 'X-Zona-Horaria': 'UTC' } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      signal: AbortSignal.timeout(metodo === 'DELETE' ? timeout
        : Math.max(1, Math.min(timeout, r._limite - inicio))) });
    const b = await x.json().catch(() => null);
    Object.assign(fila, { http: x.status, eco: runId ? x.headers.get('x-test-run-id') === runId : null,
      duracion_ms: Date.now() - inicio, respuesta: resumenCuerpo(endpoint.split('?')[0], b) });
    r._consecutivos5xx = x.status >= 500 ? r._consecutivos5xx + 1 : 0;
    return { http: x.status, cuerpo: b, eco: fila.eco };
  } catch (e) {
    Object.assign(fila, { tipo_fallo: ['TimeoutError', 'AbortError'].includes(e.name) ? 'TIMEOUT' : 'SIN_RED',
      duracion_ms: Date.now() - inicio });
    return { http: null, cuerpo: null, eco: false };
  }
}
async function ejecutarNewman(r, c, api, env, token, candidatos, usados, reservada, patologias) {
  const inicio = Date.now();
  if (inicio >= r._limite) throw Error('DURACION_EXCEDIDA');
  const item = COLECCION.item[0];
  const plan = candidatos.map(d => ({ id_resultado_inferencia: d.id_resultado_inferencia,
    id_activo_biologico: d.id_activo_biologico, activas: patologiasActivasPara(patologias, d.id_especie)
      .map(p => p.id_patologia) }));
  const estado = { plan, usados: [...usados], reservada: reservada?.id_resultado_inferencia ?? null,
    libre: null, reintento: null, consecutivos5xx: 0 };
  const collection = { ...COLECCION, item: REGISTROS.map(reg => {
    const copia = structuredClone(item);
    copia.name = reg.clave;
    copia.event = [{ listen: 'prerequest', script: { type: 'text/javascript', exec: [
      `const reg = ${JSON.stringify(reg)};`,
      `const maxReemplazos = ${PRESUPUESTO.reemplazos_por_registro};`,
      "const s = JSON.parse(pm.environment.get('estado_plan'));",
      "const libre = s.plan.find(d => !s.usados.includes(String(d.id_resultado_inferencia)));",
      "const d = reg.clave === '205-minusculas' ? s.plan.find(x => String(x.id_resultado_inferencia) === String(s.reservada)) : reg.valido ? libre : s.reintento === reg.clave ? libre : s.plan.find(x => String(x.id_resultado_inferencia) === String(s.libre)) || libre;",
      "if (!d || d.activas.length < (reg.diagnostico === 'otro' ? 2 : 1)) { pm.execution.skipRequest(); } else {",
      "const cuerpo = { id_resultado_inferencia: d.id_resultado_inferencia, id_activo_biologico: d.id_activo_biologico, observaciones_clinicas: 'QA G067 ' + reg.clave };",
      "if (reg.estado !== null) cuerpo.estado_retroalimentacion = reg.estado;",
      "if (reg.diagnostico === 'uno') cuerpo.diagnosticos_reales = [d.activas[0]];",
      "if (reg.diagnostico === 'otro') cuerpo.diagnosticos_reales = [d.activas[1]];",
      "if (reg.diagnostico === 'vacio') cuerpo.diagnosticos_reales = [];",
      "pm.environment.set('cuerpo_retroalimentacion', JSON.stringify(cuerpo));",
      "pm.environment.set('http_permitidos', JSON.stringify(reg.valido ? [201] : reg.caso === 'TC-M04-206' ? [400,422] : [422]));",
      "pm.environment.set('estado_plan', JSON.stringify(s)); }"
    ] } }, { listen: 'test', script: { type: 'text/javascript', exec: [
      ...item.event.find(e => e.listen === 'test').script.exec,
      `const reg = ${JSON.stringify(reg)};`,
      `const maxReemplazos = ${PRESUPUESTO.reemplazos_por_registro};`,
      "const s = JSON.parse(pm.environment.get('estado_plan'));",
      "const d = JSON.parse(pm.environment.get('cuerpo_retroalimentacion'));",
      "const id = String(d.id_resultado_inferencia);",
      "let b = {}; try { b = pm.response.json(); } catch (_) {}",
      "const noApto = [409,422].includes(pm.response.code) && ['RETROALIMENTACION_DUPLICADA','FUERA_DE_VENTANA_TEMPORAL'].includes(b.error_code);",
      "if (noApto && s.reintento !== reg.clave && maxReemplazos > 0) { s.usados.push(id); s.libre = null; s.reintento = reg.clave; pm.execution.setNextRequest(reg.clave); }",
      "else { s.reintento = null; if (reg.valido || pm.response.code >= 200 && pm.response.code < 300) { s.usados.push(id); s.libre = null; } else if (reg.clave !== '205-minusculas') s.libre = id; }",
      "s.consecutivos5xx = pm.response.code >= 500 ? s.consecutivos5xx + 1 : 0;",
      "if (pm.response.code === 403 || s.consecutivos5xx >= 3) pm.execution.setNextRequest(null);",
      "pm.environment.set('estado_plan', JSON.stringify(s));"
    ] } }];
    return copia;
  }) };
  const values = Object.entries({ base_url: api, token_veterinario: token,
    run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET,
    cuerpo_retroalimentacion: '{}', estado_plan: JSON.stringify(estado), http_permitidos: '[]' })
    .map(([key, value]) => ({ key, value, enabled: true }));
  const plazo = Math.max(1, Math.min(PRESUPUESTO.timeout_ms, r._limite - inicio));
  let error, summary;
  try {
    [error, summary] = await new Promise(resolve => require(paqueteNewman()).run({
      collection, environment: { values }, reporters: ['cli'], silent: true,
      timeoutRequest: plazo, timeout: Math.max(1, r._limite - inicio),
      ignoreRedirects: true, color: 'off', stopOnError: true
    }, (e, s) => resolve([e, s])));
  } catch (e) { error = e; }
  const intentos = (summary?.run?.executions ?? []).filter(ex => ex.request && ex.item);
  const ejecutados = intentos.map(ex => {
    let b = null, cuerpo = null;
    try { b = JSON.parse(ex.response.stream.toString('utf8')); } catch { /* respuesta no JSON */ }
    try { cuerpo = JSON.parse(ex.request.body.raw); } catch { /* solicitud sin cuerpo */ }
    const http = ex.response?.code ?? null;
    const eco = ex.response?.headers?.get?.('x-test-run-id') === c.runId
      || ex.response?.header?.find?.(h => String(h.key).toLowerCase() === 'x-test-run-id')?.value === c.runId;
    const clave = ex.item.name;
    const reg = REGISTROS.find(x => x.clave === clave);
    if (!reg) return null;
    const fila = { caso: reg.caso, metodo: 'POST', ruta: POST_RUTA, http,
      herramienta: 'Newman', eco: !!eco, duracion_ms: ex.response?.responseTime ?? null,
      respuesta: resumenCuerpo(POST_RUTA, b), ...(http == null ? { tipo_fallo: 'SIN_RED_O_TIMEOUT' } : {}) };
    r.solicitudes.push(fila);
    return { clave, cuerpo, post: { http, cuerpo: b, eco: !!eco }, fila };
  }).filter(Boolean);
  const nombre = 'newman-G067';
  const reporte = { herramienta: 'Newman', version: r.herramientas.newman.version,
    iteraciones: summary?.run?.stats?.iterations?.total ?? 1,
    solicitudes: summary?.run?.stats?.requests?.total ?? ejecutados.length,
    ejecuciones: ejecutados.map((x, i) => ({ clave: x.clave, caso: x.fila.caso,
      solicitud: i + 1, cuerpo: x.cuerpo, http: x.post.http, eco: x.post.eco,
      duracion_ms: x.fila.duracion_ms, respuesta: x.fila.respuesta,
      aserciones: (intentos[i]?.assertions ?? []).map(a => ({ nombre: a.assertion,
        aprobada: !a.error, error: a.error?.message ?? null })) })),
    fallos: (summary?.run?.failures ?? []).map(f => ({
      tipo: f.error?.name ?? 'Error', mensaje: f.error?.message ?? null })),
    error: error?.message ?? null };
  const secretos = [token, env.QA_SANDBOX_SECRET, env.QA_VETERINARIO_EMAIL,
    env.QA_COMMON_PASSWORD, env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD];
  const limpio = sanear(JSON.stringify(reporte, null, 2), secretos);
  const sub = path.join(c.directorio, 'newman');
  fs.mkdirSync(sub, { recursive: true });
  fs.writeFileSync(path.join(sub, `${nombre}.json`), limpio, 'utf8');
  fs.writeFileSync(path.join(sub, `${nombre}.html`),
    `<!doctype html><html lang="es"><meta charset="utf-8"><title>${nombre}</title><h1>${nombre}</h1><pre>${escaparHtml(limpio)}</pre></html>`, 'utf8');
  r.evidencias.push(`newman/${nombre}.json`, `newman/${nombre}.html`);
  r.herramientas.newman.ejecuciones = (r.herramientas.newman.ejecuciones ?? 0) + 1;
  r.herramientas.newman.iteraciones += reporte.iteraciones;
  r.herramientas.newman.solicitudes += reporte.solicitudes;
  r.herramientas.newman.aserciones += reporte.ejecuciones.reduce((n, x) => n + x.aserciones.length, 0);
  return { ejecutados, error: error?.message ?? null };
}
async function historial(pedirPagina, activo, inicio, fin, buscado = null) {
  let eventos = [], cursor = null, ultima = null, completo = false;
  for (let i = 0; i < PRESUPUESTO.paginas_historial_verificacion; i++) {
    ultima = await pedirPagina(rutaHistorial(activo, inicio, fin, cursor));
    if (ultima.http !== 200 || ultima.eco === false) break;
    eventos.push(...(ultima.cuerpo?.eventos ?? []));
    cursor = ultima.cuerpo?.cursor_siguiente ?? null;
    if (!cursor || (buscado && eventos.some(e => String(e.id_evento) === String(buscado)))) {
      completo = true; break;
    }
  }
  return { http: ultima?.http ?? null, eco: ultima?.eco, eventos, completo, cursor_pendiente: !!cursor };
}
const cortoId = x => x ? String(x).slice(0, 8) : 'sin resultado';
const oraculos = {
  'TC-M04-205':'RF-72 dominio cerrado 4070-4072, E3 4248-4252 y CA-3 4363; matriz G067: DESCONOCIDO, correcto, cadena vacía y número deben devolver HTTP 422 de estado no válido, sin persistir.',
  'TC-M04-206':'RF-72 entrada obligatoria 4162; matriz G067: estado ausente se rechaza sin persistir indicando el campo. Decisión QA 2026-10-29: HTTP 400 completo se aprueba con observación; 422 recomendado.',
  'TC-M04-207':'RF-72 obligatoriedad condicional 4074-4078, E4 4254-4258 y CA-4 4365; matriz G067: PARCIAL sin lista y con [] devuelve HTTP 422 de diagnóstico obligatorio, sin persistir.',
  'TC-M04-208':'RF-72 obligatoriedad condicional 4074-4078, E4 4254-4258 y CA-4 4365; matriz G067: INCORRECTO sin lista y con [] devuelve HTTP 422 de diagnóstico obligatorio, sin persistir.',
  'TC-M04-209':'RF-72 obligatoriedad condicional 4074-4078 y entradas 4162-4163; matriz G067: CORRECTO y SIN_EVENTO con y sin diagnóstico, sobre cuatro resultados distintos, devuelven HTTP 201 con registro. No se comprueba conservación del diagnóstico.'
};
const etiquetaCaso = (r, caso) => r.casos[caso].estado === 'APROBADO'
  && caso === CASOS[1] && r.registros.some(z => z.caso === caso && z.http === 400)
  ? 'APROBADO con observación' : r.casos[caso].estado;
function motivoInformeCaso(r, caso) {
  if (caso !== CASOS[0]) return textoInforme(r.casos[caso].motivo);
  return r.registros.filter(z => z.caso === caso).map(z => {
    if (z.veredicto?.estado === 'APROBADO')
      return `${z.clave}: HTTP, mensaje, historial y auditoría concordantes`;
    if (z.clave === '205-minusculas' && z.http === 201 && z.estado_persistido === 'CORRECTO')
      return `${z.clave}: 'correcto' recibió HTTP 201 y se guardó como CORRECTO; la matriz y E3 exigen HTTP 422 sin persistencia`;
    if (z.clave === '205-numerico' && z.http === 400)
      return `${z.clave}: HTTP 400 ${z.codigo ?? 'sin código'} (${z.detalle_campo ?? z.mensaje ?? 'sin mensaje'}); E3 exige HTTP 422 y mensaje de estado no válido`;
    return `${z.clave}: ${textoInforme(z.veredicto?.motivo ?? 'dato insuficiente')}`;
  }).join('; ') || textoInforme(r.casos[caso].motivo);
}
const mensajeIntento = z => z.codigo == null && !z.mensaje && !z.detalle_campo
  ? '—' : [z.codigo ?? 'sin código', [z.mensaje, z.detalle_campo]
    .filter((x,i,a) => x && a.indexOf(x) === i).map(textoInforme).join('; ')].filter(Boolean).join('; ');
function incidenciaInforme(x) {
  const justificacion = x.justificacion ? ` ${textoInforme(x.justificacion)}` : '';
  const hipotesis = x.hipotesis ? ` Hipótesis de causa probable: ${textoInforme(x.hipotesis)}; causa raíz no confirmada.` : ' Causa raíz no determinada.';
  return `- ${x.id ?? x.casos.join(', ')}: ${x.severidad}, certeza ${x.certeza}, atención inicial ${x.equipo_inicial} por ${x.fundamento}. ${textoInforme(x.motivo)}.${justificacion}${hipotesis}`;
}
function incidenciasDe(registros) {
  const dominio = new Set(['CORRECTO', 'PARCIAL', 'INCORRECTO', 'SIN_EVENTO']);
  const contadores = new Map();
  const rechazados = registros.filter(z => z.veredicto?.estado === 'RECHAZADO')
    .sort((a,b) => a.caso.localeCompare(b.caso)
      || Number(b.clave === '205-minusculas') - Number(a.clave === '205-minusculas'));
  return rechazados.map(z => {
    const numero = (contadores.get(z.caso) ?? 0) + 1;
    contadores.set(z.caso, numero);
    const valido = REGISTROS.find(x => x.clave === z.clave)?.valido;
    const fueraDominio = z.persistio === true && !dominio.has(z.estado_persistido);
    const severidad = fueraDominio || valido ? 'ALTA' : 'BAJA';
    const normalizado = z.clave === '205-minusculas' && z.http === 201
      && z.estado_persistido === 'CORRECTO';
    const numerico = z.clave === '205-numerico' && z.http === 400 && z.persistio === false;
    const motivo = normalizado
      ? "El valor 'correcto' recibió HTTP 201 y se guardó como CORRECTO; la matriz y E3 exigen HTTP 422 sin persistencia"
      : numerico
        ? `El valor numérico recibió HTTP 400 ${z.codigo ?? 'sin código'} (${z.detalle_campo ?? z.mensaje ?? 'sin mensaje'}); E3 exige HTTP 422 y mensaje de estado no válido`
        : z.veredicto.motivo;
    const justificacion = normalizado
      ? 'Impacto menor: el valor guardado pertenece al dominio y conserva el significado clínico; se incumple el dominio literal exigido.'
      : numerico
        ? 'Impacto menor: rechazo completo sin persistencia; el código y el mensaje difieren y pueden afectar a clientes que interpreten el código.'
        : fueraDominio
          ? 'Impacto alto: se persistió un valor fuera del dominio exigido.'
          : valido
            ? 'Impacto alto: se impide un registro válido requerido por el caso.'
            : 'Impacto menor: el rechazo impidió la persistencia, pero la respuesta incumple el oráculo.';
    const hipotesis = normalizado
      ? 'normalización con .upper() en retroalimentacion_clinica.py:45 (origin/test daefc3a5)'
      : numerico
        ? 'la ruta no declara x-codigo-validacion 422 (error_handlers.py:193-200)'
        : null;
    return { id: `INC-M04-G067-${z.caso.slice(-3)}-${String(numero).padStart(2,'0')}`,
      casos: [z.caso], clave: z.clave, severidad, certeza: 'CONFIRMADA',
      equipo_inicial: 'Desarrollo', fundamento: 'primera discrepancia en API pública',
      motivo, justificacion, hipotesis, causa_raiz: 'NO DETERMINADA' };
  });
}
function detalleCaso(r, caso) {
  const filas = r.registros.filter(z => z.caso === caso);
  const hechos = filas.map(z => `${z.clave}: ${cortoId(z.resultado)}; HTTP ${z.http ?? 'sin respuesta'}; ${mensajeIntento(z)}; persistió ${z.persistio === null ? 'no determinado' : z.persistio ? 'sí' : 'no'}${z.estado_persistido ? ` como ${z.estado_persistido}` : ''}`).join('; ') || 'sin solicitudes';
  return `### ${caso} — ${etiquetaCaso(r,caso)}

- Qué se hizo: ${filas.map(z => z.clave).join(', ') || 'No se ejecutó por interrupción'} sobre resultados INDIVIDUAL libres.
- Qué se esperaba: ${oraculos[caso]}
- Qué se observó: ${hechos}.
- Por qué ${etiquetaCaso(r,caso)}: ${motivoInformeCaso(r,caso)}. Evidencia: API-${caso.slice(-3)}-01 en resultado.json.`;
}
export function informe(c, r) {
  const estados = CASOS.map(x=>r.casos[x].estado);
  const decision = estados.includes('RECHAZADO') ? 'RECHAZADO'
    : estados.every(x=>x==='APROBADO') && r.oficial ? 'APROBADO'
      : estados.includes('BLOQUEADO') ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
  const tabla = CASOS.map(x=>`| ${x} | ${etiquetaCaso(r,x)} | ${motivoInformeCaso(r,x)} |`).join('\n');
  const intentos = r.registros.map(z=>`| ${z.clave} | ${cortoId(z.resultado)} | ${corto(JSON.stringify(z.cuerpo_enviado??{}))} | ${z.http??'sin respuesta'} | ${mensajeIntento(z)} | ${z.persistio===null?'no determinado':z.persistio?'sí':'no'} |`).join('\n');
  const incidencias = r.incidencias.length ? r.incidencias.map(incidenciaInforme).join('\n') : 'Sin incidencias de producto.';
  return `# TC-M04-G067 — ${decision}

## Identificación

Grupo G067; casos ${CASOS.join(', ')}; RF-72; versión ${c.version}; RUN ${c.runId}; ambiente ${c.ensayo?'loopback local':'TEST'}; autorización ${c.referencia}; código revisado origin/test daefc3a5; Node.js. Solo API.

## Decisión del caso

| Caso | Decisión | Motivo |
|---|---|---|
${tabla}

RUN oficial: ${r.oficial?'sí':'no'}. Qué falta: ${r.oficial?'ninguna comprobación obligatoria':corto([...r.problemas_tecnicos,...r.observaciones].join('; ')||'completar las comprobaciones y el cierre')}. El ensayo local no es evidencia TEST.

## Precondición de datos (semilla)

${r.diagnostico_seleccion?.resumen?.eventos??0} eventos examinados; se requieren cuatro resultados distintos para 209, uno libre compartido para rechazos y uno reservado para el valor en minúsculas, más reemplazos. Modelo INDIVIDUAL; patologías activas 8-14, excluida 7. La semilla no se modifica.

## Detalle por caso

${CASOS.map(x=>detalleCaso(r,x)).join('\n\n')}

## Tabla de intentos

| Intento | Resultado | Cuerpo resumido | HTTP | Código y mensaje | Persistió |
|---|---|---|---|---|---|
${intentos}

## Observaciones

${r.registros.some(z=>z.clave==='206-ausente'&&z.http===400&&z.veredicto?.estado==='APROBADO')?'OBS-M04-G067-206: HTTP 400 completo, sin persistencia, para estado ausente; RF-72 4162 no fija código para la ausencia y QA permite observación.':'Sin observaciones de producto.'}

## Incidencias de producto

${incidencias}

## Problemas técnicos y análisis de causas

${[...r.problemas_tecnicos,...r.observaciones].map(corto).join('; ')||'Ninguno.'} Derivación inicial según primera discrepancia pública; causa raíz no atribuida.

## Historial, cierre y rollback

${r.solicitudes.length} solicitudes. DELETE HTTP ${r.cierre.run.cierre_http??'sin respuesta'}; rollback ${r.cierre.rollback.verificado?'verificado por lectura pública':'no verificado'}: ${corto(r.cierre.rollback.motivo)}. Lecturas poscierre pueden crear HISTORIAL_CONSULTADO fuera del sandbox.

## Conclusión y acciones

${decision==='RECHAZADO'?'Desarrollo debe revisar las discrepancias API confirmadas en TEST y repetir los casos afectados en un RUN autorizado.':decision==='APROBADO'?'Cinco comprobaciones API aprobadas; conservar evidencias y la observación si aplica.':'Resolver el impedimento o conciliar solicitudes antes de decidir casos pendientes.'}

## Herramientas

Newman ${r.herramientas.newman.version??'no disponible'}: ${r.herramientas.newman.ejecuciones} ejecución, ${r.herramientas.newman.iteraciones} iteraciones, ${r.herramientas.newman.solicitudes} solicitudes y ${r.herramientas.newman.aserciones} aserciones. Un JSON y un HTML reales saneados en newman/. Login, descubrimiento, lecturas y cierre por fetch.

## Evidencias

${r.evidencias.map(x=>`- ${x}`).join('\n')}
`;
}
export async function evaluar(c, { env = leerEnv(), newmanVersion = versionNewman() } = {}) {
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G067', version: c.version, run_id: c.runId, operacion: c.operacion,
    ambiente: c.ensayo ? 'LOOPBACK_LOCAL' : 'TEST', casos: Object.fromEntries(CASOS.map(x => [x,
      { estado: 'NO_CONCLUYENTE', motivo: 'No ejecutado' }])), comprobaciones: [], registros: [],
    datos_elegidos: {}, diagnostico_seleccion: {}, solicitudes: [], observaciones: [],
    problemas_tecnicos: [], incidencias: [], cypress: { total_pruebas: 0 },
    herramientas: { newman: { ...newmanVersion, ejecuciones: 0, iteraciones: 0, solicitudes: 0, aserciones: 0 } },
    evidencias: ['preflight.json', 'resultado.json', INFORME(c.version)],
    cierre: { run: { cierre_http: null }, rollback: { verificado: false, motivo: 'Sin cierre' } },
    oficial: false, consume_version: false, _limite: Date.now() + 900000, _consecutivos5xx: 0 };
  fs.mkdirSync(c.directorio, { recursive: true });
  const pre = preflight(c, env, newmanVersion); guardar(path.join(c.directorio, 'preflight.json'), pre);
  let token = null, iniciado = false, usuarioId = null;
  const pedirRun = async (m, p, opts = {}) => {
    const x = await pedir(r, api, m, p, { ...opts, token: opts.token ?? token,
      secreto: env.QA_SANDBOX_SECRET, runId: c.runId });
    if (x.http === 403 && !p.startsWith('/prediccion/auditoria')) throw Error('CLAVE_403');
    if (r._consecutivos5xx >= 3) throw Error('TRES_5XX_CONSECUTIVOS');
    return x;
  };
  const inicio = fecha(Date.now() - PRESUPUESTO.dias_busqueda * 86400000), fin = fecha(Date.now());
  const leerAuditoria = async (p, caso) => {
    let x = await pedirRun('GET', p, { caso });
    return { http: x.http, eco: x.eco, items: x.cuerpo?.items ?? [],
      completo: x.http === 200 && Number(x.cuerpo?.total ?? Infinity) <= (x.cuerpo?.items?.length ?? 0) };
  };
  try {
    if (!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
    const login = await pedir(r, api, 'POST', '/sesiones/', { cuerpo: {
      correo_electronico: env.QA_VETERINARIO_EMAIL, contrasena: env.QA_COMMON_PASSWORD },
      timeout: PRESUPUESTO.timeout_login_ms });
    if (login.http !== 200 || !login.cuerpo?.token) throw Error(`LOGIN_${login.http ?? 'SIN_RESPUESTA'}`);
    token = login.cuerpo.token; usuarioId = usuarioDelToken(token);
    iniciado = true;
    const activos = [];
    for (let pagina = 1; pagina <= PRESUPUESTO.paginas_activos; pagina++) {
      const x = await pedirRun('GET', `/activos-biologicos?tipo=INDIVIDUAL&pagina=${pagina}&page_size=8`);
      if (x.http !== 200 || x.eco !== true) break;
      activos.push(...(x.cuerpo?.registros ?? []).filter(a => a.tipo === 'INDIVIDUAL'));
      if (pagina >= Number(x.cuerpo?.total_paginas ?? 1)) break;
    }
    const eventos = [];
    for (const activo of activos.slice(0, PRESUPUESTO.activos_maximos)) {
      let cursor = null, paginas = 0;
      do {
        const x = await pedirRun('GET', rutaHistorial(activo.id_activo_biologico, inicio, fin, cursor));
        paginas++;
        if (x.http !== 200 || x.eco !== true) break;
        eventos.push(...(x.cuerpo?.eventos ?? []).map(e => ({ ...e,
          id_activo_biologico: activo.id_activo_biologico, id_especie: activo.id_especie })));
        cursor = x.cuerpo?.cursor_siguiente ?? null;
      } while (cursor && paginas < PRESUPUESTO.paginas_historial_descubrimiento);
      r.diagnostico_seleccion[activo.id_activo_biologico] = { paginas, cursor_pendiente: !!cursor };
    }
    const versiones = {};
    const idsVersion = [...new Set(eventos.filter(e => e.tipo_evento === 'INFERENCIA'
      && e.payload?.tipo_modelo == null && Number.isSafeInteger(Number(e.payload?.id_version_modelo)))
      .map(e => Number(e.payload.id_version_modelo)))];
    for (const id of idsVersion.slice(0, PRESUPUESTO.versiones_maximas)) {
      const x = await pedirRun('GET', `/prediccion/modelos/${id}`);
      if (x.http === 200 && x.eco && Number(x.cuerpo?.id_version_modelo) === id)
        versiones[String(id)] = x.cuerpo.tipo_modelo;
    }
    const cat = await pedirRun('GET', '/prediccion/patologias');
    const patologias = cat.http === 200 && cat.eco === true ? cat.cuerpo?.items ?? [] : [];
    r.diagnostico_seleccion.catalogo = { activas: patologias.filter(p => p.es_activo).length,
      inactivas: patologias.filter(p => !p.es_activo).length, lectura_http: cat.http };
    r.diagnostico_seleccion.resumen = diagnosticar(eventos, usuarioId, versiones);
    const usados = new Set(), candidatos = seleccionar(eventos, usados, usuarioId, versiones, inicio, fin);
    const reservada = candidatos.find(e => !usados.has(String(e.id_resultado_inferencia)));
    if (reservada) usados.add(String(reservada.id_resultado_inferencia));
    const inicioNewman = Date.now();
    const lote = await ejecutarNewman(r, c, api, env, token, candidatos, usados, reservada, patologias);
    const aceptados = lote.ejecutados.filter(x => x.post.http >= 200 && x.post.http < 300
      && x.post.cuerpo?.id_retroalimentacion);
    for (const reg of REGISTROS) {
      const intentos = lote.ejecutados.filter(x => x.clave === reg.clave);
      for (const anterior of intentos.slice(0, -1)) if ([409,422].includes(anterior.post.http)
        && ['RETROALIMENTACION_DUPLICADA','FUERA_DE_VENTANA_TEMPORAL'].includes(anterior.post.cuerpo?.error_code))
        r.observaciones.push(`${reg.clave}: dato no apto (${anterior.post.cuerpo.error_code}); reemplazo`);
      const ultimo = intentos.at(-1);
      const post = ultimo?.post ?? null, cuerpo = ultimo?.cuerpo ?? null;
      const dato = candidatos.find(e => String(e.id_resultado_inferencia) === String(cuerpo?.id_resultado_inferencia));
      const enviada = cuerpo?.diagnosticos_reales ?? null;
      let h = null, aud = null;
      if (post?.http != null && dato) {
        h = await historial(p => pedirRun('GET', p, { caso: reg.caso }), dato.id_activo_biologico,
          inicio, fin, reg.valido && post.http === 201 ? post.cuerpo?.id_retroalimentacion : null);
        const instantePost = new Date(inicioNewman - 60000).toISOString();
        const q = post.http === 201 && post.cuerpo?.id_retroalimentacion
          ? `id_referencia=${post.cuerpo.id_retroalimentacion}`
          : `fecha_desde=${encodeURIComponent(instantePost)}&id_usuario=${usuarioId}`;
        aud = await leerAuditoria(`/prediccion/auditoria?tipo_evento=RETROALIMENTACION_REGISTRADA&${q}&por_pagina=200`, reg.caso);
        if (!reg.valido && !(post.http >= 200 && post.http < 300)) {
          const otros = new Set(aceptados.filter(x => x.clave !== reg.clave
            && String(x.cuerpo?.id_resultado_inferencia) === String(dato.id_resultado_inferencia))
            .map(x => String(x.post.cuerpo.id_retroalimentacion)));
          h = { ...h, eventos: h.eventos.filter(e => !otros.has(String(e.id_evento))) };
          aud = { ...aud, items: aud.items.filter(e => !otros.has(String(e.id_referencia))) };
        }
      }
      const elegido = { id_resultado_inferencia: dato?.id_resultado_inferencia ?? null,
        id_activo_biologico: dato?.id_activo_biologico ?? null,
        tipo_modelo: tipoModelo(dato, versiones) };
      r.datos_elegidos[reg.clave] = elegido;
      const eventos = (h?.eventos??[]).filter(e=>e.tipo_evento==='RETROALIMENTACION'
        && String(e.id_resultado_inferencia)===String(elegido.id_resultado_inferencia)
        && String(e.payload?.id_usuario_veterinario)===String(usuarioId));
      const fila = { caso: reg.caso, clave: reg.clave, resultado: elegido.id_resultado_inferencia,
        cuerpo_enviado: cuerpo && { estado_retroalimentacion: cuerpo.estado_retroalimentacion,
          diagnosticos_reales: cuerpo.diagnosticos_reales },
        lista_enviada: enviada, http: post?.http ?? null,
        codigo: post?.cuerpo?.error_code ?? null, mensaje: post?.cuerpo?.message ?? null,
        detalle_campo: post?.cuerpo?.fields?.[0]?.message ?? null,
        estado_persistido: post?.cuerpo?.estado_retroalimentacion ?? null,
        persistio: h?.completo ? eventos.length > 0 : null,
        historial_http: h?.http ?? null, auditoria_http: aud?.http ?? null };
      fila.veredicto = !post ? { estado: 'NO_CONCLUYENTE', motivo: 'Datos insuficientes' }
        : verificarRegistro({ ...reg, dato: elegido, enviada }, post, h, aud, usuarioId);
      r.registros.push(fila);
      if (post?.http === 403) throw Error('CLAVE_403');
      const ultimos = lote.ejecutados.slice(-3);
      if (ultimo === lote.ejecutados.at(-1) && ultimos.length === 3
        && ultimos.every(x => x.post.http >= 500)) throw Error('TRES_5XX_CONSECUTIVOS');
      if (!reg.valido && fila.persistio && dato) usados.add(String(dato.id_resultado_inferencia));
      if (post?.http == null) throw Error('POST_SIN_RESPUESTA');
    }
    if (lote.error) r.problemas_tecnicos.push(`Newman: ${corto(lote.error)}`);
  } catch (e) {
    r.problemas_tecnicos.push(`Interrupción: ${corto(e.message)}`);
    const bloqueo = /LOGIN|CLAVE_403|TRES_5XX|PREFLIGHT/.test(e.message);
    for (const reg of REGISTROS) if (!r.registros.some(z => z.clave === reg.clave))
      r.registros.push({ caso: reg.caso, clave: reg.clave, resultado: null, persistio: null,
        veredicto: { estado: bloqueo ? 'BLOQUEADO' : 'NO_CONCLUYENTE',
          motivo: `Interrupción técnica: ${corto(e.message)}` } });
  } finally {
    if (iniciado) {
      const cierre = await pedir(r, api, 'DELETE', `/test-control/runs/${encodeURIComponent(c.runId)}`,
        { secreto: env.QA_SANDBOX_SECRET });
      r.cierre.run.cierre_http = cierre.http;
      const examinados = r.registros.filter(z => z.resultado && r.datos_elegidos[z.clave]);
      let ausentes = cierre.http === 200 && examinados.some(z => z.http === 201);
      for (const z of examinados) {
        const d = r.datos_elegidos[z.clave];
        const id = r.solicitudes.find(s => s.caso === z.caso && s.metodo === 'POST'
          && s.respuesta?.id_resultado_inferencia === z.resultado)?.respuesta?.id_retroalimentacion;
        const h = await historial(p => pedir(r, api, 'GET', p, { token, caso: z.caso }),
          d.id_activo_biologico, inicio, fin, null);
        if (h.http !== 200 || !h.completo || h.eventos.some(e =>
          id ? String(e.id_evento) === String(id) : e.tipo_evento === 'RETROALIMENTACION'
          && String(e.id_resultado_inferencia) === String(z.resultado)
          && String(e.payload?.id_usuario_veterinario) === String(usuarioId))) ausentes = false;
      }
      r.cierre.rollback = { verificado: ausentes,
        motivo: ausentes ? 'Registros del RUN ausentes en historial público poscierre'
          : 'DELETE o lectura poscierre no confirma ausencia de todos los registros' };
    }
    for (const caso of CASOS) {
      const filas = r.registros.filter(x => x.caso === caso);
      const estado = filas.some(x => x.veredicto?.estado === 'RECHAZADO') ? 'RECHAZADO'
        : filas.every(x => x.veredicto?.estado === 'APROBADO') && filas.length === REGISTROS.filter(x => x.caso === caso).length ? 'APROBADO'
          : filas.some(x => x.veredicto?.estado === 'BLOQUEADO') ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
      r.casos[caso] = { estado, motivo: filas.map(x => `${x.clave}: ${x.veredicto?.motivo ?? 'dato insuficiente'}`).join('; ') };
    }
    r.comprobaciones = CASOS.map((caso, i) => ({ caso, fuente: 'API', id: IDS[i], tipo: 'ASSERT',
      estado: r.casos[caso].estado, motivo: r.casos[caso].motivo, evidencia: 'resultado.json' }));
    r.incidencias = incidenciasDe(r.registros);
    const postsNewman = r.solicitudes.filter(x => x.metodo === 'POST' && x.ruta === POST_RUTA);
    r.oficial = postsNewman.length >= REGISTROS.length
      && postsNewman.every(x => x.herramienta === 'Newman')
      && r.herramientas.newman.ejecuciones === 1
      && r.herramientas.newman.iteraciones === 1
      && r.herramientas.newman.solicitudes === postsNewman.length
      && r.herramientas.newman.aserciones >= 2 * postsNewman.length
      && CASOS.every(x => ['APROBADO', 'RECHAZADO'].includes(r.casos[x].estado))
      && r.cierre.rollback.verificado && r.solicitudes.length <= PRESUPUESTO.solicitudes_totales;
    r.consume_version = r.oficial;
    delete r._limite; delete r._consecutivos5xx;
    guardar(path.join(c.directorio, 'resultado.json'), r);
    fs.writeFileSync(path.join(c.directorio, INFORME(c.version)), informe(c, r), 'utf8');
  }
  return r;
}

export async function recuperar(c, { env = leerEnv() } = {}) {
  const pre = preflight(c, env); if (!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
  const previo = JSON.parse(fs.readFileSync(path.join(c.directorio, 'resultado.json'), 'utf8'));
  if (previo.run_id !== c.runId || previo.version !== c.version) throw Error('RUN previo incoherente');
  const api = String(env.SIGAB_API_TEST_BASE).replace(/\/+$/, '');
  const r = { solicitudes: [], _limite: Date.now() + 900000, _consecutivos5xx: 0 };
  const cierre = await pedir(r, api, 'DELETE', `/test-control/runs/${encodeURIComponent(c.runId)}`,
    { secreto: env.QA_SANDBOX_SECRET });
  const login = await pedir(r, api, 'POST', '/sesiones/', { cuerpo: {
    correo_electronico: env.QA_VETERINARIO_EMAIL, contrasena: env.QA_COMMON_PASSWORD },
  timeout: PRESUPUESTO.timeout_login_ms });
  const token = login.http === 200 ? login.cuerpo?.token : null;
  const usuarioId = usuarioDelToken(token);
  let ausentes = !!token && [200, 404].includes(cierre.http);
  for (const z of previo.registros.filter(x => x.resultado)) {
    if (!token) break;
    const d = previo.datos_elegidos[z.clave];
    const id = previo.solicitudes.find(s => s.caso === z.caso && s.metodo === 'POST'
      && s.respuesta?.id_resultado_inferencia === z.resultado)?.respuesta?.id_retroalimentacion;
    const h = await historial(p => pedir(r, api, 'GET', p, { token, caso: z.caso }), d.id_activo_biologico,
      fecha(Date.parse(d.fecha_inferencia) - 86400000), fecha(Date.now()), null);
    if (h.http !== 200 || !h.completo || h.eventos.some(e => id
      ? String(e.id_evento) === String(id) : e.tipo_evento === 'RETROALIMENTACION'
        && String(e.id_resultado_inferencia) === String(z.resultado)
        && String(e.payload?.id_usuario_veterinario) === String(usuarioId))) ausentes = false;
  }
  const salida = { grupo: 'G067', run_objetivo: c.runId, operacion: 'recuperar',
    cierre_http: cierre.http, rollback_verificado: ausentes,
    motivo: ausentes ? 'Registros ausentes en historial público' : 'Cierre o ausencia sin confirmar',
    solicitudes: r.solicitudes };
  guardar(path.join(c.directorio, `recuperacion-${new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14)}.json`), salida);
  return salida;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
  else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
  else try {
    const c = contexto(process.argv.slice(2));
    if (c.operacion === 'recuperar') {
      const r = await recuperar(c); console.log(JSON.stringify({ grupo: 'G067', rollback_verificado: r.rollback_verificado }));
      if (!r.rollback_verificado) process.exitCode = 2;
    } else { const r = await evaluar(c); console.log(JSON.stringify({ grupo: 'G067', run_id: r.run_id,
      oficial: r.oficial, casos: Object.fromEntries(CASOS.map(x => [x, r.casos[x].estado])) }));
      if (!r.oficial) process.exitCode = 2; }
  } catch (e) { console.error(corto(e.message)); process.exitCode = 2; }
}
