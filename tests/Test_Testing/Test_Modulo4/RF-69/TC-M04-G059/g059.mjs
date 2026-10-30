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
import { CASOS, IDS, PRESUPUESTO, CAPACIDADES, COMBINACIONES, TIPO, escenarios,
  idVersion, registroValido, estado, listaUnica, mismosEventos, eventosEstado } from './lib/g059_escenario.mjs';

const require = createRequire(import.meta.url);
const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION = path.join(DIR, 'G059.postman_collection.json');
const ARCHIVOS = ['.gitkeep', 'g059.mjs', 'G059.postman_collection.json', 'README.md',
  'lib/seguridad.mjs', 'lib/artefactos.mjs', 'lib/contrato_ejecutor.mjs',
  'lib/g059_escenario.mjs', 'pruebas/g059_env.test.mjs', 'pruebas/g059_ensayo.mjs',
  'pruebas/registro_qa.mjs'];
const corto = x => String(x ?? '').replaceAll('|', '/').replace(/[\r\n]+/g, ' ').slice(0, 350);
const informe = v => v === 1 ? 'TC-M04-G059_resultado.md' : `TC-M04-G059_reevaluacion_V${v}.md`;
const guardar = (archivo, valor, secretos) => fs.writeFileSync(archivo,
  sanearArtefacto(JSON.stringify(valor), secretos), 'utf8');
const ruta = id => `/prediccion/modelos/${id}`;

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
    coleccion = c.item.length === 1 && c.item[0].name === 'API-G059-POST'
      && c.item[0].request.method === 'POST' && !contieneMojibake(JSON.stringify(c));
  } catch { /* comprobación estructural */ }
  const faltantes = ARCHIVOS.filter(x => !fs.existsSync(path.join(DIR, x)));
  const presentes = fs.readdirSync(DIR).filter(x => !['lib', 'pruebas', 'Resultados', 'EvaluacionV2'].includes(x))
    .concat(...['lib', 'pruebas'].map(d => fs.existsSync(path.join(DIR, d))
      ? fs.readdirSync(path.join(DIR, d)).map(x => `${d}/${x}`) : []));
  const inesperados = presentes.filter(x => !ARCHIVOS.includes(x));
  const markdownSuperior = fs.existsSync(path.join(DIR, 'Resultados'))
    && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const ok = coleccion && !faltantes.length && !inesperados.length && !markdownSuperior
    && COMBINACIONES.length === 14 && versionNewman().ok;
  console.log(JSON.stringify({ grupo: 'G059', ok, coleccion, faltantes, inesperados,
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
  return { grupo: 'G059', run_id: c.runId, ok: !barreras.length, barreras,
    presupuesto: PRESUPUESTO, herramientas: { newman: versionNewman() },
    efectos_declarados: ['4_versiones_BD_sandbox_mas_1_si_reenvio_crea', '4_notas_2_activaciones',
      'intentos_rechazados_historial_auditoria_BD_sandbox', '4_o_5_ONNX_fuera_rollback',
      'respaldo_RF73_posible', 'correo_por_R_RECHAZADA_a_permiso_43_3',
      'sin_OTA_MQTT_Edge', '2_logins_previos_posible_sesion_o_auditoria'] };
}
function resumen(x) {
  const b = x?.cuerpo ?? {};
  return { http: x?.http ?? null, eco: x?.eco ?? null, id: idVersion(b),
    estado: b.estado_version ?? null, esta_produccion: b.esta_produccion ?? null,
    f1: b.f1_score ?? null, recall: b.recall_clase_riesgo_alto ?? null,
    detalle: b.detalle_validacion ?? null, total: b.total ?? null,
    items: Array.isArray(b.items) ? b.items.map(y => ({ id: idVersion(y),
      estado: y.estado_version ?? null, tipo_modelo: y.tipo_modelo ?? null,
      tipo_evento: y.tipo_evento ?? null, id_referencia: y.id_referencia ?? null,
      correlacion_id: y.correlacion_id ?? null })) : null,
    error_codigo: b.error_code ?? b.code ?? b.codigo ?? null,
    duracion_ms: x?.duracion_ms ?? null };
}
async function pedir(r, api, metodo, endpoint, { token, secreto, runId, cuerpo,
  rol = 'Sistema', caso = null, destino = null, timeout = PRESUPUESTO.timeout_ms } = {}) {
  const fila = { rol, caso, metodo, ruta: endpoint.replace(/\?.*/, '?[filtro]'), destino, http: null };
  r.solicitudes.push(fila);
  const ini = Date.now();
  try {
    if (Date.now() >= r._limite) throw Error('LIMITE_900_SEGUNDOS');
    const x = await fetch(api + endpoint, { method: metodo, redirect: 'manual',
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
    timeoutRequest: c.ensayo ? 1500 : PRESUPUESTO.timeout_login_registro_ms,
    timeout: Math.max(1, Math.min(PRESUPUESTO.timeout_login_registro_ms + 5000, r._limite - Date.now())),
    color: 'off' }, () => resolve()));
  const original = fs.existsSync(raw) ? JSON.parse(fs.readFileSync(raw, 'utf8')) : {};
  const ex = original.run?.executions?.[0];
  let cuerpo = null;
  try { cuerpo = JSON.parse(Buffer.from(ex?.response?.stream?.data ?? []).toString('utf8')); }
  catch { /* respuesta no JSON */ }
  const resp = { http: ex?.response?.code ?? null, cuerpo,
    eco: ex?.response?.header?.find(h => String(h.key).toLowerCase() === 'x-test-run-id')?.value === c.runId,
    duracion_ms: Date.now() - ini };
  r.solicitudes.push({ rol: 'RF-71 interno', caso: null, metodo: 'POST', ruta: '/prediccion/modelos',
    dato: dato.dato, ...resumen(resp) });
  r._consecutivos5xx = resp.http >= 500 ? r._consecutivos5xx + 1 : 0;
  const sub = path.join(c.directorio, 'newman'); fs.mkdirSync(sub, { recursive: true });
  const nombre = `newman-G059-${dato.dato}`;
  guardar(path.join(sub, nombre + '.json'), { info: { nombre, saneado: true, generado: !!ex },
    run: { stats: original.run?.stats ?? null, executions: [resumen(resp)],
      failures: (original.run?.failures ?? []).map(f => ({ name: corto(f.error?.name),
        message: corto(f.error?.message) })) } }, secretos);
  r.evidencias.push(`newman/${nombre}.json`);
  if (fs.existsSync(html)) {
    fs.writeFileSync(path.join(sub, nombre + '.html'),
      sanearArtefacto(fs.readFileSync(html, 'utf8'), secretos), 'utf8');
    r.evidencias.push(`newman/${nombre}.html`);
  }
  if (r._consecutivos5xx >= 3) throw Error('TRES_5XX_CONSECUTIVOS');
  return resp;
}

function clasificarIntento(x, lectura, esperado, nombre, { activar = false } = {}) {
  if (!x || x.http == null || !lectura || lectura.http == null)
    return { estado: 'NO_CONCLUYENTE', motivo: `${nombre}: sin respuesta o sin GET posterior` };
  if (x.http === 403 || lectura.http === 403)
    return { estado: 'BLOQUEADO', motivo: `${nombre}: HTTP 403` };
  if (!estado(lectura, esperado))
    return { estado: 'RECHAZADO', motivo: `${nombre}: estado posterior ${lectura.cuerpo?.estado_version ?? 'desconocido'}; esperado ${esperado}` };
  if (x.http >= 500 || lectura.http >= 500)
    return { estado: 'RECHAZADO', motivo: `${nombre}: HTTP ${x.http}/${lectura.http}` };
  if (activar ? x.http !== 409 : x.http < 200 || x.http >= 300 && x.http < 400 || x.http >= 500)
    return { estado: 'RECHAZADO', motivo: `${nombre}: HTTP ${x.http}${activar ? '; esperado 409' : ''}` };
  if (x.http >= 200 && x.http < 300 && !activar)
    return { estado: 'APROBADO', motivo: `${nombre}: HTTP ${x.http}, estado intacto; respuesta 2xx observada` };
  return { estado: 'APROBADO', motivo: `${nombre}: HTTP ${x.http}, ${esperado} intacto` };
}
const agregar = (fallos, valor, observaciones) => {
  if (!valor) return;
  if (valor.estado === 'APROBADO') { if (valor.motivo.includes('observada')) observaciones.push(valor.motivo); }
  else fallos.push(valor);
};
const decidir = (fallos, conforme) => fallos.find(x => x.estado === 'BLOQUEADO')
  ?? fallos.find(x => x.estado === 'NO_CONCLUYENTE') ?? fallos[0]
  ?? { estado: 'APROBADO', motivo: conforme };
const invalidado = (x, motivo) => ({ estado: 'NO_CONCLUYENTE', motivo: `${motivo}: HTTP ${x?.http ?? 'sin respuesta'}` });
const metricasR = x => JSON.stringify([
  x?.cuerpo?.f1_score, x?.cuerpo?.recall_clase_riesgo_alto,
  x?.cuerpo?.precision_modelo, x?.cuerpo?.accuracy, x?.cuerpo?.roc_auc_score,
  x?.cuerpo?.detalle_validacion, x?.cuerpo?.metricas_poblacionales]);

export function detalleYCombinaciones(r) {
  const ids = r.versiones ?? {};
  const solicitudes = caso => r.solicitudes.filter(s => s.caso === caso);
  const buscar = (ss, metodo, ruta) => ss.find(s => s.metodo === metodo && s.ruta === ruta);
  const ultima = (ss, ruta) => ss.filter(s => s.metodo === 'GET' && s.ruta === ruta).at(-1);
  const respuesta = s => s ? `HTTP ${s.http ?? 'sin respuesta'}${s.error_codigo ? ` ${s.error_codigo}` : ''}` : 'sin intento registrado';
  const estadoLeido = s => s?.http === 200 ? `${s.estado ?? 'sin estado'}${s.esta_produccion == null ? '' : ` (esta_produccion=${s.esta_produccion})`}` : 'sin lectura concluyente';
  const cambios = (ss, id) => {
    const intentos = ss.filter(s => ['PUT', 'PATCH'].includes(s.metodo) && s.ruta === ruta(id));
    if (!intentos.length) return 'no hubo intentos PUT/PATCH';
    const grupos = new Map();
    for (const s of intentos) grupos.set(respuesta(s), (grupos.get(respuesta(s)) ?? 0) + 1);
    return `los ${intentos.length} intentos PUT/PATCH respondieron ${[...grupos].map(([codigo, n]) => `${codigo}${grupos.size > 1 ? ` (${n})` : ''}`).join(' y ')}`;
  };
  const idActivo = Number(solicitudes('TC-M04-162').find(s => /\/prediccion\/modelos\/\d+/.test(s.ruta))?.ruta.match(/\/prediccion\/modelos\/(\d+)/)?.[1]) || ids.V2;
  const datos = [
    { n: 161, id: ids.V3, version: 'V3', esperado: 'La versión V3 debe conservar APROBADO; no debe pasar a RECHAZADO, DEPRECADO ni EN_VALIDACION; RF-69 v2.1, líneas 1822-1833 y 1887-1888.',
      hizo: id => `El Administrador envió una nota a la versión ${id} con el campo estado_version no declarado en PATCH ${ruta(id)}/notas; después intentó llevarla a RECHAZADO, DEPRECADO y EN_VALIDACION mediante PUT y PATCH sobre ${ruta(id)}, y consultó la versión tras los intentos.`,
      observo: (ss, id) => `La nota respondió ${respuesta(buscar(ss, 'PATCH', `${ruta(id)}/notas`))}; ${cambios(ss, id)}; las lecturas posteriores mostraron la ${id} en ${estadoLeido(ultima(ss, ruta(id)))}.`,
      porque: id => `El campo no declarado no cambió el estado; ninguno de los tres destinos se alcanzó y la versión ${id} conservó APROBADO. La activación sigue siendo la salida prevista para una versión aprobada.` },
    { n: 162, id: idActivo, version: idActivo === ids.V2 ? 'V2' : idActivo === ids.V1 ? 'V1' : 'versión', esperado: 'La versión activa debe conservar ACTIVO y esta_produccion=true y ser la única ACTIVO de su tipo; RF-69 v2.1, líneas 1822-1833, 1839 y 2307-2311.',
      hizo: id => `El Administrador envió a la versión ${id} una nota con el campo estado_version no declarado en PATCH ${ruta(id)}/notas; intentó pasarla a APROBADO, RECHAZADO y EN_VALIDACION con PUT y PATCH sobre ${ruta(id)}, y consultó la versión y el listado de activas.`,
      observo: (ss, id) => `La nota respondió ${respuesta(buscar(ss, 'PATCH', `${ruta(id)}/notas`))}; ${cambios(ss, id)}; la lectura final mostró ${estadoLeido(ultima(ss, ruta(id)))} y el listado devolvió ${ultima(ss, '/prediccion/modelos?[filtro]')?.total ?? 'sin total'} versión activa.`,
      porque: id => `El campo no declarado fue rechazado, los tres cambios propuestos no alteraron a la ${id} y la lectura y el listado confirmaron que seguía en producción como única ACTIVO del tipo.` },
    { n: 163, id: ids.V1, version: 'V1', esperado: 'V1 debe conservar DEPRECADO; la reactivación debe responder HTTP 409; el criterio menciona describir el intento auditado; RF-69 v2.1, líneas 1817-1833, 2177-2181 y 2302-2305.',
      hizo: id => `El Administrador envió a la versión ${id} una nota con el campo estado_version no declarado en PATCH ${ruta(id)}/notas; intentó pasarla a APROBADO, ACTIVO, RECHAZADO y EN_VALIDACION con PUT y PATCH, probó POST ${ruta(id)}/activar y consultó la versión y su auditoría.`,
      observo: (ss, id) => `La nota respondió ${respuesta(buscar(ss, 'PATCH', `${ruta(id)}/notas`))}; ${cambios(ss, id)}; /activar respondió ${respuesta(buscar(ss, 'POST', `${ruta(id)}/activar`))}; la lectura final mostró ${estadoLeido(ultima(ss, ruta(id)))}. ${r.observaciones.some(x => x.startsWith('163: sin evento')) ? 'No apareció un evento del intento inválido en la auditoría.' : 'El resultado de auditoría consta en las solicitudes del caso.'}`,
      porque: id => `La versión ${id} permaneció DEPRECADO y la reactivación fue rechazada con HTTP 409. ${r.observaciones.some(x => x.startsWith('163: sin evento')) ? 'La ausencia del evento del intento se registró como observación por la decisión QA sobre FA-08.' : 'La auditoría se revisó como parte del caso.'}` },
    { n: 164, id: ids.R, version: 'R', esperado: 'La versión rechazada debe conservar RECHAZADO, métricas y detalle; su activación debe responder HTTP 409; RF-69 v2.1, líneas 1819-1833, 2177-2181 y 2302-2305.',
      hizo: id => `Con la versión ${id} RECHAZADA (f1 ${solicitudes('TC-M04-164').find(s => s.metodo === 'GET' && s.ruta === ruta(id))?.f1 ?? 'sin lectura'}), el Administrador envió una nota con estado_version no declarado en PATCH ${ruta(id)}/notas, intentó llevarla a APROBADO, ACTIVO, DEPRECADO y EN_VALIDACION mediante PUT y PATCH, y probó POST ${ruta(id)}/activar. RF-71 interno reenvió el registro con el mismo id_proceso_rf71 y la métrica f1 corregida.`,
      observo: (ss, id) => { const lecturas = ss.filter(s => s.metodo === 'GET' && s.ruta === ruta(id));
        const primera = lecturas[0], final = lecturas.at(-1);
        const iguales = primera && final && JSON.stringify([primera.f1, primera.recall, primera.detalle]) === JSON.stringify([final.f1, final.recall, final.detalle]);
        return `La nota respondió ${respuesta(buscar(ss, 'PATCH', `${ruta(id)}/notas`))}; ${cambios(ss, id)}; /activar respondió ${respuesta(buscar(ss, 'POST', `${ruta(id)}/activar`))}; el reenvío respondió ${respuesta(buscar(ss, 'POST', '/prediccion/modelos'))}; la lectura final mostró ${estadoLeido(final)}${iguales ? ', con las mismas métricas y detalle registrados' : ', con métricas y detalle por revisar en las lecturas'}.`; },
      porque: id => `El campo no declarado no cambió el estado; los cuatro destinos y la activación fueron rechazados, el reenvío no reevaluó a la ${id}, y sus métricas y detalle permanecieron iguales.` },
    { n: 165, id: ids.V1, version: 'V1', esperado: 'V1 solo debe pasar a DEPRECADO al activar V2; V2 debe quedar como única ACTIVO; RF-69 v2.1, líneas 1827-1833, 2070-2087, 2183-2192 y 2307-2311.',
      hizo: id => `El Veterinario había activado la versión ${id}. El Administrador envió a esa versión una nota con estado_version no declarado en PATCH ${ruta(id)}/notas, intentó deprecarla directamente con POST ${ruta(id)}/deprecar y PATCH ${ruta(id)}/estado, y luego activó la versión ${ids.V2} con POST ${ruta(ids.V2)}/activar; consultó ambas versiones, el listado y la auditoría.`,
      observo: (ss, id) => `La nota respondió ${respuesta(buscar(ss, 'PATCH', `${ruta(id)}/notas`))}; /deprecar respondió ${respuesta(buscar(ss, 'POST', `${ruta(id)}/deprecar`))} y /estado ${respuesta(buscar(ss, 'PATCH', `${ruta(id)}/estado`))}; las lecturas previas mantuvieron la ${id} en ${estadoLeido(ss.filter(s => s.metodo === 'GET' && s.ruta === ruta(id)).at(-2))}. La activación de ${ids.V2} respondió ${respuesta(buscar(ss, 'POST', `${ruta(ids.V2)}/activar`))}; después, ${id} quedó ${estadoLeido(ultima(ss, ruta(id)))} y ${ids.V2} ${estadoLeido(ultima(ss, ruta(ids.V2)))}, con ${ultima(ss, '/prediccion/modelos?[filtro]')?.total ?? 'sin total'} versión activa en el listado.`,
      porque: id => `El campo no declarado y las dos vías directas no deprecaron a la ${id}; solo la activación de ${ids.V2} la llevó a DEPRECADO, dejó a ${ids.V2} como única ACTIVO y produjo el evento de deprecación verificado en la auditoría.` }
  ];
  const detalles = datos.map(d => {
    const caso = `TC-M04-${d.n}`, x = r.casos[caso], ss = solicitudes(caso);
    const motivo = x.estado === 'APROBADO' ? d.porque(d.id) : `La comprobación no satisfizo todos los puntos del criterio: ${corto(x.motivo)}.`;
    return `### ${caso} — ${x.estado}\n\n**Qué se hizo:** ${d.hizo(d.id)}\n**Qué se esperaba:** ${d.esperado}\n**Qué se observó:** ${d.observo(ss, d.id)}\n**Por qué ${x.estado}:** ${motivo}`;
  }).join('\n\n');
  const tabla = COMBINACIONES.map(([n, , origen, destino]) => {
    const caso = `TC-M04-${n}`;
    const d = datos.find(x => x.n === Number(n));
    const i = r.combinaciones.find(x => x.caso === caso && x.destino === destino);
    return `| ${caso} | ${d.version} ${d.id ?? 'sin ID'} ${origen} → ${destino} | ${i?.vias?.map(v => `${v.metodo} HTTP ${v.http ?? 'sin respuesta'}`).join('; ') ?? 'sin ejecutar'} | ${i?.estado_despues ?? 'sin lectura'} |`;
  }).join('\n');
  return `## Detalle por caso\n\n${detalles}\n\n## Catorce combinaciones\n\n| Caso | Origen → destino | Vías intentadas | Estado después |\n|---|---|---|---|\n${tabla}\n\n`;
}

function escribirInforme(c, r, secretos) {
  delete r._tokens; delete r._limite; delete r._consecutivos5xx; delete r._ensayo;
  delete r._rollback_contexto;
  r.evidencias.push('resultado.json', informe(c.version));
  r.incidencias = CASOS.filter(caso => r.casos[caso].estado === 'RECHAZADO').map((caso, i) => ({
    id: `INC-M04-G059-${caso.slice(-3)}`, casos: [caso], titulo: r.casos[caso].motivo,
    severidad: /estado posterior|cambió estado|no conservó|no siguió|se deprecó|única ACTIVO|reactiv/.test(r.casos[caso].motivo)
      ? 'ALTA' : 'MEDIA',
    impacto: 'Control de transiciones o contrato API afectado', certeza: 'CONFIRMADA',
    equipo_inicial: 'Desarrollo', fundamento: 'Primera discrepancia en API pública',
    causa_raiz: 'NO DETERMINADA' }));
  r.oficial = CASOS.every(x => ['APROBADO', 'RECHAZADO'].includes(r.casos[x].estado))
    && !r.problemas_tecnicos.length && r.cierre.run.cierre_http === 200
    && r.cierre.rollback.verificado && r.solicitudes.length <= CAPACIDADES.limite.solicitudes_totales
    && r.evidencias.some(x => x.endsWith('.html'))
    && r.evidencias.filter(x => !['resultado.json', informe(c.version)].includes(x))
      .every(x => fs.existsSync(path.join(c.directorio, x)));
  r.consume_version = r.oficial;
  const estados = CASOS.map(x => r.casos[x].estado);
  const decision = estados.includes('RECHAZADO') ? 'RECHAZADO'
    : estados.every(x => x === 'APROBADO') ? 'APROBADO'
      : estados.includes('BLOQUEADO') ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
  const versionesDecision = r.versiones ?? {};
  const idDecisionActivo = Number(r.solicitudes.find(s => s.caso === 'TC-M04-162'
    && /\/prediccion\/modelos\/\d+/.test(s.ruta))?.ruta.match(/\/prediccion\/modelos\/(\d+)/)?.[1]) || versionesDecision.V2;
  const resumenes = [
    `La versión ${versionesDecision.V3 ?? 'sin ID'} siguió APROBADO tras los intentos de cambio; su salida prevista es la activación`,
    `La versión ${idDecisionActivo ?? 'sin ID'} siguió ACTIVO, en producción y como única activa de su tipo`,
    `La versión ${versionesDecision.V1 ?? 'sin ID'} siguió DEPRECADO y se rechazó su reactivación con HTTP 409`,
    `La versión ${versionesDecision.R ?? 'sin ID'} siguió RECHAZADO, con las mismas métricas y detalle, y se rechazó su activación con HTTP 409`,
    `La versión ${versionesDecision.V1 ?? 'sin ID'} siguió ACTIVO hasta activar la ${versionesDecision.V2 ?? 'sin ID'}; entonces pasó a DEPRECADO y esta quedó como única ACTIVO`
  ];
  const motivoClaro = (caso, i) => r.casos[caso].estado === 'APROBADO'
    ? resumenes[i] : corto(r.casos[caso].motivo);
  const breve = CASOS.map((caso, i) => `| ${caso} | ${IDS[i]} | ${r.casos[caso].estado} | ${motivoClaro(caso, i)} |`).join('\n');
  const historial = r.solicitudes.map(s => `| ${s.caso ?? 'preparación/cierre'} | ${s.rol} | ${s.metodo} ${s.ruta} | ${s.http ?? 'sin respuesta'} | ${s.estado ?? '—'} | ${s.duracion_ms ?? '—'} |`).join('\n');
  const md = `# TC-M04-G059 — ${decision}\n\nGrupo G059; casos ${CASOS.join(', ')}; RF-69 v2.1; V${c.version}; RUN ${c.runId}; ambiente ${r.ambiente}; autorización ${corto(c.referencia)}; código consultado origin/test daefc3a5 (despliegue no verificado); Newman ${r.herramientas.newman.version ?? 'no disponible'}; Cypress no aplica (0).\n\n`+
    `## Decisión del caso\n\nAgrupado **TC-M04-G059**; originales **${CASOS.join(', ')}**.\n\n**Decisión: ${decision}.** ${CASOS.map((caso, i) => `${caso}: ${motivoClaro(caso, i)}.`).join(' ')}\n\n| Caso | Comprobación | Decisión | Motivo breve |\n|---|---|---|---|\n${breve}\n\n**RUN oficial: ${r.oficial && r.ambiente === 'TEST' ? 'sí' : 'no'}.** **Qué falta: ${r.oficial && r.ambiente === 'TEST' ? 'nada para este grupo' : 'evaluación autorizada en TEST y revisión del cierre/rollback'}.**\n\n`+
    detalleYCombinaciones(r)+
    `## Observaciones\n\n${r.observaciones.map(x => '- ' + corto(x)).join('\n') || 'Sin observaciones.'}\n\n`+
    `## Incidencias de producto\n\n${r.incidencias.map(x => `- ${x.id}: ${x.casos.join(', ')}; ${x.titulo}; severidad ${x.severidad} por ${x.impacto}; certeza ${x.certeza}; equipo inicial ${x.equipo_inicial} por ${x.fundamento}; causa raíz ${x.causa_raiz}.`).join('\n') || 'Sin incidencias confirmadas.'}\n\n`+
    `## Problemas técnicos\n\n${r.problemas_tecnicos.map(x => '- ' + corto(x)).join('\n') || 'Sin problemas técnicos.'}\n\n`+
    `## Historial de intentos API\n\n| Caso | Rol | Solicitud | HTTP | Estado | Duración ms |\n|---|---|---|---:|---|---:|\n${historial}\n\n`+
    `## Cierre y rollback\n\nOperación ${c.operacion}; intento ${c.intento}; ${r.solicitudes.length} solicitudes. DELETE HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. Rollback ${r.cierre.rollback.verificado ? 'comprobado por API' : 'NO_VERIFICADO'}: ${r.cierre.rollback.motivo}. Cuatro o cinco ONNX y posible respaldo RF-73 quedan fuera del DELETE; correo de R a cada usuario con permiso 43/3 irreversible.\n\n`+
    `## Evidencias\n\n${r.evidencias.map(x => '- ' + x).join('\n')}\n\n## Conclusión y acción\n\n${r.oficial ? 'Entregar al registro QA y revisar incidencias y efectos persistentes.' : 'Resolver la falta de evidencia y decidir un reintento autorizado.'}\n`;
  fs.writeFileSync(path.join(c.directorio, informe(c.version)), sanearArtefacto(md, secretos), 'utf8');
  guardar(path.join(c.directorio, 'resultado.json'), r, secretos);
}

export async function evaluar(c, { env, ensayo = false }) {
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G059', run_id: c.runId, version: c.version, intento: c.intento ?? null,
    operacion: c.operacion, autorizacion: c.referencia, ambiente: ensayo ? 'LOOPBACK_LOCAL' : 'TEST',
    oficial: false, consume_version: false, casos: Object.fromEntries(CASOS.map(x => [x,
      { estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación' }])),
    comprobaciones: CASOS.map((caso, i) => ({ caso, fuente: 'API', id: IDS[i], tipo: 'ASSERT',
      estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación', evidencia: null })),
    presupuesto: PRESUPUESTO, herramientas: { newman: versionNewman() }, solicitudes: [],
    combinaciones: [], versiones: {}, cypress: { total_pruebas: 0 }, evidencias: [],
    incidencias: [], problemas_tecnicos: [], observaciones: [],
    cierre: { run: { cierre_http: null }, rollback: { verificado: false,
      motivo: 'Sin cierre ni comprobación posterior' } }, _tokens: {},
    _limite: Date.now() + PRESUPUESTO.duracion_segundos * 1000, _consecutivos5xx: 0,
    _ensayo: ensayo };
  const secretos = [env.QA_SANDBOX_SECRET, env.RF71_INTERNAL_KEY, env.QA_ADMIN_EMAIL,
    env.QA_ADMIN_PASSWORD, env.QA_VETERINARIO_EMAIL, env.QA_COMMON_PASSWORD].filter(Boolean);
  const poner = (n, x) => { const i = n - 161; r.casos[CASOS[i]] = x;
    Object.assign(r.comprobaciones[i], { ...x, evidencia: 'resultado.json' }); };
  let temporal = null, tocado = false;
  try {
    const pre = preflight(c, env, ensayo);
    guardar(path.join(c.directorio, 'preflight.json'), pre, secretos);
    r.evidencias.push('preflight.json');
    if (!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
    if (!r.herramientas.newman.ok) throw Error('NEWMAN_NO_DISPONIBLE');
    for (const [rol, email, pass] of [['admin', env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD],
      ['vet', env.QA_VETERINARIO_EMAIL, env.QA_COMMON_PASSWORD]]) {
      const x = await pedir(r, api, 'POST', '/sesiones/', { cuerpo: { correo_electronico: email,
        contrasena: pass }, rol, timeout: PRESUPUESTO.timeout_login_registro_ms });
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
    const get = (id, caso = null, sinRun = false) => id == null ? null : pedir(r, api, 'GET', ruta(id),
      sinRun ? { token: r._tokens.admin, rol: 'Administrador poscierre' } : { ...admin, caso });
    const listar = (caso = null, sinRun = false) => pedir(r, api, 'GET',
      `/prediccion/modelos?tipo_modelo=${TIPO}&estado=ACTIVO&limit=100&offset=0`,
      sinRun ? { token: r._tokens.admin, rol: 'Administrador poscierre' } : { ...admin, caso });
    const auditar = (id, caso) => pedir(r, api, 'GET',
      `/prediccion/auditoria?id_referencia=${id}&por_pagina=200`, { ...admin, caso });
    const nota = (id, nombre, cred, caso) => pedir(r, api, 'PATCH', `${ruta(id)}/notas`,
      { ...cred, caso, cuerpo: { notas_validacion: `G059 ${c.runId} ${nombre}`,
        estado_version: nombre.endsWith('sin extra') ? undefined : 'RECHAZADO' } });
    const activar = (id, caso = null, cred = admin) => pedir(r, api, 'POST', `${ruta(id)}/activar`,
      { ...cred, caso });
    const catalogo = await pedir(r, api, 'GET', '/configuracion/variables-ambientales', admin);
    const variables = catalogo.cuerpo?.items?.map(x => x.id_variable_ambiental).filter(Number.isSafeInteger) ?? [];
    if (catalogo.http !== 200 || !catalogo.eco || !variables.length)
      throw Error(`CATALOGO_I3P1_NO_VERIFICABLE_HTTP_${catalogo.http}`);
    const inicial = await listar();
    if (inicial.http !== 200 || !inicial.eco || !Array.isArray(inicial.cuerpo?.items)
      || inicial.cuerpo.total !== inicial.cuerpo.items.length)
      throw Error(`ACTIVOS_INICIALES_NO_VERIFICABLES_HTTP_${inicial.http}`);
    temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g059-newman-'));
    const archivo = path.join(temporal, 'g059.onnx'); fs.writeFileSync(archivo, onnxMinimo());
    const datos = escenarios({ variable: variables[0], hash: sha256(fs.readFileSync(archivo)),
      dataset: sha256(Buffer.from('G059 dataset QA RF-71')), archivo });
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
      throw Error('POST_SIN_RESPUESTA');
    }
    const nombres = ['V1', 'V2', 'V3', 'R'];
    nombres.forEach((n, i) => { r.versiones[n] = idVersion(post[i]?.cuerpo); });
    r._rollback_contexto = { ids: Object.values(r.versiones).filter(x => x != null),
      activos_antes: inicial.cuerpo.items.map(idVersion).sort((a, b) => a - b) };
    const validos = nombres.map((_, i) => registroValido(post[i], i === 3 ? 'RECHAZADO' : 'APROBADO'));
    const ids = r.versiones;
    const notas = {};
    for (const [nombre, cred, caso] of [['V1', vet, null], ['V2', admin, null],
      ['V3', admin, 'TC-M04-161'], ['R', admin, 'TC-M04-164']])
      if (validos[nombres.indexOf(nombre)]) {
        notas[nombre] = await nota(ids[nombre], nombre === 'V2' ? 'V2 sin extra' : nombre, cred, caso);
        if (nombre === 'V1' && notas[nombre].http >= 400 && notas[nombre].http < 500) {
          r.observaciones.push(`Preparación V1: PATCH con campo extra HTTP ${notas[nombre].http}; se registra nota sin extra para activar`);
          notas[nombre] = await nota(ids[nombre], 'V1 sin extra', cred, null);
        }
        if (nombre === 'V3' || nombre === 'R') notas[`${nombre}Get`] = await get(ids[nombre], caso);
      }
    const comunes = { 161: [], 162: [], 163: [], 164: [], 165: [] };
    for (const [n, nombre, esperado] of [[161, 'V3', 'APROBADO'], [164, 'R', 'RECHAZADO']]) {
      if (notas[nombre]) agregar(comunes[n], clasificarIntento(notas[nombre], notas[`${nombre}Get`],
        esperado, `PATCH /notas ${nombre}`), r.observaciones);
    }
    const a1 = validos[0] && notas.V1?.http === 200 ? await activar(ids.V1, null, vet) : null;
    const preparadaV1 = estado(a1, 'ACTIVO', true);
    const pares = async (n, nombre, origen) => {
      const caso = `TC-M04-${n}`, fallos = comunes[n];
      for (const [num, etiqueta, _, destino] of COMBINACIONES.filter(x => x[0] === String(n))) {
        const vias = [];
        for (const metodo of ['PUT', 'PATCH']) {
          const x = await pedir(r, api, metodo, ruta(ids[nombre]),
            { ...admin, caso, destino, cuerpo: { estado_version: destino } });
          vias.push({ metodo, http: x.http, codigo: x.cuerpo?.code ?? null });
          if (x.http == null || x.http === 403 || x.http >= 500) {
            agregar(fallos, clasificarIntento(x, await get(ids[nombre], caso), origen,
              `${metodo} ${origen}→${destino}`), r.observaciones);
            break;
          }
        }
        const lectura = await get(ids[nombre], caso);
        r.combinaciones.push({ caso, origen, destino, vias, estado_despues: lectura?.cuerpo?.estado_version ?? null });
        for (const via of vias) agregar(fallos,
          clasificarIntento({ http: via.http, eco: true }, lectura, origen,
            `${via.metodo} ${origen}→${destino}`), r.observaciones);
        if (!estado(lectura, origen)) break;
      }
    };
    const inicioCaso = async (n, id, expected) => {
      const caso = `TC-M04-${n}`;
      const antes = await auditar(id, caso);
      const extra = await nota(id, `extra ${n}`, admin, caso);
      const despues = await get(id, caso);
      agregar(comunes[n], clasificarIntento(extra, despues, expected, `PATCH /notas caso ${n}`), r.observaciones);
      return antes;
    };
    const finCaso = async (n, id, antes, lecturaPrevia = null) => {
      const caso = `TC-M04-${n}`;
      const lectura = lecturaPrevia ?? await get(id, caso);
      const lista = await listar(caso), despues = await auditar(id, caso);
      if (!mismosEventos(antes, despues)) comunes[n].push({ estado: 'RECHAZADO',
        motivo: `${n}: auditoría VERSION_* cambió durante intentos` });
      if (lectura?.http == null || lista.http == null || despues.http == null)
        comunes[n].push({ estado: 'NO_CONCLUYENTE', motivo: `${n}: lectura final sin respuesta` });
      return { lectura, lista, despues };
    };
    // 165 primero: V1 aún ACTIVO. La activación de V2 deja una versión distinta
    // para 162; un defecto en 162 no destruye la precondición de 163.
    let v2Activa = false, v1Deprecada = false;
    if (preparadaV1 && validos[1] && notas.V2?.http === 200) {
      const caso = 'TC-M04-165', antes = await inicioCaso(165, ids.V1, 'ACTIVO');
      let directo = null;
      for (const [metodo, endpoint] of [['POST', `${ruta(ids.V1)}/deprecar`],
        ['PATCH', `${ruta(ids.V1)}/estado`]]) {
        const x = await pedir(r, api, metodo, endpoint, { ...admin, caso,
          ...(metodo === 'PATCH' ? { cuerpo: { estado_version: 'DEPRECADO' } } : {}) });
        const lectura = await get(ids.V1, caso); directo = lectura;
        agregar(comunes[165], clasificarIntento(x, lectura, 'ACTIVO',
          `${metodo} deprecación directa`), r.observaciones);
      }
      if (!estado(directo, 'ACTIVO', true)) comunes[165].push({ estado: 'RECHAZADO',
        motivo: `165: V1 ${ids.V1} se deprecó antes de activar V2` });
      const a2 = await activar(ids.V2, caso);
      const g1 = await get(ids.V1, caso), g2 = await get(ids.V2, caso);
      const lista = await listar(caso), aud = await auditar(ids.V1, caso);
      v2Activa = estado(g2, 'ACTIVO', true); v1Deprecada = estado(g1, 'DEPRECADO', false);
      if (!estado(a2, 'ACTIVO', true))
        comunes[165].push(invalidado(a2, '165: activación de V2 no acreditada'));
      else if (!v1Deprecada || !v2Activa || !listaUnica(lista, ids.V2))
        comunes[165].push({ estado: 'RECHAZADO',
          motivo: `165: activar V2 HTTP ${a2.http}, V1 ${g1?.cuerpo?.estado_version ?? 'sin lectura'}, V2 ${g2?.cuerpo?.estado_version ?? 'sin lectura'}, listado ACTIVO ${lista?.cuerpo?.total ?? 'sin lectura'}; esperado V1 DEPRECADO y V2 única ACTIVO` });
      const previos165 = eventosEstado(antes), posteriores165 = eventosEstado(aud);
      if (previos165 == null || posteriores165 == null)
        comunes[165].push({ estado: 'NO_CONCLUYENTE', motivo: '165: auditoría no verificable' });
      else if (!posteriores165.some(ev => ev[0] === 'VERSION_DEPRECADA'
        && ev[1] === String(ids.V1) && !previos165.some(p => JSON.stringify(p) === JSON.stringify(ev))))
        comunes[165].push({ estado: 'RECHAZADO',
          motivo: `165: V1 ${ids.V1} no registró VERSION_DEPRECADA al activar V2` });
      poner(165, decidir(comunes[165], `V1 ${ids.V1} ACTIVO hasta activar V2; después DEPRECADO y V2 ${ids.V2} única ACTIVO`));
    } else poner(165, invalidado(a1, '165: faltó V1 ACTIVO o V2 APROBADO con notas'));
    const idActivo = v2Activa ? ids.V2 : preparadaV1 ? ids.V1 : null;
    if (idActivo != null) {
      const caso = 'TC-M04-162', antes = await inicioCaso(162, idActivo, 'ACTIVO');
      const original = ids.V2; ids.V2 = idActivo;
      await pares(162, 'V2', 'ACTIVO'); ids.V2 = original;
      const fin = await finCaso(162, idActivo, antes);
      if (!estado(fin.lectura, 'ACTIVO', true) || !listaUnica(fin.lista, idActivo))
        comunes[162].push({ estado: 'RECHAZADO', motivo: `162: versión ${idActivo} no siguió como única ACTIVO` });
      poner(162, decidir(comunes[162], `Versión ${idActivo} siguió ACTIVO, producción verdadera y única del tipo`));
    } else poner(162, invalidado(a1, '162: ninguna versión ACTIVO preparada'));
    if (!v1Deprecada && preparadaV1) {
      const relectura = await get(ids.V1);
      v1Deprecada = estado(relectura, 'DEPRECADO', false);
    }
    if (v1Deprecada) {
      const caso = 'TC-M04-163', antes = await inicioCaso(163, ids.V1, 'DEPRECADO');
      await pares(163, 'V1', 'DEPRECADO');
      const x = await activar(ids.V1, caso), lectura = await get(ids.V1, caso);
      const filaActivo = r.combinaciones.find(y => y.caso === caso && y.destino === 'ACTIVO');
      if (filaActivo) { filaActivo.vias.push({ metodo: 'POST /activar', http: x.http,
        codigo: x.cuerpo?.code ?? null }); filaActivo.estado_despues = lectura?.cuerpo?.estado_version ?? null; }
      agregar(comunes[163], clasificarIntento(x, lectura, 'DEPRECADO', 'Reactivar V1',
        { activar: true }), r.observaciones);
      const fin = await finCaso(163, ids.V1, antes);
      if (!estado(fin.lectura, 'DEPRECADO', false)) comunes[163].push({ estado: 'RECHAZADO',
        motivo: `163: V1 ${ids.V1} no conservó DEPRECADO` });
      if (!fin.despues?.cuerpo?.items?.some(y => y.tipo_evento === 'INTENTO_ACTIVACION_INVALIDA'))
        r.observaciones.push('163: sin evento del intento inválido; FA-08 no localizado en RF-69 v2.1');
      poner(163, decidir(comunes[163], `V1 ${ids.V1} conservó DEPRECADO; /activar HTTP 409`));
    } else poner(163, { estado: 'NO_CONCLUYENTE', motivo: '163: no se preparó V1 DEPRECADO' });
    if (validos[3]) {
      const caso = 'TC-M04-164', antes = await auditar(ids.R, caso), baseR = notas.RGet;
      await pares(164, 'R', 'RECHAZADO');
      const x = await activar(ids.R, caso), lectura = await get(ids.R, caso);
      const filaActivo = r.combinaciones.find(y => y.caso === caso && y.destino === 'ACTIVO');
      if (filaActivo) { filaActivo.vias.push({ metodo: 'POST /activar', http: x.http,
        codigo: x.cuerpo?.code ?? null }); filaActivo.estado_despues = lectura?.cuerpo?.estado_version ?? null; }
      agregar(comunes[164], clasificarIntento(x, lectura, 'RECHAZADO', 'Reactivar R',
        { activar: true }), r.observaciones);
      const corregido = { ...datos[3], dato: 'R2', metricas_validacion: {
        ...datos[3].metricas_validacion, f1_score_global: 0.91 } };
      const reenvio = await registrarNewman(r, c, api, env, corregido, temporal, secretos);
      r.solicitudes.at(-1).caso = caso;
      const rDespues = await get(ids.R, caso);
      if (reenvio.http == null) comunes[164].push({ estado: 'NO_CONCLUYENTE', motivo: '164: reenvío sin respuesta' });
      else if (reenvio.http >= 500) comunes[164].push({ estado: 'RECHAZADO', motivo: `164: reenvío HTTP ${reenvio.http}` });
      else if (reenvio.http >= 200 && reenvio.http < 300 && idVersion(reenvio.cuerpo) != null
        && String(idVersion(reenvio.cuerpo)) !== String(ids.R)) {
        r._rollback_contexto.ids.push(idVersion(reenvio.cuerpo));
        r.observaciones.push(`164: reenvío creó versión nueva ${idVersion(reenvio.cuerpo)} ${reenvio.cuerpo.estado_version}; R original no se reevalúa`);
      } else if (reenvio.http >= 200 && reenvio.http < 300)
        r.observaciones.push(`164: reenvío HTTP ${reenvio.http} sin nuevo ID; se comprueba R original`);
      if (!estado(rDespues, 'RECHAZADO', false) || metricasR(baseR) !== metricasR(rDespues))
        comunes[164].push({ estado: 'RECHAZADO', motivo: `164: R ${ids.R} cambió estado, métricas o detalle tras reenvío` });
      const fin = await finCaso(164, ids.R, antes, rDespues);
      if (!estado(fin.lectura, 'RECHAZADO', false)) comunes[164].push({ estado: 'RECHAZADO', motivo: `164: R ${ids.R} no conservó RECHAZADO` });
      poner(164, decidir(comunes[164], `R ${ids.R} conservó RECHAZADO, métricas y detalle; /activar HTTP 409`));
    } else poner(164, invalidado(post[3], '164: R no se registró RECHAZADA'));
    if (validos[2] && notas.V3Get) {
      const caso = 'TC-M04-161', antes = await auditar(ids.V3, caso);
      await pares(161, 'V3', 'APROBADO');
      const fin = await finCaso(161, ids.V3, antes);
      if (!estado(fin.lectura, 'APROBADO', false)) comunes[161].push({ estado: 'RECHAZADO', motivo: `161: V3 ${ids.V3} no conservó APROBADO` });
      poner(161, decidir(comunes[161], `V3 ${ids.V3} conservó APROBADO; única salida expuesta /activar`));
    } else poner(161, invalidado(post[2], '161: V3 APROBADA no preparada'));
  } catch (e) {
    const motivo = corto(e.message); r.problemas_tecnicos.push(motivo);
    const clasificacion = /403|5XX|LOGIN|CATALOGO/.test(motivo) ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
    CASOS.forEach((caso, i) => { if (r.casos[caso].motivo === 'Sin comprobación')
      poner(161 + i, { estado: clasificacion, motivo }); });
  } finally {
    if (tocado) {
      const x = await pedir(r, api, 'DELETE', `/test-control/runs/${encodeURIComponent(c.runId)}`,
        { secreto: env.QA_SANDBOX_SECRET, rol: 'Sistema' });
      r.cierre.run.cierre_http = x.http;
      r.cierre.rollback.motivo = `DELETE HTTP ${x.http}; rollback pendiente de comprobación`;
      if (x.http === 200 && r._rollback_contexto) {
        const checks = [];
        for (const id of r._rollback_contexto.ids) checks.push(await pedir(r, api, 'GET', ruta(id),
          { token: r._tokens.admin, rol: 'Administrador poscierre' }));
        const activos = await pedir(r, api, 'GET',
          `/prediccion/modelos?tipo_modelo=${TIPO}&estado=ACTIVO&limit=100&offset=0`,
          { token: r._tokens.admin, rol: 'Administrador poscierre' });
        const idsActivos = (activos.cuerpo?.items ?? []).map(idVersion).sort((a, b) => a - b);
        const idsRun = new Set(r._rollback_contexto.ids.map(String));
        r.cierre.rollback.verificado = checks.length >= 4 && idsRun.size === checks.length
          && checks.every(y => y.http === 404) && activos.http === 200
          && activos.cuerpo?.total === idsActivos.length
          && !idsActivos.some(id => idsRun.has(String(id)))
          && JSON.stringify(idsActivos) === JSON.stringify(r._rollback_contexto.activos_antes);
        r.cierre.rollback.motivo = r.cierre.rollback.verificado
          ? `GET poscierre: ${checks.length} versiones HTTP 404; listado ACTIVO restaurado`
          : `GET poscierre: ${checks.map(y => y.http).join('/')}; listado HTTP ${activos.http}; rollback no acreditado`;
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
    const c = contextoEjecucion(process.argv.slice(2), { grupo: 'G059', casos: CASOS, directorio: DIR });
    const r = await evaluar(c, { env: leerEnv() });
    console.log(JSON.stringify({ run_id: r.run_id, casos: r.casos, oficial: r.oficial }));
    if (!r.oficial) process.exitCode = 2;
  } catch (e) { console.error(`G059: ${corto(e.message)}`); process.exitCode = 2; }
}
