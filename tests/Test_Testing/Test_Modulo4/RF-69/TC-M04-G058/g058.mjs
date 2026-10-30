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
import { CASOS, IDS, PRESUPUESTO, CAPACIDADES, TIPO, escenarios, idVersion,
  evaluarInstantanea, registroValido } from './lib/g058_escenario.mjs';

const require = createRequire(import.meta.url);
const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION = path.join(DIR, 'G058.postman_collection.json');
const ARCHIVOS = ['.gitkeep', 'g058.mjs', 'G058.postman_collection.json', 'README.md',
  'lib/seguridad.mjs', 'lib/artefactos.mjs', 'lib/contrato_ejecutor.mjs',
  'lib/g058_escenario.mjs', 'pruebas/g058_env.test.mjs', 'pruebas/g058_ensayo.mjs',
  'pruebas/registro_qa.mjs'];
const corto = x => String(x ?? '').replaceAll('|', '/').replace(/[\r\n]+/g, ' ').slice(0, 300);
const guardar = (archivo, obj, secretos = []) => fs.writeFileSync(archivo,
  sanearArtefacto(JSON.stringify(obj), secretos), 'utf8');
const informe = v => v === 1 ? 'TC-M04-G058_resultado.md' : `TC-M04-G058_reevaluacion_V${v}.md`;

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
function versionNewman() {
  try { return { ok: true, version: require(path.join(paqueteNewman(), 'package.json')).version }; }
  catch { return { ok: false, error: 'NEWMAN_NO_RESUELTO' }; }
}
export function comprobar() {
  let coleccion = false;
  try {
    const c = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const item of c.item) for (const ev of item.event ?? [])
      new vm.Script((ev.script?.exec ?? []).join('\n'));
    coleccion = c.item.length === 1 && c.item[0].name === 'API-G058-POST'
      && c.item[0].request.method === 'POST' && !contieneMojibake(JSON.stringify(c));
  } catch { /* salida de comprobación */ }
  const faltantes = ARCHIVOS.filter(x => !fs.existsSync(path.join(DIR, x)));
  const presentes = fs.readdirSync(DIR).filter(x => !['lib', 'pruebas', 'Resultados', 'EvaluacionV2'].includes(x))
    .concat(...['lib', 'pruebas'].map(d => fs.existsSync(path.join(DIR, d))
      ? fs.readdirSync(path.join(DIR, d)).map(x => `${d}/${x}`) : []));
  const inesperados = presentes.filter(x => !ARCHIVOS.includes(x));
  const suma = Object.entries(PRESUPUESTO).filter(([k]) => !['total', 'timeout_post_ms', 'timeout_ms', 'duracion_segundos'].includes(k))
    .reduce((n, [, v]) => n + v, 0);
  const markdownSuperior = fs.existsSync(path.join(DIR, 'Resultados'))
    && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const ok = coleccion && !faltantes.length && !inesperados.length && !markdownSuperior
    && suma === PRESUPUESTO.total && versionNewman().ok;
  console.log(JSON.stringify({ grupo: 'G058', ok, coleccion, faltantes, inesperados,
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
  return { grupo: 'G058', run_id: c.runId, ok: !barreras.length, barreras,
    presupuesto: PRESUPUESTO, herramientas: { newman: versionNewman() },
    efectos_declarados: ['3_versiones_BD_sandbox', '2_notas_2_activaciones_validas_4_intentos_rechazados',
      'historial_y_auditoria_BD_sandbox', '3_ONNX_fuera_rollback', 'respaldo_RF73_posible',
      'correo_a_cada_usuario_activo_permiso_43_3_por_R', 'sin_OTA_MQTT_Edge',
      '2_logins_previos_posible_sesion_o_auditoria', 'posible_deprecacion_activa_heredada'] };
}
function resumen(x) {
  const b = x?.cuerpo ?? {};
  return { http: x?.http ?? null, eco: x?.eco ?? null, id: idVersion(b),
    estado: b.estado_version ?? null, esta_produccion: b.esta_produccion ?? null,
    total: b.total ?? null, items: Array.isArray(b.items) ? b.items.map(y => ({
      id: idVersion(y), tipo_modelo: y.tipo_modelo ?? null, componente: y.componente ?? null,
      estado: y.estado_version ?? null, tipo_evento: y.tipo_evento ?? null,
      id_referencia: y.id_referencia ?? null, correlacion_id: y.correlacion_id ?? null })) : null,
    error_codigo: b.error_code ?? b.code ?? b.codigo ?? null, duracion_ms: x?.duracion_ms ?? null };
}
async function pedir(r, api, metodo, ruta, { token, secreto, runId, cuerpo, rol = 'Sistema',
  estadoAntes = null, timeout = PRESUPUESTO.timeout_ms } = {}) {
  const fila = { rol, metodo, ruta: ruta.replace(/\?.*/, '?[filtro]'), estado_antes: estadoAntes, http: null };
  r.solicitudes.push(fila);
  const ini = Date.now();
  try {
    if (Date.now() >= r._limite) throw Error('LIMITE_900_SEGUNDOS');
    const x = await fetch(api + ruta, { method: metodo, redirect: 'manual',
      headers: { ...(cuerpo ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(secreto ? { 'X-Sandbox-Secret': secreto } : {}),
        ...(runId ? { 'X-Test-Run-Id': runId, 'X-Zona-Horaria': 'UTC' } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      signal: AbortSignal.timeout(Math.max(1, Math.min(r._ensayo ? 1500 : timeout, r._limite - Date.now()))) });
    const resp = { http: x.status, eco: runId ? x.headers.get('x-test-run-id') === runId : null,
      cuerpo: await x.json().catch(() => null), duracion_ms: Date.now() - ini };
    Object.assign(fila, resumen(resp));
    r._consecutivos5xx = x.status >= 500 ? r._consecutivos5xx + 1 : 0;
    if (r._consecutivos5xx >= 3) throw Error('TRES_5XX_CONSECUTIVOS');
    return resp;
  } catch (e) {
    if (e.message === 'TRES_5XX_CONSECUTIVOS') throw e;
    fila.error = 'SIN_RESPUESTA';
    const codigo = String(e?.cause?.code ?? '');
    fila.tipo_fallo = ['AbortError', 'TimeoutError'].includes(e?.name) ? 'TIMEOUT'
      : /^[A-Z][A-Z0-9_]{1,63}$/.test(codigo) ? codigo : 'DESCONOCIDO';
    fila.duracion_ms = Date.now() - ini;
    r.problemas_tecnicos.push(`${metodo} ${fila.ruta} sin respuesta (${fila.tipo_fallo})`);
    return { http: null, eco: null, cuerpo: null };
  }
}
async function registrarNewman(r, c, api, env, dato, temporal, secretos) {
  const raw = path.join(temporal, `newman-${dato.dato}-raw.json`);
  const html = path.join(temporal, `newman-${dato.dato}-raw.html`);
  const values = Object.entries({ autorizado_run: 'SI', ensayo_loopback: c.ensayo ? 'SI' : 'NO',
    base_url: api, run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET,
    rf71_internal_key: env.RF71_INTERNAL_KEY }).map(([key, value]) => ({ key, value, enabled: true }));
  const input = { ...dato, metricas_validacion: JSON.stringify(dato.metricas_validacion),
    compatibilidad_variables: JSON.stringify(dato.compatibilidad_variables) };
  const ini = Date.now();
  await new Promise(resolve => require(paqueteNewman()).run({
    collection: JSON.parse(fs.readFileSync(COLECCION, 'utf8')),
    environment: { values }, iterationData: [input], reporters: ['json', 'htmlextra'],
    reporter: { json: { export: raw }, htmlextra: { export: html } },
    timeoutRequest: c.ensayo ? 1500 : PRESUPUESTO.timeout_post_ms,
    timeout: Math.max(1, Math.min(PRESUPUESTO.timeout_post_ms + 5000, r._limite - Date.now())),
    color: 'off' }, () => resolve()));
  const original = fs.existsSync(raw) ? JSON.parse(fs.readFileSync(raw, 'utf8')) : {};
  const ex = original.run?.executions?.[0];
  let cuerpo = null;
  try { cuerpo = JSON.parse(Buffer.from(ex?.response?.stream?.data ?? []).toString('utf8')); }
  catch { /* respuesta no JSON */ }
  const resp = { http: ex?.response?.code ?? null, cuerpo,
    eco: ex?.response?.header?.find(h => String(h.key).toLowerCase() === 'x-test-run-id')?.value === c.runId,
    duracion_ms: Date.now() - ini };
  r.solicitudes.push({ rol: 'RF-71 interno', metodo: 'POST', ruta: '/prediccion/modelos',
    dato: dato.dato, ...resumen(resp) });
  r._consecutivos5xx = resp.http >= 500 ? r._consecutivos5xx + 1 : 0;
  const sub = path.join(c.directorio, 'newman'); fs.mkdirSync(sub, { recursive: true });
  const nombre = `newman-G058-${dato.dato}`;
  guardar(path.join(sub, nombre + '.json'), { info: { nombre, saneado: true, generado: !!ex },
    run: { stats: original.run?.stats ?? null, executions: [{ ...resumen(resp) }],
      failures: (original.run?.failures ?? []).map(f => ({ name: corto(f.error?.name),
        message: corto(f.error?.message) })) } }, secretos);
  if (fs.existsSync(html)) {
    fs.writeFileSync(path.join(sub, nombre + '.html'),
      sanearArtefacto(fs.readFileSync(html, 'utf8'), secretos), 'utf8');
    r.evidencias.push(`newman/${nombre}.html`);
  }
  r.evidencias.push(`newman/${nombre}.json`);
  if (r._consecutivos5xx >= 3) throw Error('TRES_5XX_CONSECUTIVOS');
  return resp;
}

function escribirInforme(c, r, secretos) {
  delete r._tokens; delete r._limite; delete r._consecutivos5xx; delete r._rollback_contexto;
  delete r._ensayo;
  r.evidencias.push('resultado.json', informe(c.version));
  r.incidencias = CASOS.flatMap((caso, i) => r.casos[caso].estado === 'RECHAZADO' ? [{
    id: `INC-M04-G058-${157 + i}`, casos: [caso], titulo: `${IDS[i]}: ${r.casos[caso].motivo}`,
    requisito: i === 1 ? 'RF-69 E4/CA-6' : 'RF-69 E4/CA-5',
    pasos: 'Intento de activar y consultas posteriores del RUN', obtenido: r.casos[caso].motivo,
    severidad: /HTTP 409|Auditoría/.test(r.casos[caso].motivo) ? 'MEDIA'
      : /HTTP (422|500|502|503|504)/.test(r.casos[caso].motivo) ? 'MEDIA' : 'ALTA',
    impacto: /HTTP (422|500|502|503|504)|Auditoría/.test(r.casos[caso].motivo)
      ? 'Contrato HTTP o historial de un intento inválido afectado parcialmente'
      : 'Control de activación o estado de producción afectado',
    certeza: 'CONFIRMADA', equipo_inicial: 'Desarrollo',
    fundamento: 'Primera discrepancia comprobada en API pública', causa_raiz: 'NO DETERMINADA'
  }] : []);
  const agrupadas = new Map();
  for (const incidencia of r.incidencias) {
    const i = CASOS.indexOf(incidencia.casos[0]);
    const antes = ['RECHAZADO', 'DEPRECADO', 'ACTIVO'][i];
    const fallo = r.solicitudes.find(x => x.metodo === 'POST' && x.ruta.endsWith('/activar')
      && x.estado_antes === antes && x.http !== 409);
    const clave = fallo?.error_codigo && fallo?.http
      ? `${fallo.http}:${fallo.error_codigo}` : incidencia.id;
    if (!agrupadas.has(clave)) agrupadas.set(clave, incidencia);
    else {
      const principal = agrupadas.get(clave);
      principal.casos.push(...incidencia.casos);
      principal.titulo = `Misma respuesta API HTTP ${fallo.http} / ${fallo.error_codigo}`;
      principal.obtenido += `; ${incidencia.obtenido}`;
      principal.impacto += `; también afecta ${incidencia.casos.join(', ')}`;
      if (incidencia.severidad === 'ALTA') principal.severidad = 'ALTA';
    }
  }
  r.incidencias = [...agrupadas.values()];
  r.oficial = CASOS.every(x => ['APROBADO', 'RECHAZADO'].includes(r.casos[x].estado))
    && !r.problemas_tecnicos.length && r.cierre.run.cierre_http === 200
    && r.cierre.rollback.verificado && r.solicitudes.length === r.presupuesto_esperado
    && r.evidencias.some(x => x.endsWith('.html'))
    && r.evidencias.filter(x => !['resultado.json', informe(c.version)].includes(x))
      .every(x => fs.existsSync(path.join(c.directorio, x)));
  r.consume_version = r.oficial;
  const estados = CASOS.map(x => r.casos[x].estado);
  const decision = estados.includes('RECHAZADO') ? 'RECHAZADO'
    : estados.every(x => x === 'APROBADO') ? 'APROBADO'
      : estados.includes('BLOQUEADO') ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
  const esperados = [
    'Veterinario y Administrador deben recibir HTTP 409; la versión rechazada conserva su estado, la versión activa no cambia y no se agregan transiciones de estado',
    'La reactivación debe recibir HTTP 409; la versión deprecada conserva su estado, la versión activa no cambia y no se agregan transiciones de estado',
    'La activación repetida debe recibir HTTP 409; la versión conserva el estado ACTIVO y su condición de producción, sigue como única activa y no se duplican eventos de estado'];
  const citas = [
    'RF-69 E4, líneas 2177-2181; CA-5, líneas 2297-2300.',
    'RF-69 transiciones, líneas 1829-1833; E4, líneas 2177-2181; CA-6, líneas 2302-2305.',
    'RF-69 E4, líneas 2177-2181; CA-5, líneas 2297-2300; Fase 6, líneas 2089-2099.'];
  const registros = Object.fromEntries(['A', 'B', 'R'].map(letra => [letra,
    r.solicitudes.find(s => s.metodo === 'POST' && s.dato === letra)]));
  const idA = registros.A?.id, idB = registros.B?.id, idR = registros.R?.id;
  const version = id => id == null ? 'sin ID acreditado' : `versión ${id}`;
  const intentos = id => id == null ? [] : r.solicitudes.filter(s => s.metodo === 'POST'
    && s.ruta === `/prediccion/modelos/${id}/activar` && s.estado_antes !== 'APROBADO');
  const respuesta = s => s ? `${s.rol}: HTTP ${s.http ?? 'sin respuesta'}${s.error_codigo ? ` ${s.error_codigo}` : ''}` : 'sin intento registrado';
  const detalle = CASOS.map((caso, i) => {
    const x = r.casos[caso];
    const id = [idR, idA, idB][i];
    const envios = intentos(id);
    const inicio = envios.length ? r.solicitudes.indexOf(envios[0]) : -1;
    const fin = inicio < 0 ? -1 : r.solicitudes.findIndex((s, n) => n > inicio
      && (s.metodo === 'DELETE' || s.metodo === 'POST' && s.ruta.endsWith('/activar')
        && s.estado_antes !== 'APROBADO' && s.estado_antes !== envios[0].estado_antes));
    const segmento = inicio < 0 ? [] : r.solicitudes.slice(inicio, fin < 0 ? undefined : fin);
    const leer = target => segmento.findLast(s => s.metodo === 'GET' && s.ruta === `/prediccion/modelos/${target}`);
    const posterior = leer(id);
    const activa = leer(idB);
    const lista = segmento.find(s => s.metodo === 'GET' && s.ruta === '/prediccion/modelos?[filtro]');
    const auditorias = r.solicitudes.filter(s => s.metodo === 'GET' && s.ruta.startsWith('/prediccion/auditoria')
      && s.items?.some(y => String(y.id_referencia) === String(id)));
    const transiciones = s => s?.items?.filter(y => y.tipo_evento?.startsWith('VERSION_')).map(y => y.tipo_evento).sort().join(',') ?? null;
    const sinTransiciones = auditorias.length >= 2 && transiciones(auditorias[0]) === transiciones(auditorias.at(-1));
    const registro = registros[['R', 'A', 'B'][i]];
    const preparacion = i === 0
      ? `Se registró ${version(idR)} con F1 0.72 y recall 0.95 (HTTP ${registro?.http ?? 'sin respuesta'}, ${registro?.estado ?? 'sin estado'}, ${registro?.duracion_ms ?? 'sin duración'} ms); Veterinario y Administrador intentaron POST /prediccion/modelos/${idR ?? '{id}'}/activar. Se consultaron las versiones ${idR ?? 'sin ID'} y ${idB ?? 'sin ID'}, el listado y la auditoría.`
      : i === 1
        ? `Se activaron ${version(idA)} y después ${version(idB)}; Administrador intentó POST /prediccion/modelos/${idA ?? '{id}'}/activar cuando la primera estaba DEPRECADA. Se consultaron ambas versiones y sus auditorías.`
        : `Tras activar ${version(idB)}, Veterinario repitió POST /prediccion/modelos/${idB ?? '{id}'}/activar; se consultaron esa versión, el listado y la auditoría.`;
    const eventoIntento = i === 1 && segmento.some(s => s.items?.some(y => y.tipo_evento === 'INTENTO_ACTIVACION_INVALIDA'));
    const notaIntento = i === 1 ? eventoIntento
      ? ' El intento rechazado produjo INTENTO_ACTIVACION_INVALIDA; QA documenta el evento según FA-08.'
      : ' El intento rechazado no produjo evento propio; QA documenta su ausencia según FA-08 como observación, pues no localizó un oráculo normativo para exigirlo.' : '';
    const observadoCaso = `${envios.map(respuesta).join('; ') || 'no hubo intento'}; GET ${version(id)}: HTTP ${posterior?.http ?? 'sin lectura'}, estado ${posterior?.estado ?? 'sin estado'}${posterior?.esta_produccion != null ? `, esta_produccion ${posterior.esta_produccion}` : ''}; ${i !== 2 ? `GET ${version(idB)}: ${activa?.estado ?? 'sin estado'}; ` : ''}listado activo: ${lista ? lista.items?.map(y => y.id).join(', ') || 'sin versiones' : 'sin consulta en este caso'}; ${sinTransiciones ? 'sin transiciones nuevas' : 'transiciones no acreditadas como intactas'} al excluir HISTORIAL_CONSULTADO.${notaIntento}`;
    const codigos = envios.map(s => s.error_codigo).filter(Boolean).join(' y ');
    const motivo = x.estado === 'APROBADO'
      ? [
        `Los dos roles recibieron HTTP 409 ${codigos}; ${version(idR)} siguió RECHAZADA, ${version(idB)} siguió ACTIVA y la auditoría no añadió transiciones de estado.`,
        `El intento recibió HTTP 409 ${codigos}; ${version(idA)} siguió DEPRECADA, ${version(idB)} siguió ACTIVA y no hubo transiciones nuevas. ${eventoIntento ? 'El evento INTENTO_ACTIVACION_INVALIDA quedó documentado.' : 'La ausencia de evento del intento queda como observación por la decisión QA sobre FA-08.'}`,
        `La repetición recibió HTTP 409 ${codigos}; ${version(idB)} siguió ACTIVA y en producción, fue la única activa del tipo y no se duplicaron eventos de estado.`][i]
      : x.estado === 'RECHAZADO'
        ? `El criterio de ${['rechazo por ambos roles, estados intactos y auditoría', 'rechazo de reactivación, estados intactos y auditoría', 'rechazo de repetición, producción intacta y auditoría'][i]} se incumplió: ${corto(x.motivo)}. Incidencia ${r.incidencias.find(y => y.casos.includes(caso))?.id ?? 'pendiente de asignar'}.`
        : `No pudo acreditarse el criterio de ${['ambos roles, estados y auditoría', 'reactivación, estados y auditoría', 'repetición, producción y auditoría'][i]}: ${corto(x.motivo)}.`;
    return `### ${caso} — ${x.estado}\n\n**Qué se hizo:** ${preparacion}\n**Qué se esperaba:** ${esperados[i]}; ${citas[i]}\n**Qué se observó:** ${observadoCaso}\n**Por qué ${x.estado}:** ${motivo}`;
  }).join('\n\n');
  const solicitudes = r.solicitudes.map(x => `| ${x.rol} | ${x.metodo} ${corto(x.ruta)}${x.dato ? ` ${x.dato}` : ''} | ${x.http ?? 'sin respuesta'} | ${x.estado_antes ?? '—'} | ${x.estado ?? '—'} | ${x.items?.map(y => `${y.tipo_evento ?? y.estado}:${y.id ?? y.id_referencia}`).join(', ') ?? '—'} | ${x.duracion_ms ?? '—'} |`).join('\n');
  const motivosClaros = detalle.split(/\n\n### /).map(s => s.match(/\*\*Por qué [^:]+:\*\* (.+)/)?.[1] ?? '');
  const breve = CASOS.map((caso, i) => `| ${caso} | ${IDS[i]} | ${r.casos[caso].estado} | ${corto(motivosClaros[i])} |`).join('\n');
  const observado = CASOS.map((caso, i) => `| ${caso} | ${esperados[i]} | ${r.casos[caso].estado}: ${corto(r.casos[caso].motivo.replace(/\b[ABR] (?=\d)/g, 'versión ').replace('listado={B}', `listado activo: versión ${idB ?? 'sin ID'}`))} |`).join('\n');
  const resumenDecision = decision === 'APROBADO'
    ? `Activar una versión que no está APROBADA respondió siempre HTTP 409 sin cambiar estados: la ${idB} ACTIVA, la ${idA} DEPRECADA y la ${idR} RECHAZADA (con ambos roles) siguieron igual y la ${idB} continuó como única ACTIVA de MODELO_ESPECIES_GRANDES.`
    : CASOS.map((caso, i) => `${caso} ${r.casos[caso].estado}: ${corto(motivosClaros[i])}`).join(' ');
  const pendiente = r.oficial && r.ambiente === 'TEST' ? 'nada para este grupo'
    : 'evaluar o reintentar en TEST con autorización particular; confirmar cierre y rollback si faltan';
  const incidencias = r.incidencias.map(x => `### ${x.id}\n\n${x.titulo}. Casos ${x.casos.join(', ')}. Requisito ${x.requisito}. Pasos: ${x.pasos}. Obtenido: ${x.obtenido}. Severidad ${x.severidad} por ${x.impacto}; certeza ${x.certeza}; equipo inicial ${x.equipo_inicial} por ${x.fundamento}; causa raíz ${x.causa_raiz}.`).join('\n\n') || 'Sin incidencias de producto confirmadas.';
  const historialPrevio = c.version === 1 && c.intento >= 2
    ? '### Intento 1 — RUN-G058-V1-20261028-143302\n\n'
      + 'Exit 2, EJECUCION_POST_PREFLIGHT; registro QA TÉCNICO y V1 ABIERTA. '
      + 'A 101 y B 102: HTTP 201 APROBADO; R 103: HTTP 200 RECHAZADO con eco e ID, '
      + '34,9 s y correo síncrono enviado. Preparación: A DEPRECADO y B ACTIVO (HTTP 200). '
      + 'TC-M04-159: activar 102 devolvió 409 VERSION_NO_APROBADA; B siguió ACTIVO, '
      + 'sin eventos nuevos: APROBADO. TC-M04-158: activar 101 devolvió 409 '
      + 'TRANSICION_ESTADO_INVALIDA; A siguió DEPRECADO, B intacta y sin evento del '
      + 'intento observado: APROBADO. TC-M04-157: NO_CONCLUYENTE por clasificación '
      + 'técnica de R como ambigua; no se envió POST /103/activar, aunque GET posterior '
      + 'confirmó RECHAZADO. Causa técnica: el ejecutor exigía 201 a los tres registros '
      + 'y el ensayo respondía 201 a todos. DELETE HTTP 200; rollback NO_VERIFICADO. '
      + 'Evidencia nativa eliminada por decisión del responsable QA el 2026-10-28; '
      + 'este párrafo conserva la transcripción del intento 1.\n\n' : '';
  const md = `# TC-M04-G058 — ${decision}\n\nGrupo G058; casos ${CASOS.join(', ')}; RF-69 v2.1; V${c.version}; RUN ${c.runId}; ambiente ${r.ambiente}; autorización ${corto(c.referencia)}; código consultado origin/test daefc3a5 (despliegue no verificado); Newman ${r.herramientas.newman.version ?? 'no disponible'}; Cypress no aplica (0).\n\n`+
    `## Decisión del caso\n\nAgrupado **TC-M04-G058 (RF-69)**; originales **${CASOS.join(', ')}**.\n\n**Decisión: ${decision}.** ${resumenDecision}\n\n| Caso | Comprobación | Decisión | Motivo breve |\n|---|---|---|---|\n${breve}\n\n**RUN oficial: ${r.oficial && r.ambiente === 'TEST' ? 'sí' : 'no'}.** **Qué falta: ${pendiente}.**\n\n`+
    `## Detalle por caso\n\n${detalle}\n\n## Esperado y observado\n\n| Caso | Esperado | Observado |\n|---|---|---|\n${observado}\n\n`+
    `## Solicitudes API\n\n| Rol | Operación | HTTP | Estado antes | Estado después | Eventos/items | Duración ms |\n|---|---|---:|---|---|---|---:|\n${solicitudes}\n\n`+
    `## Observaciones\n\n${r.observaciones.map(x => '- ' + corto(x)).join('\n') || 'Sin observaciones.'}\n\n`+
    `## Incidencias de producto\n\n${incidencias}\n\n## Problemas técnicos\n\n${r.problemas_tecnicos.map(x => '- ' + corto(x)).join('\n') || 'Sin problemas técnicos.'}\n\n`+
    `## Historial de intentos, cierre y rollback\n\n${historialPrevio}Operación ${c.operacion}; intento ${c.intento}; ${r.solicitudes.length} solicitudes. DELETE HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. Rollback ${r.cierre.rollback.verificado ? 'comprobado por API' : 'NO_VERIFICADO'}: ${r.cierre.rollback.motivo}. Tres ONNX y posible respaldo RF-73 no quedan cubiertos por DELETE; el aviso por correo a cada usuario activo con permiso 43/3 es irreversible.\n\n`+
    `## Evidencias\n\n${r.evidencias.map(x => '- ' + x).join('\n')}\n\n## Conclusión y acción\n\n${r.oficial ? 'Entregar al registro QA y revisar incidencias y efectos persistentes.' : 'Resolver el impedimento y decidir un reintento autorizado.'}\n`;
  fs.writeFileSync(path.join(c.directorio, informe(c.version)), sanearArtefacto(md, secretos), 'utf8');
  guardar(path.join(c.directorio, 'resultado.json'), r, secretos);
}

export async function evaluar(c, { env, ensayo = false }) {
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G058', run_id: c.runId, version: c.version, intento: c.intento ?? null,
    operacion: c.operacion, autorizacion: c.referencia, ambiente: ensayo ? 'LOOPBACK_LOCAL' : 'TEST',
    oficial: false, consume_version: false,
    casos: Object.fromEntries(CASOS.map(x => [x, { estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación' }])),
    comprobaciones: CASOS.map((caso, i) => ({ caso, fuente: 'API', id: IDS[i], tipo: 'ASSERT',
      estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación', evidencia: null })),
    presupuesto: PRESUPUESTO, herramientas: { newman: versionNewman() }, solicitudes: [],
    cypress: { total_pruebas: 0 }, evidencias: [], incidencias: [], problemas_tecnicos: [],
    observaciones: [], cierre: { run: { cierre_http: null }, rollback: { verificado: false,
      motivo: 'Sin cierre ni verificación posterior' } }, _tokens: {},
    _limite: Date.now() + PRESUPUESTO.duracion_segundos * 1000, _consecutivos5xx: 0,
    _ensayo: ensayo };
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
      const x = await pedir(r, api, 'POST', '/sesiones/', { cuerpo: { correo_electronico: email,
        contrasena: pass }, rol, timeout: ensayo ? 1200 : PRESUPUESTO.timeout_post_ms });
      if (x.http !== 200 || !x.cuerpo?.token) {
        const f = r.solicitudes.at(-1);
        throw Error(x.http == null ? `LOGIN_${rol.toUpperCase()}_SIN_RESPUESTA_${f.tipo_fallo}`
          : `LOGIN_${rol.toUpperCase()}_NO_VERIFICABLE_HTTP_${x.http}`);
      }
      r._tokens[rol] = x.cuerpo.token; secretos.push(x.cuerpo.token);
    }
    tocado = true;
    const opts = (rol, token) => ({ rol, token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId });
    const admin = opts('Administrador', r._tokens.admin), vet = opts('Veterinario', r._tokens.vet);
    const catalogo = await pedir(r, api, 'GET', '/configuracion/variables-ambientales', admin);
    const variables = catalogo.cuerpo?.items?.map(x => x.id_variable_ambiental).filter(Number.isSafeInteger) ?? [];
    if (catalogo.http !== 200 || !catalogo.eco || !variables.length)
      throw Error(`CATALOGO_I3P1_NO_VERIFICABLE_HTTP_${catalogo.http}`);
    const inicial = await pedir(r, api, 'GET',
      `/prediccion/modelos?tipo_modelo=${TIPO}&estado=ACTIVO&limit=100&offset=0`, admin);
    if (inicial.http !== 200 || !inicial.eco || !Array.isArray(inicial.cuerpo?.items)
      || inicial.cuerpo.total !== inicial.cuerpo.items.length)
      throw Error(`ACTIVOS_INICIALES_NO_VERIFICABLES_HTTP_${inicial.http}`);
    temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g058-newman-'));
    const archivo = path.join(temporal, 'g058.onnx'); fs.writeFileSync(archivo, onnxMinimo());
    const datos = escenarios({ variable: variables[0], hash: sha256(fs.readFileSync(archivo)),
      dataset: sha256(Buffer.from('G058 dataset QA RF-71')), archivo });
    const post = [];
    for (const dato of datos) {
      const x = await registrarNewman(r, c, api, env, dato, temporal, secretos);
      post.push(x);
      if (x.http === 403 || x.http == null) break;
    }
    if (post.some(x => x.http === 403)) throw Error('POST_403_CLAVE');
    if (post.some(x => x.http == null)) {
      const conciliacion = await pedir(r, api, 'GET',
        `/prediccion/modelos?tipo_modelo=${TIPO}&limit=100&offset=0`, admin);
      r.observaciones.push(`Registro sin respuesta: conciliación por listado HTTP ${conciliacion.http}; ID no inequívoco`);
      throw Error('POST_SIN_RESPUESTA; ID no conciliado');
    }
    const ids = post.map(x => idVersion(x.cuerpo));
    const registrosValidos = post.map((x, i) => registroValido(x, i === 2 ? 'RECHAZADO' : 'APROBADO'));
    if (post.length !== 3) throw Error('REGISTROS_INCOMPLETOS');
    if (registrosValidos[2] && post[2].http === 201)
      r.observaciones.push('Registro R RECHAZADO respondió HTTP 201 en vez del 200 de RF-69 E3; estado, ID y eco acreditados; se continúa con 157');
    if (registrosValidos.some(x => !x)) r.observaciones.push('Un registro no acreditó el estado esperado; continúan casos independientes');
    r._rollback_contexto = { ids: ids.filter(id => id != null), tipo: TIPO,
      activos_antes: inicial.cuerpo.items.map(idVersion).sort((a, b) => a - b) };
    const base = id => `/prediccion/modelos/${id}`;
    const notasA = registrosValidos[0] ? await pedir(r, api, 'PATCH', `${base(ids[0])}/notas`, { ...vet,
      cuerpo: { notas_validacion: `G058 ${c.runId} Veterinario nota clínica A` }, estadoAntes: 'APROBADO' }) : null;
    const notasB = registrosValidos[1] ? await pedir(r, api, 'PATCH', `${base(ids[1])}/notas`, { ...admin,
      cuerpo: { notas_validacion: `G058 ${c.runId} Administrador nota clínica B` }, estadoAntes: 'APROBADO' }) : null;
    const activar = (id, cred, antes) => pedir(r, api, 'POST', `${base(id)}/activar`,
      { ...cred, estadoAntes: antes });
    const get = (id, cred = admin) => id == null ? null : pedir(r, api, 'GET', base(id), cred);
    const listar = () => pedir(r, api, 'GET',
      `/prediccion/modelos?tipo_modelo=${TIPO}&estado=ACTIVO&limit=100&offset=0`, admin);
    const auditoria = id => id == null ? null
      : pedir(r, api, 'GET', `/prediccion/auditoria?id_referencia=${id}&por_pagina=200`, admin);
    const aAct = notasA?.http === 200 && notasA.eco ? await activar(ids[0], vet, 'APROBADO') : null;
    const bAct = notasB?.http === 200 && notasB.eco ? await activar(ids[1], admin, 'APROBADO') : null;
    const estadoA = await get(ids[0]), estadoB = await get(ids[1]);
    const preparada = { A: aAct?.http === 200 && aAct.eco
      && estadoA.http === 200 && estadoA.eco && estadoA.cuerpo?.estado_version === 'DEPRECADO'
      && estadoA.cuerpo?.esta_produccion === false,
    B: bAct?.http === 200 && bAct.eco && estadoB.http === 200 && estadoB.eco
      && estadoB.cuerpo?.estado_version === 'ACTIVO' && estadoB.cuerpo?.esta_produccion === true,
    R: registrosValidos[2] };
    const aud = { Aantes: await auditoria(ids[0]), Bantes: await auditoria(ids[1]),
      Rantes: await auditoria(ids[2]) };
    const intentos = {};
    const listaActiva = {};
    intentos.B = preparada.B ? await activar(ids[1], vet, 'ACTIVO') : null;
    const get159 = { B159: await get(ids[1]) };
    listaActiva.B = await listar();
    aud.B159 = await auditoria(ids[1]);
    intentos.A = preparada.A ? await activar(ids[0], admin, 'DEPRECADO') : null;
    const get158 = { A158: await get(ids[0]), B158: await get(ids[1]) };
    aud.Aintermedia = await auditoria(ids[0]); aud.B158 = await auditoria(ids[1]);
    const idActiva = get158.A158?.cuerpo?.estado_version === 'ACTIVO' ? ids[0]
      : get158.B158?.cuerpo?.estado_version === 'ACTIVO' ? ids[1] : null;
    r.presupuesto_esperado = PRESUPUESTO.total - (idActiva == null ? 2 : 0);
    const activaAntes = idActiva == null ? null : await get(idActiva);
    if (idActiva == null) r.observaciones.push('157: no había versión ACTIVO antes de los intentos sobre R; solo se comprueba R');
    intentos.Rvet = registrosValidos[2] ? await activar(ids[2], vet, 'RECHAZADO') : null;
    intentos.Radmin = registrosValidos[2] ? await activar(ids[2], admin, 'RECHAZADO') : null;
    const activaDespues = idActiva == null ? null : await get(idActiva);
    const get157 = { R157: await get(ids[2]), ActivaAntes157: activaAntes,
      ActivaDespues157: activaDespues };
    listaActiva.R = await listar();
    aud.Rdespues = await auditoria(ids[2]);
    const resultados = evaluarInstantanea({ ids, intentos, get: { ...get157, ...get158, ...get159 },
      listaActiva, aud, preparada, observaciones: r.observaciones });
    resultados.forEach((x, i) => poner(i, x));
    if (!preparada.A || !preparada.B) r.observaciones.push('Activación de preparación fallida; casos dependientes NO_CONCLUYENTES');
    if (registrosValidos.every(Boolean) && preparada.A && preparada.B
      && intentos.A && intentos.B && intentos.Rvet && intentos.Radmin
      && r.solicitudes.length !== r.presupuesto_esperado - 1 - PRESUPUESTO.comprobacion_rollback)
      r.problemas_tecnicos.push(`Presupuesto antes de cierre ${r.solicitudes.length}/${r.presupuesto_esperado - 1 - PRESUPUESTO.comprobacion_rollback}`);
  } catch (e) {
    const motivo = corto(e.message); r.problemas_tecnicos.push(motivo);
    const estado = /403|5XX|LOGIN|CATALOGO|REGISTRO_ESTADOS/.test(motivo) ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
    CASOS.forEach((caso, i) => { if (r.casos[caso].motivo === 'Sin comprobación') poner(i, { estado, motivo }); });
  } finally {
    if (tocado) {
      const x = await pedir(r, api, 'DELETE', `/test-control/runs/${encodeURIComponent(c.runId)}`,
        { secreto: env.QA_SANDBOX_SECRET, rol: 'Sistema' });
      r.cierre.run.cierre_http = x.http;
      r.cierre.rollback.motivo = `DELETE HTTP ${x.http}; rollback pendiente de comprobación`;
      if (x.http === 200 && r._rollback_contexto) {
        const checks = [];
        for (const id of r._rollback_contexto.ids) checks.push(await pedir(r, api, 'GET',
          `/prediccion/modelos/${id}`, { token: r._tokens.admin, rol: 'Administrador poscierre' }));
        const activos = await pedir(r, api, 'GET',
          `/prediccion/modelos?tipo_modelo=${TIPO}&estado=ACTIVO&limit=100&offset=0`,
          { token: r._tokens.admin, rol: 'Administrador poscierre' });
        const idsActivos = (activos.cuerpo?.items ?? []).map(idVersion).sort((a, b) => a - b);
        const idsRun = new Set(r._rollback_contexto.ids.map(String));
        r.cierre.rollback.verificado = checks.length === 3
          && idsRun.size === 3
          && checks.every(y => y.http === 404) && activos.http === 200
          && activos.cuerpo?.total === idsActivos.length
          && !idsActivos.some(id => idsRun.has(String(id)))
          && JSON.stringify(idsActivos) === JSON.stringify(r._rollback_contexto.activos_antes);
        r.cierre.rollback.motivo = r.cierre.rollback.verificado
          ? `GET poscierre: ${checks.length} versiones HTTP 404; listado ACTIVO restaurado`
          : `GET poscierre: ${checks.length}/3 versiones ${checks.map(y => y.http).join('/')}; listado HTTP ${activos.http}; rollback no acreditado`;
      }
    }
    if (temporal) {
      if (!path.resolve(temporal).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
      fs.rmSync(temporal, { recursive: true, force: true });
    }
    escribirInforme(c, r, secretos);
  }
  return r;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
  else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
  else try {
    const c = contextoEjecucion(process.argv.slice(2), { grupo: 'G058', casos: CASOS, directorio: DIR });
    const r = await evaluar(c, { env: leerEnv() });
    console.log(JSON.stringify({ run_id: r.run_id, casos: r.casos, oficial: r.oficial }));
    if (!r.oficial) process.exitCode = 2;
  } catch (e) { console.error(`G058: ${corto(e.message)}`); process.exitCode = 2; }
}
