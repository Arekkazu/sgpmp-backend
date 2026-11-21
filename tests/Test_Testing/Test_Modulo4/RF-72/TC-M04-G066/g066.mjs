#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { CASOS, IDS, REGISTROS, PRESUPUESTO, CAPACIDADES,
  usuarioDelToken, tipoModelo, diagnosticar, seleccionar, patologiasActivasPara, verificarRegistro } from './lib/g066_core.mjs';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION_RUTA = path.join(DIR, 'G066.postman_collection.json');
const COLECCION = (() => { try { return JSON.parse(fs.readFileSync(COLECCION_RUTA, 'utf8')); }
  catch { return null; } })();
const POST_RUTA = '/prediccion/retroalimentacion';
const INFORME = v => v === 1 ? 'TC-M04-G066_resultado.md' : `TC-M04-G066_reevaluacion_V${v}.md`;
const corto = x => String(x ?? '').replace(/[\r\n|]/g, ' ').slice(0, 180);
const fecha = d => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota',
  year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(d));
const rutaHistorial = (id, inicio, fin, cursor) => `/prediccion/historial/${id}?fecha_inicio=${inicio}&fecha_fin=${fin}${cursor ? `&cursor_paginacion=${encodeURIComponent(cursor)}` : ''}`;
const guardar = (f, x) => fs.writeFileSync(f, JSON.stringify(x, null, 2), 'utf8');
const coleccionValida = c => c?.item?.length === 2 && c.item[0].request?.method === 'POST'
  && c.item[0].request.url?.path?.join('/') === 'prediccion/retroalimentacion'
  && c.item[1].request?.method === 'PATCH'
  && c.item[1].request.url?.path?.join('/') === 'prediccion/patologias/{{id_patologia}}/desactivar';
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
  const archivos = ['g066.mjs', 'lib/g066_core.mjs', 'G066.postman_collection.json',
    'pruebas/g066_ensayo.mjs', 'pruebas/g066_env.test.mjs', 'pruebas/registro_qa.mjs', 'README.md'];
  const faltantes = archivos.filter(x => !fs.existsSync(path.join(DIR, x)));
  let coleccion = false;
  try { const c = JSON.parse(fs.readFileSync(path.join(DIR, 'G066.postman_collection.json'), 'utf8'));
    coleccion = coleccionValida(c); } catch { /* estructural */ }
  const markdownSuperior = fs.existsSync(path.join(DIR, 'Resultados'))
    && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const newman = versionNewman();
  const ok = !faltantes.length && coleccion && !markdownSuperior && newman.ok;
  console.log(JSON.stringify({ grupo: 'G066', ok, faltantes, coleccion, markdownSuperior,
    presupuesto: PRESUPUESTO, newman }));
  return ok ? 0 : 2;
}
function contexto(args) {
  const v = k => args.includes(k) ? args[args.indexOf(k) + 1] : undefined;
  const operacion = v('--operacion'), version = Number(v('--version')),
    intento = Number(v('--intento')), runId = v('--run-id'), referencia = v('--autorizacion'), archivo = v('--contexto');
  if (!CAPACIDADES.operaciones.includes(operacion) || !Number.isInteger(version) || version < 1
    || !Number.isInteger(intento) || intento < 1 || !referencia || !archivo
    || !new RegExp(`^RUN-G066-V${version}-\\d{8}-\\d{6}$`).test(runId ?? ''))
    throw Error('Contexto de ejecución incompleto');
  const destino = path.join(DIR, ...(version === 1
    ? ['Resultados', runId] : [`EvaluacionV${version}`, 'Resultados', runId]));
  const ruta = path.resolve(archivo);
  if (path.dirname(ruta) !== destino || !(operacion === 'recuperar'
    ? /^recuperacion-\d{14}\.contexto\.json$/.test(path.basename(ruta))
    : path.basename(ruta) === 'contexto_operacion.json')) throw Error('Contexto fuera del RUN canónico');
  const c = JSON.parse(fs.readFileSync(ruta, 'utf8'));
  if (c.grupo !== 'G066' || c.run_id !== runId || c.version !== version || c.intento !== intento
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
  return { grupo: 'G066', run_id: c.runId, ok: !barreras.length, barreras,
    presupuesto: PRESUPUESTO, herramientas: { newman }, efectos: ['login Veterinario y, si hace falta, Administrador',
      'lecturas descubrimiento, catálogo, historial y auditoría',
      '5 retroalimentaciones válidas y sus auditorías', '4 intentos rechazados sin persistencia esperada',
      'PATCH desactivar patología no base solo si falta inactiva apta', 'DELETE sandbox',
      'lecturas poscierre con HISTORIAL_CONSULTADO fuera del sandbox'] };
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
async function pedirNewman(r, c, api, env, token, metodo, endpoint, caso, cuerpo, esperados) {
  if (r.solicitudes.length >= PRESUPUESTO.solicitudes_totales) throw Error('PRESUPUESTO_AGOTADO');
  const fila = { caso, metodo, ruta: endpoint.split('?')[0], http: null, herramienta: 'Newman' };
  r.solicitudes.push(fila);
  const inicio = Date.now();
  if (inicio >= r._limite) throw Error('DURACION_EXCEDIDA');
  const item = COLECCION.item.find(x => x.request.method === metodo);
  if (!item) throw Error('COLECCION_INCOMPLETA');
  const values = Object.entries({ base_url: api, token_veterinario: token,
    run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET,
    cuerpo_retroalimentacion: JSON.stringify(cuerpo ?? {}),
    id_patologia: endpoint.match(/patologias\/(\d+)/)?.[1] ?? '' })
    .map(([key, value]) => ({ key, value, enabled: true }));
  const plazo = Math.max(1, Math.min(PRESUPUESTO.timeout_ms, r._limite - inicio));
  const collection = { ...COLECCION, item: [item] };
  const iterationData = [{ http_permitidos: JSON.stringify(esperados) }];
  let error, summary;
  try {
    [error, summary] = await new Promise(resolve => require(paqueteNewman()).run({
      collection, environment: { values }, iterationData, reporters: ['cli'], silent: true,
      timeoutRequest: plazo, timeout: plazo, ignoreRedirects: true, color: 'off'
    }, (e, s) => resolve([e, s])));
  } catch (e) { error = e; }
  const ex = summary?.run?.executions?.[0];
  let b = null;
  try { b = JSON.parse(ex.response.stream.toString('utf8')); } catch { /* respuesta no JSON */ }
  const http = ex?.response?.code ?? null;
  const eco = ex?.response?.headers?.get?.('x-test-run-id') === c.runId
    || ex?.response?.header?.find?.(h => String(h.key).toLowerCase() === 'x-test-run-id')?.value === c.runId;
  const duracion = ex?.response?.responseTime ?? Date.now() - inicio;
  Object.assign(fila, { http, eco: !!eco, duracion_ms: duracion,
    respuesta: resumenCuerpo(endpoint.split('?')[0], b),
    ...(http == null ? { tipo_fallo: 'SIN_RED_O_TIMEOUT' } : {}) });
  r._consecutivos5xx = http >= 500 ? r._consecutivos5xx + 1 : 0;
  const nombre = `newman-G066-${metodo}-${caso.slice(-3)}-${r.solicitudes.filter(x => x.caso === caso && x.metodo === metodo).length}`;
  const reporte = { herramienta: 'Newman', version: r.herramientas.newman.version,
    caso, metodo, ruta: fila.ruta, http, eco: !!eco, duracion_ms: duracion,
    solicitudes: summary?.run?.stats?.requests?.total ?? (ex ? 1 : 0),
    aserciones: (ex?.assertions ?? []).map(a => ({ nombre: a.assertion,
      aprobada: !a.error, error: a.error?.message ?? null })),
    respuesta: fila.respuesta, fallos: (summary?.run?.failures ?? []).map(f => ({
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
  r.herramientas.newman.iteraciones++;
  r.herramientas.newman.solicitudes += reporte.solicitudes;
  r.herramientas.newman.aserciones += reporte.aserciones.length;
  return { http, cuerpo: b, eco: !!eco };
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
const cortoId = x => x ? String(x).slice(0, 8) : 'sin resultado apto';
const lista = x => `[${(x ?? []).join(', ')}]`;
const intento = (r, clave) => r.registros.find(x => x.clave === clave);
const observacion202 = r => {
  const cuatro = intento(r, '202-cuatro');
  return cuatro?.http === 400 && cuatro.veredicto?.estado === 'APROBADO';
};
const etiquetaCaso = (r, caso) => r.casos[caso].estado === 'APROBADO'
  && caso === 'TC-M04-202' && observacion202(r) ? 'APROBADO con observación' : r.casos[caso].estado;
function respuestaPost(r, z) {
  if (!z) return null;
  const registros = r.registros.filter(x => x.caso === z.caso && x.http === z.http);
  const posicion = registros.indexOf(z);
  return r.solicitudes.filter(x => x.metodo === 'POST' && x.ruta === POST_RUTA
    && x.caso === z.caso && x.http === z.http)[posicion]?.respuesta ?? null;
}
function resumenIntento(z) {
  if (!z) return 'sin intento';
  return `${cortoId(z.resultado)} ${lista(z.lista_enviada)} → ${z.http == null ? 'sin respuesta' : `HTTP ${z.http}`}`;
}
const oraculos = {
  'TC-M04-200': 'RF-72, línea 4163 y CA-12 (4387–4388): una patología activa en INCORRECTO se registra con HTTP 201; es la principal y no hay secundarias.',
  'TC-M04-201': 'RF-72, línea 4163 y CA-12 (4387–4388): tres patologías activas se registran con HTTP 201 en orden; la primera es principal y las otras dos, comorbilidades.',
  'TC-M04-202': 'RF-72, línea 4163 y CA-12 (4387–4388): se registran listas de uno a tres; cuatro exceden el máximo y no deben persistir. La matriz recomienda HTTP 422 para el exceso.',
  'TC-M04-203': 'RF-72, líneas 4067–4068, E5 (4260–4264) y CA-5 (4367): una patología inexistente, sola o mezclada con válidas, se rechaza con HTTP 422 sin persistencia parcial.',
  'TC-M04-204': 'RF-72, líneas 4067–4068, E5 (4260–4264) y CA-5 (4367): una patología existente pero inactiva se rechaza con HTTP 422 sin persistencia.'
};
function detalleCaso(r, caso) {
  const z = clave => intento(r, clave);
  const msg = clave => {
    const respuesta = respuestaPost(r, z(clave));
    return respuesta?.error_code ? `${respuesta.error_code}: “${corto(respuesta.detalle_campo || respuesta.mensaje)}”` : 'sin mensaje de error conservado';
  };
  const observados = {
    'TC-M04-200': `${resumenIntento(z('200-una'))}; ${lista(z('200-una')?.lista_observada)} en respuesta, historial y auditoría.`,
    'TC-M04-201': `${resumenIntento(z('201-tres'))}; ${lista(z('201-tres')?.lista_observada)} en respuesta, historial y auditoría, en el mismo orden.`,
    'TC-M04-202': `${['202-una', '202-dos', '202-tres'].map(k => resumenIntento(z(k))).join('; ')}. ${resumenIntento(z('202-cuatro'))}, ${msg('202-cuatro')}; ${z('202-cuatro')?.veredicto?.estado === 'APROBADO' ? 'campo diagnosticos_reales y máximo de 3 verificados; sin registro en historial ni auditoría' : 'verificar la discrepancia del rechazo en el veredicto'}.`,
    'TC-M04-203': `${resumenIntento(z('203-inexistente'))} y ${resumenIntento(z('203-mixta'))}; primera respuesta ${msg('203-inexistente')}; segunda ${msg('203-mixta')}; ${['203-inexistente', '203-mixta'].every(k => z(k)?.veredicto?.estado === 'APROBADO') ? 'sin registro, tampoco de las patologías válidas de la lista mixta' : 'verificar la discrepancia de rechazo o persistencia en el veredicto'}.`,
    'TC-M04-204': z('204-inactiva')?.lista_enviada?.length
      ? `${resumenIntento(z('204-inactiva'))}; ${msg('204-inactiva')}; ${z('204-inactiva')?.veredicto?.estado === 'APROBADO' ? 'sin registro' : 'verificar la discrepancia de rechazo o persistencia en el veredicto'}. ${r.diagnostico_seleccion?.contingencia ? 'Se documentó contingencia.' : 'No se necesitó contingencia.'}`
      : `${resumenIntento(z('204-inactiva'))}; no hubo patología inactiva apta para el POST.`
  };
  const aprobados = r.casos[caso].estado === 'APROBADO';
  const razones = {
    'TC-M04-200': 'HTTP 201; una sola patología, por posición principal, conservada en respuesta, historial y auditoría; sin secundarias.',
    'TC-M04-201': `HTTP 201; ${z('201-tres')?.lista_enviada?.[0]} quedó principal y ${z('201-tres')?.lista_enviada?.slice(1).join(' y ')} como comorbilidades por posición; respuesta, historial y auditoría conservaron el orden.`,
    'TC-M04-202': 'Las listas de 1, 2 y 3 tuvieron HTTP 201 y conservaron su orden; la de 4 se rechazó con campo y máximo, sin persistencia. OBS-M04-G066-202: HTTP 400 en lugar del 422 recomendado, según decisión QA del 2026-10-29.',
    'TC-M04-203': 'Ambos intentos devolvieron HTTP 422 con patología no válida; historial y auditoría no muestran registro ni de las válidas mezcladas.',
    'TC-M04-204': 'La patología inactiva devolvió HTTP 422 con mensaje de no válida o inactiva; historial y auditoría no muestran registro.'
  };
  const razon = aprobados ? razones[caso] : corto(r.casos[caso].motivo)
    .replaceAll('HTTP, lista, historial y auditoría concordantes', 'respuesta y lecturas coincidentes');
  return `### ${caso} — ${etiquetaCaso(r, caso)}\n\n- Qué se hizo: ${{
    'TC-M04-200': `Se envió INCORRECTO con una patología activa: ${resumenIntento(z('200-una')).split(' → ')[0]}.`,
    'TC-M04-201': `Se envió INCORRECTO con tres patologías activas en orden: ${resumenIntento(z('201-tres')).split(' → ')[0]}.`,
    'TC-M04-202': `Se enviaron cuatro listas, de 1 a 4 patologías: ${['202-una','202-dos','202-tres','202-cuatro'].map(k => resumenIntento(z(k)).split(' → ')[0]).join('; ')}.`,
    'TC-M04-203': `Se probó el ID inexistente y una lista mixta: ${resumenIntento(z('203-inexistente')).split(' → ')[0]}; ${resumenIntento(z('203-mixta')).split(' → ')[0]}.`,
    'TC-M04-204': `Se envió la patología inactiva: ${resumenIntento(z('204-inactiva')).split(' → ')[0]}.`
  }[caso]}\n- Qué se esperaba: ${oraculos[caso]}\n- Qué se observó: ${observados[caso]}\n- Por qué ${etiquetaCaso(r, caso)}: ${razon} Evidencia: API-${caso.slice(-3)}-01 en resultado.json.`;
}
function observacionesInforme(r) {
  const obs = [];
  if (observacion202(r)) obs.push('OBS-M04-G066-202 (TC-M04-202): La lista de 4 respondió HTTP 400 VAL_ENTRADA en vez del 422 recomendado. RF-72, línea 4163, fija el rango 1–3, sin código para el exceso; por decisión QA del 2026-10-29 queda como observación, igual que OBS-M04-G065-224. Hipótesis, no causa demostrada: la ruta no declara x-codigo-validacion 422 (src/shared/error_handlers.py:193–200, 298–324; src/prediction/infrastructure/routers/retroalimentacion_clinica_router.py:36–50).');
  obs.push('RF-72 exige que la patología exista y esté activa en el catálogo (4067-4068, 4163); no exige que corresponda a la especie del activo, y el sistema no lo comprueba.');
  return obs.length ? obs.map(x => `- ${x}`).join('\n') : 'Sin observaciones documentadas.';
}
export function informe(c, r) {
  const estados = CASOS.map(x => r.casos[x].estado);
  const decision = estados.includes('RECHAZADO') ? 'RECHAZADO'
    : estados.every(x => x === 'APROBADO') ? (r.oficial ? 'APROBADO' : 'NO_CONCLUYENTE')
      : estados.includes('BLOQUEADO') ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
  const explicaciones = {
    'TC-M04-200': 'Una patología activa registrada con HTTP 201 como principal y sin secundarias.',
    'TC-M04-201': 'Tres patologías activas registradas con HTTP 201 en orden: principal y dos comorbilidades.',
    'TC-M04-202': 'Listas de 1 a 3 registradas con HTTP 201; lista de 4 rechazada sin persistir, con OBS-M04-G066-202 por HTTP 400 en lugar del 422 recomendado.',
    'TC-M04-203': 'Patología inexistente, sola o mezclada, rechazada con HTTP 422 sin persistencia parcial.',
    'TC-M04-204': 'Patología inactiva rechazada con HTTP 422 sin persistencia.'
  };
  const tabla = CASOS.map(caso => `| ${caso} | ${etiquetaCaso(r, caso)} | ${r.casos[caso].estado === 'APROBADO'
    ? explicaciones[caso] : corto(r.casos[caso].motivo).replaceAll('HTTP, lista, historial y auditoría concordantes', 'respuesta y lecturas coincidentes')} |`).join('\n');
  const detalle = CASOS.map(caso => detalleCaso(r, caso)).join('\n\n');
  const incidencias = r.incidencias.length ? r.incidencias.map(x => `- ${x.casos.join(', ')}: ${x.severidad}; certeza ${x.certeza}; atención inicial ${x.equipo_inicial} por ${x.fundamento}. ${corto(x.motivo)}. Causa raíz no determinada.`).join('\n') : 'Sin incidencias de producto.';
  const frase = decision === 'APROBADO'
    ? 'Las listas de 1 a 3 patologías se registraron con 201 conservando el orden y la principal; la lista de 4 se rechazó sin persistir indicando el máximo (HTTP 400 en lugar del 422 recomendado); las patologías inexistentes, la lista mixta y la patología inactiva se rechazaron con 422 sin persistir nada.'
    : 'La decisión se desglosa por caso y por intento en el detalle siguiente.';
  return `# TC-M04-G066 — ${decision}

## Identificación

Grupo G066; casos ${CASOS.join(', ')}; RF-72; versión ${c.version}; RUN ${c.runId}; ambiente ${c.ensayo ? 'loopback local' : 'TEST'}; autorización ${c.referencia}; código revisado origin/test daefc3a5; Node.js. Solo API.

## Decisión del caso

${frase}

| Caso | Estado | Motivo claro |
|---|---|---|
${tabla}

Apto para registro QA: ${r.oficial ? 'sí' : 'no'}. Un ensayo local nunca constituye evidencia TEST.

## Precondición de datos (semilla)

${r.diagnostico_seleccion?.resumen ? `${r.diagnostico_seleccion.resumen.eventos} eventos examinados; ${r.registros.filter(z => z.resultado).length}/9 intentos con resultado. Se necesitan 5 resultados distintos para 201 y uno libre para rechazos, todos INDIVIDUAL y sin retroalimentación del Veterinario. Catálogo: ${r.diagnostico_seleccion.catalogo?.activas ?? 0} activas, ${r.diagnostico_seleccion.catalogo?.inactivas ?? 0} inactivas; contingencia ${r.diagnostico_seleccion.contingencia ?? 'no utilizada'}.` : 'Descubrimiento no completado.'} La semilla externa no se modifica.

## Detalle por caso

${detalle}

## Observaciones

${observacionesInforme(r)}

## Incidencias de producto

${incidencias}

## Problemas técnicos y causas

${[...r.problemas_tecnicos, ...r.observaciones].map(corto).join('; ') || 'Ninguno.'} Las incidencias se orientan por la primera discrepancia comprobada; la causa raíz no se presume.

## Historial, cierre y rollback

${r.solicitudes.length} solicitudes. DELETE HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}; rollback ${r.cierre.rollback.verificado ? 'verificado por lectura pública' : 'no verificado'}: ${corto(r.cierre.rollback.motivo)}. Las lecturas poscierre pueden crear HISTORIAL_CONSULTADO fuera del sandbox.

## Conclusión y acciones

${decision === 'APROBADO' ? 'Las cinco comprobaciones API se aprobaron. Conservar evidencias; registrar OBS-M04-G066-202 y la precisión general de RF-72 sobre especie.' : decision === 'RECHAZADO' ? 'Desarrollo debe revisar las discrepancias de API documentadas; repetir solo los casos afectados en un RUN autorizado tras la corrección.' : 'Resolver datos, conciliación o cierre antes de decidir los casos pendientes.'}

## Herramientas

Newman ${r.herramientas.newman.version ?? 'no disponible'}: ${r.herramientas.newman.iteraciones} iteraciones, ${r.herramientas.newman.solicitudes} solicitudes y ${r.herramientas.newman.aserciones} aserciones. Reportes reales saneados en newman/ para las solicitudes ejecutadas. Login, descubrimiento, lecturas y cierre por API con fetch.

## Evidencias

${r.evidencias.map(x => `- ${x}`).join('\n')}
`;
}
export async function evaluar(c, { env = leerEnv(), newmanVersion = versionNewman() } = {}) {
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G066', version: c.version, run_id: c.runId, operacion: c.operacion,
    ambiente: c.ensayo ? 'LOOPBACK_LOCAL' : 'TEST', casos: Object.fromEntries(CASOS.map(x => [x,
      { estado: 'NO_CONCLUYENTE', motivo: 'No ejecutado' }])), comprobaciones: [], registros: [],
    datos_elegidos: {}, diagnostico_seleccion: {}, solicitudes: [], observaciones: [],
    problemas_tecnicos: [], incidencias: [], cypress: { total_pruebas: 0 },
    herramientas: { newman: { ...newmanVersion, iteraciones: 0, solicitudes: 0, aserciones: 0 } },
    evidencias: ['preflight.json', 'resultado.json', INFORME(c.version)],
    cierre: { run: { cierre_http: null }, rollback: { verificado: false, motivo: 'Sin cierre' } },
    oficial: false, consume_version: false, _limite: Date.now() + 900000, _consecutivos5xx: 0 };
  fs.mkdirSync(c.directorio, { recursive: true });
  const pre = preflight(c, env, newmanVersion); guardar(path.join(c.directorio, 'preflight.json'), pre);
  let token = null, adminToken = null, iniciado = false, usuarioId = null;
  let patologiaContingencia = null;
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
    if (x.http === 403 && adminToken) x = await pedirRun('GET', p, { caso, token: adminToken });
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
    if (env.QA_ADMIN_EMAIL && env.QA_ADMIN_PASSWORD) {
      const admin = await pedir(r, api, 'POST', '/sesiones/', { cuerpo: {
        correo_electronico: env.QA_ADMIN_EMAIL, contrasena: env.QA_ADMIN_PASSWORD },
        timeout: PRESUPUESTO.timeout_login_ms });
      adminToken = admin.http === 200 ? admin.cuerpo?.token : null;
      if (!adminToken) r.observaciones.push('Login Administrador no disponible; auditoría puede ser no concluyente');
    }
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
    const idInexistente = Math.max(0, ...patologias.map(p => Number(p.id_patologia) || 0)) + 1000;
    const activosPara = dato => patologiasActivasPara(patologias, dato.id_especie);
    let libreRechazo = null;
    for (const reg of REGISTROS) {
      let dato = reg.valido ? candidatos.find(e => !usados.has(String(e.id_resultado_inferencia)))
        : libreRechazo ?? candidatos.find(e => !usados.has(String(e.id_resultado_inferencia)));
      if (!dato) { r.registros.push({ caso: reg.caso, clave: reg.clave, resultado: null,
        veredicto: { estado: 'NO_CONCLUYENTE', motivo: 'Sin resultado de inferencia libre' } }); continue; }
      let post = null, enviada = null, h = null, aud = null;
      for (let intento = 0; intento <= PRESUPUESTO.reemplazos_por_registro; intento++) {
        const activas = activosPara(dato);
        if (activas.length < (reg.clave === '202-cuatro' ? 4 : reg.lista === 3 ? 3 : reg.clave === '202-dos' ? 2 : reg.clave === '203-mixta' ? 2 : 1)
          && reg.clave !== '204-inactiva') break;
        let inactiva = patologias.find(p => !p.es_activo);
        if (reg.clave === '204-inactiva' && !inactiva) {
          const inferidas = new Set(eventos.filter(e => e.tipo_evento === 'INFERENCIA').map(e => Number(e.payload?.id_patologia)));
          const elegibles = patologias.filter(p => p.es_activo && Number(p.id_patologia) !== 7
            && !p.es_base && !inferidas.has(Number(p.id_patologia))
            && !activas.slice(0,4).some(a => a.id_patologia === p.id_patologia));
          const candidata = elegibles[0];
          if (candidata) {
            const patch = await pedirNewman(r, c, api, env, token, 'PATCH',
              `/prediccion/patologias/${candidata.id_patologia}/desactivar`, reg.caso, null, [200]);
            r.diagnostico_seleccion.contingencia = `PATCH ${candidata.id_patologia}: HTTP ${patch.http}; revertir por DELETE`;
            if (patch.http === 200 && patch.cuerpo?.es_activo === false) {
              inactiva = patch.cuerpo;
               patologiaContingencia = candidata.id_patologia;
              const original = patologias.find(p => p.id_patologia === candidata.id_patologia);
              if (original) original.es_activo = false;
            }
          } else r.diagnostico_seleccion.contingencia = 'sin patología no base libre para desactivar';
        }
        if (reg.clave === '204-inactiva' && !inactiva) break;
        enviada = reg.clave === '203-inexistente' ? [idInexistente]
          : reg.clave === '203-mixta' ? [activas[0].id_patologia, activas[1].id_patologia, idInexistente]
            : reg.clave === '204-inactiva' ? [inactiva.id_patologia]
              : activas.slice(0, reg.lista).map(x => x.id_patologia);
        const instantePost = new Date(Date.now() - 60000).toISOString();
        post = await pedirNewman(r, c, api, env, token, 'POST', POST_RUTA, reg.caso, {
          id_resultado_inferencia: dato.id_resultado_inferencia, id_activo_biologico: dato.id_activo_biologico,
          estado_retroalimentacion: 'INCORRECTO', diagnosticos_reales: enviada,
          observaciones_clinicas: `QA G066 ${reg.clave}` }, reg.valido ? [201]
            : reg.clave === '202-cuatro' ? [400, 422] : [422]);
        if ([409,422].includes(post.http) && ['RETROALIMENTACION_DUPLICADA','FUERA_DE_VENTANA_TEMPORAL'].includes(post.cuerpo?.error_code)) {
          usados.add(String(dato.id_resultado_inferencia)); libreRechazo = null;
          r.observaciones.push(`${reg.clave}: dato no apto (${post.cuerpo.error_code}); reemplazo`);
          dato = candidatos.find(e => !usados.has(String(e.id_resultado_inferencia)));
          if (!dato) break;
          continue;
        }
        if (reg.valido || post.http === 201) usados.add(String(dato.id_resultado_inferencia));
        else libreRechazo = dato;
        if (post.http == null) throw Error('POST_SIN_RESPUESTA');
        h = await historial(p => pedirRun('GET', p, { caso: reg.caso }), dato.id_activo_biologico,
          inicio, fin, reg.valido && post.http === 201 ? post.cuerpo?.id_retroalimentacion : null);
        const q = post.http === 201 && post.cuerpo?.id_retroalimentacion
          ? `id_referencia=${post.cuerpo.id_retroalimentacion}`
          : `fecha_desde=${encodeURIComponent(instantePost)}&id_usuario=${usuarioId}`;
        aud = await leerAuditoria(`/prediccion/auditoria?tipo_evento=RETROALIMENTACION_REGISTRADA&${q}&por_pagina=200`, reg.caso);
        break;
      }
      const elegido = { id_resultado_inferencia: dato?.id_resultado_inferencia ?? null,
        id_activo_biologico: dato?.id_activo_biologico ?? null,
        tipo_modelo: tipoModelo(dato, versiones) };
      r.datos_elegidos[reg.clave] = elegido;
      const fila = { caso: reg.caso, clave: reg.clave, resultado: elegido.id_resultado_inferencia,
        lista_enviada: enviada, http: post?.http ?? null, lista_observada: post?.cuerpo?.diagnosticos_reales ?? null,
        historial_http: h?.http ?? null, auditoria_http: aud?.http ?? null };
      fila.veredicto = !post ? { estado: 'NO_CONCLUYENTE', motivo: 'Datos o patología inactiva insuficientes' }
        : verificarRegistro({ ...reg, dato: elegido, enviada }, post, h, aud, usuarioId);
      r.registros.push(fila);
      if (!reg.valido && /persisti|se audit/.test(fila.veredicto.motivo)) {
        usados.add(String(dato.id_resultado_inferencia)); libreRechazo = null;
      }
    }
  } catch (e) {
    r.problemas_tecnicos.push(`Interrupción: ${corto(e.message)}`);
    const bloqueo = /LOGIN|CLAVE_403|TRES_5XX|PREFLIGHT/.test(e.message);
    for (const reg of REGISTROS) if (!r.registros.some(z => z.clave === reg.clave))
      r.registros.push({ caso: reg.caso, clave: reg.clave, resultado: null,
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
       if (patologiaContingencia !== null) {
         const catPoscierre = await pedir(r, api, 'GET', `/prediccion/patologias/${patologiaContingencia}`,
           { token, caso: 'TC-M04-204' });
         r.cierre.catalogo = { id_patologia: patologiaContingencia,
           lectura_http: catPoscierre.http, restaurada: catPoscierre.http === 200
             && catPoscierre.cuerpo?.es_activo === true };
         if (!r.cierre.catalogo.restaurada) ausentes = false;
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
    const grupos = new Map();
    for (const z of r.registros.filter(x => x.veredicto?.estado === 'RECHAZADO')) {
      const motivo = z.veredicto.motivo.replace(/HTTP \d{3}/g, 'HTTP_ERROR');
      const severidad = /persisti?|se audit?/.test(motivo) ? 'ALTA' : 'MEDIA';
      if (!grupos.has(motivo)) grupos.set(motivo, { casos: [], severidad,
        certeza: 'CONFIRMADA', equipo_inicial: 'Desarrollo', fundamento: 'primera discrepancia en API pública',
        motivo: z.veredicto.motivo, causa_raiz: 'NO DETERMINADA' });
      if (!grupos.get(motivo).casos.includes(z.caso)) grupos.get(motivo).casos.push(z.caso);
    }
    r.incidencias = [...grupos.values()];
    r.oficial = r.herramientas.newman.solicitudes > 0
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
  const salida = { grupo: 'G066', run_objetivo: c.runId, operacion: 'recuperar',
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
      const r = await recuperar(c); console.log(JSON.stringify({ grupo: 'G066', rollback_verificado: r.rollback_verificado }));
      if (!r.rollback_verificado) process.exitCode = 2;
    } else { const r = await evaluar(c); console.log(JSON.stringify({ grupo: 'G066', run_id: r.run_id,
      oficial: r.oficial, casos: Object.fromEntries(CASOS.map(x => [x, r.casos[x].estado])) }));
      if (!r.oficial) process.exitCode = 2; }
  } catch (e) { console.error(corto(e.message)); process.exitCode = 2; }
}
