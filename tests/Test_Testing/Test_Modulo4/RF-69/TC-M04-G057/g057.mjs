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
import { CASOS, IDS, PRESUPUESTO, CAPACIDADES, TIPOS, escenarios,
  idVersion, evaluarInstantanea } from './lib/g057_escenario.mjs';

const require = createRequire(import.meta.url);
const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const LOGIN_TIMEOUT_MS = PRESUPUESTO.timeout_post_ms;
const COLECCION = path.join(DIR, 'G057.postman_collection.json');
const ARCHIVOS = ['.gitkeep', 'g057.mjs', 'G057.postman_collection.json', 'README.md',
  'lib/contrato_ejecutor.mjs', 'lib/seguridad.mjs', 'lib/artefactos.mjs',
  'lib/g057_escenario.mjs', 'pruebas/g057_ensayo.mjs', 'pruebas/g057_env.test.mjs',
  'pruebas/registro_qa.mjs'];
const limpio = x => String(x ?? '').replaceAll('|', '/').replace(/[\r\n]+/g, ' ').slice(0, 250);
const CRITERIOS = [
  'La versión nueva pasa a ACTIVO sin deprecar otra; el listado solo muestra esa versión activa y la respuesta no reporta una versión deprecada (RF-69, Fase 5, líneas 2070-2087; Salida 3, líneas 2231-2235).',
  'La versión anterior pasa a DEPRECADO y la nueva a ACTIVO en la misma operación; queda exactamente una ACTIVO del mismo tipo y componente (RF-69, E5, líneas 2183-2190; CA-7, líneas 2307-2311).',
  'Los eventos de deprecación y activación de la misma operación comparten identificador de correlación, distinto del de la activación inicial (RF-69, E5, líneas 2191-2192).',
  'Se rechazan las activaciones sin notas o con notas de solo espacios; ambas versiones siguen APROBADO y la activa previa no se depreca (RF-69, CA-13, líneas 2337-2342).'
];
function motivoClaro(motivo) {
  return limpio(motivo)
    .replace(/lista ACTIVO=\{A\}/g, 'el listado mostró solo la versión activada')
    .replace(/listado=\{A\}/g, 'el listado muestra solo la versión activada')
    .replace(/MODELO_ESPECIES_GRANDES\s*[|/]\s*<NULL>/g, 'tipo MODELO_ESPECIES_GRANDES sin componente')
    .replace(/<NULL>/g, 'sin componente')
    .replace(/LOGIN_(ADMIN|VET)_SIN_RESPUESTA_([A-Za-z0-9_]+)/g, (_, rol, fallo) =>
      `el inicio de sesión del ${rol === 'ADMIN' ? 'Administrador' : 'Veterinario'} no respondió${fallo.includes('TIMEOUT') ? ' en 120 s' : ` (${fallo === 'ECONNREFUSED' ? 'conexión rechazada' : 'fallo de conexión'})`}`)
    .replace(/LOGIN_(ADMIN|VET)_NO_VERIFICABLE_HTTP_(\w+)/g, (_, rol, http) =>
      `el inicio de sesión del ${rol === 'ADMIN' ? 'Administrador' : 'Veterinario'} devolvió HTTP ${http}`)
    .replace(/POST_403_CLAVE/g, 'el registro de la versión devolvió HTTP 403 y no se pudo verificar la clave o el permiso')
    .replace(/CATALOGO_I3P1_NO_VERIFICABLE_HTTP_(\w+)/g, (_, http) => `el catálogo no pudo verificarse (HTTP ${http})`)
    .replace(/ACTIVOS_INICIALES_NO_VERIFICABLES_HTTP_(\w+)/g, (_, http) => `el listado inicial de versiones activas no pudo verificarse (HTTP ${http})`)
    .replace(/REGISTRO_APROBADO_NO_VERIFICABLE/g, 'el registro no acreditó una versión APROBADO')
    .replace(/NOTAS_AB_NO_VERIFICABLES/g, 'las notas de las versiones preparadas no pudieron verificarse')
    .replace(/POST_SIN_RESPUESTA/g, 'el registro de la versión no respondió')
    .replace(/NEWMAN_NO_DISPONIBLE/g, 'Newman no estaba disponible')
    .replace(/PREFLIGHT:/g, 'la comprobación previa impidió ejecutar la prueba: ');
}
function motivoDetalle(r, motivo) {
  const id = nombre => r.solicitudes.find(x => x.metodo === 'POST' && x.dato === nombre)?.id;
  return motivoClaro(motivo)
    .replace(/VERSION_DEPRECADA/g, 'evento de deprecación')
    .replace(/VERSION_ACTIVADA/g, 'evento de activación')
    .replace(/correlacion_id/g, 'identificador de correlación')
    .replace(/\b([ABCDE])\b/g, (_, nombre) => id(nombre) == null ? 'la versión solicitada' : `la versión ${id(nombre)}`)
    .replace(/\bGET\b/g, 'consulta')
    .replace(/\bPATCH\b/g, 'envío de notas');
}
function motivoBreve(r, i) {
  const caso = CASOS[i];
  if (r.casos[caso].estado !== 'APROBADO') return motivoClaro(r.casos[caso].motivo);
  const s = r.solicitudes;
  const id = nombre => s.find(x => x.metodo === 'POST' && x.dato === nombre)?.id;
  const nueva = id('E') == null ? 'B' : 'E';
  const anterior = id('E') == null ? 'A' : 'B';
  const primeraActiva = id('E') == null ? 'A' : 'B';
  const aud = s.filter(x => x.ruta === '/prediccion/auditoria?[filtro]');
  const corr = (x, evento, referencia) => x?.items?.find(y => y.tipo_evento === evento && String(y.id_referencia) === String(referencia))?.correlacion_id;
  return [
    `La versión ${id('A')} quedó ACTIVO; el listado mostró solo esa versión y la respuesta no reportó versión deprecada.`,
    `La versión ${id(anterior)} quedó DEPRECADO y la ${id(nueva)} ACTIVO; el listado mostró una sola activa del mismo tipo y componente.`,
    `La deprecación de ${id(anterior)} y la activación de ${id(nueva)} compartieron el identificador ${corr(aud.at(-2), 'VERSION_DEPRECADA', id(anterior))}; la activación inicial de ${id(primeraActiva)} tuvo ${corr(aud[id('E') == null ? 0 : 1], 'VERSION_ACTIVADA', id(primeraActiva))}.`,
    `Las versiones ${id('C')} y ${id('D')} quedaron APROBADO tras las activaciones rechazadas; la versión ${id(nueva)} siguió ACTIVO.`
  ][i];
}
function detallePorCaso(r) {
  const solicitudes = r.solicitudes;
  const registro = nombre => solicitudes.find(x => x.metodo === 'POST' && x.dato === nombre);
  const id = nombre => registro(nombre)?.id ?? null;
  const nombreId = nombre => id(nombre) == null ? 'versión solicitada sin ID recibido' : `versión ${id(nombre)}`;
  const operacion = (metodo, ruta) => solicitudes.find(x => x.metodo === metodo && x.ruta === ruta);
  const http = x => x ? `HTTP ${x.http ?? 'sin respuesta'}` : 'sin solicitud registrada';
  const estado = x => x?.estado ?? 'estado no verificado';
  const lista = (x, tipo) => x?.items?.filter(y => y.estado === tipo).map(y => y.id).join(', ') || 'ninguna';
  const prev = id('E') == null ? 'A' : 'B';
  const nueva = id('E') == null ? 'B' : 'E';
  const primeraActiva = id('E') == null ? 'A' : 'B';
  const a = id('A'), d = id('D');
  const activar = nombre => id(nombre) == null ? null : operacion('POST', `/prediccion/modelos/${id(nombre)}/activar`);
  const consultar = nombre => id(nombre) == null ? null : operacion('GET', `/prediccion/modelos/${id(nombre)}`);
  const antesCierre = solicitudes.findIndex(x => x.metodo === 'DELETE');
  const delRun = antesCierre < 0 ? solicitudes : solicitudes.slice(0, antesCierre);
  const ultConsulta = nombre => id(nombre) == null ? null : delRun.filter(x => x.metodo === 'GET' && x.ruta === `/prediccion/modelos/${id(nombre)}`).at(-1);
  const trasSustitucion = nombre => {
    const indice = solicitudes.indexOf(activar(nueva));
    return indice < 0 || id(nombre) == null ? null : solicitudes.slice(indice + 1)
      .find(x => x.metodo === 'GET' && x.ruta === `/prediccion/modelos/${id(nombre)}`);
  };
  const listadoTrasSustitucion = (() => {
    const indice = solicitudes.indexOf(activar(nueva));
    return indice < 0 ? null : solicitudes.slice(indice + 1)
      .find(x => x.metodo === 'GET' && x.ruta === '/prediccion/modelos?[filtro]');
  })();
  const listados = solicitudes.filter(x => x.metodo === 'GET' && x.ruta === '/prediccion/modelos?[filtro]');
  const auditorias = solicitudes.filter(x => x.metodo === 'GET' && x.ruta === '/prediccion/auditoria?[filtro]');
  const corr = (x, evento, referencia) => x?.items?.find(y => y.tipo_evento === evento && String(y.id_referencia) === String(referencia))?.correlacion_id;
  const corrInicial = corr(auditorias[id('E') == null ? 0 : 1], 'VERSION_ACTIVADA', id(primeraActiva));
  const corrDeprecada = corr(auditorias.at(-2), 'VERSION_DEPRECADA', id(prev));
  const corrActivada = corr(auditorias.at(-1), 'VERSION_ACTIVADA', id(nueva));
  const inicio = solicitudes.find(x => x.ruta === '/sesiones/' && x.http !== 200);
  const pasoInicial = inicio
    ? `Se intentó iniciar sesión del ${inicio.rol === 'admin' ? 'Administrador' : 'Veterinario'} (${http(inicio)}); no se ejecutó ninguna prueba del caso.`
    : 'La preparación se detuvo antes de ejecutar las solicitudes de este caso.';
  const pasos = [
    `Se registró ${nombreId('A')} del tipo ${r.observaciones.find(x => x.startsWith('Tipo elegido '))?.match(/Tipo elegido ([^;]+)/)?.[1] ?? 'no verificado'}; el Veterinario envió una nota clínica no vacía e intentó activar la versión, y el Administrador consultó su estado y los listados de activas y deprecadas.`,
    id('E') == null
      ? `Se registró ${nombreId(nueva)} del mismo tipo; el Administrador envió una nota clínica no vacía e intentó activar la versión. Después consultó ${nombreId(prev)}, ${nombreId(nueva)} y el listado de activas.`
      : `Se registraron ${nombreId(prev)} y ${nombreId(nueva)} del mismo tipo; el Administrador envió notas a la primera y el Veterinario a la segunda, ambas no vacías. Se intentó activar ${nombreId(prev)}${activar('E') ? ` y ${nombreId(nueva)}` : ''} y se consultaron los estados y el listado de activas.`,
    `El Administrador consultó la auditoría de ${nombreId(prev)} y ${nombreId(nueva)} tras la activación, y la comparó con el evento de la activación inicial de ${nombreId(primeraActiva)}.`,
    `Se registraron ${nombreId('C')} y ${nombreId('D')} APROBADO; el Veterinario intentó activar ${nombreId('C')} sin notas y el Administrador envió solo espacios como notas de ${nombreId('D')} e intentó activarla. Después consultó ambas versiones, ${nombreId(nueva)} y el listado de activas.`
  ];
  const observados = [
    `La activación de ${nombreId('A')} devolvió ${http(activar('A'))}; la consulta posterior mostró ${estado(consultar('A'))}. El listado de activas mostró ${lista(listados[2], 'ACTIVO')} y el de deprecadas ${lista(listados[3], 'DEPRECADO')}; la respuesta ${activar('A')?.campo_version_deprecada ? 'reportó' : 'no reportó'} versión deprecada.`,
    `La activación de ${nombreId(nueva)} devolvió ${http(activar(nueva))}; las consultas mostraron ${nombreId(prev)} ${estado(trasSustitucion(prev))} y ${nombreId(nueva)} ${estado(trasSustitucion(nueva))}. El listado filtrado posterior registró ${listadoTrasSustitucion?.total ?? 'total no verificado'} versión activa.`,
    `La activación inicial de ${nombreId(primeraActiva)} tuvo identificador ${corrInicial ?? 'no verificado'}; la deprecación de ${nombreId(prev)} tuvo ${corrDeprecada ?? 'no verificado'} y la activación de ${nombreId(nueva)} tuvo ${corrActivada ?? 'no verificado'}. Las consultas de auditoría devolvieron ${auditorias.map(http).join(', ') || 'ninguna respuesta'}.`,
    `Activar ${nombreId('C')} devolvió ${http(activar('C'))}; enviar notas de solo espacios a ${nombreId('D')} devolvió ${http(d == null ? null : operacion('PATCH', `/prediccion/modelos/${d}/notas`))} y activarla ${http(activar('D'))}. Las consultas finales mostraron ${nombreId('C')} ${estado(ultConsulta('C'))}, ${nombreId('D')} ${estado(ultConsulta('D'))} y ${nombreId(nueva)} ${estado(ultConsulta(nueva))}; el listado registró ${listados.at(-2)?.total ?? 'total no verificado'} activa.`
  ];
  const conformes = [
    'La única versión activa fue la nueva, no apareció otra deprecada y la respuesta no reportó una versión deprecada.',
    'La anterior quedó DEPRECADO, la nueva ACTIVO y el listado confirmó una sola activa del tipo y componente.',
    'Los dos eventos de la sustitución compartieron identificador y este fue distinto del de la primera activación.',
    'Ambas activaciones fueron rechazadas, las dos versiones permanecieron APROBADO y la versión activa previa quedó intacta.'
  ];
  return CASOS.map((caso, i) => {
    const decision = r.casos[caso].estado;
    const ejecutado = [!!activar('A'), !!activar(nueva), auditorias.length >= 3, !!activar('C')][i];
    const incidencia = r.incidencias.find(x => x.casos.includes(caso));
    const razon = decision === 'APROBADO' ? conformes[i]
      : decision === 'RECHAZADO' ? `Se incumplió el criterio: ${motivoDetalle(r, r.casos[caso].motivo)}; valor observado: ${observados[i]} Incidencia ${incidencia?.id ?? 'sin ID asignado'}.`
        : `${motivoDetalle(r, r.casos[caso].motivo)}; hace falta resolver el impedimento y repetir las comprobaciones pendientes en un RUN autorizado.`;
    return `### ${caso} — ${decision}\n\n**Qué se hizo:** ${ejecutado ? pasos[i] : pasoInicial}\n**Qué se esperaba:** ${CRITERIOS[i]}\n**Qué se observó:** ${ejecutado ? observados[i] : `${motivoDetalle(r, r.casos[caso].motivo)}; no se obtuvieron las respuestas necesarias del caso.`}\n**Por qué ${decision}:** ${razon}`;
  }).join('\n\n');
}
const guardar = (p, x, secretos = []) => fs.writeFileSync(p, sanearArtefacto(JSON.stringify(x), secretos), 'utf8');
const informe = v => v === 1 ? 'TC-M04-G057_resultado.md' : `TC-M04-G057_reevaluacion_V${v}.md`;

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
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const i of col.item) for (const e of i.event ?? []) new vm.Script((e.script?.exec ?? []).join('\n'));
    coleccion = col.item.length === 1 && col.item[0].name === 'API-G057-POST'
      && col.item[0].request.method === 'POST' && !contieneMojibake(JSON.stringify(col));
  } catch { /* se comunica false */ }
  const faltantes = ARCHIVOS.filter(x => !fs.existsSync(path.join(DIR, x)));
  const presentes = fs.readdirSync(DIR).filter(x => !['lib', 'pruebas', 'Resultados', 'EvaluacionV2'].includes(x))
    .concat(...['lib', 'pruebas'].map(d => fs.existsSync(path.join(DIR, d))
      ? fs.readdirSync(path.join(DIR, d)).map(x => `${d}/${x}`) : []));
  const inesperados = presentes.filter(x => !ARCHIVOS.includes(x));
  const markdownSuperior = fs.existsSync(path.join(DIR, 'Resultados'))
    && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const suma = Object.entries(PRESUPUESTO).filter(([k]) => !['total', 'contingencia_maxima', 'timeout_post_ms', 'timeout_ms', 'duracion_segundos'].includes(k))
    .reduce((n, [, v]) => n + v, 0);
  const ok = coleccion && !faltantes.length && !inesperados.length && !markdownSuperior
    && PRESUPUESTO.total === suma && PRESUPUESTO.contingencia_maxima === 40
    && PRESUPUESTO.contingencia_maxima <= 900 && versionNewman().ok;
  console.log(JSON.stringify({ grupo: 'G057', ok, coleccion, faltantes, inesperados,
    markdownSuperior, newman: versionNewman(), presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}
export function preflight(c, env, ensayo = false) {
  const base = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const faltan = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_ADMIN_EMAIL',
    'QA_ADMIN_PASSWORD', 'QA_VETERINARIO_EMAIL', 'QA_COMMON_PASSWORD', 'RF71_INTERNAL_KEY']
    .filter(k => !String(env[k] ?? '').trim());
  if (env.QA_AUTORIZADO !== 'SI') faltan.push('QA_AUTORIZADO');
  if (ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base) : base !== API)
    faltan.push('API_NO_CANONICA');
  if (c.version > 1 && c.operacion !== 'reevaluar') faltan.push('REEVALUACION_SIN_DECISION');
  return { grupo: 'G057', run_id: c.runId, ok: !faltan.length, barreras: faltan,
    presupuesto: PRESUPUESTO, herramientas: { newman: versionNewman() },
    efectos_declarados: ['4_versiones_APROBADO_BD_sandbox', '2_notas_2_activaciones_hasta_2_intentos_rechazados',
      'contingencia_A_5xx_una_version_E_un_ONNX_un_PATCH_una_activacion_y_lecturas_adicionales',
      'historial_y_auditoria_BD_sandbox', 'hasta_5_ONNX_fuera_rollback', 'respaldo_RF73_posible',
      'sin_correo_esperado', '2_logins_previos_posible_sesion_o_auditoria',
      'contingencia_deprecacion_activa_heredada'] };
}
function resumen(x) {
  const b = x?.cuerpo ?? {};
  return { http: x?.http ?? null, eco: x?.eco ?? null, id: idVersion(b),
    estado: b.estado_version ?? null, esta_produccion: b.esta_produccion ?? null,
    componente: b.componente ?? null, notas_presentes: !!String(b.notas_validacion ?? '').trim(),
    total: b.total ?? null, items: Array.isArray(b.items) ? b.items.map(y => ({
      id: idVersion(y), tipo_modelo: y.tipo_modelo, componente: y.componente ?? null,
      estado: y.estado_version, correlacion_id: y.correlacion_id ?? null,
      tipo_evento: y.tipo_evento ?? null, id_referencia: y.id_referencia ?? null })) : null,
    error_codigo: b.code ?? b.codigo ?? null, version_deprecada: b.version_deprecada ?? null,
    campo_version_deprecada: Object.hasOwn(b, 'version_deprecada'),
    duracion_ms: x?.duracion_ms ?? null };
}
async function pedir(r, api, metodo, ruta, { token, secreto, runId, cuerpo,
  rol = 'Sistema', estadoAntes = null, timeout = PRESUPUESTO.timeout_ms } = {}) {
  const fila = { rol, metodo, ruta: ruta.replace(/\?.*/, '?[filtro]'),
    estado_antes: estadoAntes, http: null };
  r.solicitudes.push(fila);
  const ini = Date.now();
  let etapa = 'red';
  try {
    if (Date.now() >= r._limite) throw Error('LIMITE_900_SEGUNDOS');
    const x = await fetch(api + ruta, { method: metodo, redirect: 'manual',
      headers: { ...(cuerpo ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(secreto ? { 'X-Sandbox-Secret': secreto } : {}),
        ...(runId ? { 'X-Test-Run-Id': runId, 'X-Zona-Horaria': 'UTC' } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      signal: AbortSignal.timeout(Math.max(1, Math.min(timeout, r._limite - Date.now()))) });
    const resp = { http: x.status, eco: runId ? x.headers.get('x-test-run-id') === runId : null,
      cuerpo: await x.json().catch(() => null), duracion_ms: Date.now() - ini };
    etapa = 'resumen';
    Object.assign(fila, resumen(resp));
    etapa = 'final';
    r._consecutivos5xx = x.status >= 500 ? r._consecutivos5xx + 1 : 0;
    if (r._consecutivos5xx >= 3) throw Error('TRES_5XX_CONSECUTIVOS');
    return resp;
  } catch (e) {
    if (e.message === 'TRES_5XX_CONSECUTIVOS') throw e;
    fila.error = 'SIN_RESPUESTA';
    const codigo = String(e?.cause?.code ?? '');
    const nombre = String(e?.name ?? 'Error').replace(/[^A-Za-z0-9_]/g, '').slice(0, 40) || 'Error';
    fila.tipo_fallo = etapa === 'resumen' ? `ERROR_LOCAL_${nombre}`
      : ['AbortError', 'TimeoutError'].includes(e?.name) ? 'TIMEOUT'
        : /^[A-Z][A-Z0-9_]{1,63}$/.test(codigo) ? codigo : 'DESCONOCIDO';
    fila.duracion_ms = Date.now() - ini;
    return { http: null, eco: null, cuerpo: null };
  }
}
async function registrarNewman(r, c, api, env, dato, temporal, secretos) {
  const raw = path.join(temporal, `newman-${dato.dato}-raw.json`);
  const values = Object.entries({ autorizado_run: 'SI', ensayo_loopback: c.ensayo ? 'SI' : 'NO',
    base_url: api, run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET,
    rf71_internal_key: env.RF71_INTERNAL_KEY }).map(([key, value]) => ({ key, value, enabled: true }));
  const input = { ...dato, metricas_validacion: JSON.stringify(dato.metricas_validacion),
    compatibilidad_variables: JSON.stringify(dato.compatibilidad_variables) };
  const ini = Date.now();
  await new Promise(resolve => require(paqueteNewman()).run({
    collection: JSON.parse(fs.readFileSync(COLECCION, 'utf8')),
    environment: { values }, iterationData: [input], reporters: ['json'],
    reporter: { json: { export: raw } }, timeoutRequest: c.ensayo ? 1500 : PRESUPUESTO.timeout_post_ms,
    timeout: Math.max(1, Math.min(PRESUPUESTO.timeout_post_ms + 5000, r._limite - Date.now())),
    color: 'off' }, () => resolve()));
  const original = fs.existsSync(raw) ? JSON.parse(fs.readFileSync(raw, 'utf8')) : {};
  const ex = original.run?.executions?.[0];
  let cuerpo = null;
  try { cuerpo = JSON.parse(Buffer.from(ex?.response?.stream?.data ?? []).toString('utf8')); }
  catch { /* sin JSON */ }
  const resp = { http: ex?.response?.code ?? null, cuerpo,
    eco: ex?.response?.header?.find(h => String(h.key).toLowerCase() === 'x-test-run-id')?.value === c.runId,
    duracion_ms: Date.now() - ini };
  r.solicitudes.push({ rol: 'RF-71 interno', metodo: 'POST', ruta: '/prediccion/modelos',
    dato: dato.dato, ...resumen(resp) });
  r._consecutivos5xx = resp.http >= 500 ? r._consecutivos5xx + 1 : 0;
  const sub = path.join(c.directorio, 'newman'); fs.mkdirSync(sub, { recursive: true });
  const nombre = `newman-G057-${dato.dato}`;
  guardar(path.join(sub, nombre + '.json'), { info: { nombre, saneado: true, generado: !!ex },
    run: { stats: original.run?.stats ?? null, executions: [{ ...resumen(resp) }],
      failures: (original.run?.failures ?? []).map(f => ({ name: limpio(f.error?.name),
        message: limpio(f.error?.message) })) } }, secretos);
  fs.writeFileSync(path.join(sub, nombre + '.html'),
    `<!doctype html><html lang="es"><meta charset="utf-8"><title>${nombre}</title>`
    + `<h1>${nombre}</h1><p>HTTP ${resp.http ?? 'sin respuesta'}; eco ${!!resp.eco}; duración ${resp.duracion_ms} ms</p></html>`, 'utf8');
  r.evidencias.push(`newman/${nombre}.json`, `newman/${nombre}.html`);
  if (r._consecutivos5xx >= 3) throw Error('TRES_5XX_CONSECUTIVOS');
  return resp;
}

function cierreInforme(c, r, secretos) {
  delete r._tokens; delete r._limite; delete r._consecutivos5xx; delete r._rollback_contexto;
  r.evidencias.push('resultado.json', informe(c.version));
  const activaciones5xx = (r.activaciones ?? []).filter(x => x.http >= 500);
  const cubiertos = new Set();
  const porActivacion = activaciones5xx.map((x, i) => {
    const casos = x.operacion === 'A' ? ['TC-M04-150']
      : x.operacion === 'B' || x.operacion === 'E' ? ['TC-M04-151', 'TC-M04-152']
        : ['TC-M04-153'];
    casos.forEach(caso => cubiertos.add(caso));
    return { id: `INC-M04-G057-ACT-${i + 1}`, casos, titulo: `Activar ${x.operacion} HTTP ${x.http}`,
      requisito: x.operacion === 'C' ? 'RF-69 CA-13' : 'RF-69 Fase 5/E5/E6',
      pasos: `Activar ${x.operacion} y consultar GET/listado/auditoría`,
      obtenido: `HTTP ${x.http}; código ${x.codigo ?? 'no expuesto'}; estado antes ${x.antes}; estado después ${x.despues ?? 'no verificable'}`,
      http: x.http, codigo: x.codigo ?? null, estado_antes: x.antes, estado_despues: x.despues ?? null,
      severidad: x.operacion === 'A' ? 'MEDIA' : 'ALTA',
      impacto: x.operacion === 'C' ? 'Rechazo por notas no conforme' : 'Activación o correlación exigida impedida',
      certeza: 'CONFIRMADA', equipo_inicial: 'Desarrollo',
      fundamento: 'Primera discrepancia comprobada en API pública', causa_raiz: 'NO DETERMINADA' };
  });
  if (porActivacion.length === 2 && porActivacion[0].http === porActivacion[1].http
    && porActivacion[0].codigo === porActivacion[1].codigo) {
    porActivacion[0].casos = ['TC-M04-150', 'TC-M04-151', 'TC-M04-152'];
    porActivacion[0].titulo = 'Activar A/B devuelve el mismo 5xx';
    porActivacion[0].obtenido += `; activar B HTTP ${porActivacion[1].http}, código ${porActivacion[1].codigo ?? 'no expuesto'}, estado antes ${porActivacion[1].estado_antes}, después ${porActivacion[1].estado_despues}`;
    porActivacion.splice(1, 1);
  }
  r.incidencias = [...porActivacion, ...CASOS.flatMap((caso, i) => r.casos[caso].estado === 'RECHAZADO' && !cubiertos.has(caso) ? [{
    id: `INC-M04-G057-${150 + i}`, casos: [caso], titulo: `${IDS[i]}: ${r.casos[caso].motivo}`,
    requisito: ['RF-69 Fase 5, líneas 2070-2087', 'RF-69 E5/CA-7, líneas 2183-2192, 2307-2311',
      'RF-69 E5/Fase 6, líneas 2096-2099, 2191-2192', 'RF-69 CA-13, líneas 2337-2342'][i],
    pasos: 'Consultar solicitudes API y respuestas persistidas del RUN', obtenido: r.casos[caso].motivo,
    severidad: i === 0 ? 'MEDIA' : 'ALTA',
    impacto: i === 0 ? 'Activación sin previa afectada' : 'Integridad o control de activación afectado',
    certeza: 'CONFIRMADA', equipo_inicial: 'Desarrollo',
    fundamento: 'Primera discrepancia comprobada en API pública',
    causa_raiz: 'NO DETERMINADA' }] : [])];
  r.oficial = CASOS.every(x => ['APROBADO', 'RECHAZADO'].includes(r.casos[x].estado))
    && !r.problemas_tecnicos.length && r.cierre.run.cierre_http === 200
    && r.cierre.rollback.verificado && r.solicitudes.length === (r.presupuesto_aplicado ?? PRESUPUESTO.total)
    && r.evidencias.some(x => x.startsWith('newman/'))
    && r.evidencias.filter(x => !['resultado.json', informe(c.version)].includes(x))
      .every(x => fs.existsSync(path.join(c.directorio, x)));
  r.consume_version = r.oficial;
  const estados = CASOS.map(x => r.casos[x].estado);
  const decision = estados.includes('RECHAZADO') ? 'RECHAZADO'
    : estados.every(x => x === 'APROBADO') ? 'APROBADO'
      : estados.includes('BLOQUEADO') ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
  const breve = CASOS.map((x, i) => `| ${x} | ${IDS[i]} | ${r.casos[x].estado} | ${motivoBreve(r, i)} |`).join('\n');
  const esperados = [
    'A ACTIVO, ninguna previa deprecada, listado={A}, respuesta sin versión deprecada',
    'A DEPRECADO, B ACTIVO, exactamente una ACTIVO de la llave',
    'VERSION_DEPRECADA(A) y VERSION_ACTIVADA(B) con correlacion_id igual y distinto del de A inicial',
    'C/D rechazadas por notas vacías, C/D APROBADO, B ACTIVO'];
  const detalle = CASOS.map((x, i) => `| ${x} | ${esperados[i]} | ${r.casos[x].estado}: ${limpio(r.casos[x].motivo)} |`).join('\n');
  const solicitudes = r.solicitudes.map(x => {
    const catalogo = x.ruta === '/configuracion/variables-ambientales';
    const items = catalogo && Number.isSafeInteger(x.total)
      ? `${x.total} variables`
      : x.items?.map(y => `${y.tipo_evento ?? y.estado}:${y.id ?? y.id_referencia}:${y.correlacion_id ?? '—'}`).join(', ') ?? '—';
    return `| ${x.rol} | ${x.metodo} ${limpio(x.ruta)}${x.dato ? ' '+x.dato : ''} | ${x.http ?? 'sin respuesta'} | ${x.tipo_fallo ?? '—'} | ${x.estado_antes ?? '—'} | ${x.estado ?? '—'} | ${x.total ?? '—'} | ${items} | ${x.duracion_ms ?? '—'} |`;
  }).join('\n');
  const oficialTest = r.oficial && r.ambiente === 'TEST';
  const pendientes = [];
  if (r.problemas_tecnicos.length) pendientes.push(`resolver ${r.problemas_tecnicos.map(limpio).join(', ')}`);
  const casosPendientes = CASOS.filter(x => !['APROBADO', 'RECHAZADO'].includes(r.casos[x].estado));
  if (casosPendientes.length) pendientes.push(`comprobar ${casosPendientes.join(', ')} en un RUN autorizado`);
  if (r.cierre.run.cierre_http !== 200) pendientes.push('confirmar cierre DELETE 200');
  if (!r.cierre.rollback.verificado) pendientes.push('contrastar rollback por API');
  if (r.oficial && !oficialTest) pendientes.push('evaluar en TEST con autorización');
  const queFalta = pendientes.length ? pendientes.join('; ') : 'nada para este grupo';
  const loginSinRun = r.solicitudes.some(x => x.ruta === '/sesiones/' && x.error === 'SIN_RESPUESTA')
    && r.solicitudes.every(x => x.ruta === '/sesiones/');
  const diagnosticoLogin = loginSinRun
    ? 'El login previo al RUN terminó sin respuesta; no hubo peticiones dentro del RUN.\n\n' : '';
  const incid = r.incidencias.map(x => `### ${x.id}\n\n${x.titulo}. Casos ${x.casos.join(', ')}. Requisito: ${x.requisito}. Pasos: ${x.pasos}. Obtenido: ${x.obtenido}. Severidad ${x.severidad} por ${x.impacto}; certeza ${x.certeza}; equipo inicial ${x.equipo_inicial} por ${x.fundamento}; causa raíz ${x.causa_raiz}.`).join('\n\n') || 'Sin incidencias de producto confirmadas.';
  const md = `# TC-M04-G057 — ${decision}\n\n`+
    `Grupo G057; casos ${CASOS.join(', ')}; RF-69 v2.1; V${c.version}; RUN ${c.runId}; ambiente ${r.ambiente}; autorización ${limpio(c.referencia)}; código local consultado origin/test daefc3a5 (despliegue no verificado); Newman ${r.herramientas.newman.version ?? 'no disponible'}; Cypress no aplica (${r.cypress.total_pruebas}).\n\n`+
    `## Decisión del caso\n\nAgrupado **TC-M04-G057 (RF-69)**; originales **${CASOS.join(', ')}**.\n\n`+
    `**Decisión: ${decision}.** ${CASOS.map((x, i) => `${x} ${r.casos[x].estado}: ${motivoBreve(r, i)}`).join('; ')}\n\n`+
    `| Caso | Comprobación | Decisión | Motivo breve |\n|---|---|---|---|\n${breve}\n\n`+
    `**RUN oficial: ${oficialTest ? 'sí' : 'no'}.** **Qué falta: ${queFalta}.**\n\n`+
    `## Detalle por caso\n\n${detallePorCaso(r)}\n\n`+
    `## Esperado y observado\n\n| Caso | Esperado | Observado |\n|---|---|---|\n${detalle}\n\n`+
    `## Solicitudes API\n\n| Rol | Operación | HTTP | Tipo de fallo | Estado antes | Estado después | Total | Items/eventos y correlacion_id | Duración ms |\n|---|---|---:|---|---|---|---:|---|---:|\n${solicitudes}\n\n`+
    `## Observaciones\n\n${r.observaciones.map(x => '- '+limpio(x)).join('\n') || 'Sin observaciones.'}\n\n`+
    `## Incidencias de producto\n\n${incid}\n\n## Problemas técnicos\n\n${diagnosticoLogin}${r.problemas_tecnicos.map(x => '- '+limpio(x)).join('\n') || 'Sin problemas técnicos.'}\n\n`+
    `## Historial de intentos, cierre y rollback\n\nOperación ${c.operacion}; intento ${c.intento}; ${r.solicitudes.length} solicitudes. DELETE HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. Rollback ${r.cierre.rollback.verificado ? 'comprobado por GET poscierre' : 'NO_VERIFICADO'}: ${r.cierre.rollback.motivo}. Los cuatro ONNX en MODELOS_STORAGE_PATH y posible respaldo RF-73 no quedan cubiertos por DELETE.\n\n`+
    `## Evidencias\n\n${r.evidencias.map(x => '- '+x).join('\n')}\n\n`+
    `## Conclusión y acción\n\n${r.oficial ? 'Entregar al registro QA y revisar incidencias y efectos persistentes.' : 'Determinar la causa del impedimento y decidir un reintento autorizado.'}\n`;
  fs.writeFileSync(path.join(c.directorio, informe(c.version)), sanearArtefacto(md, secretos), 'utf8');
  guardar(path.join(c.directorio, 'resultado.json'), r, secretos);
}

export async function evaluar(c, { env, ensayo = false }) {
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G057', run_id: c.runId, version: c.version, intento: c.intento ?? null,
    operacion: c.operacion, autorizacion: c.referencia, ambiente: ensayo ? 'LOOPBACK_LOCAL' : 'TEST',
    oficial: false, consume_version: false,
    casos: Object.fromEntries(CASOS.map(x => [x, { estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación' }])),
    comprobaciones: CASOS.map((caso, i) => ({ caso, fuente: 'API', id: IDS[i], tipo: 'ASSERT',
      estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación', evidencia: null })),
    presupuesto: PRESUPUESTO, herramientas: { newman: versionNewman() },
    solicitudes: [], cypress: { total_pruebas: 0 }, evidencias: [], incidencias: [],
    problemas_tecnicos: [], observaciones: [],
    cierre: { run: { cierre_http: null }, rollback: { verificado: false,
      motivo: 'Sin cierre ni verificación posterior' } },
    _tokens: {}, _limite: Date.now() + PRESUPUESTO.duracion_segundos * 1000,
    _consecutivos5xx: 0 };
  const secretos = [env.QA_SANDBOX_SECRET, env.RF71_INTERNAL_KEY, env.QA_ADMIN_EMAIL,
    env.QA_ADMIN_PASSWORD, env.QA_VETERINARIO_EMAIL, env.QA_COMMON_PASSWORD].filter(Boolean);
  let temporal = null, tocado = false;
  const poner = (i, x) => { r.casos[CASOS[i]] = x;
    Object.assign(r.comprobaciones[i], { ...x, evidencia: 'resultado.json' }); };
  try {
    const pre = preflight(c, env, ensayo); guardar(path.join(c.directorio, 'preflight.json'), pre, secretos);
    r.evidencias.push('preflight.json');
    if (!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
    if (!r.herramientas.newman.ok) throw Error('NEWMAN_NO_DISPONIBLE');
    for (const [rol, email, pass] of [['admin', env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD],
      ['vet', env.QA_VETERINARIO_EMAIL, env.QA_COMMON_PASSWORD]]) {
      const x = await pedir(r, api, 'POST', '/sesiones/',
        { cuerpo: { correo_electronico: email, contrasena: pass }, rol,
          timeout: ensayo ? LOGIN_TIMEOUT_MS / 100 : LOGIN_TIMEOUT_MS });
      if (x.http !== 200 || !x.cuerpo?.token) {
        const fallo = r.solicitudes.at(-1);
        const tipo = fallo?.tipo_fallo ?? 'DESCONOCIDO';
        const motivo = x.http == null && fallo?.error === 'SIN_RESPUESTA'
          ? `LOGIN_${rol.toUpperCase()}_SIN_RESPUESTA_${tipo}${tipo === 'TIMEOUT' ? '_120s' : ''}`
          : `LOGIN_${rol.toUpperCase()}_NO_VERIFICABLE_HTTP_${x.http}`;
        throw Error(motivo);
      }
      r._tokens[rol] = x.cuerpo.token; secretos.push(x.cuerpo.token);
    }
    tocado = true;
    const opts = (rol, token) => ({ rol, token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId });
    const admin = opts('Administrador', r._tokens.admin), vet = opts('Veterinario', r._tokens.vet);
    const catalogo = await pedir(r, api, 'GET', '/configuracion/variables-ambientales', admin);
    const variables = catalogo.cuerpo?.items?.map(x => x.id_variable_ambiental).filter(Number.isSafeInteger) ?? [];
    if (catalogo.http !== 200 || !catalogo.eco || !variables.length) throw Error(`CATALOGO_I3P1_NO_VERIFICABLE_HTTP_${catalogo.http}`);
    const inicial = await pedir(r, api, 'GET', '/prediccion/modelos?estado=ACTIVO&limit=100&offset=0', admin);
    if (inicial.http !== 200 || !inicial.eco || !Array.isArray(inicial.cuerpo?.items)
      || inicial.cuerpo.total > inicial.cuerpo.items.length) throw Error(`ACTIVOS_INICIALES_NO_VERIFICABLES_HTTP_${inicial.http}`);
    const libre = TIPOS.find(t => !inicial.cuerpo.items.some(x => x.tipo_modelo === t && x.componente == null));
    const tipo = libre ?? TIPOS[0];
    const heredada = libre ? null : idVersion(inicial.cuerpo.items.find(x => x.tipo_modelo === tipo && x.componente == null));
    r.observaciones.push(`Tipo elegido ${tipo}; ACTIVO heredada ${heredada ?? 'ninguna'}`);
    temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g057-newman-'));
    const archivo = path.join(temporal, 'g057.onnx'); fs.writeFileSync(archivo, onnxMinimo());
    const datos = escenarios({ tipo, variable: variables[0], hash: sha256(fs.readFileSync(archivo)),
      dataset: sha256(Buffer.from('G057 dataset QA RF-71')), archivo });
    const post = [];
    for (const dato of datos) {
      const x = await registrarNewman(r, c, api, env, dato, temporal, secretos);
      post.push(x);
      if (x.http === 403 || x.http == null) break;
    }
    if (post.some(x => x.http === 403)) throw Error('POST_403_CLAVE');
    if (post.some(x => x.http == null)) {
      const conciliacion = await pedir(r, api, 'GET', `/prediccion/modelos?tipo_modelo=${tipo}&limit=100&offset=0`, admin);
      r.observaciones.push(`Registro sin respuesta: conciliación GET/listado HTTP ${conciliacion.http}; total ${conciliacion.cuerpo?.total ?? 'no verificable'}`);
      throw Error('POST_SIN_RESPUESTA; conciliación GET/listado sin ID de respuesta inequívoco');
    }
    const ids = post.map(x => idVersion(x.cuerpo));
    if (ids.some(x => x == null) || post.some(x => x.http !== 201 || !x.eco || x.cuerpo?.estado_version !== 'APROBADO'))
      throw Error('REGISTRO_APROBADO_NO_VERIFICABLE');
    r._rollback_contexto = { tipo, ids, activos_antes: inicial.cuerpo.items
      .filter(x => x.tipo_modelo === tipo).map(idVersion).sort((a, b) => a - b) };
    const base = id => `/prediccion/modelos/${id}`;
    const notas = {};
    notas.A = await pedir(r, api, 'PATCH', `${base(ids[0])}/notas`,
      { ...vet, cuerpo: { notas_validacion: `G057 ${c.runId} Veterinario nota clínica` }, estadoAntes: 'APROBADO' });
    notas.B = await pedir(r, api, 'PATCH', `${base(ids[1])}/notas`,
      { ...admin, cuerpo: { notas_validacion: `G057 ${c.runId} Administrador nota clínica` }, estadoAntes: 'APROBADO' });
    if (![notas.A, notas.B].every(x => x.http >= 200 && x.http < 300 && x.eco)) throw Error('NOTAS_AB_NO_VERIFICABLES');
    const respuesta = {}, get = {}, listas = {}, aud = {};
    const activar = async (nombre, id, credenciales) => {
      const x = await pedir(r, api, 'POST', `${base(id)}/activar`,
        { ...credenciales, estadoAntes: 'APROBADO' });
      if (x.http >= 500) r.activaciones.push({ operacion: nombre, http: x.http,
        codigo: x.cuerpo?.code ?? x.cuerpo?.codigo ?? null, antes: 'APROBADO', despues: null });
      return x;
    };
    r.activaciones = [];
    const listar = () => pedir(r, api, 'GET', `/prediccion/modelos?tipo_modelo=${tipo}&estado=ACTIVO&limit=100&offset=0`, admin);
    const deprecadas = () => pedir(r, api, 'GET', `/prediccion/modelos?tipo_modelo=${tipo}&estado=DEPRECADO&limit=100&offset=0`, admin);
    const auditoria = id => pedir(r, api, 'GET', `/prediccion/auditoria?id_referencia=${id}&por_pagina=200`, admin);
    listas.deprecAntes = await deprecadas();
    respuesta.A = await activar('A', ids[0], vet);
    get.A150 = await pedir(r, api, 'GET', base(ids[0]), admin);
    if (respuesta.A.http >= 500) r.activaciones.at(-1).despues = get.A150.cuerpo?.estado_version ?? null;
    listas.A = await listar();
    listas.deprecDespues = await deprecadas();
    aud.A150 = await auditoria(ids[0]);
    if (respuesta.A.http >= 500) poner(0, { estado: 'RECHAZADO',
      motivo: `Activar A HTTP ${respuesta.A.http}; estado posterior ${get.A150.cuerpo?.estado_version ?? 'no verificable'}` });
    let contingencia = null;
    if (respuesta.A.http >= 500 && !heredada) {
      const datoE = escenarios({ tipo, variable: variables[0], hash: sha256(fs.readFileSync(archivo)),
        dataset: sha256(Buffer.from('G057 dataset QA RF-71')), archivo, nombres: ['E'] })[0];
      const postE = await registrarNewman(r, c, api, env, datoE, temporal, secretos);
      const idE = idVersion(postE.cuerpo);
      if (postE.http !== 201 || !postE.eco || idE == null || postE.cuerpo?.estado_version !== 'APROBADO')
        throw Error('REGISTRO_E_APROBADO_NO_VERIFICABLE');
      ids.push(idE);
      notas.E = await pedir(r, api, 'PATCH', `${base(idE)}/notas`,
        { ...vet, cuerpo: { notas_validacion: `G057 ${c.runId} Veterinario nota clínica E` }, estadoAntes: 'APROBADO' });
      if (notas.E.http !== 200 || !notas.E.eco) throw Error('NOTAS_E_NO_VERIFICABLES');
      const primeraB = await activar('B', ids[1], admin);
      if (primeraB.http >= 500) {
        respuesta.B = primeraB;
        get.A151 = await pedir(r, api, 'GET', base(ids[0]), admin);
        get.B151 = await pedir(r, api, 'GET', base(ids[1]), admin);
        r.activaciones.at(-1).despues = get.B151.cuerpo?.estado_version ?? null;
        poner(1, { estado: 'RECHAZADO', motivo: `Activar B HTTP ${primeraB.http}; sin transición atómica` });
        poner(2, { estado: 'RECHAZADO', motivo: `Activar B HTTP ${primeraB.http}; no hay par correlacionado` });
        contingencia = { falloInicial5xx: primeraB.http };
        r.presupuesto_aplicado = PRESUPUESTO.total + 3;
      } else if (primeraB.http >= 200 && primeraB.http < 300 && primeraB.eco) {
        const getPrevia = await pedir(r, api, 'GET', base(ids[1]), admin);
        contingencia = { anterior: ids[1], nueva: idE, getPrevia };
        respuesta.B = await activar('E', idE, vet);
        get.A151 = await pedir(r, api, 'GET', base(ids[1]), admin);
        get.B151 = await pedir(r, api, 'GET', base(idE), admin);
        if (respuesta.B.http >= 500) r.activaciones.at(-1).despues = get.B151.cuerpo?.estado_version ?? null;
        if (respuesta.B.http >= 500) {
          poner(1, { estado: 'RECHAZADO', motivo: `Activar E HTTP ${respuesta.B.http}; sin transición atómica` });
          poner(2, { estado: 'RECHAZADO', motivo: `Activar E HTTP ${respuesta.B.http}; no hay par correlacionado` });
        }
        r.presupuesto_aplicado = PRESUPUESTO.contingencia_maxima;
      } else throw Error(`ACTIVAR_B_CONTINGENCIA_NO_VERIFICABLE_HTTP_${primeraB.http}`);
    } else {
      respuesta.B = await activar('B', ids[1], admin);
      get.A151 = await pedir(r, api, 'GET', base(ids[0]), admin);
      get.B151 = await pedir(r, api, 'GET', base(ids[1]), admin);
      if (respuesta.B.http >= 500) r.activaciones.at(-1).despues = get.B151.cuerpo?.estado_version ?? null;
      if (respuesta.B.http >= 500) {
        poner(1, { estado: 'RECHAZADO', motivo: `Activar B HTTP ${respuesta.B.http}; sin transición atómica` });
        poner(2, { estado: 'RECHAZADO', motivo: `Activar B HTTP ${respuesta.B.http}; no hay par correlacionado` });
      }
    }
    listas.B = await listar();
    aud.A151 = await auditoria(contingencia?.anterior ?? ids[0]);
    aud.B151 = await auditoria(contingencia?.nueva ?? ids[1]);
    respuesta.C = await activar('C', ids[2], vet);
    notas.D = await pedir(r, api, 'PATCH', `${base(ids[3])}/notas`,
      { ...admin, cuerpo: { notas_validacion: '   ' }, estadoAntes: 'APROBADO' });
    respuesta.D = await pedir(r, api, 'POST', `${base(ids[3])}/activar`, { ...admin, estadoAntes: 'APROBADO' });
    get.C153 = await pedir(r, api, 'GET', base(ids[2]), admin);
    if (respuesta.C.http >= 500) r.activaciones.at(-1).despues = get.C153.cuerpo?.estado_version ?? null;
    if (respuesta.C.http >= 500) poner(3, { estado: 'RECHAZADO',
      motivo: `Activar C HTTP ${respuesta.C.http}; rechazo por notas no conforme` });
    get.D153 = await pedir(r, api, 'GET', base(ids[3]), admin);
    get.B153 = await pedir(r, api, 'GET', base(contingencia?.nueva ?? ids[1]), admin);
    listas.final = await listar();
    const resultado = evaluarInstantanea({ tipo, ids, iniciales: inicial, respuesta, get,
       listas, aud, notas, heredada, contingencia });
    resultado.forEach((x, i) => poner(i, x));
    if (!Object.hasOwn(respuesta.B.cuerpo ?? {}, 'version_deprecada'))
      r.observaciones.push('Respuesta de activar B no reporta version_deprecada (Salida 3); no altera el oráculo de 151');
    const esperadoAntes = (r.presupuesto_aplicado ?? PRESUPUESTO.total) - 1 - (PRESUPUESTO.comprobacion_rollback + (contingencia ? 1 : 0));
    if (r.solicitudes.length !== esperadoAntes)
      r.problemas_tecnicos.push(`Presupuesto antes de cierre ${r.solicitudes.length}/${esperadoAntes}`);
  } catch (e) {
    const motivo = limpio(e.message); r.problemas_tecnicos.push(motivo);
    const estado = /403|5XX|LOGIN|CATALOGO|ACTIVOS_INICIALES|REGISTRO|NOTAS_AB/.test(motivo)
      ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
    CASOS.forEach((caso, i) => { if (r.casos[caso].motivo === 'Sin comprobación') poner(i, { estado, motivo }); });
  } finally {
    if (tocado) {
      try {
        const x = await pedir(r, api, 'DELETE', `/test-control/runs/${encodeURIComponent(c.runId)}`,
          { secreto: env.QA_SANDBOX_SECRET, rol: 'Sistema' });
        r.cierre.run.cierre_http = x.http;
        r.cierre.rollback.motivo = `DELETE HTTP ${x.http}; rollback pendiente de comprobación`;
        if (x.http === 200 && r._rollback_contexto) {
          const { tipo, ids, activos_antes } = r._rollback_contexto;
          const consultas = [];
          for (const id of ids) consultas.push(await pedir(r, api, 'GET', `/prediccion/modelos/${id}`,
            { token: r._tokens.admin, rol: 'Administrador poscierre' }));
          const activos = await pedir(r, api, 'GET',
            `/prediccion/modelos?tipo_modelo=${tipo}&estado=ACTIVO&limit=100&offset=0`,
            { token: r._tokens.admin, rol: 'Administrador poscierre' });
          const idsActivos = (activos.cuerpo?.items ?? []).map(idVersion).sort((a, b) => a - b);
          r.cierre.rollback.verificado = consultas.every(y => y.http === 404)
            && activos.http === 200 && activos.cuerpo?.total === idsActivos.length
            && JSON.stringify(idsActivos) === JSON.stringify(activos_antes);
           r.cierre.rollback.motivo = r.cierre.rollback.verificado
             ? `GET poscierre: ${ids.length} versiones HTTP 404; activos iniciales de ${tipo} restaurados (${idsActivos.join(',') || 'ninguno'})`
            : `GET poscierre: versiones ${consultas.map(y => y.http ?? 'sin respuesta').join('/')}; activos HTTP ${activos.http}; rollback no acreditado`;
        }
      } catch (e) { r.problemas_tecnicos.push(`CIERRE:${limpio(e.message)}`); }
    }
    if (temporal) {
      if (!path.resolve(temporal).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
      fs.rmSync(temporal, { recursive: true, force: true });
    }
    cierreInforme(c, r, secretos);
  }
  return r;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
  else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
  else try {
    const c = contextoEjecucion(process.argv.slice(2), { grupo: 'G057', casos: CASOS, directorio: DIR });
    const r = await evaluar(c, { env: leerEnv() });
    console.log(JSON.stringify({ run_id: r.run_id, casos: r.casos, oficial: r.oficial }));
    if (!r.oficial) process.exitCode = 2;
  } catch (e) { console.error(`G057: ${limpio(e.message)}`); process.exitCode = 2; }
}
