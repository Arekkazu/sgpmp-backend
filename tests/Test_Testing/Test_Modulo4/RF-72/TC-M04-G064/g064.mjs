#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { CASOS, IDS, ESTADOS, PRESUPUESTO, CAPACIDADES, seleccionar, diagnosticar, decidirCaso } from './lib/g064_escenario.mjs';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION = JSON.parse(fs.readFileSync(path.join(DIR, 'G064.postman_collection.json'), 'utf8'));
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
  }
  catch { return { ok: false, error: 'NEWMAN_NO_DISPONIBLE' }; }
}
function coleccionValida() {
  try {
    const c = JSON.parse(fs.readFileSync(path.join(DIR, 'G064.postman_collection.json'), 'utf8'));
    for (const i of c.item) for (const e of i.event ?? []) new vm.Script((e.script?.exec ?? []).join('\n'));
    const h = c.item[0].request.header.map(x => x.key.toLowerCase());
    return c.item.length === 1 && c.item[0].request.method === 'POST'
      && c.item[0].request.url.raw.includes('/prediccion/retroalimentacion')
      && ['authorization', 'x-test-run-id', 'x-sandbox-secret'].every(x => h.includes(x));
  } catch { return false; }
}
const INFORME = v => v === 1 ? 'TC-M04-G064_resultado.md' : `TC-M04-G064_reevaluacion_V${v}.md`;
const corto = x => String(x ?? '').replace(/[\r\n|]/g, ' ').slice(0, 240);
const fecha = d => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota',
  year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(d));
const rutaHistorial = (id, inicio, fin, cursor) => `/prediccion/historial/${id}?fecha_inicio=${inicio}&fecha_fin=${fin}${cursor ? `&cursor_paginacion=${encodeURIComponent(cursor)}` : ''}`;
function usuarioDelToken(token) {
  try {
    const partes = String(token).split('.');
    if (partes.length !== 3) return null;
    const sub = JSON.parse(Buffer.from(partes[1], 'base64url').toString('utf8')).sub;
    return /^\d+$/.test(String(sub)) ? String(sub) : null;
  } catch { return null; }
}
async function leerHistorial(pedirPagina, activo, inicio, fin, idBuscado) {
  const eventos = [];
  let cursor = null, pagina;
  for (let n = 0; n < PRESUPUESTO.paginas_historial_verificacion; n++) {
    pagina = await pedirPagina(rutaHistorial(activo, inicio, fin, cursor));
    if (pagina.http !== 200 || pagina.eco === false) return pagina;
    eventos.push(...(pagina.cuerpo?.eventos ?? []));
    cursor = pagina.cuerpo?.cursor_siguiente ?? null;
    if (eventos.some(e => String(e.id_evento) === String(idBuscado)) || !cursor) break;
  }
  return { ...pagina, cuerpo: { ...pagina.cuerpo, eventos, cursor_siguiente: cursor } };
}

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
  const archivos = ['g064.mjs', 'lib/g064_escenario.mjs', 'G064.postman_collection.json',
    'pruebas/g064_ensayo.mjs', 'pruebas/g064_env.test.mjs', 'pruebas/registro_qa.mjs', 'README.md'];
  const faltantes = archivos.filter(x => !fs.existsSync(path.join(DIR, x)));
  const coleccion = coleccionValida();
  const markdownSuperior = fs.existsSync(path.join(DIR, 'Resultados'))
    && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const newman = versionNewman();
  const ok = !faltantes.length && coleccion && !markdownSuperior && newman.ok;
  console.log(JSON.stringify({ grupo: 'G064', ok, faltantes, coleccion, markdownSuperior,
    presupuesto: PRESUPUESTO, newman }));
  return ok ? 0 : 2;
}
function contexto(args, ensayo = false) {
  const v = k => args.includes(k) ? args[args.indexOf(k) + 1] : undefined;
  const operacion = v('--operacion'), version = Number(v('--version')),
    intento = Number(v('--intento')), runId = v('--run-id'), referencia = v('--autorizacion'),
    archivo = v('--contexto');
  if (!CAPACIDADES.operaciones.includes(operacion) || !Number.isInteger(version) || version < 1
    || !Number.isInteger(intento) || intento < 1 || !referencia || !archivo
    || !new RegExp(`^RUN-G064-V${version}-\\d{8}-\\d{6}$`).test(runId ?? ''))
    throw Error('Contexto de ejecución incompleto');
  const destino = path.join(DIR, version === 1 ? 'Resultados' : `EvaluacionV${version}`,
    version === 1 ? runId : 'Resultados', ...(version === 1 ? [] : [runId]));
  const ruta = path.resolve(archivo);
  if (!ensayo && (path.dirname(ruta) !== destino || !(operacion === 'recuperar'
    ? /^recuperacion-\d{14}\.contexto\.json$/.test(path.basename(ruta))
    : path.basename(ruta) === 'contexto_operacion.json')))
    throw Error('Contexto fuera del RUN canónico');
  if (ensayo && !ruta.startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('Ensayo fuera de temporal');
  const c = JSON.parse(fs.readFileSync(ruta, 'utf8'));
  if (c.grupo !== 'G064' || c.run_id !== runId || c.version !== version || c.intento !== intento
    || c.operacion !== operacion.toUpperCase() || c.referencia !== referencia
    || JSON.stringify(c.casos) !== JSON.stringify(CASOS)
    || (operacion === 'reevaluar' && (version < 2 || c.version_anterior !== version - 1
      || !c.alcance_reevaluacion)) || (operacion === 'recuperar' && v('--run-objetivo') !== runId))
    throw Error('Contexto incoherente');
  return { operacion, version, intento, runId, referencia, directorio: path.dirname(ruta), ensayo };
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
  return { grupo: 'G064', run_id: c.runId, ok: !barreras.length, barreras,
    presupuesto: PRESUPUESTO, herramientas: { newman },
    efectos: ['login', 'lecturas', 'retroalimentaciones',
      'RETROALIMENTACION_REGISTRADA', 'CONFLICTO_RETROALIMENTACION posible', 'DELETE sandbox'] };
}
function guardar(archivo, valor) { fs.writeFileSync(archivo, JSON.stringify(valor, null, 2), 'utf8'); }
function resumenCuerpo(endpoint, b) {
  if (!b || typeof b !== 'object') return null;
  if (endpoint.startsWith('/sesiones/')) return { token_recibido: !!b.token };
  if (endpoint.startsWith('/prediccion/retroalimentacion')) return {
    id_retroalimentacion: b.id_retroalimentacion ?? null, id_resultado_inferencia: b.id_resultado_inferencia ?? null,
    id_activo_biologico: b.id_activo_biologico ?? null, estado_retroalimentacion: b.estado_retroalimentacion ?? null,
    diagnosticos_reales: b.diagnosticos_reales ?? null, estado_registro: b.estado_registro ?? null,
    fecha_retroalimentacion: b.fecha_retroalimentacion ?? null, es_fuente_desconocida: b.es_fuente_desconocida ?? null,
    error_code: b.error_code ?? null, message: b.message ?? null };
  return { total: b.total ?? b.total_registros ?? b.total_pagina ?? null,
    registros: b.registros?.length ?? null, eventos: b.eventos?.length ?? null, items: b.items?.length ?? null,
    error_code: b.error_code ?? null };
}
async function pedir(r, api, metodo, endpoint, { token, secreto, runId, cuerpo, caso,
  timeout = PRESUPUESTO.timeout_ms } = {}) {
  if (r.solicitudes.length >= PRESUPUESTO.solicitudes_totales) throw Error('PRESUPUESTO_AGOTADO');
  const fila = { caso: caso ?? null, metodo, ruta: endpoint.replace(/\?.*/, '?[filtro]'), http: null };
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
      duracion_ms: Date.now() - inicio, respuesta: resumenCuerpo(endpoint, b) });
    r._consecutivos5xx = x.status >= 500 ? r._consecutivos5xx + 1 : 0;
    return { http: x.status, cuerpo: b, eco: fila.eco };
  } catch (e) {
    Object.assign(fila, { tipo_fallo: ['TimeoutError', 'AbortError'].includes(e.name) ? 'TIMEOUT' : 'SIN_RED',
      duracion_ms: Date.now() - inicio });
    return { http: null, cuerpo: null };
  }
}
async function pedirNewman(r, c, api, env, token, caso, cuerpo) {
  if (r.solicitudes.length >= PRESUPUESTO.solicitudes_totales) throw Error('PRESUPUESTO_AGOTADO');
  const fila = { caso, metodo: 'POST', ruta: POST_RUTA, http: null, herramienta: 'Newman' };
  r.solicitudes.push(fila);
  const inicio = Date.now();
  if (inicio >= r._limite) throw Error('DURACION_EXCEDIDA');
  const datos = { cuerpo_retroalimentacion: JSON.stringify(cuerpo),
    estado_retroalimentacion: cuerpo.estado_retroalimentacion };
  const values = Object.entries({ base_url: api, token_veterinario: token,
    run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET })
    .map(([key, value]) => ({ key, value, enabled: true }));
  const plazo = Math.max(1, Math.min(PRESUPUESTO.timeout_ms, r._limite - inicio));
  let error, summary;
  try {
    [error, summary] = await new Promise(resolve => require(paqueteNewman()).run({
      collection: COLECCION, environment: { values }, iterationData: [datos],
      reporters: ['cli'], silent: true,
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
    respuesta: resumenCuerpo(POST_RUTA, b), ...(http == null ? { tipo_fallo: error?.name === 'Error' ? 'SIN_RED' : 'TIMEOUT' } : {}) });
  r._consecutivos5xx = http >= 500 ? r._consecutivos5xx + 1 : 0;
  const sub = path.join(c.directorio, 'newman');
  fs.mkdirSync(sub, { recursive: true });
  const nombre = `newman-G064-${caso.slice(-3)}-${r.solicitudes.filter(x => x.caso === caso && x.metodo === 'POST').length}`;
  const fallos = (summary?.run?.failures ?? []).map(f => ({
    name: corto(f.error?.name), message: corto(f.error?.message) }));
  const reporte = { info: { nombre, herramienta: 'Newman', version: r.herramientas.newman.version },
    run: { stats: summary?.run?.stats ?? null, executions: [{ caso, http, eco: !!eco,
      duracion_ms: duracion, respuesta: fila.respuesta }], failures: fallos,
      error: error ? corto(error.name) : null } };
  const secretos = [token, env.QA_SANDBOX_SECRET, env.QA_VETERINARIO_EMAIL,
    env.QA_COMMON_PASSWORD, env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD].filter(x => typeof x === 'string' && x.length >= 4);
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
    + `<h1>${nombre}</h1><p>Newman ${escape(reporte.info.version)}; ${caso}; HTTP ${http ?? 'sin respuesta'}; `
    + `eco ${!!eco}; duración ${duracion} ms</p><pre>${escape(sanear(JSON.stringify(reporte.run)))}</pre></html>`, 'utf8');
  r.evidencias.push(`newman/${nombre}.json`, `newman/${nombre}.html`);
  return { http, cuerpo: b, eco: !!eco };
}
function informe(c, r) {
  const estados = CASOS.map(x => r.casos[x].estado);
  const decision = estados.includes('RECHAZADO') ? 'RECHAZADO'
    : estados.every(x => x === 'APROBADO') ? 'APROBADO'
      : estados.includes('BLOQUEADO') ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
  const resumen = CASOS.map((caso, i) => {
    const x = r.casos[caso], d = r.datos_elegidos[caso];
    const mensaje = x.estado === 'APROBADO'
      ? `${ESTADOS[i]} aceptado con HTTP 201${i >= 2 ? '; diagnóstico principal registrado' : '; sin diagnóstico real'}; historial y auditoría concordantes.`
      : d ? `Comprobación pendiente o discrepante: ${corto(x.motivo)}` : `No se encontró un resultado apto: ${corto(x.motivo)}`;
    return `| ${caso} | ${x.estado} | ${mensaje} |`;
  }).join('\n');
  const detalle = CASOS.map((caso, i) => {
    const d = r.datos_elegidos[caso], x = r.casos[caso];
    const ss = r.solicitudes.filter(s => s.caso === caso);
    const post = ss.find(s => s.metodo === 'POST');
    const b = post?.respuesta;
    const historial = ss.find(s => s.metodo === 'GET' && s.ruta.startsWith('/prediccion/historial/'));
    const auditoria = ss.find(s => s.metodo === 'GET' && s.ruta.startsWith('/prediccion/auditoria'));
    const posterior = ss.filter(s => s.metodo === 'GET' && s.ruta.startsWith('/prediccion/historial/')).at(-1);
    const hecho = d
      ? `Se eligió el resultado ${d.id_resultado_inferencia} del activo ${d.id_activo_biologico}, inferido el ${d.fecha_inferencia}, con riesgo ${d.nivel_riesgo} y patología estimada ${d.id_patologia_estimada ?? 'ninguna'}. El Veterinario envió ${ESTADOS[i]}${d.id_patologia_real == null ? ' sin diagnóstico real' : ` con diagnóstico real ${d.id_patologia_real} como principal`}.`
      : 'No se seleccionó un resultado apto ni se envió retroalimentación clínica.';
    const esperado = `La matriz G064 pide HTTP 201 y estado ${ESTADOS[i]}${i === 0 ? ', sin diagnósticos reales, registro ACTIVO y fecha asignada' : i === 1 ? ' para la predicción de riesgo sin evento posterior (falso positivo)' : i === 2 ? ', con el diagnóstico activo como principal' : ', con diagnóstico activo distinto del estimado (falso negativo)'}; RF-72 líneas 3987-3988, 4067-4068, 4156-4167, 4299-4323 y CA-1/CA-4/CA-5.`;
    const observado = post
      ? `La respuesta fue HTTP ${post.http ?? 'sin respuesta'}, estado ${b?.estado_retroalimentacion ?? 'ausente'}, diagnosticos_reales ${JSON.stringify(b?.diagnosticos_reales ?? null)}, estado_registro ${b?.estado_registro ?? 'ausente'}, fecha_retroalimentacion ${b?.fecha_retroalimentacion ?? 'ausente'} y es_fuente_desconocida ${b?.es_fuente_desconocida ?? 'ausente'}. Historial ${historial ? `HTTP ${historial.http ?? 'sin respuesta'}` : 'sin lectura'}; auditoría ${auditoria ? `HTTP ${auditoria.http ?? 'sin respuesta'}` : 'sin lectura'}; historial poscierre ${posterior && posterior !== historial ? `HTTP ${posterior.http ?? 'sin respuesta'}` : 'sin lectura'}.`
      : 'No hubo POST clínico ni comprobaciones posteriores de historial y auditoría.';
    const razon = x.estado === 'APROBADO'
      ? `Coinciden HTTP 201, estado ${ESTADOS[i]}, ${i >= 2 ? `diagnóstico principal ${d.id_patologia_real}` : 'diagnósticos reales nulos'}, registro ACTIVO y fecha asignada; el historial y la auditoría corroboraron el registro y la lectura poscierre acreditó su ausencia. ${i === 1 ? 'SIN_EVENTO representa el falso positivo según RF-72 3987-3988.' : i === 3 ? 'INCORRECTO representa el falso negativo según RF-72 3987-3988.' : ''}`
      : corto(x.motivo);
    return `### ${caso} — ${x.estado}\n\n**Qué se hizo:** ${hecho}\n\n**Qué se esperaba:** ${esperado}\n\n**Qué se observó:** ${observado}\n\n**Por qué ${x.estado}:** ${razon}`;
  }).join('\n\n');
  const datos = CASOS.map(caso => {
    const d = r.datos_elegidos[caso];
    return `| ${caso} | ${d?.id_resultado_inferencia ?? 'sin dato'} | ${d?.id_activo_biologico ?? '—'} | ${d?.fecha_inferencia ?? '—'} | ${d?.nivel_riesgo ?? '—'} | ${d?.tipo_modelo ?? '—'} | ${d?.id_patologia_estimada ?? '—'} | ${d?.id_patologia_real ?? '—'} |`;
  }).join('\n');
  const h = r.diagnostico_seleccion?.historiales ?? [];
  const precondicion = h.length
    ? `El descubrimiento localizó ${h.reduce((n, x) => n + (x.resumen?.por_tipo_evento?.INFERENCIA ?? 0), 0)} inferencias en los activos examinados; ${CASOS.filter(x => r.datos_elegidos[x]).length} casos tuvieron un resultado elegido. Los datos y descartes constan en resultado.json. La procedencia y permanencia de una semilla externa deben documentarse con su registro de orquestación cuando corresponda.`
    : 'No consta un diagnóstico de selección de datos en este resultado; consultar resultado.json antes de atribuir una semilla.';
  return `# TC-M04-G064 — ${decision}\n\n## Identificación\n\nGrupo G064; casos ${CASOS.join(', ')}; RF-72; versión ${c.version}; RUN ${c.runId}; ambiente ${c.ensayo ? 'loopback local' : 'TEST'}; autorización ${c.referencia}; commit de contrato origin/test daefc3a5; herramienta Node.js.\n\n## Decisión del caso\n\n| Caso | Estado | Motivo |\n|---|---|---|\n${resumen}\n\nRUN oficial: ${r.oficial ? 'sí' : 'no'}. Qué falta: ${r.oficial ? 'ninguna comprobación obligatoria' : 'resolver los casos no concluyentes, barreras técnicas o el rollback'}.\n\n## Precondición de datos (semilla)\n\n${precondicion}\n\n## Detalle por caso\n\n${detalle}\n\n${seccionDiagnostico(r)}## Datos elegidos y justificación\n\n| Caso | Resultado | Activo | Fecha inferencia | Riesgo | Modelo | Estimada | Real |\n|---|---|---:|---|---:|---|---:|---:|\n${datos}\n\n## Observaciones e incidencias\n\n${r.observaciones.map(x => `- ${corto(x)}`).join('\n') || 'Sin observaciones.'}\n\n${r.incidencias.map(x => `- ${x.casos.join(', ')}: ${x.severidad}, ${x.certeza}; ${x.equipo_inicial} (${x.fundamento}); ${corto(x.motivo)}. Causa raíz: no determinada.`).join('\n') || 'Sin incidencias de producto confirmadas.'}\n\n## Historial, cierre y rollback\n\n${r.solicitudes.length} solicitudes; cierre HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}; rollback ${r.cierre.rollback.verificado ? 'verificado para las retroalimentaciones mediante lecturas públicas' : 'no verificado'} (${corto(r.cierre.rollback.motivo)}). Las consultas públicas posteriores al cierre pueden generar eventos RF-67 fuera del sandbox; esta verificación no abarca esos eventos ni un posible respaldo local RF-73.\n\n## Conclusión y acciones\n\n${decision === 'APROBADO' ? 'Los cuatro estados cumplieron las comprobaciones públicas.' : decision === 'RECHAZADO' ? 'Derivar las discrepancias confirmadas a Desarrollo con las solicitudes y lecturas del caso.' : 'Conciliar las solicitudes sin respuesta o preparar datos aptos y reintentar solo los casos afectados.'}\n\n## Evidencias\n\n${r.evidencias.map(x => `- ${x}`).join('\n')}\n`;
}
function seccionDiagnostico(r) {
  const d = r.diagnostico_seleccion;
  const filas = (d?.historiales ?? []).map(h => {
    const s = h.resumen;
    if (!s) return `- Activo ${h.activo}: ${h.paginas} página(s), lectura incompleta.`;
    return `- Activo ${h.activo}: ${s.eventos} eventos en ${h.paginas} página(s); tipos ${JSON.stringify(s.por_tipo_evento)}; inferencias por modelo ${JSON.stringify(s.inferencias_por_tipo_modelo)}; fechas ${s.fecha_evento_desde ?? 'sin eventos'} a ${s.fecha_evento_hasta ?? 'sin eventos'}; riesgo ${JSON.stringify(s.nivel_riesgo)}; con patología ${s.inferencias_con_patologia}; ya retroalimentadas por este usuario ${s.inferencias_retroalimentadas_usuario ?? 'no identificable'}; cursor pendiente ${h.cursor_pendiente ? 'sí' : 'no'}.`;
  });
  const a = d?.agregado;
  return `## Diagnóstico saneado de selección\n\n${filas.join('\n') || 'No se leyeron historiales.'}\n\n${a ? `Criterios de descarte, con solapamiento: ${JSON.stringify(a.descarte)}. Inferencias por modelo: ${JSON.stringify(a.inferencias_por_tipo_modelo)}. Riesgo: ${JSON.stringify(a.nivel_riesgo)}. Con patología: ${a.inferencias_con_patologia}. Ya retroalimentadas por este usuario: ${a.inferencias_retroalimentadas_usuario ?? 'no identificable'}.` : 'No se completó el diagnóstico.'} Versiones consultadas: ${d?.versiones_consultadas ?? 0}; tipos recuperados por versión: ${d?.tipos_recuperados ?? 0}; versiones sin resolver: ${d?.versiones_sin_resolver ?? 0}. No se guardan observaciones clínicas ni identificadores de usuario.\n\n`;
}
export async function evaluar(c, { env = leerEnv(), newmanVersion = versionNewman() } = {}) {
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G064', version: c.version, run_id: c.runId, operacion: c.operacion,
    ambiente: c.ensayo ? 'LOOPBACK_LOCAL' : 'TEST', casos: Object.fromEntries(CASOS.map(x => [x,
      { estado: 'NO_CONCLUYENTE', motivo: 'No ejecutado' }])), comprobaciones: [],
    datos_elegidos: {}, diagnostico_seleccion: { historiales: [], agregado: null,
      versiones_consultadas: 0, tipos_recuperados: 0, versiones_sin_resolver: 0 },
    solicitudes: [], observaciones: [], incidencias: [], herramientas: { newman: newmanVersion },
    cypress: { total_pruebas: 0 }, evidencias: ['preflight.json', 'resultado.json', INFORME(c.version)],
    cierre: { run: { cierre_http: null }, rollback: { verificado: false, motivo: 'Sin cierre' } },
    oficial: false, consume_version: false, _limite: Date.now() + 900000, _consecutivos5xx: 0 };
  fs.mkdirSync(c.directorio, { recursive: true });
  const pre = preflight(c, env, newmanVersion); guardar(path.join(c.directorio, 'preflight.json'), pre);
  let token = null, adminToken = null, iniciado = false;
  const pedirRun = async (m, p, opts = {}) => {
    const x = await pedir(r, api, m, p,
      { ...opts, token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId });
    if (x.http === 403 && !p.startsWith('/prediccion/auditoria')) throw Error('CLAVE_403');
    if (r._consecutivos5xx >= 3) throw Error('TRES_5XX_CONSECUTIVOS');
    return x;
  };
  const inicio = fecha(Date.now() - PRESUPUESTO.dias_busqueda * 86400000), fin = fecha(Date.now());
  try {
    if (!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
    const login = await pedir(r, api, 'POST', '/sesiones/', { cuerpo: {
      correo_electronico: env.QA_VETERINARIO_EMAIL, contrasena: env.QA_COMMON_PASSWORD },
      timeout: PRESUPUESTO.timeout_login_ms });
    if (login.http !== 200 || !login.cuerpo?.token) throw Error(`LOGIN_${login.http ?? 'SIN_RESPUESTA'}`);
    token = login.cuerpo.token;
    const usuarioId = usuarioDelToken(token);
    iniciado = true;
    const activos = [];
    for (let pagina = 1; pagina <= 4 && activos.length < 32; pagina++) {
      const x = await pedirRun('GET', `/activos-biologicos?tipo=INDIVIDUAL&pagina=${pagina}&page_size=8`);
      if (x.http === 403) throw Error('CLAVE_403');
      if (x.http !== 200) break;
      activos.push(...(x.cuerpo?.registros ?? []).filter(a => a.tipo === 'INDIVIDUAL'));
      if (pagina >= Number(x.cuerpo?.total_paginas ?? 1)) break;
    }
    const eventos = [];
    for (const activo of activos.slice(0, 32)) {
      let cursor = null, paginas = 0, lecturaIncompleta = false;
      const leidos = [];
      do {
        const x = await pedirRun('GET', rutaHistorial(activo.id_activo_biologico, inicio, fin, cursor));
        paginas++;
        if (x.http !== 200 || x.eco === false) { lecturaIncompleta = true; break; }
        leidos.push(...(x.cuerpo?.eventos ?? []).map(e => ({ ...e,
          id_activo_biologico: activo.id_activo_biologico, id_especie: activo.id_especie })));
        cursor = x.cuerpo?.cursor_siguiente ?? null;
      } while (cursor && paginas < PRESUPUESTO.paginas_historial_descubrimiento);
      eventos.push(...leidos);
      r.diagnostico_seleccion.historiales.push({ activo: activo.id_activo_biologico,
        paginas, cursor_pendiente: !!cursor, lectura_incompleta: lecturaIncompleta,
        resumen: null });
    }
    const versiones = {};
    const idsVersion = [...new Set(eventos.filter(e => e.tipo_evento === 'INFERENCIA'
      && e.payload?.tipo_modelo == null && e.payload?.id_version_modelo != null
      && Number.isSafeInteger(Number(e.payload.id_version_modelo)))
      .map(e => Number(e.payload.id_version_modelo)))];
    for (const id of idsVersion.slice(0, PRESUPUESTO.versiones_maximas)) {
      const x = await pedir(r, api, 'GET', `/prediccion/modelos/${id}`,
        { token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId });
      r.diagnostico_seleccion.versiones_consultadas++;
      if (x.http === 200 && x.eco === true && Number(x.cuerpo?.id_version_modelo) === id
        && typeof x.cuerpo?.tipo_modelo === 'string') {
        versiones[String(id)] = x.cuerpo.tipo_modelo;
        r.diagnostico_seleccion.tipos_recuperados++;
      }
    }
    r.diagnostico_seleccion.versiones_sin_resolver = Math.max(0,
      idsVersion.length - r.diagnostico_seleccion.tipos_recuperados);
    const catalogo = await pedirRun('GET', '/prediccion/patologias?solo_activas=true');
    const patologias = (catalogo.cuerpo?.items ?? []).filter(p => p.es_activo);
    const usados = new Set();
    for (const h of r.diagnostico_seleccion.historiales) h.resumen = diagnosticar(
      eventos.filter(e => e.id_activo_biologico === h.activo), patologias, usados,
      usuarioId, versiones, inicio, fin);
    r.diagnostico_seleccion.agregado = diagnosticar(eventos, patologias, usados,
      usuarioId, versiones, inicio, fin);
    let elegidos = seleccionar(eventos, patologias, usados, [194, 195, 196, 197],
      versiones, usuarioId, inicio, fin);
    r.diagnostico_seleccion.agregado.descarte.duplicada_otro_caso = usados.size;
    for (const n of [194, 195, 196, 197]) {
      const caso = `TC-M04-${n}`;
      let dato = elegidos[n];
      if (dato && dato.id_patologia_real != null) {
        const a = activos.find(x => x.id_activo_biologico === dato.id_activo_biologico);
        const p = patologias.find(x => x.id_patologia === dato.id_patologia_real);
        if (!p || !['TODAS', String(a?.id_especie)].includes(String(p.especie_aplicable))) dato = null;
      }
      r.datos_elegidos[caso] = dato ?? null;
      if (!dato) {
        const a = r.diagnostico_seleccion.agregado;
        const pendientes = r.diagnostico_seleccion.historiales.filter(h => h.cursor_pendiente).length;
        r.casos[caso] = { estado: 'NO_CONCLUYENTE', motivo:
          `${a.eventos} eventos: ${a.por_tipo_evento.INFERENCIA} inferencias, ${a.por_tipo_evento.ALERTA} alertas, ${a.por_tipo_evento.RETROALIMENTACION} retroalimentaciones; modelos ${JSON.stringify(a.inferencias_por_tipo_modelo)}; descartes ${JSON.stringify(a.descarte)}; ${pendientes} historial(es) con cursor pendiente` };
        continue;
      }
      let post = null;
      for (let intento = 0; intento < 2; intento++) {
        post = await pedirNewman(r, c, api, env, token, caso,
          { id_resultado_inferencia: dato.id_resultado_inferencia,
            id_activo_biologico: dato.id_activo_biologico, estado_retroalimentacion: ESTADOS[n - 194],
            diagnosticos_reales: dato.id_patologia_real == null ? null : [dato.id_patologia_real] });
        const duplicada = post.http === 409 && post.cuerpo?.error_code === 'RETROALIMENTACION_DUPLICADA';
        const fuera = post.http === 422 && post.cuerpo?.error_code === 'FUERA_DE_VENTANA_TEMPORAL';
        if (!duplicada && !fuera) break;
        if (fuera) r.observaciones.push(`${caso}: resultado ${dato.id_resultado_inferencia} fuera de ventana; ${corto(post.cuerpo?.message)}`);
        const reemplazo = seleccionar(eventos, patologias, usados, [n],
          versiones, usuarioId, inicio, fin)[n];
        if (!reemplazo) break;
        dato = reemplazo; r.datos_elegidos[caso] = dato;
        r.observaciones.push(`${caso}: se reemplazó resultado por ${duplicada ? 'retroalimentación previa (409)' : 'ventana vencida (422)'}`);
      }
      if (post.http == null) { r.casos[caso] = decidirCaso(n, dato, post); throw Error('POST_SIN_RESPUESTA'); }
      if (post.http === 403) throw Error('CLAVE_403');
      if (r._consecutivos5xx >= 3) throw Error('TRES_5XX_CONSECUTIVOS');
      let lectura = null, auditoria = null;
      if (post.http === 201) {
        lectura = await leerHistorial(p => pedirRun('GET', p, { caso }),
          dato.id_activo_biologico, inicio, fin, post.cuerpo?.id_retroalimentacion);
        auditoria = await pedirRun('GET', `/prediccion/auditoria?tipo_evento=RETROALIMENTACION_REGISTRADA&id_referencia=${post.cuerpo?.id_retroalimentacion}&por_pagina=20`, { caso });
        if (auditoria.http === 403 && env.QA_ADMIN_EMAIL && env.QA_ADMIN_PASSWORD) {
          if (!adminToken) {
            const loginAdmin = await pedir(r, api, 'POST', '/sesiones/', { cuerpo: {
              correo_electronico: env.QA_ADMIN_EMAIL, contrasena: env.QA_ADMIN_PASSWORD },
              timeout: PRESUPUESTO.timeout_login_ms });
            adminToken = loginAdmin.http === 200 ? loginAdmin.cuerpo?.token : null;
          }
          if (adminToken) auditoria = await pedir(r, api, 'GET',
            `/prediccion/auditoria?tipo_evento=RETROALIMENTACION_REGISTRADA&id_referencia=${post.cuerpo?.id_retroalimentacion}&por_pagina=20`,
            { caso, token: adminToken, secreto: env.QA_SANDBOX_SECRET, runId: c.runId });
        }
      }
      r.casos[caso] = decidirCaso(n, dato, post, lectura, auditoria);
      if ([196, 197].includes(n) && post.http === 201 && post.cuerpo
        && Object.hasOwn(post.cuerpo, 'es_fuente_desconocida'))
        r.observaciones.push(`${caso}: es_fuente_desconocida=${post.cuerpo.es_fuente_desconocida}`);
      if (r._consecutivos5xx >= 3) throw Error('TRES_5XX_CONSECUTIVOS');
      if (dato.observacion) r.observaciones.push(`${caso}: ${dato.observacion}`);
    }
  } catch (e) {
    r.observaciones.push(`Ejecución interrumpida: ${corto(e.message)}`);
    const bloqueo = /LOGIN|CLAVE_403|TRES_5XX|PREFLIGHT/.test(e.message);
    for (const caso of CASOS) if (r.casos[caso].motivo === 'No ejecutado')
      r.casos[caso] = { estado: bloqueo ? 'BLOQUEADO' : 'NO_CONCLUYENTE',
        motivo: `Interrupción técnica: ${corto(e.message)}` };
  } finally {
    if (iniciado) {
      // El cierre se intenta también cuando una petición anterior quedó sin respuesta.
      const cierre = await pedir(r, api, 'DELETE', `/test-control/runs/${encodeURIComponent(c.runId)}`,
        { secreto: env.QA_SANDBOX_SECRET });
      r.cierre.run.cierre_http = cierre.http;
      const creados = CASOS.map(caso => ({ caso, id: r.solicitudes.find(s => s.caso === caso
        && s.metodo === 'POST' && s.http === 201)?.respuesta?.id_retroalimentacion,
        activo: r.datos_elegidos[caso]?.id_activo_biologico })).filter(x => x.id && x.activo);
      let ausentes = cierre.http === 200;
      for (const x of creados.slice(0, 4)) {
        const p = await leerHistorial(ruta => pedir(r, api, 'GET', ruta, { token, caso: x.caso }),
          x.activo, inicio, fin, x.id);
        if (p.http !== 200 || p.cuerpo?.cursor_siguiente
          || p.cuerpo?.eventos?.some(e => String(e.id_evento) === String(x.id))) ausentes = false;
      }
      r.cierre.rollback = { verificado: ausentes && creados.length > 0,
        motivo: creados.length === 0 ? 'Sin registros creados; cierre HTTP observado'
          : ausentes ? 'Retroalimentaciones ausentes en lecturas públicas poscierre'
            : 'Cierre o lecturas poscierre no confirmaron ausencia' };
    }
    r.comprobaciones = CASOS.map((caso, i) => ({ caso, fuente: 'API', id: IDS[i], tipo: 'ASSERT',
      estado: r.casos[caso].estado, motivo: r.casos[caso].motivo, evidencia: 'resultado.json' }));
    const gruposIncidencia = new Map();
    for (const caso of CASOS.filter(x => r.casos[x].estado === 'RECHAZADO')) {
      const motivo = r.casos[caso].motivo;
      const clave = motivo.replace(/HTTP \d{3}/g, 'HTTP_ERROR');
      if (!gruposIncidencia.has(clave)) gruposIncidencia.set(clave, { casos: [],
        severidad: /^HTTP 200; esperado 201$/.test(motivo) ? 'MEDIA' : 'ALTA',
        certeza: 'CONFIRMADA', equipo_inicial: 'Desarrollo', fundamento: 'Primera discrepancia en API pública',
        motivo, causa_raiz: 'NO DETERMINADA' });
      gruposIncidencia.get(clave).casos.push(caso);
    }
    r.incidencias = [...gruposIncidencia.values()];
    r.oficial = CASOS.every(x => ['APROBADO', 'RECHAZADO'].includes(r.casos[x].estado))
      && r.cierre.rollback.verificado && r.solicitudes.length <= PRESUPUESTO.solicitudes_totales;
    r.consume_version = r.oficial;
    delete r._limite; delete r._consecutivos5xx;
    guardar(path.join(c.directorio, 'resultado.json'), r);
    const herramienta = r.solicitudes.some(x => x.herramienta === 'Newman')
      ? `Los POST evaluados y sus aserciones HTTP, estado y eco de RUN se ejecutaron con Newman ${newmanVersion.version}; los reportes reales saneados figuran en newman/.`
      : `No hubo POST evaluados con Newman (${newmanVersion.version ?? 'no disponible'}); no se generaron reportes Newman.`;
    const md = informe(c, r).replace('## Evidencias\n',
      `## Herramientas\n\n${herramienta} Login, descubrimiento, verificaciones y cierre usan fetch.\n\n## Evidencias\n`);
    fs.writeFileSync(path.join(c.directorio, INFORME(c.version)), md, 'utf8');
  }
  return r;
}

export async function recuperar(c, { env = leerEnv() } = {}) {
  const pre = preflight(c, env);
  if (!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
  const previo = JSON.parse(fs.readFileSync(path.join(c.directorio, 'resultado.json'), 'utf8'));
  if (previo.run_id !== c.runId || previo.version !== c.version) throw Error('RUN previo incoherente');
  const api = String(env.SIGAB_API_TEST_BASE).replace(/\/+$/, '');
  const r = { solicitudes: [], _limite: Date.now() + 900000, _consecutivos5xx: 0 };
  // El DELETE se envía primero, aunque el login necesario para la lectura falle.
  const cierre = await pedir(r, api, 'DELETE', `/test-control/runs/${encodeURIComponent(c.runId)}`,
    { secreto: env.QA_SANDBOX_SECRET });
  const login = await pedir(r, api, 'POST', '/sesiones/', { cuerpo: {
    correo_electronico: env.QA_VETERINARIO_EMAIL, contrasena: env.QA_COMMON_PASSWORD },
    timeout: PRESUPUESTO.timeout_login_ms });
  const token = login.http === 200 ? login.cuerpo?.token : null;
  const fin = fecha(Date.now());
  const creados = CASOS.map(caso => ({ caso,
    id: previo.solicitudes?.find(s => s.caso === caso && s.metodo === 'POST'
      && s.http === 201)?.respuesta?.id_retroalimentacion,
    activo: previo.datos_elegidos?.[caso]?.id_activo_biologico,
    inferencia: previo.datos_elegidos?.[caso]?.fecha_inferencia })).filter(x => x.id && x.activo && x.inferencia);
  let ausentes = !!token && (cierre.http === 200 || cierre.http === 404) && creados.length > 0;
  for (const x of creados) {
    if (!token) break;
    const inicio = fecha(Date.parse(x.inferencia) - 86400000);
    const lectura = await leerHistorial(ruta => pedir(r, api, 'GET', ruta, { token, caso: x.caso }),
      x.activo, inicio, fin, x.id);
    if (lectura.http !== 200 || lectura.cuerpo?.cursor_siguiente
      || lectura.cuerpo?.eventos?.some(e => String(e.id_evento) === String(x.id)))
      ausentes = false;
  }
  const salida = { grupo: 'G064', run_objetivo: c.runId, operacion: 'recuperar',
    cierre_http: cierre.http, rollback_verificado: ausentes,
    motivo: ausentes ? 'Registros del RUN ausentes en lectura pública poscierre'
      : 'No se pudo confirmar el cierre o la ausencia de todos los registros',
    solicitudes: r.solicitudes };
  const nombre = `recuperacion-${new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14)}.json`;
  guardar(path.join(c.directorio, nombre), salida);
  return salida;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
  else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
  else {
    try {
      const c = contexto(process.argv.slice(2));
      if (c.operacion === 'recuperar') {
        const r = await recuperar(c);
        console.log(JSON.stringify({ grupo: 'G064', run_objetivo: r.run_objetivo,
          rollback_verificado: r.rollback_verificado }));
        if (!r.rollback_verificado) process.exitCode = 2;
      } else {
        const r = await evaluar(c);
        console.log(JSON.stringify({ grupo: 'G064', run_id: r.run_id, oficial: r.oficial,
          casos: Object.fromEntries(CASOS.map(x => [x, r.casos[x].estado])) }));
        if (!r.oficial) process.exitCode = 2;
      }
    } catch (e) { console.error(corto(e.message)); process.exitCode = 2; }
  }
}
