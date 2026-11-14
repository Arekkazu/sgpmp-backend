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
import { CASOS, IDS, PRESUPUESTO, CAPACIDADES, escenarios, idVersion, metricasCompletas } from './lib/g056_escenario.mjs';

const require = createRequire(import.meta.url);
const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION = path.join(DIR, 'G056.postman_collection.json');
const ARCHIVOS = ['.gitkeep', 'g056.mjs', 'G056.postman_collection.json', 'README.md',
  'lib/contrato_ejecutor.mjs', 'lib/seguridad.mjs', 'lib/artefactos.mjs', 'lib/g056_escenario.mjs',
  'pruebas/g056_ensayo.mjs', 'pruebas/g056_env.test.mjs', 'pruebas/registro_qa.mjs'];
const limpio = x => String(x ?? '').replaceAll('|', '/').replace(/[\r\n]+/g, ' ').slice(0, 220);
const guardar = (p, x) => fs.writeFileSync(p, JSON.stringify(x, null, 2), 'utf8');
const informe = v => v === 1 ? 'TC-M04-G056_resultado.md' : `TC-M04-G056_reevaluacion_V${v}.md`;

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
    if (!p) throw Error('NEWMAN_NO_RESUELTO');
    return path.dirname(p);
  }
}
function versionNewman() {
  try { return { ok: true, version: require(path.join(paqueteNewman(), 'package.json')).version }; }
  catch { return { ok: false, error: 'NEWMAN_NO_RESUELTO' }; }
}
export function comprobar() {
  let coleccion = false;
  try {
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const i of col.item) for (const e of i.event ?? []) new vm.Script((e.script?.exec ?? []).join('\n'));
    coleccion = col.item.length === 1 && col.item[0].name === 'API-G056-POST'
      && col.item[0].request.method === 'POST' && !contieneMojibake(JSON.stringify(col));
  } catch { /* se informa como false */ }
  const faltantes = ARCHIVOS.filter(x => !fs.existsSync(path.join(DIR, x)));
  const presentes = fs.readdirSync(DIR).filter(x => !['lib', 'pruebas', 'Resultados', 'EvaluacionV2'].includes(x))
    .concat(...['lib', 'pruebas'].map(d => fs.existsSync(path.join(DIR, d))
      ? fs.readdirSync(path.join(DIR, d)).map(x => `${d}/${x}`) : []));
  const inesperados = presentes.filter(x => !ARCHIVOS.includes(x));
  const markdownSuperior = fs.existsSync(path.join(DIR, 'Resultados'))
    && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const ok = coleccion && !faltantes.length && !inesperados.length && !markdownSuperior
    && PRESUPUESTO.total === 41 && versionNewman().ok;
  console.log(JSON.stringify({ grupo: 'G056', ok, coleccion, faltantes, inesperados,
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
  return { grupo: 'G056', run_id: c.runId, ok: !faltan.length, barreras: faltan,
    presupuesto: PRESUPUESTO, herramientas: { newman: versionNewman() },
    efectos_declarados: ['4_versiones_y_notas_BD_sandbox', '4_ONNX_fuera_rollback',
      'respaldo_RF73_posible', '1_aviso_por_destinatario_activo_irreversible',
      '2_logins_previos_posible_sesion_o_auditoria'] };
}
function resumenRespuesta(x) {
  return { http: x?.http ?? null, eco: x?.eco ?? null, estado: x?.cuerpo?.estado_version ?? null,
    notas: x?.cuerpo?.notas_validacion ?? null, id: idVersion(x?.cuerpo),
    esta_produccion: x?.cuerpo?.esta_produccion ?? null,
    metricas_completas: metricasCompletas(x?.cuerpo),
    items: Array.isArray(x?.cuerpo?.items) ? x.cuerpo.items.map(y => ({ id: idVersion(y),
      tipo_modelo: y.tipo_modelo, paradigma: y.paradigma, estado: y.estado_version,
      metricas_completas: metricasCompletas(y),
      metricas_esquema: metricasEsquema(y) })) : null,
    eventos: Array.isArray(x?.cuerpo?.items) ? x.cuerpo.items.filter(y => y.tipo_evento)
      .map(y => ({ id: y.id_evento, tipo: y.tipo_evento, referencia: y.id_referencia,
        huella: TRANSICION.test(y.tipo_evento) ? sha256(Buffer.from(JSON.stringify(y))) : null })) : null };
}
async function pedir(r, api, metodo, ruta, { token, secreto, runId, cuerpo,
  estadoAntes = null, timeout = PRESUPUESTO.timeout_ms } = {}) {
  const fila = { rol: token === r._tokens?.admin ? 'Administrador' : token === r._tokens?.vet ? 'Veterinario' : 'Sistema',
    metodo, ruta: ruta.replace(/\?.*/, '?[filtro]'), http: null, eco: null, estado_antes: estadoAntes };
  r.solicitudes.push(fila);
  try {
    const resto = r._limite - Date.now();
    if (resto <= 0) throw Error('LIMITE_900_SEGUNDOS');
    const x = await fetch(api + ruta, { method: metodo, redirect: 'manual',
      headers: { ...(cuerpo ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(secreto ? { 'X-Sandbox-Secret': secreto } : {}),
        ...(runId ? { 'X-Test-Run-Id': runId, 'X-Zona-Horaria': 'UTC' } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      signal: AbortSignal.timeout(Math.max(1, Math.min(timeout, resto))) });
    const data = await x.json().catch(() => null);
    const out = { http: x.status, eco: runId ? x.headers.get('x-test-run-id') === runId : null, cuerpo: data };
    Object.assign(fila, resumenRespuesta(out));
    return out;
  } catch { fila.error = 'SIN_RESPUESTA'; return { http: null, eco: null, cuerpo: null }; }
}
async function registrarNewman(r, c, api, env, escenario, indice, temporal, secretos) {
  const raw = path.join(temporal, `newman-${indice}-raw.json`);
  const values = Object.entries({ autorizado_run: 'SI', ensayo_loopback: c.ensayo ? 'SI' : 'NO',
    base_url: api, run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET,
    rf71_internal_key: env.RF71_INTERNAL_KEY }).map(([key, value]) => ({ key, value, enabled: true }));
  const dato = { ...escenario, metricas_validacion: JSON.stringify(escenario.metricas_validacion),
    compatibilidad_variables: JSON.stringify(escenario.compatibilidad_variables) };
  const ini = Date.now();
  await new Promise(resolve => require(paqueteNewman()).run({
    collection: JSON.parse(fs.readFileSync(COLECCION, 'utf8')),
    environment: { values }, iterationData: [dato], reporters: ['json'],
    reporter: { json: { export: raw } }, timeoutRequest: c.ensayo ? 1500 : PRESUPUESTO.timeout_post_ms,
    timeout: Math.max(1, Math.min(PRESUPUESTO.timeout_post_ms + 5000, r._limite - Date.now())), color: 'off'
  }, error => resolve(error)));
  const original = fs.existsSync(raw) ? JSON.parse(fs.readFileSync(raw, 'utf8')) : {};
  const ex = original.run?.executions?.[0];
  let cuerpo = null;
  try { cuerpo = JSON.parse(Buffer.from(ex?.response?.stream?.data ?? []).toString('utf8')); } catch { /* sin JSON */ }
  const http = ex?.response?.code ?? null;
  const eco = ex?.response?.header?.find(h => String(h.key).toLowerCase() === 'x-test-run-id')?.value === c.runId;
  const resp = { http, eco, cuerpo, duracion_ms: Date.now() - ini };
  r.solicitudes.push({ rol: 'RF-71 interno', metodo: 'POST', ruta: '/prediccion/modelos', dato: escenario.dato,
    ...resumenRespuesta(resp), duracion_ms: resp.duracion_ms });
  const seguro = JSON.parse(sanearArtefacto(JSON.stringify({ info: { nombre: `Newman G056 ${escenario.dato}`,
    generado: !!ex, saneado: true }, run: { stats: original.run?.stats ?? null,
    executions: [{ http, eco, estado: cuerpo?.estado_version, id: idVersion(cuerpo),
      duracion_ms: resp.duracion_ms }], failures: (original.run?.failures ?? []).map(f => ({
      name: limpio(f.error?.name), message: limpio(f.error?.message) })) } }), secretos));
  const sub = path.join(c.directorio, 'newman'); fs.mkdirSync(sub, { recursive: true });
  guardar(path.join(sub, `newman-G056-${escenario.dato}.json`), seguro);
  fs.writeFileSync(path.join(sub, `newman-G056-${escenario.dato}.html`),
    `<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G056 ${escenario.dato}</title>`
    + `<h1>Newman G056 ${escenario.dato}</h1><p>HTTP ${http ?? 'sin respuesta'}; eco ${!!eco}; duración ${resp.duracion_ms} ms</p></html>`, 'utf8');
  r.evidencias.push(`newman/newman-G056-${escenario.dato}.json`, `newman/newman-G056-${escenario.dato}.html`);
  return resp;
}

function decidir(r, i, estado, motivo) {
  r.casos[CASOS[i]] = { estado, motivo: limpio(motivo) };
  Object.assign(r.comprobaciones[i], { estado, motivo: limpio(motivo), evidencia: 'resultado.json' });
}
function evaluarCaso(condiciones, conforme) {
  if (condiciones.some(x => x.tipo === 'sin_respuesta')) return ['NO_CONCLUYENTE', condiciones.find(x => x.tipo === 'sin_respuesta').motivo];
  if (condiciones.some(x => x.tipo === 'bloqueo')) return ['BLOQUEADO', condiciones.find(x => x.tipo === 'bloqueo').motivo];
  if (condiciones.some(x => x.tipo === 'defecto')) return ['RECHAZADO', condiciones.find(x => x.tipo === 'defecto').motivo];
  return ['APROBADO', conforme];
}
const falta = (x, nombre) => !x?.http ? { tipo: 'sin_respuesta', motivo: `${nombre}: sin respuesta` }
  : x.http === 403 || x.http >= 500 ? { tipo: 'defecto', motivo: `${nombre}: HTTP ${x.http}` } : null;
const defecto = (ok, motivo) => ok ? null : { tipo: 'defecto', motivo };
function decidirCon(r, i, xs, conforme) { decidir(r, i, ...evaluarCaso(xs.filter(Boolean), conforme)); }
const TRANSICION = /^(VERSION_REGISTRADA|VERSION_RECHAZADA|VERSION_APROBADA)$|ESTADO|ACTIV/i;
function transiciones(x) {
  const normalizar = y => JSON.stringify(Object.fromEntries(Object.entries(y).sort(([a], [b]) => a.localeCompare(b))));
  return (x?.cuerpo?.items ?? []).filter(y => TRANSICION.test(y.tipo_evento ?? ''))
    .map(normalizar).sort();
}
function metricasEsquema(y) {
  if (!y || typeof y !== 'object') return false;
  if (y.paradigma === 'POBLACIONAL') return Object.hasOwn(y, 'metricas_poblacionales');
  return Object.hasOwn(y, 'f1_score') && Object.hasOwn(y, 'recall_clase_riesgo_alto');
}
function coberturaListado(x, filtro, versiones, sinFiltro = false) {
  if (x.http !== 200 || !x.eco || !Array.isArray(x.cuerpo?.items)) return false;
  const items = x.cuerpo.items;
  if (items.some(y => !y.estado_version || (sinFiltro ? !metricasEsquema(y) : !metricasCompletas(y)))) return false;
  if (filtro.tipo && items.some(y => y.tipo_modelo !== filtro.tipo)) return false;
  if (filtro.estado && items.some(y => y.estado_version !== filtro.estado)) return false;
  return versiones.every(v => items.some(y => String(idVersion(y)) === String(idVersion(v))
    && y.estado_version === v?.estado_version && metricasCompletas(y)));
}
function diagnosticoListado(x, filtro, versiones, sinFiltro = false) {
  if (x.http !== 200 || !x.eco) return `HTTP ${x.http ?? 'sin respuesta'}, eco RUN ${x.eco}`;
  if (!Array.isArray(x.cuerpo?.items)) return 'items ausentes';
  const items = x.cuerpo.items;
  const sinEstado = items.find(y => !y.estado_version);
  if (sinEstado) return `versión ${idVersion(sinEstado)} sin estado`;
  const sinBloque = items.find(y => sinFiltro ? !metricasEsquema(y) : !metricasCompletas(y));
  if (sinBloque) return `versión ${idVersion(sinBloque)} paradigma ${sinBloque.paradigma ?? 'nulo'} sin bloque de métricas ${sinFiltro ? 'en esquema' : 'completo'}`;
  const fuera = items.find(y => filtro.tipo && y.tipo_modelo !== filtro.tipo
    || filtro.estado && y.estado_version !== filtro.estado);
  if (fuera) return `versión ${idVersion(fuera)} fuera de filtro: tipo ${fuera.tipo_modelo ?? 'nulo'}, estado ${fuera.estado_version}`;
  for (const v of versiones) {
    const y = items.find(z => String(idVersion(z)) === String(idVersion(v)));
    if (!y) return `versión RUN ${idVersion(v)} ausente entre ${items.length} items`;
    if (y.estado_version !== v.estado_version || !metricasCompletas(y))
      return `versión RUN ${idVersion(v)}: estado ${y.estado_version}, métricas completas ${metricasCompletas(y)}`;
  }
  return `${items.length} items; discrepancia por determinar`;
}
function incidencias(r) {
  const porMotivo = new Map();
  CASOS.forEach((c, i) => {
    const x = r.casos[c]; if (x.estado !== 'RECHAZADO') return;
    const clave = x.motivo; const actual = porMotivo.get(clave) ?? { id: `INC-G056-${porMotivo.size + 1}`,
      casos: [], titulo: `Incumplimiento de ${IDS[i]} en API RF-69`,
      requisito: [`RF-69 v2.1 línea 1968; matriz G056 línea 29, subcaso 1`,
        `RF-69 v2.1 líneas 1890-1891 y 2177-2181; matriz G056 línea 29, subcaso 2`,
        `RF-69 v2.1 líneas 1822-1832 y 2066-2068; matriz G056 línea 29, subcaso 3`,
        `RF-69 v2.1 líneas 2313-2315; matriz G056 línea 29, subcaso 4`][i],
      pasos: i === 0 ? 'Registrar notas con ambos roles y consultar V1/V1b' : i === 1
        ? 'Consultar V2 RECHAZADA e historial; intentar estado, activación y auditoría; consultar de nuevo'
        : i === 2 ? 'Registrar V3 del mismo tipo y consultar la versión APROBADA con notas'
          : 'Listar sin filtro y con filtros de tipo y estado con ambos roles',
      obtenido: clave, hipotesis: 'Causa técnica por determinar; requiere análisis de Desarrollo',
      severidad: i < 2 ? 'ALTA' : 'MEDIA',
      certeza: 'CONFIRMADA', equipo_inicial: 'Desarrollo', causa_raiz: 'NO DETERMINADA',
      fundamento: 'Primera discrepancia observada en API pública de RF-69',
      impacto: i < 2 ? 'Acción clínica o restricción de seguridad funcional incumplida sin alternativa en el flujo'
        : 'Consulta o permanencia parcial incorrecta con impacto acotado' };
    actual.casos.push(c); porMotivo.set(clave, actual);
  });
  return [...porMotivo.values()];
}
function detallePorCaso(r) {
  const solicitudes = r.solicitudes;
  const post = dato => solicitudes.find(x => x.metodo === 'POST' && x.dato === dato);
  const id = dato => post(dato)?.id ?? 'sin identificador';
  const http = x => x?.http ?? 'sin respuesta';
  const nota = rol => solicitudes.find(x => x.rol === rol && x.metodo === 'PATCH' && x.ruta.endsWith('/notas'))?.notas;
  const consultas = rol => solicitudes.filter(x => x.rol === rol && x.metodo === 'GET' && x.ruta === `/prediccion/modelos/${id('V2')}`);
  const historial = rol => solicitudes.filter(x => x.rol === rol && x.metodo === 'GET' && x.ruta.startsWith('/prediccion/auditoria'));
  const transiciones = x => (x?.eventos ?? []).filter(y => TRANSICION.test(y.tipo ?? '')).length;
  const listas = rol => solicitudes.filter(x => x.rol === rol && x.metodo === 'GET' && x.ruta.startsWith('/prediccion/modelos?'));
  const listaResumen = rol => listas(rol).map(x => `${x.items?.length ?? 'sin datos'} (HTTP ${http(x)})`).join(', ') || 'sin consultas';
  const itemsRun = listas('Administrador')[0]?.items?.filter(x => ['V1', 'V1b', 'V2', 'V3'].some(dato => String(id(dato)) === String(x.id))) ?? [];
  const resumenRun = itemsRun.map(x => `${x.id} ${x.estado ?? 'sin estado'}, métricas ${x.metricas_completas ? 'completas' : 'incompletas'}`).join('; ') || 'sin versiones del RUN en el listado';
  const observacion = r.observaciones.find(x => x.startsWith('TC-M04-148:')) ?? '';
  const usada = observacion.match(/versión usada (V1b|V1)/)?.[1];
  const consulta148 = usada && solicitudes.findLast(x => x.metodo === 'GET' && x.ruta === `/prediccion/modelos/${id(usada)}`);
  const pasos147 = solicitudes.filter(x => x.ruta === `/prediccion/modelos/${id('V2')}` || x.ruta === `/prediccion/modelos/${id('V2')}/activar` || x.ruta.startsWith('/prediccion/auditoria'));
  const intentos147 = pasos147.filter(x => ['PUT', 'PATCH', 'DELETE'].includes(x.metodo));
  const filtros149 = ['sin filtro', 'tipo MODELO_ESPECIES_GRANDES', 'estado RECHAZADO', 'estado APROBADO'];
  const filtrosPorRol = rol => `${rol}: ${filtros149.slice(0, listas(rol).length).join(', ') || 'ninguno'}`;
  const hecho146 = post('V1') && post('V1b')
    ? `Se registraron V1, id ${id('V1')}, y V1b, id ${id('V1b')}; el Veterinario ${nota('Veterinario') ? `envió la nota «${limpio(nota('Veterinario'))}»` : 'no registró una nota observable'} y el Administrador ${nota('Administrador') ? `envió la nota «${limpio(nota('Administrador'))}»` : 'no registró una nota observable'}; hubo ${['Veterinario', 'Administrador'].filter(rol => solicitudes.some(x => x.rol === rol && x.metodo === 'GET' && x.ruta === `/prediccion/modelos/${id(rol === 'Veterinario' ? 'V1' : 'V1b')}`)).length} consultas de esas versiones con los roles respectivos.`
    : `El registro de V1 y V1b no se completó: V1 HTTP ${http(post('V1'))}, V1b HTTP ${http(post('V1b'))}; los pasos posteriores solo se intentaron si hubo identificadores.`;
  const hecho147 = consultas('Administrador').length || consultas('Veterinario').length
    ? `Sobre V2, id ${id('V2')}, se registraron ${pasos147.filter(x => x.metodo === 'GET' && x.ruta === `/prediccion/modelos/${id('V2')}`).length} consultas de la versión, ${pasos147.filter(x => x.metodo === 'GET' && x.ruta.startsWith('/prediccion/auditoria')).length} del historial, ${intentos147.length} intentos de cambiar el estado a APROBADO o intervenir el historial con PUT, PATCH y DELETE, y ${pasos147.filter(x => x.ruta.endsWith('/activar')).length} intentos de activación; participaron ${[...new Set(pasos147.map(x => x.rol))].join(' y ')}.`
    : 'No se pudieron ejecutar las consultas ni los intentos de cambio de V2 porque faltó una versión identificable.';
  const hecho148 = post('V3')
    ? `Se registró V3, id ${id('V3')}, del mismo tipo que ${usada ?? 'la versión con nota'}; ${consulta148 ? `después el Administrador consultó ${usada}, id ${id(usada)}, con la nota «${limpio(nota(usada === 'V1b' ? 'Administrador' : 'Veterinario') ?? 'sin nota registrada')}»` : 'no quedó una consulta posterior de una versión con nota'}, sin activarla.`
    : 'No se registró V3; faltó la comparación posterior con una versión aprobada y con nota.';
  const hecho149 = listas('Administrador').length || listas('Veterinario').length
    ? `Se ejecutaron ${listas('Administrador').length} consultas de listado con Administrador y ${listas('Veterinario').length} con Veterinario (${filtrosPorRol('Administrador')}; ${filtrosPorRol('Veterinario')}); se buscaron los ids ${['V1', 'V1b', 'V2', 'V3'].map(id).join(', ')}.`
    : 'No se ejecutaron consultas del listado; faltan las respuestas de ambos roles y de los cuatro filtros.';
  const intento = CASOS.map((caso, i) => {
    const estado = r.casos[caso].estado;
    const causa = limpio(r.casos[caso].motivo).replaceAll('_', ' ').replace(/\bnull\b/gi, 'sin respuesta');
    const incidencia = r.incidencias.find(x => x.casos.includes(caso))?.id;
    const aprobado = [
      'Ambos roles pudieron guardar y consultar sus notas; las dos versiones conservaron el estado APROBADO.',
      'Las métricas y el historial fueron consultables; se rechazaron cambios y activación, y las transiciones permanecieron iguales. Los eventos de consulta creados por las propias consultas GET de auditoría realizadas en este RUN no cuentan como intervención.',
      'La versión con nota siguió APROBADA y sin activación automática; ese estado conserva su elegibilidad para activación. No se ejecutó una activación en este caso.',
      'Ambos roles recibieron filtros acotados y las cuatro versiones del RUN tuvieron estado y métricas completas. Los datos heredados incompletos son una observación, no un defecto demostrado del listado.'
    ][i];
    const porQue = estado === 'APROBADO' ? aprobado
      : estado === 'RECHAZADO' ? `Se incumplió la comprobación: ${causa}; incidencia ${incidencia ?? 'pendiente de identificación'}.`
        : `Impidió concluir: ${causa}. Hace falta completar la comprobación pendiente con evidencia de API en un RUN autorizado.`;
    const descripciones = [
      [
        hecho146,
        'Las notas deben quedar asociadas y consultables, sin cambiar el estado, y ambos roles deben poder registrarlas (matriz G056, punto 1; RF-69 v2.1, líneas 1792, 1968, 2045-2063 y 2369-2376).',
        `V1 y V1b: registro HTTP ${http(post('V1'))}/${http(post('V1b'))}; notas HTTP ${solicitudes.filter(x => x.metodo === 'PATCH' && x.ruta.endsWith('/notas')).map(http).join('/') || 'sin envíos'}; consultas HTTP ${['Veterinario', 'Administrador'].map(rol => http(solicitudes.find(x => x.rol === rol && x.metodo === 'GET' && x.ruta === `/prediccion/modelos/${id(rol === 'Veterinario' ? 'V1' : 'V1b')}`))).join('/')}; estados ${['V1', 'V1b'].map(dato => post(dato)?.estado ?? 'sin dato').join('/')}; notas consultadas ${['Veterinario', 'Administrador'].map(rol => solicitudes.find(x => x.rol === rol && x.metodo === 'GET' && x.ruta === `/prediccion/modelos/${id(rol === 'Veterinario' ? 'V1' : 'V1b')}`)?.notas ? 'presentes' : 'ausentes').join('/')}.`
      ],
      [
        hecho147,
        'Deben poder consultarse métricas e historial, sin cambiar el estado, activar ni intervenir las transiciones (matriz G056, punto 2; RF-69 v2.1, líneas 1887-1891, 2048-2059, 2177-2181 y 2313-2315).',
        `V2: registro HTTP ${http(post('V2'))}, estado ${post('V2')?.estado ?? 'sin dato'}; por rol, consultas ${['Administrador', 'Veterinario'].map(rol => `${rol} ${consultas(rol).map(x => `${http(x)} ${x.estado ?? 'sin estado'}, métricas ${x.metricas_completas ? 'completas' : 'incompletas'}`).join('/') || 'sin respuesta'}, historial ${historial(rol).map(http).join('/') || 'sin respuesta'}, transiciones ${historial(rol).map(transiciones).join('/') || 'sin datos'}`).join('; ')}; cambios de versión e historial ${solicitudes.filter(x => ['PUT', 'PATCH', 'DELETE'].includes(x.metodo) && (x.ruta === `/prediccion/modelos/${id('V2')}` || x.ruta.startsWith('/prediccion/auditoria'))).map(http).join('/') || 'sin intentos'}; activación ${solicitudes.filter(x => x.ruta === `/prediccion/modelos/${id('V2')}/activar`).map(http).join('/') || 'sin intentos'}.`
      ],
      [
        hecho148,
        'La versión con nota debe permanecer APROBADA, sin activarse sola y disponible para activación (matriz G056, punto 3; RF-69 v2.1, líneas 1814-1832 y 2061-2068).',
        `V3: registro HTTP ${http(post('V3'))}, estado ${post('V3')?.estado ?? 'sin dato'}; consulta de ${usada ?? 'la versión con nota'} HTTP ${http(consulta148)}, estado ${consulta148?.estado ?? 'sin dato'}, en producción ${consulta148?.esta_produccion === false ? 'no' : consulta148?.esta_produccion === true ? 'sí' : 'sin dato'}, nota ${consulta148?.notas ? 'conservada' : 'sin dato'}.`
      ],
      [
        hecho149,
        'El listado debe devolver estado y métricas completas y acotar cada filtro (matriz G056, punto 4; RF-69 v2.1, líneas 2048-2051 y 2204-2223).',
        `Resultados sin filtro, por tipo, RECHAZADO y APROBADO, respectivamente: Administrador ${listaResumen('Administrador')}; Veterinario ${listaResumen('Veterinario')}. Versiones del RUN: ${resumenRun}; ${r.observaciones.some(x => x.startsWith('Datos heredados')) ? 'hubo datos heredados incompletos.' : 'sin observación de datos heredados.'}`
      ]
    ][i];
    return `### ${caso} — ${estado}\n**Qué se hizo:** ${descripciones[0]}\n**Qué se esperaba:** ${descripciones[1]}\n**Qué se observó:** ${descripciones[2]}\n**Por qué ${estado}:** ${porQue}`;
  });
  return `## Detalle por caso\n\n${intento.join('\n\n')}\n\n`;
}
function finalizar(c, r, secretos) {
  delete r._tokens; delete r._limite;
  r.incidencias = incidencias(r);
  r.evidencias.push('resultado.json', informe(c.version));
  r.oficial = CASOS.every(x => ['APROBADO', 'RECHAZADO'].includes(r.casos[x].estado))
    && !r.problemas_tecnicos.length && r.cierre.run.cierre_http === 200
    && r.cierre.rollback.verificado && r.evidencias.some(x => x.endsWith('.json') && x.startsWith('newman/'))
    && r.evidencias.filter(x => !['resultado.json', informe(c.version)].includes(x))
      .every(x => fs.existsSync(path.join(c.directorio, x)));
  r.consume_version = r.oficial;
  const esperados = [
    'Las notas quedan asociadas y consultables; el estado no cambia al registrarlas; ambos roles pueden hacerlo',
    'Puede consultar métricas e historial; no puede modificar el estado, activar ni intervenir el historial',
    'Permanece en APROBADO, no se activa sola y sigue disponible para activación',
    'Se devuelven estado y métricas completas y los filtros acotan correctamente el resultado'
  ];
  const filas = CASOS.map((x, i) => `| ${x} | ${IDS[i]} | ${esperados[i]} | ${r.casos[x].estado} | ${limpio(r.casos[x].motivo)} |`).join('\n');
  const estados = CASOS.map(x => r.casos[x].estado);
  const decision = estados.includes('RECHAZADO') ? 'RECHAZADO'
    : estados.every(x => x === 'APROBADO') ? 'APROBADO'
      : estados.includes('BLOQUEADO') ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
  const motivoDecision = decision === 'APROBADO'
    ? 'Ambos roles registran notas sin alterar el estado; una versión RECHAZADA solo admite consulta; la versión aprobada persiste sin activarse; el listado y sus filtros devuelven estado y métricas.'
    : `Comprobaciones pendientes o discrepantes: ${CASOS.filter(x => r.casos[x].estado !== 'APROBADO').map(x => `${x} ${r.casos[x].estado}`).join(', ')}.`;
  const filasDecision = CASOS.map((x, i) => `| ${x} | ${IDS[i]} | ${r.casos[x].estado} | ${limpio(r.casos[x].motivo)} |`).join('\n');
  const solicitudes = r.solicitudes.map(x => `| ${x.rol} | ${x.metodo} ${limpio(x.ruta)} | ${x.http ?? 'sin respuesta'} | ${x.eco ?? '—'} | ${x.id ?? '—'} | ${x.estado ?? '—'} | ${limpio(x.notas ?? '—')} | ${x.metricas_completas ?? '—'} | ${x.items?.length ?? '—'} | ${x.eventos?.length ?? '—'} |`).join('\n');
  const incid = r.incidencias.map(x => `### ${x.id}: ${x.titulo}\n\nCasos ${x.casos.join(', ')}. Requisito: ${x.requisito}. Pasos: ${x.pasos}. Obtenido: ${x.obtenido}. Hipótesis: ${x.hipotesis}. Severidad ${x.severidad} por ${x.impacto}; certeza ${x.certeza}; atención inicial ${x.equipo_inicial} por ${x.fundamento}; causa raíz ${x.causa_raiz}.`).join('\n\n') || 'Ninguna incidencia de producto confirmada.';
  const candidatoOficial = r.oficial && r.ambiente === 'TEST';
  const md = `# TC-M04-G056 — ${decision}\n\n`+
    `Grupo G056; casos ${CASOS.join(', ')}; RF-69 v2.1; V${c.version}; RUN ${c.runId}; ambiente ${r.ambiente}; autorización ${limpio(c.referencia)}; código local consultado daefc3a5 (despliegue no verificado); Newman ${r.herramientas.newman.version ?? 'no disponible'}; Cypress no aplica: ${r.cypress.total_pruebas} ejecuciones.\n\n`+
    `## Decisión del caso\n\nAgrupado **TC-M04-G056 (RF-69)**; casos originales **${CASOS.join(', ')}**.\n\n`+
    `**Decisión: ${decision}.** ${motivoDecision}\n\n`+
    `| Caso | Comprobación | Decisión | Motivo breve |\n|---|---|---|---|\n${filasDecision}\n\n`+
    `**RUN oficial: ${candidatoOficial ? 'pendiente de clasificación del registro QA; DELETE '+(r.cierre.run.cierre_http ?? 'sin respuesta')+', rollback '+(r.cierre.rollback.verificado ? 'informado por el sandbox' : 'no verificado') : 'no; ambiente '+r.ambiente}.**\n\n`+
    `**Qué falta:** ${candidatoOficial && decision === 'APROBADO' ? 'clasificación del registro QA; revisar las observaciones de datos heredados en TEST.' : 'resolver los casos pendientes o discrepantes y obtener una decisión oficial autorizada.'}\n\n`+
    detallePorCaso(r)+
    `### Esperado y observado por caso\n\n| Caso | Comprobación | Esperado | Estado | Observado y motivo |\n|---|---|---|---|---|\n${filas}\n\n`+
    `## Solicitudes API\n\n| Rol | Operación | HTTP | Eco RUN | ID | Estado | Notas observadas | Siete métricas | Items | Eventos |\n|---|---|---:|---|---:|---|---|---|---:|---:|\n${solicitudes}\n\n`+
    `## Incidencias de producto\n\n${incid}\n\n## Observaciones y problemas técnicos\n\n`+
    `${r.observaciones.map(x => '- '+String(x).replace(/[\r\n]+/g, ' ')).join('\n') || 'Sin observaciones.'}\n\n`+
    `${r.problemas_tecnicos.map(x => '- '+limpio(x)).join('\n') || 'Sin problemas técnicos.'}\n\n`+
    `## Evidencias y cierre\n\n${r.evidencias.map(x => '- '+x).join('\n')}\n\n`+
    `DELETE del RUN: HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. Rollback: ${r.cierre.rollback.verificado ? 'confirmación informada por sandbox' : 'NO_VERIFICADO'}; ${r.cierre.rollback.motivo}. Sin lectura posterior de BD. ONNX y correo: no revertidos por DELETE.\n\n`+
    `## Conclusión y acción\n\n${r.oficial ? 'Someter este resultado al registro QA y revisar las observaciones y efectos persistentes del cierre.' : 'Resolver el impedimento técnico y decidir un reintento autorizado del mismo V1.'}\n`;
  fs.writeFileSync(path.join(c.directorio, informe(c.version)), sanearArtefacto(md, secretos), 'utf8');
  guardar(path.join(c.directorio, 'resultado.json'), JSON.parse(sanearArtefacto(JSON.stringify(r), secretos)));
}

export async function evaluar(c, { env, ensayo = false }) {
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G056', run_id: c.runId, version: c.version,
    intento: c.intento ?? null, operacion: c.operacion, autorizacion: c.referencia,
    ambiente: ensayo ? 'LOOPBACK_LOCAL' : 'TEST', oficial: false, consume_version: false,
    casos: Object.fromEntries(CASOS.map(x => [x, { estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación' }])),
    comprobaciones: CASOS.map((caso, i) => ({ caso, id: IDS[i], fuente: 'API', tipo: 'ASSERT',
      estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación', evidencia: null })),
    presupuesto: PRESUPUESTO, herramientas: { newman: versionNewman() }, solicitudes: [],
    cypress: { total_pruebas: 0 }, evidencias: [], incidencias: [], problemas_tecnicos: [], observaciones: [],
    cierre: { run: { cierre_http: null }, rollback: { verificado: false,
      motivo: 'Sin cierre ni comprobación posterior de BD' } }, _limite: Date.now() + PRESUPUESTO.duracion_segundos * 1000,
    _tokens: {} };
  const secretos = [env.QA_SANDBOX_SECRET, env.RF71_INTERNAL_KEY, env.QA_ADMIN_EMAIL,
    env.QA_ADMIN_PASSWORD, env.QA_VETERINARIO_EMAIL, env.QA_COMMON_PASSWORD].filter(Boolean);
  let temporal = null, tocado = false;
  try {
    const pre = preflight(c, env, ensayo); guardar(path.join(c.directorio, 'preflight.json'), pre);
    r.evidencias.push('preflight.json');
    if (!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
    if (!r.herramientas.newman.ok) throw Error('NEWMAN_NO_DISPONIBLE');
    for (const [rol, email, pass] of [['admin', env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD],
      ['vet', env.QA_VETERINARIO_EMAIL, env.QA_COMMON_PASSWORD]]) {
      const x = await pedir(r, api, 'POST', '/sesiones/', { cuerpo: { correo_electronico: email, contrasena: pass } });
      if (x.http !== 200 || !x.cuerpo?.token) throw Error(`LOGIN_${rol.toUpperCase()}_NO_VERIFICABLE_HTTP_${x.http}`);
      r._tokens[rol] = x.cuerpo.token; secretos.push(x.cuerpo.token);
    }
    tocado = true;
    const opts = token => ({ token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId });
    const catalogo = await pedir(r, api, 'GET', '/configuracion/variables-ambientales', opts(r._tokens.admin));
    const variables = catalogo.cuerpo?.items?.map(x => x.id_variable_ambiental).filter(Number.isSafeInteger) ?? [];
    if (catalogo.http !== 200 || !catalogo.eco || !variables.length) throw Error(`CATALOGO_I3P1_NO_VERIFICABLE_HTTP_${catalogo.http}`);
    temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g056-newman-'));
    const archivo = path.join(temporal, 'g056.onnx'); fs.writeFileSync(archivo, onnxMinimo());
    const datos = escenarios({ variable: variables[0], hash: sha256(fs.readFileSync(archivo)),
      dataset: sha256(Buffer.from('G056 dataset QA RF-71')), archivo });
    const post = [];
    const registrar = async i => { post[i] = await registrarNewman(r, c, api, env, datos[i], i, temporal, secretos); return post[i]; };
    await registrar(0); await registrar(1); await registrar(2);
    if (post.some(x => x.http === 403)) throw Error('POST_403_CLAVE');
    const id1 = idVersion(post[0].cuerpo), id1b = idVersion(post[1].cuerpo);
    const id2 = idVersion(post[2].cuerpo);
    const notas = [], lecturas = [];
    for (const [rol, token, id] of [['Veterinario', r._tokens.vet, id1], ['Administrador', r._tokens.admin, id1b]]) {
      if (id == null) { notas.push(null); lecturas.push(null); continue; }
      const texto = `G056 ${c.runId} ${rol} nota clínica`;
      notas.push(await pedir(r, api, 'PATCH', `/prediccion/modelos/${id}/notas`,
        { ...opts(token), estadoAntes: 'APROBADO', cuerpo: { notas_validacion: texto } }));
      lecturas.push(await pedir(r, api, 'GET', `/prediccion/modelos/${id}`, opts(token)));
    }
    const c146 = [];
    for (const [i, nombre] of [[0, 'V1'], [1, 'V1b']]) {
      c146.push(falta(post[i], `${nombre} POST`), defecto(post[i].http === 201 && post[i].eco
        && post[i].cuerpo?.estado_version === 'APROBADO',
      `${nombre} POST HTTP ${post[i].http}, estado ${post[i].cuerpo?.estado_version}`));
    }
    c146.push(defecto(id1 != null && id1b != null && String(id1) !== String(id1b),
      'V1 y V1b deben tener identificadores distintos'));
    for (let i = 0; i < 2; i++) {
      c146.push(falta(notas[i], `PATCH notas ${i}`), falta(lecturas[i], `GET notas ${i}`));
      c146.push(defecto(notas[i]?.http >= 200 && notas[i]?.http < 300 && notas[i]?.eco,
        `${i ? 'Administrador' : 'Veterinario'} PATCH notas HTTP ${notas[i]?.http}`));
      const esperada = `G056 ${c.runId} ${i ? 'Administrador' : 'Veterinario'} nota clínica`;
      c146.push(defecto(lecturas[i]?.http === 200 && lecturas[i]?.eco && lecturas[i]?.cuerpo?.estado_version === 'APROBADO'
        && lecturas[i]?.cuerpo?.notas_validacion?.includes(esperada),
      `${i ? 'Administrador' : 'Veterinario'} GET estado ${lecturas[i]?.cuerpo?.estado_version}, notas ${lecturas[i]?.cuerpo?.notas_validacion ?? 'ausentes'}`));
    }
    decidirCon(r, 0, c146, `V1 ${id1} y V1b ${id1b}: POST 201 APROBADO; PATCH notas ${notas.map(x => x?.http ?? 'sin respuesta').join('/')}; GET ${lecturas.map(x => x?.http ?? 'sin respuesta').join('/')}, estado APROBADO y notas asociadas`);
    const intentos147 = [];
    if (id2 != null) for (const [rol, token] of [['Administrador', r._tokens.admin], ['Veterinario', r._tokens.vet]]) {
      const o = opts(token), base = `/prediccion/modelos/${id2}`;
      const aud = `/prediccion/auditoria?id_referencia=${id2}&por_pagina=50`;
      const antes = await pedir(r, api, 'GET', base, o);
      const histAntes = await pedir(r, api, 'GET', aud, o);
      const put = await pedir(r, api, 'PUT', base, { ...o, estadoAntes: 'RECHAZADO', cuerpo: { estado_version: 'APROBADO' } });
      const patch = await pedir(r, api, 'PATCH', base, { ...o, estadoAntes: 'RECHAZADO', cuerpo: { estado_version: 'APROBADO' } });
      const activar = await pedir(r, api, 'POST', `${base}/activar`, { ...o, estadoAntes: 'RECHAZADO' });
      const hput = await pedir(r, api, 'PUT', aud, { ...o, cuerpo: { estado_version: 'APROBADO' } });
      const hpatch = await pedir(r, api, 'PATCH', aud, { ...o, cuerpo: { estado_version: 'APROBADO' } });
      const hdelete = await pedir(r, api, 'DELETE', aud, o);
      const despues = await pedir(r, api, 'GET', base, o);
      const histDespues = await pedir(r, api, 'GET', aud, o);
      intentos147.push({ rol, antes, histAntes, put, patch, activar, hput, hpatch, hdelete, despues, histDespues });
    }
    const c147 = [falta(post[2], 'V2 POST'), defecto(post[2].http === 200 && post[2].eco && post[2].cuerpo?.estado_version === 'RECHAZADO',
      `V2 POST HTTP ${post[2].http}, estado ${post[2].cuerpo?.estado_version}`)];
    for (const x of intentos147) {
      for (const [k, v] of Object.entries(x)) if (k !== 'rol') c147.push(falta(v, `${x.rol} ${k}`));
      c147.push(defecto(x.antes.http === 200 && x.antes.eco && metricasCompletas(x.antes.cuerpo)
        && x.antes.cuerpo?.estado_version === 'RECHAZADO', `${x.rol} GET inicial: HTTP ${x.antes.http}, estado ${x.antes.cuerpo?.estado_version}, métricas ${metricasCompletas(x.antes.cuerpo)}`));
      c147.push(defecto(x.histAntes.http === 200 && x.histAntes.eco
        && Array.isArray(x.histAntes.cuerpo?.items) && x.histAntes.cuerpo.items.length > 0
        && x.histAntes.cuerpo.items.every(y => String(y.id_referencia) === String(id2)),
        `${x.rol} historial inicial HTTP ${x.histAntes.http}, eventos ${x.histAntes.cuerpo?.items?.length ?? 'ausentes'}`));
      for (const k of ['put', 'patch', 'hput', 'hpatch', 'hdelete']) c147.push(defecto(x[k].http >= 400 && x[k].http < 500,
        `${x.rol} ${k} aceptado o sin rechazo HTTP ${x[k].http}`));
      c147.push(defecto(x.activar.http === 409, `${x.rol} activar RECHAZADO HTTP ${x.activar.http}; E4 exige 409`));
      c147.push(defecto(x.despues.http === 200 && x.despues.eco && x.despues.cuerpo?.estado_version === 'RECHAZADO',
        `${x.rol} estado posterior ${x.despues.cuerpo?.estado_version}`));
      c147.push(defecto(x.histDespues.http === 200 && x.histDespues.eco
        && JSON.stringify(transiciones(x.histAntes)) === JSON.stringify(transiciones(x.histDespues)),
      `${x.rol} transiciones de historial alteradas: antes ${transiciones(x.histAntes).length} huella ${sha256(Buffer.from(JSON.stringify(transiciones(x.histAntes)))).slice(0, 12)}, después ${transiciones(x.histDespues).length} huella ${sha256(Buffer.from(JSON.stringify(transiciones(x.histDespues)))).slice(0, 12)}`));
    }
    decidirCon(r, 1, c147, `V2 ${id2} RECHAZADO; ambos roles: GET inicial/posterior 200, auditoría 200, PUT/PATCH versión y PUT/PATCH/DELETE auditoría 4xx, activar 409; transiciones ${intentos147.map(x => `${x.rol} ${transiciones(x.histAntes).length}/${transiciones(x.histDespues).length}`).join('; ')}`);
    await registrar(3);
    const version148 = [
      { nombre: 'V1', id: id1, rol: 'Veterinario', indice: 0 },
      { nombre: 'V1b', id: id1b, rol: 'Administrador', indice: 1 }
    ].find(v => post[v.indice].http === 201 && post[v.indice].eco
      && post[v.indice].cuerpo?.estado_version === 'APROBADO'
      && notas[v.indice]?.http >= 200 && notas[v.indice]?.http < 300 && notas[v.indice]?.eco
      && lecturas[v.indice]?.http === 200 && lecturas[v.indice]?.eco
      && lecturas[v.indice]?.cuerpo?.estado_version === 'APROBADO'
      && lecturas[v.indice]?.cuerpo?.notas_validacion?.includes(`G056 ${c.runId} ${v.rol} nota clínica`));
    r.observaciones.push(`TC-M04-148: versión usada ${version148?.nombre ?? 'ninguna'}; ${version148?.rol ?? 'sin nota registrada en V1 ni V1b'}`);
    const consulta148 = version148 ? await pedir(r, api, 'GET', `/prediccion/modelos/${version148.id}`, opts(r._tokens.admin)) : null;
    const comprobaciones148 = [falta(post[3], 'V3 POST'), falta(consulta148, `GET ${version148?.nombre} tras V3`),
      defecto(post[3].http === 201 && post[3].eco && post[3].cuerpo?.estado_version === 'APROBADO',
        `V3 POST HTTP ${post[3].http}, estado ${post[3].cuerpo?.estado_version}`),
      defecto(consulta148?.http === 200 && consulta148?.eco && consulta148?.cuerpo?.estado_version === 'APROBADO'
        && consulta148?.cuerpo?.esta_produccion === false
        && consulta148?.cuerpo?.notas_validacion?.includes(`G056 ${c.runId} ${version148?.rol} nota clínica`),
      `${version148?.nombre} tras V3: estado ${consulta148?.cuerpo?.estado_version}, producción ${consulta148?.cuerpo?.esta_produccion}, notas ${consulta148?.cuerpo?.notas_validacion ?? 'ausentes'}`)];
    if (version148) decidirCon(r, 2, comprobaciones148, `${version148.nombre} ${version148.id} con nota de ${version148.rol}: tras V3 POST ${post[3].http}, GET ${consulta148?.http}, estado ${consulta148?.cuerpo?.estado_version}, esta_produccion=${consulta148?.cuerpo?.esta_produccion}`);
    else decidir(r, 2, 'NO_CONCLUYENTE', 'Ni V1 ni V1b tienen evidencia de nota registrada en versión APROBADA para comprobar permanencia');
    const listas = [];
    for (const [rol, token] of [['Administrador', r._tokens.admin], ['Veterinario', r._tokens.vet]]) {
      for (const [nombre, qs, filtro, requeridos] of [
        ['sin_filtro', '', {}, [post[0].cuerpo, post[1].cuerpo, post[2].cuerpo, post[3].cuerpo]],
        ['tipo', '&tipo_modelo=MODELO_ESPECIES_GRANDES', { tipo: 'MODELO_ESPECIES_GRANDES' }, [post[0].cuerpo, post[1].cuerpo, post[2].cuerpo, post[3].cuerpo]],
        ['rechazado', '&estado=RECHAZADO', { estado: 'RECHAZADO' }, [post[2].cuerpo]],
        ['aprobado', '&estado=APROBADO', { estado: 'APROBADO' }, [post[0].cuerpo, post[1].cuerpo, post[3].cuerpo]]]) {
        const x = await pedir(r, api, 'GET', `/prediccion/modelos?limit=100&offset=0${qs}`, opts(token));
        listas.push({ rol, nombre, x, filtro, requeridos });
      }
    }
    const c149 = [];
    for (const l of listas) { c149.push(falta(l.x, `${l.rol} ${l.nombre}`));
      c149.push(defecto(l.requeridos.every(x => idVersion(x) != null)
        && coberturaListado(l.x, l.filtro, l.requeridos, l.nombre === 'sin_filtro'),
        `${l.rol} ${l.nombre}: ${diagnosticoListado(l.x, l.filtro, l.requeridos, l.nombre === 'sin_filtro')}`)); }
    const idsRun = new Set(post.map(x => String(idVersion(x.cuerpo))));
    const heredados = new Map();
    for (const l of listas.filter(x => x.nombre === 'sin_filtro')) for (const y of l.x.cuerpo?.items ?? []) {
      if (idsRun.has(String(idVersion(y)))) continue;
      const faltan = y.tipo_modelo == null ? 'tipo_modelo nulo'
        : y.paradigma === 'POBLACIONAL' ? y.metricas_poblacionales == null ? 'métricas poblacionales nulas' : null
          : !metricasCompletas(y) ? 'métricas almacenadas incompletas' : null;
      if (faltan) heredados.set(String(idVersion(y)), `versión ${idVersion(y)} ${y.tipo_modelo ?? 'sin tipo'} ${y.estado_version ?? 'sin estado'}: ${faltan}`);
    }
    if (heredados.size) r.observaciones.push(`Datos heredados inconsistentes en TEST: ${[...heredados.values()].join('; ')}`);
    decidirCon(r, 3, c149, `Administrador/Veterinario: sin filtro ${listas.filter(x => x.nombre === 'sin_filtro').map(x => x.x.cuerpo?.items?.length ?? 'sin items').join('/')}, tipo ${listas.filter(x => x.nombre === 'tipo').map(x => x.x.cuerpo?.items?.length ?? 'sin items').join('/')}, RECHAZADO ${listas.filter(x => x.nombre === 'rechazado').map(x => x.x.cuerpo?.items?.length ?? 'sin items').join('/')}, APROBADO ${listas.filter(x => x.nombre === 'aprobado').map(x => x.x.cuerpo?.items?.length ?? 'sin items').join('/')}; V1/V1b/V2/V3 presentes con estado y métricas`);
    if (post.every(x => x.http >= 500)) throw Error('POST_5XX_SISTEMICO');
    if (post.every(x => x.http == null)) throw Error('POST_SIN_RESPUESTA_SISTEMICO');
  } catch (e) {
    const motivo = limpio(e.message); r.problemas_tecnicos.push(motivo);
    const estado = /403|5XX|LOGIN|CATALOGO/.test(motivo) ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
    CASOS.forEach((caso, i) => { if (r.casos[caso].motivo === 'Sin comprobación') decidir(r, i, estado, motivo); });
    if (/POST_5XX_SISTEMICO/.test(motivo)) CASOS.forEach((_, i) => decidir(r, i, 'BLOQUEADO', motivo));
    if (/POST_SIN_RESPUESTA_SISTEMICO/.test(motivo)) CASOS.forEach((_, i) => decidir(r, i, 'NO_CONCLUYENTE', motivo));
  } finally {
    if (tocado) {
      const cierre = await pedir(r, api, 'DELETE', `/test-control/runs/${encodeURIComponent(c.runId)}`,
        { secreto: env.QA_SANDBOX_SECRET });
      r.cierre.run.cierre_http = cierre.http;
      r.cierre.rollback.verificado = cierre.http === 200 && /rollback|cerrad/i.test(JSON.stringify(cierre.cuerpo ?? {}));
      r.cierre.rollback.motivo = r.cierre.rollback.verificado
        ? 'Sandbox informó cierre; rollback de BD sin lectura posterior' : `DELETE HTTP ${cierre.http}; rollback no acreditado`;
    }
    if (temporal) { if (!path.resolve(temporal).startsWith(path.resolve(os.tmpdir()) + path.sep))
      throw Error('TEMP_FUERA_RAIZ'); fs.rmSync(temporal, { recursive: true, force: true }); }
    finalizar(c, r, secretos);
  }
  return r;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
  else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
  else try {
    const c = contextoEjecucion(process.argv.slice(2), { grupo: 'G056', casos: CASOS, directorio: DIR });
    const r = await evaluar(c, { env: leerEnv() });
    console.log(JSON.stringify({ run_id: r.run_id, casos: r.casos, oficial: r.oficial }));
    if (!r.oficial) process.exitCode = 2;
  } catch (e) { console.error(`G056: ${limpio(e.message)}`); process.exitCode = 2; }
}
