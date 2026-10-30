#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { CASOS, IDS, FUENTES, REGISTROS, PRESUPUESTO, CAPACIDADES,
  usuarioDelToken, tipoModelo, diagnosticar, seleccionar, verificarRegistro } from './lib/g065_escenario.mjs';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION = JSON.parse(fs.readFileSync(path.join(DIR, 'G065.postman_collection.json'), 'utf8'));
const POST_RUTA = `/${COLECCION.item[0].request.url.path.join('/')}`;
function paqueteNewman() {
  try { return path.dirname(require.resolve('newman/package.json', { paths: [RAIZ] })); }
  catch {
    const p = String(process.env.PATH ?? '').split(path.delimiter)
      .map(x => path.join(x, 'node_modules', 'newman', 'package.json')).find(fs.existsSync);
    return p ? path.dirname(p) : null;
  }
}
function versionNewman() {
  const inicio = Date.now();
  try {
    const dir = paqueteNewman();
    const paquete = require(path.join(dir, 'package.json'));
    if (!/^\d+\.\d+\.\d+/.test(paquete.version) || Date.now() - inicio > 30000)
      throw Error('VERSION_INVALIDA');
    return { ok: true, version: paquete.version, duracion_ms: Date.now() - inicio, limite_ms: 30000 };
  } catch { return { ok: false, error: 'NEWMAN_NO_DISPONIBLE' }; }
}
function coleccionValida() {
  try {
    const c = JSON.parse(fs.readFileSync(path.join(DIR, 'G065.postman_collection.json'), 'utf8'));
    for (const i of c.item) for (const e of i.event ?? []) new vm.Script((e.script?.exec ?? []).join('\n'));
    const h = c.item[0].request.header.map(x => x.key.toLowerCase());
    return c.item.length === 1 && c.item[0].request.method === 'POST'
      && c.item[0].request.url.path.join('/') === 'prediccion/retroalimentacion'
      && ['authorization', 'x-test-run-id', 'x-sandbox-secret'].every(x => h.includes(x));
  } catch { return false; }
}
const INFORME = v => v === 1 ? 'TC-M04-G065_resultado.md' : `TC-M04-G065_reevaluacion_V${v}.md`;
const corto = x => String(x ?? '').replace(/[\r\n|]/g, ' ').slice(0, 180);
const fecha = d => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota',
  year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(d));
const rutaHistorial = (id, inicio, fin, cursor) => `/prediccion/historial/${id}?fecha_inicio=${inicio}&fecha_fin=${fin}${cursor ? `&cursor_paginacion=${encodeURIComponent(cursor)}` : ''}`;
const guardar = (f, x) => fs.writeFileSync(f, JSON.stringify(x, null, 2), 'utf8');

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
  const archivos = ['g065.mjs', 'lib/g065_escenario.mjs', 'G065.postman_collection.json',
    'pruebas/g065_ensayo.mjs', 'pruebas/g065_env.test.mjs', 'pruebas/registro_qa.mjs', 'README.md'];
  const faltantes = archivos.filter(x => !fs.existsSync(path.join(DIR, x)));
  const coleccion = coleccionValida();
  const newman = versionNewman();
  const markdownSuperior = fs.existsSync(path.join(DIR, 'Resultados'))
    && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const ok = !faltantes.length && coleccion && !markdownSuperior && newman.ok;
  console.log(JSON.stringify({ grupo: 'G065', ok, faltantes, coleccion, markdownSuperior,
    presupuesto: PRESUPUESTO, newman }));
  return ok ? 0 : 2;
}
function contexto(args) {
  const v = k => args.includes(k) ? args[args.indexOf(k) + 1] : undefined;
  const operacion = v('--operacion'), version = Number(v('--version')),
    intento = Number(v('--intento')), runId = v('--run-id'), referencia = v('--autorizacion'), archivo = v('--contexto');
  if (!CAPACIDADES.operaciones.includes(operacion) || !Number.isInteger(version) || version < 1
    || !Number.isInteger(intento) || intento < 1 || !referencia || !archivo
    || !new RegExp(`^RUN-G065-V${version}-\\d{8}-\\d{6}$`).test(runId ?? ''))
    throw Error('Contexto de ejecución incompleto');
  const destino = path.join(DIR, ...(version === 1
    ? ['Resultados', runId] : [`EvaluacionV${version}`, 'Resultados', runId]));
  const ruta = path.resolve(archivo);
  if (path.dirname(ruta) !== destino || !(operacion === 'recuperar'
    ? /^recuperacion-\d{14}\.contexto\.json$/.test(path.basename(ruta))
    : path.basename(ruta) === 'contexto_operacion.json')) throw Error('Contexto fuera del RUN canónico');
  const c = JSON.parse(fs.readFileSync(ruta, 'utf8'));
  if (c.grupo !== 'G065' || c.run_id !== runId || c.version !== version || c.intento !== intento
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
  if (c.ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base) : base !== API)
    barreras.push('API_NO_CANONICA');
  if (!newman.ok) barreras.push('NEWMAN_NO_DISPONIBLE');
  if (!coleccionValida()) barreras.push('COLECCION_INVALIDA');
  return { grupo: 'G065', run_id: c.runId, ok: !barreras.length, barreras,
    presupuesto: PRESUPUESTO, herramientas: { newman }, efectos: ['login', 'lecturas descubrimiento e historial',
      '9 registros válidos y auditoría', '1 rechazo esperado', 'DELETE sandbox',
      'lecturas poscierre con HISTORIAL_CONSULTADO fuera del sandbox'] };
}
function resumenCuerpo(p, b) {
  if (!b || typeof b !== 'object') return null;
  if (p.startsWith('/sesiones/')) return { token_recibido: !!b.token };
  if (p === POST_RUTA) return { id_retroalimentacion: b.id_retroalimentacion ?? null,
    id_resultado_inferencia: b.id_resultado_inferencia ?? null,
    estado_retroalimentacion: b.estado_retroalimentacion ?? null,
    fuente_diagnostico: b.fuente_diagnostico ?? null,
    es_fuente_desconocida: b.es_fuente_desconocida ?? null,
    error_code: b.error_code ?? null, field: b.fields?.[0]?.field ?? null,
    catalogo_completo: FUENTES.every(f => `${b.message ?? ''} ${JSON.stringify(b.fields ?? [])}`.includes(f)) };
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
async function pedirNewman(r, c, api, env, token, reg, cuerpo) {
  if (r.solicitudes.length >= PRESUPUESTO.solicitudes_totales) throw Error('PRESUPUESTO_AGOTADO');
  const fila = { caso: reg.caso, metodo: 'POST', ruta: POST_RUTA, http: null, herramienta: 'Newman' };
  r.solicitudes.push(fila);
  const inicio = Date.now();
  if (inicio >= r._limite) throw Error('DURACION_EXCEDIDA');
  const datos = { cuerpo_retroalimentacion: JSON.stringify(cuerpo),
    http_permitidos: JSON.stringify(reg.clave === '224-invalida' ? [400, 422] : [201]) };
  const values = Object.entries({ base_url: api, token_veterinario: token,
    run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET })
    .map(([key, value]) => ({ key, value, enabled: true }));
  const plazo = Math.max(1, Math.min(PRESUPUESTO.timeout_ms, r._limite - inicio));
  let error, summary;
  try {
    [error, summary] = await new Promise(resolve => require(paqueteNewman()).run({
      collection: COLECCION, environment: { values }, iterationData: [datos],
      reporters: ['cli'], silent: true, timeoutRequest: plazo, timeout: plazo,
      ignoreRedirects: true, color: 'off'
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
    respuesta: resumenCuerpo(POST_RUTA, b),
    ...(http == null ? { tipo_fallo: error?.name === 'Error' ? 'SIN_RED' : 'TIMEOUT' } : {}) });
  r._consecutivos5xx = http >= 500 ? r._consecutivos5xx + 1 : 0;
  const sub = path.join(c.directorio, 'newman');
  fs.mkdirSync(sub, { recursive: true });
  const nombre = `newman-G065-${reg.caso.slice(-3)}-${r.solicitudes.filter(x => x.caso === reg.caso && x.metodo === 'POST').length}`;
  const reporte = { info: { nombre, herramienta: 'Newman', version: r.herramientas.newman.version },
    run: { stats: summary?.run?.stats ?? null, executions: [{ caso: reg.caso, http,
      eco: !!eco, duracion_ms: duracion, respuesta: { estado_retroalimentacion: fila.respuesta?.estado_retroalimentacion ?? null,
        fuente_diagnostico: fila.respuesta?.fuente_diagnostico ?? null,
        es_fuente_desconocida: fila.respuesta?.es_fuente_desconocida ?? null,
        error_code: fila.respuesta?.error_code ?? null, field: fila.respuesta?.field ?? null,
        catalogo_completo: fila.respuesta?.catalogo_completo ?? null },
      aserciones: (ex?.assertions ?? []).map(a => ({ nombre: String(a.assertion).slice(0, 100),
        aprobada: !a.error })) }],
      fallos: (summary?.run?.failures ?? []).map(f => ({ tipo: String(f.error?.name ?? 'Error').slice(0, 60) })),
      error: error ? String(error.name).slice(0, 60) : null } };
  const secretos = [token, env.QA_SANDBOX_SECRET, env.QA_VETERINARIO_EMAIL,
    env.QA_COMMON_PASSWORD, env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD,
    ...REGISTROS.map(x => x.observaciones)].filter(x => typeof x === 'string' && x.length >= 4);
  const sanear = texto => {
    let salida = String(texto);
    for (const valor of secretos) salida = salida.split(valor).join('[REDACTADO]');
    return salida.replace(/eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}/g, '[JWT_REDACTADO]')
      .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[CORREO_REDACTADO]');
  };
  fs.writeFileSync(path.join(sub, `${nombre}.json`), sanear(JSON.stringify(reporte, null, 2)), 'utf8');
  const escape = x => String(x ?? '').replace(/[&<>"']/g, y => ({ '&': '&amp;', '<': '&lt;',
    '>': '&gt;', '"': '&quot;', "'": '&#39;' })[y]);
  fs.writeFileSync(path.join(sub, `${nombre}.html`),
    `<!doctype html><html lang="es"><meta charset="utf-8"><title>${nombre}</title>`
    + `<h1>${nombre}</h1><p>Newman ${escape(reporte.info.version)}; ${reg.caso}; HTTP ${http ?? 'sin respuesta'}; `
    + `eco ${!!eco}; duración ${duracion} ms</p><pre>${escape(sanear(JSON.stringify(reporte.run)))}</pre></html>`, 'utf8');
  r.evidencias.push(`newman/${nombre}.json`, `newman/${nombre}.html`);
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
const idCorto = z => z?.resultado ? String(z.resultado).slice(0, 8) : 'sin resultado apto';
const solicitud = (r, caso, metodo) => r.solicitudes.find(s => s.caso === caso && s.metodo === metodo);
function detalleCaso(caso, r) {
  const x = r.casos[caso], filas = r.registros.filter(z => z.caso === caso);
  const motivo = x.motivo.replaceAll('HTTP, historial y auditoría concordantes', 'comprobación aprobada');
  const porClave = clave => filas.find(z => z.clave === clave);
  const descripcion = z => z ? `${idCorto(z)}: ${z.estado}, fuente ${z.fuente_enviada ?? 'omitida'}, HTTP ${z.http ?? 'sin respuesta'}` : 'sin POST';
  let hecho, esperado, observado, razon;
  if (caso === 'TC-M04-198') {
    const con = porClave('198-con'), sin = porClave('198-sin');
    hecho = `Se enviaron dos CORRECTO: ${idCorto(con)} con observaciones clínicas de prueba y ${idCorto(sin)} sin el campo observaciones_clinicas.`;
    esperado = 'Ambos HTTP 201; el historial debe conservar íntegro el texto enviado, incluidos acentos, signos y salto de línea; al omitir el campo debe quedar nulo (RF-72, Entrada 4164).';
    observado = `${descripcion(con)}; ${descripcion(sin)}. ${x.estado === 'APROBADO' ? 'El historial mostró el texto enviado sin cambios en el primero y nulo en el segundo; ambos registros tuvieron lectura de historial y auditoría HTTP 200.' : 'Consultar resultado.json para las comprobaciones de historial y auditoría.'}`;
    razon = x.estado === 'APROBADO' ? 'El texto se comparó carácter por carácter con el enviado y la omisión quedó nula; los dos POST fueron aceptados.' : `El resultado no cumplió la expectativa: ${motivo}.`;
  } else if (caso === 'TC-M04-199') {
    hecho = `Se enviaron cuatro INCORRECTO: ${filas.map(z => `${idCorto(z)} con ${z.fuente_enviada}`).join('; ') || 'sin resultados aptos'}.`;
    esperado = `Cada valor ${FUENTES.join(', ')} debe dar HTTP 201, conservar la fuente en respuesta y auditoría y mostrar es_fuente_desconocida=false (RF-72, Entrada 4167; Salida 4316-4317).`;
    observado = `${filas.map(z => `${idCorto(z)}: HTTP ${z.http ?? 'sin respuesta'}, ${z.fuente_observada ?? 'sin fuente'}, marca ${z.marca_observada ?? 'ausente'}`).join('; ') || 'Sin POST'}. ${x.estado === 'APROBADO' ? 'La auditoría registró esas mismas fuentes y la marca false en los cuatro casos.' : 'La verificación de auditoría se detalla en resultado.json.'}`;
    razon = x.estado === 'APROBADO' ? 'Las cuatro fuentes enviadas se conservaron en respuesta y auditoría, con marca false y HTTP 201.' : `El resultado no cumplió la expectativa: ${motivo}.`;
  } else if (caso === 'TC-M04-223') {
    hecho = `Se enviaron INCORRECTO sobre ${idCorto(porClave('223-incorrecto'))} y PARCIAL sobre ${idCorto(porClave('223-parcial'))} sin fuente; PARCIAL sobre ${idCorto(porClave('223-contraste'))} con LABORATORIO como contraste.`;
    esperado = 'Los dos registros sin fuente deben dar HTTP 201 y marca true; el contraste con LABORATORIO, HTTP 201 y marca false, también en auditoría (RF-72, 4118-4120).';
    observado = `${filas.map(z => `${idCorto(z)}: HTTP ${z.http ?? 'sin respuesta'}, marca ${z.marca_observada ?? 'ausente'}`).join('; ') || 'Sin POST'}. ${x.estado === 'APROBADO' ? 'La auditoría confirmó true, true y false, respectivamente.' : 'La verificación de auditoría se detalla en resultado.json.'}`;
    razon = x.estado === 'APROBADO' ? 'Omitir la fuente marcó true para INCORRECTO y PARCIAL; informar LABORATORIO dejó la marca false en respuesta y auditoría.' : `El resultado no cumplió la expectativa: ${motivo}.`;
  } else {
    const z = porClave('224-invalida'), post = solicitud(r, caso, 'POST'),
      indicePost = r.solicitudes.indexOf(post),
      antes = r.solicitudes.slice(0, indicePost).filter(s => s.ruta === '/prediccion/historial/885').at(-1),
      lecturas = r.solicitudes.filter(s => s.caso === caso && s.metodo === 'GET'),
      h = lecturas.find(s => s.ruta?.startsWith('/prediccion/historial/')),
      a = lecturas.find(s => s.ruta === '/prediccion/auditoria');
    hecho = `Se envió INCORRECTO sobre ${idCorto(z)} con fuente RESONANCIA_MAGNETICA, fuera del catálogo.`;
    esperado = `Rechazo que identifique fuente_diagnostico y ${FUENTES.join(', ')}, sin registro en historial ni auditoría (RF-72, Entrada 4167: Enum opcional de dominio cerrado; Regla 2, 4033-4041; matriz G065, subcaso 4: HTTP 422 recomendado).`;
    observado = `HTTP ${z?.http ?? 'sin respuesta'}, error ${post?.respuesta?.error_code ?? 'sin dato'}, campo ${post?.respuesta?.field ?? 'sin dato'}, catálogo completo ${post?.respuesta?.catalogo_completo ?? 'sin dato'}; historial con ${antes?.respuesta?.eventos ?? 'sin dato'} eventos antes y ${h?.respuesta?.eventos ?? 'sin dato'} después (HTTP ${h?.http ?? 'sin lectura'}), auditoría HTTP ${a?.http ?? 'sin lectura'} con ${a?.respuesta?.items ?? 'sin dato'} registros del intento.`;
    razon = x.estado === 'APROBADO' ? `El valor inválido se rechazó, se identificó fuente_diagnostico y el catálogo completo, y no se persistió nada. HTTP ${z?.http ?? 'sin dato'}; si fue 400, queda como observación porque RF-72 no fija 422 para esta fuente.`
      : `El resultado ${x.estado} se explica por ${motivo}.`;
  }
  return `### ${caso} — ${x.estado}\n\n**Qué se hizo:** ${hecho}\n\n**Qué se esperaba:** ${esperado}\n\n**Qué se observó:** ${observado}\n\n**Por qué ${x.estado}:** ${razon}`;
}
function observacion224(r) {
  const z = r.registros.find(x => x.clave === '224-invalida');
  if (z?.http !== 400 || z.veredicto?.estado !== 'APROBADO') return null;
  const post = solicitud(r, 'TC-M04-224', 'POST');
  const i = r.solicitudes.indexOf(post);
  const antes = r.solicitudes.slice(0, i).filter(s => s.ruta === '/prediccion/historial/885').at(-1);
  const despues = r.solicitudes.slice(i).find(s => s.caso === 'TC-M04-224' && s.ruta === '/prediccion/historial/885');
  const auditoria = r.solicitudes.slice(i).find(s => s.caso === 'TC-M04-224' && s.ruta === '/prediccion/auditoria');
  return `### OBS-M04-G065-224 — Fuente de diagnóstico fuera del catálogo responde HTTP 400; se recomienda 422 por coherencia con RF-72 E3 y E5\n\n- Caso y estado: TC-M04-224, APROBADO con observación. Certeza de la respuesta: CONFIRMADA en ${r.ambiente ?? 'el ambiente informado'}.\n- Atención sugerida: Desarrollo, por el código HTTP de la API pública; la causa raíz no está determinada.\n- Requisito y criterio: RF-72 Entrada 4167 (Enum), Regla 2 (4033-4041) y matriz G065 subcaso 4; el rechazo con campo, catálogo y sin persistencia es obligatorio. HTTP 422 es recomendado porque RF-72 no fija código para esta fuente.\n- Precondiciones: resultado de inferencia ${z.resultado ?? 'no disponible'} apto, INCORRECTO con diagnóstico real activo y fuente RESONANCIA_MAGNETICA fuera del catálogo.\n- Pasos: consultar historial; enviar POST /prediccion/retroalimentacion; consultar respuesta, historial y auditoría.\n- Observado: HTTP ${z.http}, ${post?.respuesta?.error_code ?? 'sin código'}, field=${post?.respuesta?.field ?? 'sin campo'}, catálogo completo=${post?.respuesta?.catalogo_completo ?? 'sin dato'}; historial ${antes?.respuesta?.eventos ?? 'sin lectura'} antes y ${despues?.respuesta?.eventos ?? 'sin lectura'} después; auditoría ${auditoria?.respuesta?.items ?? 'sin lectura'} registros del intento.\n- Evidencia: resultado.json del mismo RUN, registro 224-invalida y solicitudes POST, GET historial y GET auditoría.\n- Hipótesis para Desarrollo, sin causa raíz demostrada: en origin/test daefc3a5, src/prediction/domain/entities/retroalimentacion_clinica.py:62-67 lanza ValidationError; src/shared/errors.py:69-77 asigna HTTP 400 a ValidationError y src/shared/errors.py:91-98 asigna HTTP 422 a BusinessRuleError.\n- Relación: INC-M04-G051-VAL400 sigue siendo incidencia porque RF-69 E2 sí fija HTTP 422 explícitamente; G051 no se modifica.\n- Acción sugerida: considerar HTTP 422 por coherencia y evaluar su compatibilidad con clientes.`;
}
export function informe(c, r) {
  const estados = CASOS.map(x => r.casos[x].estado);
  const decision = estados.includes('RECHAZADO') ? 'RECHAZADO'
    : estados.every(x => x === 'APROBADO') ? 'APROBADO'
      : estados.includes('BLOQUEADO') ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
  const tabla = CASOS.map(caso => `| ${caso} | ${r.casos[caso].estado} | ${caso === 'TC-M04-224' && r.casos[caso].estado === 'APROBADO' && r.registros.find(z => z.clave === '224-invalida')?.http === 400 ? 'Rechazo completo sin persistencia; HTTP 400 en lugar del 422 recomendado (observación OBS-M04-G065-224).' : r.casos[caso].estado === 'APROBADO' ? 'Cumplió las comprobaciones de respuesta, historial y auditoría descritas abajo.' : corto(r.casos[caso].motivo)} |`).join('\n');
  const detalles = CASOS.map(caso => detalleCaso(caso, r)).join('\n\n');
  const filas = r.registros.map(z => `| ${z.clave} | ${z.resultado ?? 'sin dato'} | ${z.estado} | ${z.fuente_enviada ?? 'omitida'} | ${z.http ?? 'sin respuesta'} | ${z.fuente_observada ?? 'nula'} | ${z.marca_observada ?? 'ausente'} |`).join('\n');
  const especial224 = observacion224(r);
  const incidencias = r.incidencias.map(x => `- ${x.casos.join(', ')}: ${x.severidad}, certeza ${x.certeza}; contacto inicial ${x.equipo_inicial} por ${x.fundamento}. ${corto(x.motivo)}. Causa raíz: no determinada.`)
    .join('\n\n') || 'Ninguna.';
  const frase = decision === 'APROBADO' && especial224
    ? 'Los cuatro casos cumplen RF-72: observaciones opcionales, fuente persistida, marca de fuente desconocida y rechazo de la fuente fuera del catálogo sin persistir; la respuesta a la fuente inválida usa HTTP 400 en lugar del 422 recomendado, registrado como observación.'
    : 'La decisión se basa en las comprobaciones API descritas por caso y en resultado.json.';
  return `# TC-M04-G065 — ${decision}\n\n## Identificación\n\nGrupo G065; casos ${CASOS.join(', ')}; RF-72; versión ${c.version}; RUN ${c.runId}; ambiente ${c.ensayo ? 'loopback local' : 'TEST'}; autorización ${c.referencia}; contrato revisado origin/test daefc3a5; Node.js. Solo API.\n\n## Decisión del caso\n\n${frase}\n\n| Caso | Estado | Motivo |\n|---|---|---|\n${tabla}\n\nRUN oficial: ${r.oficial ? 'sí' : 'no'}. Qué falta: ${r.oficial ? 'nada para este grupo' : 'resolver datos, barreras técnicas o rollback pendiente'}; el ensayo loopback nunca constituye evidencia TEST.\n\n## Precondición de datos (semilla)\n\n${r.diagnostico_seleccion?.resumen ? `${r.diagnostico_seleccion.resumen.eventos} eventos examinados; modelos ${JSON.stringify(r.diagnostico_seleccion.resumen.por_modelo)}; ${r.registros.filter(z => z.resultado).length}/10 resultados asignados. Se requieren 10 inferencias distintas de modelo INDIVIDUAL, sin retroalimentación previa del Veterinario, con patología activa aplicable. La procedencia de la semilla externa debe constar en la orquestación.` : 'Descubrimiento no completado.'}\n\n## Detalle por caso\n\n${detalles}\n\n## Registros y observaciones\n\n| Registro | Resultado | Estado enviado | Fuente enviada | HTTP | Fuente observada | Marca observada |\n|---|---|---|---|---:|---|---|\n${filas}\n\nObservaciones: ${r.observaciones.map(corto).join('; ') || 'sin otras observaciones'}. El texto clínico de prueba se compara en memoria y no se vuelca al informe.\n\n## Observación QA\n\n${especial224 ?? 'Sin observaciones.'}\n\n## Incidencias de producto\n\n${incidencias}\n\n## Problemas técnicos y causas\n\n${r.problemas_tecnicos.map(corto).join('; ') || 'Sin problemas técnicos registrados.'} Las discrepancias de API orientan el contacto inicial, sin atribuir causa raíz.\n\n## Historial, cierre y rollback\n\n${r.solicitudes.length} solicitudes; DELETE HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}; rollback ${r.cierre.rollback.verificado ? 'verificado por lectura pública' : 'no verificado'}: ${corto(r.cierre.rollback.motivo)}. Las lecturas poscierre pueden crear HISTORIAL_CONSULTADO fuera del sandbox; no prueban ausencia de esos eventos.\n\n## Conclusión y acciones\n\n${decision === 'APROBADO' ? 'Las cuatro comprobaciones públicas concordaron; conservar evidencias del RUN y considerar la recomendación de HTTP 422 de la observación, si aplica.' : decision === 'RECHAZADO' ? 'Desarrollo debe ajustar la ruta para responder HTTP 422; QA debe repetir TC-M04-224 en un RUN autorizado y verificar respuesta y no persistencia.' : 'Conciliar respuestas ausentes, preparar datos aptos o recuperar el cierre antes de un nuevo intento.'}\n\n## Herramientas\n\n${r.solicitudes.some(x => x.herramienta === 'Newman') ? `Solicitudes y aserciones de Newman ${r.herramientas.newman.version}; reportes reales saneados en newman/.` : `No hubo POST evaluados con Newman (${r.herramientas.newman.version ?? 'no disponible'}); no se generaron reportes Newman.`} Login, lecturas y cierre mediante API con fetch.\n\n## Evidencias\n\n${r.evidencias.map(x => `- ${x}`).join('\n')}\n`;
}

export async function evaluar(c, { env = leerEnv(), newmanVersion = versionNewman() } = {}) {
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G065', version: c.version, run_id: c.runId, operacion: c.operacion,
    ambiente: c.ensayo ? 'LOOPBACK_LOCAL' : 'TEST', casos: Object.fromEntries(CASOS.map(x => [x,
      { estado: 'NO_CONCLUYENTE', motivo: 'No ejecutado' }])), comprobaciones: [], registros: [],
    datos_elegidos: {}, diagnostico_seleccion: {}, solicitudes: [], observaciones: [],
    problemas_tecnicos: [], incidencias: [], herramientas: { newman: newmanVersion },
    cypress: { total_pruebas: 0 },
    evidencias: ['preflight.json', 'resultado.json', INFORME(c.version)],
    cierre: { run: { cierre_http: null }, rollback: { verificado: false, motivo: 'Sin cierre' } },
    oficial: false, consume_version: false, _limite: Date.now() + 900000, _consecutivos5xx: 0 };
  fs.mkdirSync(c.directorio, { recursive: true });
  const pre = preflight(c, env, newmanVersion); guardar(path.join(c.directorio, 'preflight.json'), pre);
  let token = null, adminToken = null, adminIntentado = false, iniciado = false, usuarioId = null;
  const pedirRun = async (m, p, opts = {}) => {
    const x = await pedir(r, api, m, p, { ...opts, token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId });
    if (x.http === 403 && !p.startsWith('/prediccion/auditoria')) throw Error('CLAVE_403');
    if (r._consecutivos5xx >= 3) throw Error('TRES_5XX_CONSECUTIVOS');
    return x;
  };
  const inicio = fecha(Date.now() - PRESUPUESTO.dias_busqueda * 86400000), fin = fecha(Date.now());
  const leerAuditoria = async (p, caso) => {
    let x = await pedirRun('GET', p, { caso });
    if (x.http === 403 && env.QA_ADMIN_EMAIL && env.QA_ADMIN_PASSWORD) {
      if (!adminIntentado) {
        adminIntentado = true;
        const login = await pedir(r, api, 'POST', '/sesiones/', { cuerpo: {
          correo_electronico: env.QA_ADMIN_EMAIL, contrasena: env.QA_ADMIN_PASSWORD },
        timeout: PRESUPUESTO.timeout_login_ms });
        adminToken = login.http === 200 ? login.cuerpo?.token : null;
      }
      if (adminToken) x = await pedir(r, api, 'GET', p, { caso, token: adminToken,
        secreto: env.QA_SANDBOX_SECRET, runId: c.runId });
    }
    return { http: x.http, eco: x.eco, items: x.cuerpo?.items ?? [],
      completo: x.http === 200 && Number(x.cuerpo?.total ?? Infinity) <= (x.cuerpo?.items?.length ?? 0) };
  };
  try {
    if (!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
    const login = await pedir(r, api, 'POST', '/sesiones/', { cuerpo: {
      correo_electronico: env.QA_VETERINARIO_EMAIL, contrasena: env.QA_COMMON_PASSWORD },
    timeout: PRESUPUESTO.timeout_login_ms });
    if (login.http !== 200 || !login.cuerpo?.token) throw Error(`LOGIN_${login.http ?? 'SIN_RESPUESTA'}`);
    token = login.cuerpo.token; usuarioId = usuarioDelToken(token); iniciado = true;
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
    const cat = await pedirRun('GET', '/prediccion/patologias?solo_activas=true');
    const patologias = (cat.cuerpo?.items ?? []).filter(p => p.es_activo);
    r.diagnostico_seleccion.resumen = diagnosticar(eventos, usuarioId, versiones);
    const usados = new Set();
    const candidatos = seleccionar(eventos, patologias, usados, usuarioId, versiones, inicio, fin);
    for (const reg of REGISTROS) {
      let dato = candidatos.find(e => !usados.has(String(e.id_resultado_inferencia)));
      if (!dato) { r.registros.push({ caso: reg.caso, clave: reg.clave, estado: reg.estado,
        fuente_enviada: reg.fuente ?? null, resultado: null }); continue; }
      let post = null, cuerpo = null, patologia = null;
      const instantePost = new Date(Date.now() - 60000).toISOString();
      for (let intento = 0; intento <= PRESUPUESTO.reemplazos_por_registro; intento++) {
        usados.add(String(dato.id_resultado_inferencia));
        patologia = patologias.find(p => p.es_activo
          && ['TODAS', String(dato.id_especie)].includes(String(p.especie_aplicable)));
        cuerpo = { id_resultado_inferencia: dato.id_resultado_inferencia,
          id_activo_biologico: dato.id_activo_biologico, estado_retroalimentacion: reg.estado,
          diagnosticos_reales: reg.estado === 'CORRECTO' ? null : [patologia.id_patologia],
          ...(reg.fuente ? { fuente_diagnostico: reg.fuente } : {}),
          ...(reg.observaciones ? { observaciones_clinicas: reg.observaciones } : {}) };
        post = await pedirNewman(r, c, api, env, token, reg, cuerpo);
        if (post.http === 403) throw Error('CLAVE_403');
        if (r._consecutivos5xx >= 3) throw Error('TRES_5XX_CONSECUTIVOS');
        if (!([409, 422].includes(post.http) && ['RETROALIMENTACION_DUPLICADA',
          'FUERA_DE_VENTANA_TEMPORAL'].includes(post.cuerpo?.error_code))) break;
        r.observaciones.push(`${reg.clave}: dato no apto (${post.cuerpo.error_code}); se busca reemplazo`);
        dato = candidatos.find(e => !usados.has(String(e.id_resultado_inferencia)));
        if (!dato) break;
      }
      const elegido = { id_resultado_inferencia: dato?.id_resultado_inferencia ?? null,
        id_activo_biologico: dato?.id_activo_biologico ?? null, fecha_inferencia: dato?.fecha_evento ?? null,
        tipo_modelo: tipoModelo(dato, versiones), id_patologia_real: patologia?.id_patologia ?? null };
      r.datos_elegidos[reg.clave] = elegido;
      const fila = { caso: reg.caso, clave: reg.clave, estado: reg.estado,
        resultado: elegido.id_resultado_inferencia, fuente_enviada: reg.fuente ?? null,
        http: post?.http ?? null, fuente_observada: post?.cuerpo?.fuente_diagnostico ?? null,
        marca_observada: post?.cuerpo?.es_fuente_desconocida ?? null };
      r.registros.push(fila);
      if (post?.http == null) {
        fila.veredicto = { estado: 'NO_CONCLUYENTE', motivo: 'POST sin respuesta; conciliación necesaria' };
        throw Error('POST_SIN_RESPUESTA');
      }
      let h = null, a = null;
      if (post.http === 201 || reg.clave === '224-invalida') {
        h = await historial(p => pedirRun('GET', p, { caso: reg.caso }),
          dato.id_activo_biologico, inicio, fin, post.http === 201 ? post.cuerpo?.id_retroalimentacion : null);
        if (reg.clave === '224-invalida') {
          const desde = encodeURIComponent(instantePost);
          a = await leerAuditoria(`/prediccion/auditoria?tipo_evento=RETROALIMENTACION_REGISTRADA&fecha_desde=${desde}&id_usuario=${usuarioId}&por_pagina=200`, reg.caso);
        } else a = await leerAuditoria(`/prediccion/auditoria?tipo_evento=RETROALIMENTACION_REGISTRADA&id_referencia=${post.cuerpo.id_retroalimentacion}&por_pagina=20`, reg.caso);
      }
      fila.historial_http = h?.http ?? null; fila.auditoria_http = a?.http ?? null;
      fila.veredicto = verificarRegistro({ ...reg, dato: elegido }, post, h, a, usuarioId);
    }
  } catch (e) {
    r.problemas_tecnicos.push(`Interrupción: ${corto(e.message)}`);
    const bloqueo = /LOGIN|CLAVE_403|TRES_5XX|PREFLIGHT/.test(e.message);
    for (const reg of REGISTROS) if (!r.registros.some(z => z.clave === reg.clave))
      r.registros.push({ caso: reg.caso, clave: reg.clave, estado: reg.estado,
        fuente_enviada: reg.fuente ?? null, resultado: null,
        veredicto: { estado: bloqueo ? 'BLOQUEADO' : 'NO_CONCLUYENTE',
          motivo: `Interrupción técnica: ${corto(e.message)}` } });
  } finally {
    if (iniciado) {
      const cierre = await pedir(r, api, 'DELETE', `/test-control/runs/${encodeURIComponent(c.runId)}`,
        { secreto: env.QA_SANDBOX_SECRET });
      r.cierre.run.cierre_http = cierre.http;
      const examinados = r.registros.filter(z => z.resultado);
      let ausentes = cierre.http === 200 && examinados.some(z => z.http === 201);
      for (const z of examinados) {
        const d = r.datos_elegidos[z.clave], id = r.solicitudes.find(s => s.caso === z.caso
          && s.metodo === 'POST' && s.respuesta?.id_resultado_inferencia === z.resultado)?.respuesta?.id_retroalimentacion;
        const h = await historial(p => pedir(r, api, 'GET', p, { token, caso: z.caso }),
          d.id_activo_biologico, inicio, fin, null);
        if (h.http !== 200 || !h.completo || h.eventos.some(e =>
          id ? String(e.id_evento) === String(id) : e.tipo_evento === 'RETROALIMENTACION'
          && String(e.id_resultado_inferencia) === String(z.resultado)
          && String(e.payload?.id_usuario_veterinario) === String(usuarioId)))
          ausentes = false;
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
      const error224 = z.caso === 'TC-M04-224' && z.http === 400
        && z.veredicto.motivo === 'HTTP 400; esperado 422';
      const post224 = error224 && solicitud(r, z.caso, 'POST');
      const indice224 = r.solicitudes.indexOf(post224);
      const historialAntes = r.solicitudes.slice(0, indice224).filter(s => s.ruta === '/prediccion/historial/885').at(-1);
      const historialDespues = r.solicitudes.slice(indice224).find(s => s.caso === z.caso && s.ruta === '/prediccion/historial/885');
      const sinPersistencia = error224 && post224?.respuesta?.error_code === 'FUENTE_DIAGNOSTICO_INVALIDA'
        && post224?.respuesta?.field === 'fuente_diagnostico' && post224?.respuesta?.catalogo_completo === true
        && historialAntes?.http === 200 && historialDespues?.http === 200
        && historialAntes?.respuesta?.eventos === historialDespues?.respuesta?.eventos
        && r.solicitudes.some(s => s.caso === z.caso && s.ruta === '/prediccion/auditoria' && s.respuesta?.items === 0);
      const severidad = sinPersistencia ? 'BAJA' : /persistió registro inválido|se auditó registro inválido/.test(z.veredicto.motivo) ? 'ALTA' : 'MEDIA';
      if (!grupos.has(motivo)) grupos.set(motivo, { casos: [], severidad,
        certeza: 'CONFIRMADA', equipo_inicial: 'Desarrollo', fundamento: 'primera discrepancia en API pública',
        motivo: z.veredicto.motivo, causa_raiz: 'NO DETERMINADA' });
      if (!grupos.get(motivo).casos.includes(z.caso)) grupos.get(motivo).casos.push(z.caso);
    }
    r.incidencias = [...grupos.values()];
    r.oficial = CASOS.every(x => ['APROBADO', 'RECHAZADO'].includes(r.casos[x].estado))
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
  const salida = { grupo: 'G065', run_objetivo: c.runId, operacion: 'recuperar',
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
      const r = await recuperar(c); console.log(JSON.stringify({ grupo: 'G065', rollback_verificado: r.rollback_verificado }));
      if (!r.rollback_verificado) process.exitCode = 2;
    } else { const r = await evaluar(c); console.log(JSON.stringify({ grupo: 'G065', run_id: r.run_id,
      oficial: r.oficial, casos: Object.fromEntries(CASOS.map(x => [x, r.casos[x].estado])) }));
      if (!r.oficial) process.exitCode = 2; }
  } catch (e) { console.error(corto(e.message)); process.exitCode = 2; }
}
