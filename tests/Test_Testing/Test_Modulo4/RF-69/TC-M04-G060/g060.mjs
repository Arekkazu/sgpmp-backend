#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';
import { sanearArtefacto, contieneMojibake } from './lib/seguridad.mjs';
import { onnxMinimo, sha256 } from './lib/artefactos.mjs';
import { CASOS, IDS, LLAVES, LINEA_BASE_RECUPERACION, PRESUPUESTO, CAPACIDADES, idVersion, llaveId, version,
  eventosVersion, decidirDisparo, solapadas } from './lib/g060_escenario.mjs';

const require = createRequire(import.meta.url);
const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION = path.join(DIR, 'G060.postman_collection.json');
const ARCHIVOS = ['.gitkeep', 'g060.mjs', 'G060.postman_collection.json', 'README.md',
  'lib/contrato_ejecutor.mjs', 'lib/seguridad.mjs', 'lib/artefactos.mjs',
  'lib/g060_escenario.mjs', 'pruebas/registro_qa.mjs', 'pruebas/g060_env.test.mjs',
  'pruebas/g060_ensayo.mjs'];
const limpio = x => String(x ?? '').replaceAll('|', '/').replace(/[\r\n]+/g, ' ').slice(0, 400);
const archivoInforme = v => v === 1 ? 'TC-M04-G060_resultado.md' : `TC-M04-G060_reevaluacion_V${v}.md`;
const guardar = (p, x, secretos = []) => fs.writeFileSync(p,
  sanearArtefacto(JSON.stringify(x, null, 2), secretos), 'utf8');
const ruta = id => `/prediccion/modelos/${id}`;
const listaRuta = k => `/prediccion/modelos?tipo_modelo=${encodeURIComponent(k.tipo)}&estado=ACTIVO&limit=100&offset=0`;
const auditoriaRuta = id => `/prediccion/auditoria?id_referencia=${encodeURIComponent(id)}&por_pagina=200`;

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
    return p ? path.dirname(p) : null;
  }
}
const versionNewman = () => {
  try { return { ok: true, version: require(path.join(paqueteNewman(), 'package.json')).version }; }
  catch { return { ok: false, error: 'NEWMAN_NO_RESUELTO' }; }
};
export function comprobar() {
  let coleccion = false;
  try {
    const c = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const item of c.item) for (const ev of item.event ?? [])
      new vm.Script((ev.script?.exec ?? []).join('\n'));
    coleccion = c.item.length === 1 && c.item[0].request.method === 'POST'
      && c.item[0].name === 'API-G060-POST' && !contieneMojibake(JSON.stringify(c));
  } catch { /* estructura inválida */ }
  const faltantes = ARCHIVOS.filter(x => !fs.existsSync(path.join(DIR, x)));
  const presentes = fs.readdirSync(DIR).filter(x => !['lib', 'pruebas', 'Resultados', 'EvaluacionV2'].includes(x))
    .concat(...['lib', 'pruebas'].map(d => fs.existsSync(path.join(DIR, d))
      ? fs.readdirSync(path.join(DIR, d)).map(x => `${d}/${x}`) : []));
  const inesperados = presentes.filter(x => !ARCHIVOS.includes(x));
  const markdownSuperior = fs.existsSync(path.join(DIR, 'Resultados'))
    && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const ok = coleccion && !faltantes.length && !inesperados.length && !markdownSuperior && versionNewman().ok;
  console.log(JSON.stringify({ grupo: 'G060', ok, coleccion, faltantes, inesperados,
    markdownSuperior, newman: versionNewman(), presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}
export function preflight(c, env, ensayo = false) {
  const base = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const barreras = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_ADMIN_EMAIL',
    'QA_ADMIN_PASSWORD', 'QA_VETERINARIO_EMAIL', 'QA_COMMON_PASSWORD', 'RF71_INTERNAL_KEY']
    .filter(k => !String(env[k] ?? '').trim());
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base) : base !== API)
    barreras.push('API_NO_CANONICA');
  if (c.version > 1 && c.operacion !== 'reevaluar') barreras.push('REEVALUACION_SIN_DECISION');
  if (!versionNewman().ok) barreras.push('NEWMAN_NO_RESUELTO');
  return { grupo: 'G060', run_id: c.runId, ok: !barreras.length, barreras,
    presupuesto: PRESUPUESTO, herramientas: { newman: versionNewman() },
    efectos_declarados: ['22_versiones_ONNX_camino_normal', 'hasta_58_versiones_ONNX_contingencia',
      'notas_activaciones_deprecaciones_historial_auditoria_BD_sandbox',
      'archivos_MODELOS_STORAGE_PATH_fuera_rollback', 'respaldo_RF73_posible',
      'sin_correo_por_APROBADO', 'sin_OTA', 'ACTIVO_heredadas_deprecadas_temporalmente'] };
}
async function pedir(r, api, metodo, endpoint, { token, secreto, runId, cuerpo, rol = 'Sistema',
  caso = null, timeout = PRESUPUESTO.timeout_ms, cierre = false } = {}) {
  if (!cierre) {
    if (Date.now() >= r._limite) throw Error('LIMITE_900_SEGUNDOS');
    if (r._clave403) throw Error('CLAVE_403');
    if (r._consecutivos5xx >= 3) throw Error('TRES_5XX_CONSECUTIVOS');
  }
  const fila = { caso, rol, metodo, ruta: endpoint.replace(/\?.*/, '?[filtro]'), http: null };
  r.solicitudes.push(fila);
  const envio = Date.now(); fila.envio_ms = envio;
  try {
    const x = await fetch(api + endpoint, { method: metodo, redirect: 'manual',
      headers: { ...(cuerpo ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(secreto ? { 'X-Sandbox-Secret': secreto } : {}),
        ...(runId ? { 'X-Test-Run-Id': runId, 'X-Zona-Horaria': 'UTC' } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      signal: AbortSignal.timeout(cierre ? (r._ensayo ? 2500 : timeout)
        : Math.max(1, Math.min(r._ensayo ? 2500 : timeout, r._limite - Date.now()))) });
    const respuesta = Date.now();
    const body = await x.json().catch(() => null);
    Object.assign(fila, { http: x.status, respuesta_ms: respuesta, duracion_ms: respuesta - envio,
      codigo: body?.error_code ?? body?.code ?? body?.codigo ?? null,
      eco: runId ? x.headers.get('x-test-run-id') === runId : null,
      sin_cabecera_run: runId ? null : x.headers.get('x-test-run-id') === null,
      estado: body?.estado_version ?? null });
    if (x.status === 403) r._clave403 = true;
    if (metodo !== 'POST' || !endpoint.endsWith('/activar'))
      r._consecutivos5xx = x.status >= 500 ? r._consecutivos5xx + 1 : 0;
    return { ...fila, cuerpo: body };
  } catch (e) {
    Object.assign(fila, { respuesta_ms: Date.now(), duracion_ms: Date.now() - envio,
      tipo_fallo: ['AbortError', 'TimeoutError'].includes(e?.name) ? 'TIMEOUT'
        : /^[A-Z][A-Z0-9_]{1,63}$/.test(e?.cause?.code ?? '') ? e.cause.code : 'SIN_RED' });
    return { ...fila, cuerpo: null };
  }
}
async function registrarNewman(r, c, api, env, dato, n, secretos, temporal) {
  const raw = path.join(temporal, `g060-${n}.json`);
  const html = path.join(temporal, `g060-${n}.html`);
  const sub = path.join(c.directorio, 'newman'); fs.mkdirSync(sub, { recursive: true });
  const variables = { autorizado_run: 'SI', ensayo_loopback: c.ensayo ? 'SI' : 'NO',
    base_url: api, run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET,
    rf71_internal_key: env.RF71_INTERNAL_KEY, componente: dato.componente ?? '' };
  const input = { ...dato, metricas_validacion: JSON.stringify(dato.metricas_validacion),
    compatibilidad_variables: JSON.stringify(dato.compatibilidad_variables),
    omitir: dato.componente ? [] : ['componente'] };
  const ini = Date.now();
  await new Promise(resolve => require(paqueteNewman()).run({
    collection: JSON.parse(fs.readFileSync(COLECCION, 'utf8')),
    environment: { values: Object.entries(variables).map(([key, value]) => ({ key, value, enabled: true })) },
    iterationData: [input], reporters: ['json', 'htmlextra'],
    reporter: { json: { export: raw }, htmlextra: { export: html } },
    timeoutRequest: c.ensayo ? 2500 : PRESUPUESTO.timeout_login_registro_ms,
    timeout: Math.min(PRESUPUESTO.timeout_login_registro_ms + 5000, r._limite - Date.now()),
    color: 'off' }, () => resolve()));
  let original = {}; try { original = JSON.parse(fs.readFileSync(raw, 'utf8')); } catch { /* sin reporte */ }
  const ex = original.run?.executions?.[0];
  let body = null; try { body = JSON.parse(Buffer.from(ex?.response?.stream?.data ?? []).toString('utf8')); }
  catch { /* cuerpo no JSON */ }
  const http = ex?.response?.code ?? null;
  const eco = ex?.response?.header?.find(h => String(h.key).toLowerCase() === 'x-test-run-id')?.value === c.runId;
  const x = { http, eco, cuerpo: body, envio_ms: ini, respuesta_ms: Date.now(),
    duracion_ms: Date.now() - ini, codigo: body?.code ?? null };
  r.solicitudes.push({ caso: null, rol: 'RF-71 interno', metodo: 'POST', ruta: '/prediccion/modelos',
    http, eco, estado: body?.estado_version ?? null, duracion_ms: x.duracion_ms,
    envio_ms: ini, respuesta_ms: x.respuesta_ms });
  r._consecutivos5xx = http >= 500 ? r._consecutivos5xx + 1 : 0;
  if (http === 403) r._clave403 = true;
  const nombre = `newman-G060-${String(n).padStart(2, '0')}`;
  guardar(path.join(sub, nombre + '.json'), { info: { nombre, saneado: true, generado: !!ex },
    run: { stats: original.run?.stats ?? null, executions: [{ http, eco,
      id: idVersion(body), estado: body?.estado_version ?? null }],
      failures: (original.run?.failures ?? []).map(f => ({ message: limpio(f.error?.message) })) } }, secretos);
  r.evidencias.push(`newman/${nombre}.json`);
  if (fs.existsSync(html)) {
    fs.writeFileSync(path.join(sub, nombre + '.html'),
      sanearArtefacto(fs.readFileSync(html, 'utf8'), secretos), 'utf8');
    r.evidencias.push(`newman/${nombre}.html`);
  }
  return x;
}
const activas = (x, k, exigirEco = true) => x?.http === 200 && (!exigirEco || x.eco === true)
  && Array.isArray(x.cuerpo?.items)
  && x.cuerpo.total === x.cuerpo.items.length ? x.cuerpo.items.filter(y =>
    y.tipo_modelo === k.tipo && (y.componente ?? null) === k.componente)
    .map(y => ({ id: idVersion(y), estado: y.estado_version, tipo: y.tipo_modelo,
      componente: y.componente ?? null })) : null;
const evento = x => x?.http === 200 && x.eco === true && Array.isArray(x.cuerpo?.items)
  && x.cuerpo.total === x.cuerpo.items.length ? eventosVersion(x.cuerpo) : null;

function informe(c, r) {
  const estados = CASOS.map(x => r.casos[x].estado);
  const decision = estados.includes('RECHAZADO') ? 'RECHAZADO' : estados.every(x => x === 'APROBADO')
    ? 'APROBADO' : estados.includes('BLOQUEADO') ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
  const tabla = CASOS.map((x, i) => `| ${x} | ${IDS[i]} | ${r.casos[x].estado} | ${limpio(r.casos[x].motivo)} |`).join('\n');
  const lineas = CASOS.map((x, i) => {
    const d = r.detalle[x] ?? {};
    const esperado = [
      'Una sola activación exitosa, otra cancelada y revertida; una ACTIVO por llave (Restricción 12, Fase 5, CA-7; RF-69 v2.1, líneas 1908-1909, 2078-2087, 2307-2311).',
      'X ACTIVO una vez, P DEPRECADO una vez, sin eventos duplicados ni estados parciales (E5, CA-7; líneas 2183-2192, 2307-2311).',
      'En diez repeticiones, una ACTIVO y ningún estado intermedio inconsistente (RNF-02; líneas 2354-2356).',
      'Las cuatro llaves se activan y cada una conserva una ACTIVO (RFC-009, CA-7; líneas 1784, 2307-2311).'
    ][i];
    return `### ${x}\n\n- Qué se hizo: ${limpio(d.hizo ?? 'Preparación o disparo no completado')}.\n- Qué se esperaba: ${esperado}\n- Qué se observó: ${limpio(d.observo ?? 'Sin lectura concluyente')}.\n- Por qué ${r.casos[x].estado}: ${limpio(r.casos[x].motivo)}.\n`;
  }).join('\n');
  const rep = r.repeticiones.map(x => `| ${x.numero} | ${x.ids.join(', ')} | ${x.http.join('/')} | ${x.activo ?? 'sin lectura'} | ${x.estado} |`).join('\n');
  const solicitudes = r.solicitudes.map(x => `| ${x.caso ?? 'preparación/cierre'} | ${x.rol} | ${x.metodo} ${x.ruta} | ${x.http ?? 'sin respuesta'} | ${x.duracion_ms ?? '—'} |`).join('\n');
  return `# TC-M04-G060 — ${decision}\n\n## Decisión del caso\n\nAgrupado TC-M04-G060; originales ${CASOS.join(', ')}. Decisión ${decision}: ${CASOS.map(x => `${x}: ${limpio(r.casos[x].motivo)}`).join('; ')}.\n\n| Caso | Comprobación | Decisión | Motivo |\n|---|---|---|---|\n${tabla}\n\nRUN oficial: ${r.oficial ? 'sí' : 'no'}${r.ambiente !== 'TEST' ? ' (ensayo local)' : ''}. Qué falta: ${r.oficial ? 'ninguna comprobación de este ensayo' : 'resolver el impedimento o revisar cierre y rollback antes de registrar'}.\n\n## Detalle por caso\n\n${lineas}\n## Diez repeticiones de TC-M04-168\n\n| Repetición | IDs | HTTP concurrentes | ACTIVO final | Decisión |\n|---:|---|---|---|---|\n${rep}\n\n## Identificación\n\nGrupo G060; RF-69 v2.1; V${c.version}; RUN ${c.runId}; ambiente ${r.ambiente}; autorización ${limpio(c.referencia)}; origin/test daefc3a5 consultado, despliegue no verificado; Newman ${r.herramientas.newman.version ?? 'no disponible'}; Cypress 0 (solo API).\n\n## Observaciones\n\n${r.observaciones.map(x => `- ${limpio(x)}`).join('\n') || 'Ninguna.'}\n\n## Incidencias de producto\n\n${r.incidencias.map(x => `- ${x.id}: ${x.casos.join(', ')}; ${limpio(x.titulo)}; severidad ${x.severidad}, impacto ${limpio(x.impacto)}, certeza ${x.certeza}; equipo inicial ${x.equipo_inicial} por primera discrepancia en API; causa raíz NO DETERMINADA.`).join('\n') || 'Ninguna confirmada.'}\n\n## Problemas técnicos y análisis\n\n${r.problemas_tecnicos.map(x => `- ${limpio(x)}`).join('\n') || 'Ninguno.'} El código local solo orienta hipótesis; no demuestra causa raíz en TEST.\n\n## Historial de solicitudes\n\n| Caso | Rol | Solicitud | HTTP | Duración ms |\n|---|---|---|---:|---:|\n${solicitudes}\n\n## Cierre y rollback\n\nDELETE HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. Rollback ${r.cierre.rollback.verificado ? 'verificado por GET y listados' : 'NO_VERIFICADO'}: ${limpio(r.cierre.rollback.motivo)}. Los artefactos ONNX en MODELOS_STORAGE_PATH y posible respaldo RF-73 no están cubiertos por el DELETE.\n\n## Evidencias\n\n${r.evidencias.map(x => `- ${x}`).join('\n')}\n\n## Conclusión y acción\n\n${r.oficial ? 'Entregar al registro QA y atender incidencias observadas.' : 'Resolver la evidencia pendiente y solicitar un reintento si corresponde.'}\n`;
}

export async function evaluar(c, { env, ensayo = false } = {}) {
  if (!fs.existsSync(c.directorio)) throw Error('RUN_NO_CREADO_POR_LANZADOR');
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G060', run_id: c.runId, version: c.version, intento: c.intento,
    operacion: c.operacion, autorizacion: c.referencia, ambiente: ensayo ? 'LOOPBACK_LOCAL' : 'TEST',
    oficial: false, consume_version: false, casos: Object.fromEntries(CASOS.map(x =>
      [x, { estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación' }])),
    comprobaciones: CASOS.map((caso, i) => ({ caso, fuente: 'API', id: IDS[i], tipo: 'ASSERT',
      estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación', evidencia: 'resultado.json' })),
    presupuesto: PRESUPUESTO, herramientas: { newman: versionNewman() }, solicitudes: [],
    repeticiones: [], detalle: {}, cypress: { total_pruebas: 0 }, evidencias: [],
    incidencias: [], problemas_tecnicos: [], observaciones: [],
    estado_inicial_activo: {}, cierre: { run: { cierre_http: null }, rollback: { verificado: false,
      motivo: 'Sin cierre ni comprobación posterior' } }, _limite: Date.now() + 900000,
    _ensayo: ensayo, _consecutivos5xx: 0, _clave403: false };
  const secretos = [env.QA_SANDBOX_SECRET, env.RF71_INTERNAL_KEY, env.QA_ADMIN_EMAIL,
    env.QA_ADMIN_PASSWORD, env.QA_VETERINARIO_EMAIL, env.QA_COMMON_PASSWORD].filter(Boolean);
  const poner = (n, x) => { const i = n - 166; r.casos[CASOS[i]] = { estado: x.estado, motivo: x.motivo };
    Object.assign(r.comprobaciones[i], { estado: x.estado, motivo: x.motivo });
    r.observaciones.push(...(x.observaciones ?? []).map(v => `${n}: ${v}`)); };
  let temporal = null, tocado = false, registroN = 0;
  const idsRun = [], inicial = new Map(), tokens = {};
  try {
    const pre = preflight(c, env, ensayo);
    guardar(path.join(c.directorio, 'preflight.json'), pre, secretos); r.evidencias.push('preflight.json');
    if (!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
    tocado = true;
    for (const [rol, email, pass] of [['admin', env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD],
      ['vet', env.QA_VETERINARIO_EMAIL, env.QA_COMMON_PASSWORD]]) {
      const x = await pedir(r, api, 'POST', '/sesiones/', { rol, cuerpo: {
        correo_electronico: email, contrasena: pass }, timeout: 120000 });
      if (x.http !== 200 || !x.cuerpo?.token) throw Error(`LOGIN_${rol.toUpperCase()}_${x.http ?? x.tipo_fallo}`);
      tokens[rol] = x.cuerpo.token; secretos.push(tokens[rol]);
    }
    const acceso = (rol = 'admin', conRun = true) => ({ token: tokens[rol],
      secreto: conRun ? env.QA_SANDBOX_SECRET : undefined, runId: conRun ? c.runId : undefined,
      rol: rol === 'vet' ? 'Veterinario' : 'Administrador' });
    const pet = (metodo, endpoint, caso = null, rol = 'admin', cuerpo = null, conRun = true) =>
      pedir(r, api, metodo, endpoint, { ...acceso(rol, conRun), caso, cuerpo });
    const get = (id, caso = null, conRun = true) => pet('GET', ruta(id), caso, 'admin', null, conRun);
    const listar = (k, caso = null, conRun = true) => pet('GET', listaRuta(k), caso, 'admin', null, conRun);
    const auditar = (id, caso = null) => pet('GET', auditoriaRuta(id), caso);
    const nota = (id) => pet('PATCH', `${ruta(id)}/notas`, null, 'admin',
      { notas_validacion: `G060 ${c.runId} validación clínica` });
    const catalogo = await pet('GET', '/configuracion/variables-ambientales');
    const variable = catalogo.cuerpo?.items?.find(x => Number.isSafeInteger(x.id_variable_ambiental));
    if (catalogo.http !== 200 || !catalogo.eco || !variable) throw Error(`CATALOGO_I3P1_${catalogo.http}`);
    const llaves = [LLAVES[166], LLAVES[167], LLAVES[168], ...LLAVES[169]];
    for (const k of llaves) {
      const x = await listar(k);
      if (r._clave403 || r._consecutivos5xx >= 3)
        throw Error(r._clave403 ? 'CLAVE_403' : 'TRES_5XX_CONSECUTIVOS');
      const a = activas(x, k);
      if (!a || a.length > 1) throw Error(`ESTADO_INICIAL_NO_AISLABLE_${llaveId(k)}`);
      inicial.set(llaveId(k), a.map(y => y.id).sort());
      r.estado_inicial_activo[llaveId(k)] = a.map(y => y.id).sort();
    }
    temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g060-newman-'));
    const artefacto = path.join(temporal, 'g060.onnx');
    const bytes = onnxMinimo(); fs.writeFileSync(artefacto, bytes);
    const hash = sha256(bytes);
    const preparar = async (k, n) => {
      if (Date.now() >= r._limite) throw Error('LIMITE_900_SEGUNDOS');
      if (r._clave403 || r._consecutivos5xx >= 3) throw Error(r._clave403 ? 'CLAVE_403' : 'TRES_5XX_CONSECUTIVOS');
      const d = version(k, variable.id_variable_ambiental, hash, artefacto);
      const p = await registrarNewman(r, c, api, env, d, ++registroN, secretos, temporal);
      const id = idVersion(p.cuerpo);
      if (id != null) idsRun.push(id);
      if (p.http !== 201 || !p.eco || p.cuerpo?.estado_version !== 'APROBADO' || id == null)
        return { id, ok: false, http: p.http };
      const z = await nota(id);
      if (r._clave403 || r._consecutivos5xx >= 3) throw Error(r._clave403 ? 'CLAVE_403' : 'TRES_5XX_CONSECUTIVOS');
      return { id, ok: z.http === 200 && z.eco && z.cuerpo?.estado_version === 'APROBADO',
        http: z.http };
    };
    const activar = (id, caso, rol = 'admin') => pet('POST', `${ruta(id)}/activar`, caso, rol);
    const disparar = async (ids, caso, roles = []) => {
      // Promise.all libera todas las solicitudes en la misma vuelta del event loop.
      const tareas = ids.map((id, i) => () => activar(id, caso, roles[i] ?? 'admin'));
      return Promise.all(tareas.map(t => t()));
    };
    const observar = async (k, ids, previo, caso) => {
      const afectados = [...new Set([...ids, ...(previo == null ? [] : [previo])])];
      const posteriores = [];
      for (const id of afectados) posteriores.push(await get(id, caso));
      const listado = await listar(k, caso);
      const auditorias = [];
      for (const id of afectados) auditorias.push(await auditar(id, caso));
      const ev = auditorias.map(evento);
      return { posteriores, activos: activas(listado, k),
        eventos: ev.every(Array.isArray) ? ev.flat() : null,
        eventoConflicto: auditorias.some(x => x.cuerpo?.items?.some(e =>
          /CONFLICTO|CANCELAD|INTENTO_ACTIVACION/.test(String(e.tipo_evento ?? '')))),
        http: { gets: posteriores.map(x => x.http), lista: listado.http,
          auditorias: auditorias.map(x => x.http) } };
    };
    const antesEventos = async (ids, caso) => {
      const xs = [];
      for (const id of ids) xs.push(await auditar(id, caso));
      const es = xs.map(evento); return es.every(Array.isArray) ? es.flat() : null;
    };
    const previoActivo = async (k, caso) => {
      const x = await listar(k, caso), a = activas(x, k);
      return a?.length === 1 ? a[0].id : a?.length === 0 ? null : undefined;
    };
    const evaluarUno = async (n, k, ids, roles, previo, extras = {}) => {
      const caso = `TC-M04-${n}`;
      const refs = [...new Set([...ids, ...(previo == null ? [] : [previo])])];
      const evAntes = await antesEventos(refs, caso);
      const respuestas = await disparar(ids, caso, roles);
      if (r._clave403) throw Error('CLAVE_403');
      const obs = await observar(k, ids, previo, caso);
      if (r._clave403 || r._consecutivos5xx >= 3)
        throw Error(r._clave403 ? 'CLAVE_403' : 'TRES_5XX_CONSECUTIVOS');
      const x = decidirDisparo({ caso, claveCaso: k, previos: previo == null ? [] : [previo],
        candidatos: ids, respuestas, posteriores: obs.posteriores, activos: obs.activos,
        eventosAntes: evAntes ?? [], eventosDespues: obs.eventos,
        eventoConflicto: obs.eventoConflicto, ...extras });
      if (evAntes == null) { x.estado = 'NO_CONCLUYENTE'; x.motivo = 'Auditoría previa no verificable'; }
      return { ...x, respuestas, obs };
    };
    // 169: cada llave es independiente; se liberan las cuatro activaciones juntas.
    const p169 = [];
    for (const k of LLAVES[169]) p169.push(await preparar(k, 169));
    if (r._clave403 || r._consecutivos5xx >= 3)
      throw Error(r._clave403 ? 'CLAVE_403' : 'TRES_5XX_CONSECUTIVOS');
    if (p169.every(x => x.ok)) {
      const prev = [];
      for (const k of LLAVES[169]) prev.push(await previoActivo(k, 'TC-M04-169'));
      const refs = p169.map((x, i) => [x.id, ...(prev[i] == null ? [] : [prev[i]])]);
      const antes = [];
      for (const x of refs) antes.push(await antesEventos(x, 'TC-M04-169'));
      const respuestas = await disparar(p169.map(x => x.id), 'TC-M04-169');
      if (r._clave403) throw Error('CLAVE_403');
      const despues = [];
      for (let i = 0; i < LLAVES[169].length; i++)
        despues.push(await observar(LLAVES[169][i], [p169[i].id], prev[i], 'TC-M04-169'));
      if (r._clave403 || r._consecutivos5xx >= 3)
        throw Error(r._clave403 ? 'CLAVE_403' : 'TRES_5XX_CONSECUTIVOS');
      const xs = LLAVES[169].map((k, i) => decidirDisparo({ caso: 'TC-M04-169', claveCaso: k,
        previos: prev[i] == null ? [] : [prev[i]], candidatos: [p169[i].id],
        respuestas: [respuestas[i]], posteriores: despues[i].posteriores,
        activos: despues[i].activos, eventosAntes: antes[i] ?? [], eventosDespues: despues[i].eventos }));
      const malo = xs.find(x => x.estado !== 'APROBADO');
      poner(169, malo ?? { estado: 'APROBADO', motivo: `Cuatro HTTP ${respuestas.map(x => x.http).join('/')}; una ACTIVO por cada llave`,
        observaciones: xs.flatMap(x => x.observaciones) });
      r.detalle['TC-M04-169'] = { hizo: `Se registraron ${p169.length} versiones con notas y se activaron juntas en cuatro llaves`,
        observo: `HTTP ${respuestas.map(x => x.http).join('/')}; ACTIVO por llave ${despues.map(x => x.activos?.length ?? 'sin dato').join('/')}` };
    } else poner(169, { estado: 'NO_CONCLUYENTE', motivo: `Preparación 169: ${p169.map(x => x.http).join('/')}` });
    // 166: dos sesiones y una llave exclusiva.
    const p166 = [await preparar(LLAVES[166], 166), await preparar(LLAVES[166], 166)];
    if (p166.every(x => x.ok)) {
      const prev = await previoActivo(LLAVES[166], 'TC-M04-166');
      const x = await evaluarUno(166, LLAVES[166], p166.map(y => y.id), ['vet', 'admin'], prev);
      poner(166, x);
      r.detalle['TC-M04-166'] = { hizo: 'Dos versiones APROBADAS con notas, Veterinario y Administrador, disparadas juntas',
        observo: `HTTP ${x.respuestas.map(y => y.http).join('/')}; intervalos ${x.respuestas.map(y => `${y.envio_ms}-${y.respuesta_ms}`).join(' / ')}; solape ${solapadas(x.respuestas)}; ACTIVO ${x.obs.activos?.map(y => y.id).join(',') ?? 'sin lectura'}` };
    } else poner(166, { estado: 'NO_CONCLUYENTE', motivo: `Preparación 166: ${p166.map(x => x.http).join('/')}` });
    // 167: P se activa antes de disparar dos solicitudes idénticas de X.
    const p167 = await preparar(LLAVES[167], 167);
    if (p167.ok) {
      const a = await activar(p167.id, null);
      if (r._clave403 || r._consecutivos5xx >= 3)
        throw Error(r._clave403 ? 'CLAVE_403' : 'TRES_5XX_CONSECUTIVOS');
      const x167 = await preparar(LLAVES[167], 167);
      const pLeida = await get(p167.id, 'TC-M04-167');
      const pLista = await listar(LLAVES[167], 'TC-M04-167');
      const pActiva = pLeida.http === 200 && pLeida.eco && pLeida.cuerpo?.estado_version === 'ACTIVO'
        && pLeida.cuerpo?.esta_produccion === true
        && activas(pLista, LLAVES[167])?.length === 1
        && String(activas(pLista, LLAVES[167])[0].id) === String(p167.id);
      if (a.http >= 200 && a.http < 300 && x167.ok && pActiva) {
        const x = await evaluarUno(167, LLAVES[167], [x167.id, x167.id],
          ['admin', 'admin'], p167.id);
        poner(167, x);
        r.detalle['TC-M04-167'] = { hizo: `P=${p167.id} activada; X=${x167.id} solicitada dos veces a la vez`,
          observo: `HTTP ${x.respuestas.map(y => y.http).join('/')}; estados ${x.obs.posteriores.map(y => y.cuerpo?.estado_version ?? '?').join('/')}; ACTIVO ${x.obs.activos?.map(y => y.id).join(',') ?? 'sin lectura'}` };
      } else poner(167, { estado: 'NO_CONCLUYENTE',
        motivo: `Preparación 167: P HTTP ${a.http}, GET ${pLeida.http}, ACTIVO ${pLista.http}; X HTTP ${x167.http}` });
    } else poner(167, { estado: 'NO_CONCLUYENTE', motivo: `Preparación P de 167 HTTP ${p167.http}` });
    // 168: cinco candidatas por repetición; conservar perdedoras APROBADAS.
    let bolsa = [], agotado = false;
    for (let rep = 1; rep <= 10; rep++) {
      while (bolsa.length < 5 && registroN < PRESUPUESTO.versiones_maximas) {
        const p = await preparar(LLAVES[168], 168);
        if (!p.ok) { agotado = true; break; }
        bolsa.push(p.id);
      }
      if (agotado || bolsa.length < 5) {
        poner(168, { estado: 'NO_CONCLUYENTE', motivo: `Repetición ${rep}: faltan cinco APROBADAS; registros agotados o fallidos` }); break;
      }
      const prev = await previoActivo(LLAVES[168], 'TC-M04-168');
      const ids = bolsa.slice(0, 5);
      const x = await evaluarUno(168, LLAVES[168], ids, Array(5).fill('admin'), prev, { repeticion: rep });
      r.repeticiones.push({ numero: rep, ids, http: x.respuestas.map(y => y.http),
        activo: x.obs.activos?.[0]?.id ?? null, estado: x.estado });
      bolsa = x.obs.posteriores.filter(y => y.cuerpo?.estado_version === 'APROBADO')
        .map(y => idVersion(y.cuerpo)).filter(y => ids.map(String).includes(String(y)));
      if (x.estado !== 'APROBADO') { poner(168, x); break; }
      if (rep === 10) poner(168, { estado: 'APROBADO',
        motivo: 'Diez repeticiones completas; una ACTIVO por llave, sin estados parciales ni eventos duplicados' });
    }
    r.detalle['TC-M04-168'] = { hizo: `${r.repeticiones.length} repeticiones de cinco solicitudes simultáneas; perdedoras APROBADAS reutilizadas`,
      observo: r.repeticiones.map(x => `R${x.numero} HTTP ${x.http.join('/')}, ACTIVO ${x.activo ?? '?'}`).join('; ') };
  } catch (e) {
    const motivo = limpio(e.message); r.problemas_tecnicos.push(motivo);
    const estado = /403|5XX|LOGIN|CATALOGO|PREFLIGHT/.test(motivo) ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
    CASOS.forEach((caso, i) => { if (r.casos[caso].motivo === 'Sin comprobación'
      || /CLAVE_403|TRES_5XX_CONSECUTIVOS/.test(motivo) && r.casos[caso].estado === 'NO_CONCLUYENTE') poner(166 + i,
      { estado, motivo: `Impedimento técnico: ${motivo}` }); });
  } finally {
    if (tocado) {
      const x = await pedir(r, api, 'DELETE', `/test-control/runs/${encodeURIComponent(c.runId)}`,
        { secreto: env.QA_SANDBOX_SECRET, cierre: true });
      r.cierre.run.cierre_http = x.http;
      {
        const ids = [];
        for (const id of idsRun) ids.push(await pedir(r, api, 'GET', ruta(id),
          { token: tokens.admin, rol: 'Administrador poscierre', cierre: true }));
        const keys = [LLAVES[166], LLAVES[167], LLAVES[168], ...LLAVES[169]];
        const listados = [];
        for (const k of keys) listados.push(await pedir(r, api, 'GET', listaRuta(k),
          { token: tokens.admin, rol: 'Administrador poscierre', cierre: true }));
        r.cierre.rollback.verificado = x.http === 200 && inicial.size === keys.length
          && ids.length === idsRun.length
          && ids.every(y => y.http === 404)
          && listados.every((y, i) => Array.isArray(activas(y, keys[i], false))
            && JSON.stringify(activas(y, keys[i], false).map(z => z.id).sort())
            === JSON.stringify(inicial.get(llaveId(keys[i])) ?? []));
        r.cierre.rollback.motivo = r.cierre.rollback.verificado
          ? `${ids.length} versiones GET 404; siete listados ACTIVO restaurados`
          : `GET ${ids.map(y => y.http).join('/')}; listados ${listados.map(y => y.http).join('/')}; rollback no acreditado`;
      }
    }
    if (temporal) {
      if (!path.resolve(temporal).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
      fs.rmSync(temporal, { recursive: true, force: true });
    }
    for (const caso of CASOS) if (r.casos[caso].estado === 'RECHAZADO') {
      const motivo = r.casos[caso].motivo;
      const causa = /\d+ ACTIVO|dos ACTIVO|0 ACTIVO/.test(motivo) ? 'UNICIDAD'
        : /duplicad|correlacion_id|VERSION_/.test(motivo) ? 'AUDITORIA' : caso;
      let incidencia = r.incidencias.find(x => x.causa_grupo === causa);
      if (incidencia) { incidencia.casos.push(caso); incidencia.titulo += `; ${motivo}`; }
      else r.incidencias.push({ id: `INC-M04-G060-${caso.slice(-3)}`, causa_grupo: causa,
        casos: [caso], titulo: motivo, severidad: causa === 'UNICIDAD'
          || ['TC-M04-166', 'TC-M04-168', 'TC-M04-169'].includes(caso) ? 'ALTA' : 'MEDIA',
        impacto: 'Concurrencia de activación o auditoría afectada', certeza: 'CONFIRMADA',
        equipo_inicial: 'Desarrollo' });
    }
    const nombre = archivoInforme(c.version);
    r.evidencias = [...new Set([...r.evidencias, 'preflight.json', nombre, 'resultado.json'])];
    r.oficial = CASOS.every(x => ['APROBADO', 'RECHAZADO'].includes(r.casos[x].estado))
      && r.cierre.run.cierre_http === 200 && r.cierre.rollback.verificado
      && !r.problemas_tecnicos.length && r.solicitudes.length <= CAPACIDADES.limite.solicitudes_totales
      && r.evidencias.some(x => x.endsWith('.html'))
      && r.evidencias.filter(x => !['resultado.json', nombre].includes(x))
        .every(x => fs.existsSync(path.join(c.directorio, x)));
    r.consume_version = r.oficial;
    fs.writeFileSync(path.join(c.directorio, nombre), sanearArtefacto(informe(c, r), secretos), 'utf8');
    const publico = { ...r }; Object.keys(publico).filter(k => k.startsWith('_')).forEach(k => delete publico[k]);
    guardar(path.join(c.directorio, 'resultado.json'), publico, secretos);
  }
  return r;
}

export async function recuperar(c, { env, ensayo = false } = {}) {
  if (c.operacion !== 'recuperar' || c.objetivo !== c.runId || !fs.existsSync(c.directorio))
    throw Error('RECUPERACION_CONTEXTO_INVALIDO');
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  if (env.QA_AUTORIZADO !== 'SI' || (ensayo
    ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(api) : api !== API)
    || !env.QA_SANDBOX_SECRET || !env.QA_ADMIN_EMAIL || !env.QA_ADMIN_PASSWORD)
    throw Error('RECUPERACION_PREFLIGHT');
  const original = JSON.parse(fs.readFileSync(path.join(c.directorio, 'resultado.json'), 'utf8'));
  if (original.grupo !== 'G060' || original.run_id !== c.runId || original.version !== c.version)
    throw Error('RECUPERACION_RESULTADO_INCOHERENTE');
  const keys = LLAVES[169];
  const baseRun = original.estado_inicial_activo;
  const historica = c.runId === LINEA_BASE_RECUPERACION.run
    ? LINEA_BASE_RECUPERACION.por_llave : {};
  const lineasBase = Object.fromEntries(keys.map(k => {
    const llave = llaveId(k);
    const guardada = baseRun?.[llave];
    if (Array.isArray(guardada) && guardada.every(Number.isSafeInteger))
      return [llave, { ids: guardada, fuente: 'resultado.json del RUN objetivo: estado_inicial_activo' }];
    const previa = historica[llave];
    return [llave, previa ? { ids: previa.ids, fuente: previa.fuente } : { ids: null, fuente: null }];
  }));
  const baseValida = keys.every(k => Array.isArray(lineasBase[llaveId(k)].ids));
  const r = { grupo: 'G060', run_objetivo: c.runId, operacion: 'recuperar',
    autorizacion: c.referencia, cierre_solicitado: false, cierre_confirmado: false,
    cierre: { run: { cierre_http: null, estaba_abierto: null } }, rollback_verificado: false,
    linea_base_disponible: baseValida, lineas_base: lineasBase, observaciones: [],
    solicitudes: [], comprobacion: {},
    _limite: Infinity, _ensayo: ensayo, _consecutivos5xx: 0, _clave403: false };
  const secretos = [env.QA_SANDBOX_SECRET, env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD];
  const marca = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14);
  const evidencia = path.join(c.directorio, `recuperacion-${marca}.json`);
  if (fs.existsSync(evidencia)) throw Error('RECUPERACION_EVIDENCIA_EXISTENTE');
  try {
    r.cierre_solicitado = true;
    const cierre = await pedir(r, api, 'DELETE', `/test-control/runs/${encodeURIComponent(c.runId)}`,
      { secreto: env.QA_SANDBOX_SECRET, cierre: true });
    r.cierre.run.cierre_http = cierre.http;
    const cerradoAhora = cierre.http >= 200 && cierre.http < 300;
    const yaCerrado = cierre.http === 404 && cierre.cuerpo?.detail === 'Run ID no encontrado.';
    r.cierre_confirmado = cerradoAhora || yaCerrado;
    r.cierre.run.estaba_abierto = cerradoAhora ? true : yaCerrado ? false : null;
    const login = await pedir(r, api, 'POST', '/sesiones/', { rol: 'Administrador fuera del RUN',
      cuerpo: { correo_electronico: env.QA_ADMIN_EMAIL, contrasena: env.QA_ADMIN_PASSWORD },
      cierre: true, timeout: PRESUPUESTO.timeout_login_registro_ms });
    if (login.http === 200 && login.cuerpo?.token) {
      const token = login.cuerpo.token; secretos.push(token);
      const ids = [];
      for (let id = 112; id <= 124; id++) ids.push(await pedir(r, api, 'GET', ruta(id),
        { token, rol: 'Administrador poscierre', cierre: true }));
      const listados = [];
      for (const k of keys) listados.push(await pedir(r, api, 'GET', listaRuta(k),
        { token, rol: 'Administrador poscierre', cierre: true }));
      const versiones404 = ids.length === 13 && ids.every(x => x.http === 404
        && x.sin_cabecera_run === true);
      const listadosCompletos = listados.length === keys.length && listados.every(x =>
        x.http === 200 && x.sin_cabecera_run === true && Array.isArray(x.cuerpo?.items)
        && x.cuerpo.total === x.cuerpo.items.length
        && x.cuerpo.items.every(y => Number.isSafeInteger(idVersion(y))));
      const idsRunActivos = listadosCompletos && listados.some(x => x.cuerpo.items.some(y =>
        idVersion(y) >= 112 && idVersion(y) <= 124));
      const actuales = Object.fromEntries(keys.map((k, i) => [llaveId(k),
        listadosCompletos ? activas(listados[i], k, false).map(y => y.id).sort((a, b) => a - b) : null]));
      const diferencias = keys.map(llaveId).filter(llave => Array.isArray(lineasBase[llave].ids)
        && Array.isArray(actuales[llave])
        && JSON.stringify(actuales[llave]) !== JSON.stringify([...lineasBase[llave].ids].sort((a, b) => a - b)));
      const sinBase = keys.map(llaveId).filter(llave => lineasBase[llave].ids === null);
      if (sinBase.length) r.observaciones.push(`Sin línea base para ${sinBase.join(', ')}; comparación histórica no aplica.`);
      if (diferencias.length && !idsRunActivos) r.observaciones.push(
        `Diferencia frente a la línea base sin ids del RUN; posible actividad ajena: ${diferencias.join(', ')}.`);
      r.comprobacion = { versiones_404_sin_cabecera_run: versiones404,
        listados_completos_sin_cabecera_run: listadosCompletos, ids_del_run_activos: idsRunActivos,
        listados_iguales: diferencias.length === 0, diferencias_linea_base: diferencias,
        sin_linea_base: sinBase, activos_por_llave: actuales,
        versiones_http: ids.map(x => x.http), listados_http: listados.map(x => x.http) };
      r.rollback_verificado = r.cierre_confirmado && versiones404 && listadosCompletos
        && !idsRunActivos;
    } else r.comprobacion = { login_http: login.http, motivo: 'LOGIN_NO_DISPONIBLE' };
  } finally {
    const publico = { ...r }; Object.keys(publico).filter(k => k.startsWith('_')).forEach(k => delete publico[k]);
    guardar(evidencia, publico, secretos);
  }
  return r;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
  else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
  else try {
    const c = contextoEjecucion(process.argv.slice(2), { grupo: 'G060', casos: CASOS, directorio: DIR });
    const r = c.operacion === 'recuperar' ? await recuperar(c, { env: leerEnv() })
      : await evaluar(c, { env: leerEnv() });
    console.log(JSON.stringify(c.operacion === 'recuperar'
      ? { run_objetivo: r.run_objetivo, cierre_http: r.cierre.run.cierre_http,
        rollback_verificado: r.rollback_verificado }
      : { run_id: r.run_id, casos: r.casos, oficial: r.oficial }));
    if (c.operacion === 'recuperar' ? !r.rollback_verificado : !r.oficial) process.exitCode = 2;
  } catch (e) { console.error(`G060: ${limpio(e.message)}`); process.exitCode = 2; }
}
