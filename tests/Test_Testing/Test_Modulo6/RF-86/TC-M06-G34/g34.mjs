#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { CASOS, IDS, PRESUPUESTO, CAPACIDADES, casoCompleto, evaluarA, evaluarB, costosDe,
  mismosCostos, soloNuevo, igualMonto, oficialidadLocal, medicionesConEstado } from './lib/g34_core.mjs';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const require = createRequire(import.meta.url);
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION = path.join(DIR, 'G34.postman_collection.json');
const ARCHIVOS = ['g34.mjs', 'G34.postman_collection.json', 'g34.cy.js', 'g34.cypress.config.cjs', 'README.md', 'lib/g34_core.mjs',
  'pruebas/g34_env.test.mjs', 'pruebas/g34_ensayo.mjs', 'pruebas/registro_qa.mjs',
  'pruebas/newman_hijo.mjs'];
const guardar = (p, x) => fs.writeFileSync(p, JSON.stringify(x, null, 2), 'utf8');
const limpio = x => String(x ?? '').replace(/[\r\n|]/g, ' ').slice(0, 300);
const esc = x => String(x).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
export function sanear(x, secretos = []) {
  let s = String(x);
  for (const v of secretos.filter(v => typeof v === 'string' && v.length > 3)) s = s.split(v).join('[REDACTADO]');
  return s.replace(/eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}/g, '[JWT_REDACTADO]')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[CORREO_REDACTADO]');
}
function cuerpoErrorSaneado(cuerpo, secretos = []) {
  const limpiar = (x, profundidad = 0) => {
    if (typeof x === 'string') return sanear(x, secretos).slice(0, 300);
    if (typeof x === 'number' || typeof x === 'boolean' || x === null) return x;
    if (profundidad >= 3) return '[OMITIDO]';
    if (Array.isArray(x)) return x.slice(0, 10).map(v => limpiar(v, profundidad + 1));
    if (!x || typeof x !== 'object') return null;
    return Object.fromEntries(Object.entries(x).slice(0, 20).map(([k, v]) => [k.slice(0, 60),
      /token|secret|password|contrasena|cookie|jwt|serial|authorization|correo|email|telefono|documento|numero_id_tributaria/i.test(k)
        ? '[REDACTADO]' : limpiar(v, profundidad + 1)]));
  };
  return JSON.stringify(limpiar(cuerpo)).slice(0, 1200);
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
function newmanDir() {
  try { return path.dirname(require.resolve('newman/package.json', { paths: [RAIZ] })); }
  catch {
    const p = path.join(path.dirname(process.execPath), 'node_modules', 'newman', 'package.json');
    return fs.existsSync(p) ? path.dirname(p) : null;
  }
}
function newmanVersion() {
  try { return require(path.join(newmanDir(), 'package.json')).version; }
  catch { return null; }
}
export function comprobar() {
  const faltantes = ARCHIVOS.filter(x => !fs.existsSync(path.join(DIR, x)));
  let coleccion = false;
  try {
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    coleccion = col.item?.length === 2 && col.item.every((x, i) => x.name === IDS[i] && x.request.method === 'GET');
  } catch { /* colección inválida */ }
  const markdownSuperior = fs.existsSync(path.join(DIR, 'Resultados')) &&
    fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const ok = !faltantes.length && coleccion && !markdownSuperior && PRESUPUESTO.timeout_post_ms === 120000;
  console.log(JSON.stringify({ grupo: 'G34', ok, faltantes, coleccion, markdown_superior: markdownSuperior,
    newman_local: !!newmanVersion(), presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}
export function contexto(args) {
  const v = k => args.includes(k) ? args[args.indexOf(k) + 1] : undefined;
  const operacion = v('--operacion'), version = Number(v('--version')), intento = Number(v('--intento')),
    runId = v('--run-id'), referencia = v('--autorizacion'), archivo = v('--contexto');
  if (!CAPACIDADES.operaciones.includes(operacion) || !Number.isInteger(version) || version < 1 || version > 99 ||
      !Number.isInteger(intento) || intento < 1 || !referencia || !archivo ||
      !new RegExp(`^RUN-G34-V${version}-\\d{8}-\\d{6}$`).test(runId ?? '')) throw Error('Contexto incompleto');
  const destino = path.join(DIR, ...(version === 1 ? ['Resultados', runId] : [`EvaluacionV${version}`, 'Resultados', runId]));
  const ruta = path.resolve(archivo);
  if (path.dirname(ruta) !== destino || path.basename(ruta) !== 'contexto_operacion.json') throw Error('Contexto fuera del RUN');
  const c = JSON.parse(fs.readFileSync(ruta, 'utf8'));
  if (c.grupo !== 'G34' || c.run_id !== runId || c.version !== version || c.intento !== intento ||
      c.operacion !== operacion.toUpperCase() || c.referencia !== referencia ||
      JSON.stringify(c.casos) !== JSON.stringify(CASOS) ||
      (version > 1 && !(operacion === 'reevaluar' && c.version_anterior === version - 1 && c.alcance_reevaluacion ||
        operacion === 'reintentar' && (c.version_anterior === null || c.version_anterior === version - 1) &&
        typeof c.alcance_reevaluacion?.motivo === 'string' && c.alcance_reevaluacion.motivo.trim())) ||
      (version === 1 && operacion === 'reevaluar')) throw Error('Contexto incoherente');
  return { operacion, version, intento, runId, referencia, directorio: destino, ensayo: false };
}
export function preflight(c, env, n = newmanVersion()) {
  const barreras = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_CONTADOR_EMAIL', 'QA_CONTADOR_PASSWORD',
    'QA_ADMIN_EMAIL', 'QA_ADMIN_PASSWORD']
    .filter(k => !String(env[k] ?? '').trim());
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (c.ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(String(env.SIGAB_API_TEST_BASE))
    : String(env.SIGAB_API_TEST_BASE).replace(/\/+$/, '') !== API) barreras.push('API_NO_CANONICA');
  if (!n) barreras.push('NEWMAN_NO_DISPONIBLE');
  return { grupo: 'G34', run_id: c.runId, fase: 'PREFLIGHT_LOCAL', ok: !barreras.length,
    barreras, presupuesto: PRESUPUESTO, herramientas: { node: process.version, newman: n },
    efectos: ['Dos logins fuera del RUN', 'Hasta tres eventos M02 y tres procesamientos M06',
      'Un PUT de costos a 100 %, restauración explícita y una reserva condicionada por lectura discrepante',
      'Cypress antes de restaurar y cerrar; Newman con exportación temporal',
      'DELETE con secreto y lecturas poscierre; HTTP 200 solo no prueba rollback'] };
}
export async function pedir(r, api, metodo, ruta, { token, secreto, runId, cuerpo, caso, timeout, auxiliar = false } = {}) {
  if (r.solicitudes.length >= PRESUPUESTO.solicitudes_totales && metodo !== 'DELETE')
    return { http: null, cuerpo: null, eco: false, fallo: 'PRESUPUESTO_AGOTADO' };
  const fila = { caso: caso ? casoCompleto(caso) : null, metodo, ruta: ruta.split('?')[0], http: null };
  r.solicitudes.push(fila);
  const inicio = Date.now();
  try {
    if (inicio > r._limite && metodo !== 'DELETE') throw Error('DURACION_EXCEDIDA');
    const res = await fetch(api + ruta, { method: metodo, redirect: 'manual',
      headers: { ...(cuerpo ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(runId ? { 'X-Test-Run-Id': runId, 'X-Zona-Horaria': 'America/Bogota' } : {}),
        ...(secreto ? { 'X-Sandbox-Secret': secreto } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      signal: AbortSignal.timeout(metodo === 'DELETE' ? (timeout ?? PRESUPUESTO.timeout_ms) :
        Math.max(1, Math.min(timeout ?? (metodo === 'POST' ? PRESUPUESTO.timeout_post_ms : PRESUPUESTO.timeout_ms), r._limite - inicio))) });
    const b = await res.json().catch(() => null);
    fila.http = res.status; fila.duracion_ms = Date.now() - inicio;
    fila.eco = runId ? res.headers.get('x-test-run-id') === runId : null;
    fila.codigo = limpio(sanear(b?.error_code ?? b?.code ?? '', [token, secreto, ...(r._secretos ?? [])]));
    if (res.status >= 400) fila.cuerpo_saneado = cuerpoErrorSaneado(b, [token, secreto, ...(r._secretos ?? [])]);
    r._seguidos5xx = auxiliar ? 0 : res.status >= 500 ? r._seguidos5xx + 1 : 0;
    if (res.status === 403 || r._seguidos5xx >= 3) r._corte = true;
    return { http: res.status, cuerpo: b, eco: fila.eco, fila };
  } catch (e) {
    fila.duracion_ms = Date.now() - inicio;
    fila.fallo = e.name === 'TimeoutError' || e.name === 'AbortError' ? 'TIMEOUT' : 'SIN_RESPUESTA';
    return { http: null, cuerpo: null, eco: false, fallo: fila.fallo, fila };
  }
}
const id = x => Number.isInteger(Number(x)) && Number(x) > 0 ? Number(x) : null;
const fecha = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
const nombreInforme = v => v === 1 ? 'TC-M06-G34_resultado.md' : `TC-M06-G34_reevaluacion_V${v}.md`;
export function preciosVigentes(items, especie, hoy = fecha()) {
  const lista = items.filter(p => id(p.id_especie) === id(especie) && p.categoria === 'PESO_KG' && p.fecha_vigencia <= hoy);
  for (const fuente of ['MERCADO_ACTIVO', 'UPRA', 'ESTIMADA']) {
    const ultimo = lista.filter(p => p.fuente === fuente).sort((a, b) =>
      String(b.fecha_vigencia).localeCompare(String(a.fecha_vigencia)) || id(b.id_precio_mercado) - id(a.id_precio_mercado))[0];
    if (ultimo && (!ultimo.fecha_vencimiento || ultimo.fecha_vencimiento >= hoy)) return ultimo;
  }
  return null;
}
export function periodoDestino(periodos, nit, hoy = fecha()) {
  if (!nit) return { motivo: 'sin titular tributario en detalle financiero' };
  const propios = periodos.filter(p => String(p.numero_id_tributaria) === String(nit));
  const actual = propios.find(p => p.fecha_inicio <= hoy && p.fecha_fin >= hoy);
  if (actual?.estado === 'ABIERTO') return { periodo: actual };
  return { motivo: actual ? `período que contiene hoy ${actual.estado}` : 'sin período que contenga hoy' };
}
function ultimoCalculo(detalle) {
  return (detalle?.calculos ?? []).filter(x => x.estado === 'CALCULADO' && x.json_metodo_costo?.es_producto !== true)
    .sort((a, b) => String(b.fecha_calculo).localeCompare(String(a.fecha_calculo)) ||
      id(b.id_calculo_valor_razonable) - id(a.id_calculo_valor_razonable))[0] ?? null;
}
function estadoRespuesta(x) {
  if (x.http == null) return ['NO_CONCLUYENTE', 'Solicitud sin respuesta; no se reintentó.'];
  if (x.http >= 500) return ['BLOQUEADO', `HTTP ${x.http} técnico; no se reintentó.`];
  if (x.http === 403) return ['BLOQUEADO', 'HTTP 403 de autorización o sandbox.'];
  if (x.http >= 400) return ['BLOQUEADO', `Precondición no satisfecha: HTTP ${x.http}, código ${x.fila?.codigo || 'sin código'}.`];
  if (!x.eco) return ['NO_CONCLUYENTE', 'Respuesta sin eco del RUN.'];
  return null;
}
function casoRegistro(caso, estado, motivo, extra = {}) {
  return { ...extra, caso: casoCompleto(caso), estado, motivo: limpio(motivo) };
}
const avisoNic41 = x => String(x?.mensaje ?? '').startsWith('Hay un nuevo precio de mercado vigente.');
async function bandejaPropia(r, api, token, runId = null, secreto = null) {
  const corte = r._corte, seguidos5xx = r._seguidos5xx;
  const x = await pedir(r, api, 'GET', '/notificaciones?pagina=1&tamano=50',
    { token, runId, secreto });
  r._corte = corte; r._seguidos5xx = seguidos5xx;
  if (x.http !== 200 || (runId && !x.eco) || !Array.isArray(x.cuerpo?.items)) return null;
  return x.cuerpo.items;
}

const CASO = CASOS[0];
const informeNombre = v => v === 1 ? 'TC-M06-G34_resultado.md' : 'TC-M06-G34_reevaluacion_V' + v + '.md';
const ids = (lista, clave) => lista.map(x => String(x[clave]));
const recencia = x => ({ id: id(x?.id_notificacion) });
const compararRecencia = (a, b) => a.id - b.id;
const paginaValida = (x, campo, total) => x?.http === 200 && x.eco !== false &&
  Array.isArray(x.cuerpo?.[campo]) && Number.isSafeInteger(x.cuerpo?.[total]) && x.cuerpo[total] >= 0;

async function leerAuditoria(r, api, opciones, aid, pid) {
  const ruta = '/finanzas/auditoria?id_activo_biologico=' + aid + '&id_periodo_contable=' + pid + '&formato=TECNICO&tamano=500';
  const eventos = [], vistos = new Set();
  for (let pagina = 1; !r._corte; pagina++) {
    const x = await pedir(r, api, 'GET', ruta + '&pagina=' + pagina, opciones);
    if (!paginaValida(x, 'eventos', 'total_registros')) return { completa: false, eventos };
    for (const e of x.cuerpo.eventos) {
      const clave = id(e.id_evento);
      if (!clave || vistos.has(clave)) return { completa: false, eventos };
      vistos.add(clave); eventos.push(e);
    }
    if (eventos.length === Number(x.cuerpo.total_registros)) return { completa: true, eventos };
    if (!x.cuerpo.eventos.length || eventos.length > Number(x.cuerpo.total_registros)) break;
  }
  return { completa: false, eventos };
}

async function leerBandeja(r, api, opciones, lineaBase = undefined) {
  const items = [], vistos = new Set();
  for (let pagina = 1; !r._corte; pagina++) {
    const x = await pedir(r, api, 'GET', '/notificaciones?pagina=' + pagina + '&tamano=50', opciones);
    if (!paginaValida(x, 'items', 'total')) return { completa: false, items };
    const paginaItems = x.cuerpo.items;
    for (const aviso of paginaItems) {
      const clave = recencia(aviso);
      if (!clave.id || vistos.has(clave.id)) return { completa: false, items };
      vistos.add(clave.id);
      if (lineaBase && compararRecencia(clave, lineaBase) <= 0)
        return { completa: true, items, lineaBase };
      items.push(aviso);
    }
    if (lineaBase === undefined && pagina === 1) return {
      completa: true, items, lineaBase: paginaItems.length ? recencia(paginaItems[0]) : null };
    if (items.length >= Number(x.cuerpo.total)) return { completa: true, items, lineaBase };
    if (!paginaItems.length) break;
  }
  return { completa: false, items, lineaBase };
}

async function instantanea(r, api, opciones, aid, pid, bandejaBase = null) {
  const rutas = [
    '/finanzas/periodos/' + pid + '/variaciones',
    '/finanzas/lineas?id_periodo_contable=' + pid,
    '/finanzas/periodos/' + pid + '/mediciones',
    '/finanzas/periodos/' + pid + '/eventos-pendientes',
    '/finanzas/activos/' + aid,
  ];
  const respuestas = [];
  for (const ruta of rutas) {
    if (r._corte) break;
    respuestas.push(await pedir(r, api, 'GET', ruta, opciones));
  }
  if (respuestas.length !== rutas.length) return { completa: false, motivo: 'Corte antes de completar las lecturas.' };
  const [v, l, m, ep, d] = respuestas;
  const a = await leerAuditoria(r, api, opciones, aid, pid);
  const b = await leerBandeja(r, api, opciones, bandejaBase ? bandejaBase.bandejaLineaBase : undefined);
  if (![v, l, m, ep, d].every(x => x.http === 200 && x.eco !== false) || !Array.isArray(v.cuerpo) ||
      !Array.isArray(l.cuerpo) || !Array.isArray(m.cuerpo) || !Array.isArray(ep.cuerpo) || !Array.isArray(d.cuerpo?.calculos) ||
      !Array.isArray(d.cuerpo?.mediciones) || !a.completa || !b.completa)
    return { completa: false, motivo: 'Lectura pública incompleta, 5xx, sin eco o página truncada.',
      http: respuestas.map(x => x.http), rutas, auditoriaCompleta: a.completa, bandejaCompleta: b.completa };
  const calculos = d.cuerpo.calculos;
  return { completa: true, activo: aid, periodo: pid, variaciones: v.cuerpo, lineas: l.cuerpo,
    eventosPendientes: ep.cuerpo,
    mediciones: medicionesConEstado(d.cuerpo.mediciones, m.cuerpo, aid),
    calculos, auditoria: a.eventos, bandeja: b.items, bandejaLineaBase: b.lineaBase,
    auditoriaCompleta: a.completa, bandejaCompleta: b.completa,
    calculoUltimo: ultimoCalculo(d.cuerpo) };
}

async function comprobarRollback(r, api, env, token, tokenM02, datos) {
  if (r.cierre.run.cierre_http !== 200) return { verificado: false, motivo: 'DELETE no confirmó cierre.' };
  const opt = { token }, optM02 = { token: tokenM02 };
  const { aid, pid, eventos } = datos;
  const base = datos.rollbackBase ?? datos.base;
  if (!base?.completa || !aid || !pid) return { verificado: false, motivo: 'No hay línea base completa para contrastar poscierre.' };
  const s = await instantanea(r, api, opt, aid, pid, base);
  const e = await pedir(r, api, 'GET', '/activos-biologicos/' + aid + '/eventos', optM02);
  if (!s.completa || e.http !== 200 || !Array.isArray(e.cuerpo?.eventos))
    return { verificado: false, motivo: 'Lectura poscierre incompleta de M02, M06 o RF-94.' };
  const presentes = eventos.some(idEvento => e.cuerpo.eventos.some(x => Number(x.id_eventos) === idEvento));
  const nuevaAuditoria = soloNuevo(base.auditoria, s.auditoria, 'id_evento').some(x =>
    x.tipo_evento === 'MEDICION_SIN_VARIACION' && eventos.some(n => String(x.id_referencia) === String(n)));
  const nuevas = ['variaciones', 'lineas', 'mediciones', 'calculos'].some((k, i) =>
    soloNuevo(base[k], s[k], ['id_variacion_valor_razonable', 'id_linea_asiento_nic41', 'id_medicion_posterior', 'id_calculo_valor_razonable'][i]).some(x => Number(x.id_activo_biologico) === aid));
  return { verificado: !presentes && !nuevaAuditoria && !nuevas,
    motivo: presentes || nuevaAuditoria || nuevas ? 'Persisten registros del RUN tras DELETE.' :
      'DELETE 200; eventos M02, auditoría RF-94 y registros financieros del RUN ausentes en lecturas públicas.' };
}

async function conciliarEvento(r, api, opciones, aid, baseIds) {
  const x = await pedir(r, api, 'GET', '/activos-biologicos/' + aid + '/eventos', opciones);
  if (x.http !== 200 || !x.eco || !Array.isArray(x.cuerpo?.eventos)) return null;
  const nuevos = x.cuerpo.eventos.filter(e => !baseIds.has(String(e.id_eventos)));
  return nuevos.length === 1 ? id(nuevos[0].id_eventos) : null;
}

async function newmanLecturas(r, c, env, token, aid, bid, pid, eventoId, eventoB, variacionB, base, secretos) {
  if (r.solicitudes.length + 2 > PRESUPUESTO.solicitudes_totales) return null;
  const vars = { base_url: String(env.SIGAB_API_TEST_BASE).replace(/\/+$/, ''), run_id: c.runId,
    sandbox_secret: env.QA_SANDBOX_SECRET, token, activo_id: String(aid), periodo_id: String(pid),
    evento_id: String(eventoId), activo_b_id: String(bid),
    evento_b_id: String(eventoB), variacion_b_id: String(variacionB ?? ''),
    ids_variaciones_base: JSON.stringify(ids(base.variaciones, 'id_variacion_valor_razonable')) };
  const environment = { values: Object.entries(vars).map(([key, value]) => ({ key, value, enabled: true })) };
  const out = spawnSync(process.execPath, [path.join(DIR, 'pruebas', 'newman_hijo.mjs')], {
    input: JSON.stringify({ coleccion: JSON.parse(fs.readFileSync(COLECCION, 'utf8')), environment,
      timeout: PRESUPUESTO.timeout_ms }), timeout: 120000, encoding: 'utf8', windowsHide: true, maxBuffer: 1024 * 1024 });
  let hijo = null; try { hijo = JSON.parse(out.stdout); } catch { /* hijo sin respuesta */ }
  const sintesis = { version: newmanVersion(), codigo: out.status, error: out.error?.code ?? hijo?.error ?? null,
    estadisticas: hijo?.estadisticas ?? null, solicitudes: hijo?.solicitudes ?? [] };
  const dir = path.join(c.directorio, 'newman'); fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'newman-G34.json'), sanear(JSON.stringify(sintesis, null, 2), secretos));
  fs.writeFileSync(path.join(dir, 'newman-G34.html'), '<!doctype html><meta charset="utf-8"><title>G34 Newman</title><h1>G34 Newman</h1><pre>' + esc(sanear(JSON.stringify(sintesis, null, 2), secretos)) + '</pre>', 'utf8');
  for (const s of sintesis.solicitudes) r.solicitudes.push({ caso: casoCompleto(CASO), metodo: 'GET',
    ruta: '/finanzas/periodos/{id}/variaciones',
    http: s.http, duracion_ms: s.duracion_ms, herramienta: 'Newman' });
  const fallos = sintesis.solicitudes.flatMap(s => s.aserciones.filter(x => x.error)).length;
  r.herramientas.newman = { version: sintesis.version, iteraciones: sintesis.solicitudes.length === 2 ? 1 : 0,
    solicitudes: sintesis.solicitudes.length, fallos, codigo: out.status };
  return sintesis;
}

function incidencia(r, clave, discrepancia, severidad, justificacion) {
  const fijo=clave==='A_AVISO'?'01':clave==='UI'?'02':null;
  const numero=fijo??String(Math.max(3,r.incidencias.length+3)).padStart(2,'0');
  r.incidencias.push({ id: 'INC-M06-G34-' + numero,
    caso: casoCompleto(CASO), criterio: clave, discrepancia, severidad, justificacion,
    certeza: 'CONFIRMADA', equipo_inicial: 'Desarrollo', fundamento_derivacion:
      'Primera discrepancia comprobada por API o UI pública en TEST.', causa_raiz: 'NO DETERMINADA' });
}
function registrarParte(r, idComprobacion, fuente, decision, evidencia) {
  // registro_qa.py coteja el ID corto de la clave casos, no el rótulo legible del informe.
  r.comprobaciones.push({ caso: CASO, id: idComprobacion, fuente, tipo: 'ASSERT',
    estado: decision?.estado ?? 'NO_CONCLUYENTE', motivo: (decision?.fallos ?? []).join(' ') ||
      decision?.motivo || 'Conforme', evidencia });
}
export function motivosNoOficial(r, sinArtefactos = false, ahora = Date.now()) {
  const motivos = [];
  const exigir = (cumple, motivo) => { if (!cumple) motivos.push(motivo); };
  exigir(r.cierre?.rollback?.verificado === true, 'rollback sin verificar');
  exigir(r.cierre?.costos?.restaurados === true, 'costos sin restaurar');
  exigir(r.cypress?.total_pruebas > 0, 'Cypress sin pruebas ejecutadas');
  exigir(r.cypress?.total_failed === 0, 'Cypress con pruebas fallidas');
  exigir(r.cypress?.captura === true, 'captura Cypress ausente');
  exigir(['APROBADO','RECHAZADO'].includes(r.casos?.[CASO]?.estado), 'caso no concluyente');
  if (!sinArtefactos) {
    exigir(r.herramientas?.newman?.iteraciones === 1, 'Newman sin una iteración completa');
    exigir(r.herramientas?.newman?.codigo === 0, 'Newman con código distinto de cero');
    exigir(r.casos?.[CASO]?.estado === 'RECHAZADO' || r.herramientas?.newman?.fallos === 0,
      'Newman con fallos para caso aprobado');
  }
  exigir(r.comprobaciones?.every(x => x.caso === CASO && ['APROBADO','RECHAZADO'].includes(x.estado)) === true,
    'comprobaciones no concluyentes o de otro caso');
  exigir(IDS.every(id => r.comprobaciones?.some(x => x.id === id)), 'comprobaciones obligatorias incompletas');
  exigir(r.solicitudes?.length <= PRESUPUESTO.solicitudes_totales, 'presupuesto API excedido');
  exigir((r.cypress?.solicitudes ?? 0) <= PRESUPUESTO.solicitudes_cypress, 'presupuesto Cypress excedido');
  exigir(ahora <= r._limite, 'duración máxima excedida');
  exigir(r.cierre?.run?.cierre_http === 200, 'DELETE de cierre sin HTTP 200');
  exigir(r.cierre?.costos?.poscierre_original !== false, 'costos poscierre distintos del original');
  // Conserva la condición canónica del core, además de detallar cada incumplimiento en el informe.
  if (!oficialidadLocal(r, sinArtefactos) && motivos.length === 0) motivos.push('oficialidad local incumplida');
  return motivos;
}
export function informe(c, r) {
  const x = r.casos[CASO] ?? {}, p = x.preparacion ?? {}, o = x.observados ?? {};
  const parte = id => r.comprobaciones.find(z => z.id === id);
  const sinParcialesA = ['variaciones', 'lineas', 'mediciones', 'calculos'].every(k =>
    Array.isArray(o.A?.nuevos?.[k]) && o.A.nuevos[k].length === 0);
  const auditoriaA = o.A?.auditorias?.some(z => z.tipo === 'MEDICION_PENDIENTE' &&
    z.referencia === p.A?.evento);
  const idsIncidencia = r.incidencias.map(i => i.id);
  const val = z => z == null ? 'no observado' :
    String(typeof z === 'object' ? JSON.stringify(z) : z).replace(/[\r\n|]/g,' ').slice(0,1800);
  const incidencias = r.incidencias.length ? r.incidencias.map(i => i.criterio === 'A_AVISO' ?
    '### ' + i.id + ' — Falta aviso de suspensión de medición al Contador\n\n' +
    '**Requisito:** RF-86 paso 1a y CA-15: al no completar RF-83, suspender sin persistir variación ni línea y notificar al Contador con causa `RF_83_NO_COMPLETADO`, activo y evento.\n\n' +
    '**Pasos para reproducir:** con A y B elegibles en el mismo período ABIERTO, completar B; fijar temporalmente costo de venta de la especie al 100 % dentro del sandbox; registrar y procesar el evento de A; consultar la bandeja del Contador, la auditoría RF-94 y las variaciones; restaurar costos y cerrar el RUN.\n\n' +
    '**Esperado:** exactamente un aviso nuevo al Contador que indique suspensión, identificador de A y fecha del evento; sin variación ni línea de A. `RF_83_NO_COMPLETADO` se interpreta por la ruta interna (`procesar_eventos_m02_use_case.py:85-86,411-425`), no por código literal en la bandeja pública.\n\n' +
    '**Obtenido:** línea base de bandeja ' + val(o.A?.bandeja_linea_base) +
    '; lecturas posteriores completas ' + val(parte(IDS[0])?.estado !== 'NO_CONCLUYENTE') +
    '; avisos relacionados ' + val(o.A?.avisos_relacionados) +
    '; auditoría `MEDICION_PENDIENTE` presente ' + val(o.A?.auditorias?.length) +
    '; datos nuevos de A ' + val(o.A?.nuevos) + '.\n\n' +
    '**Apoyo de código leído, sin atribución causal:** `src/financial_valuation/application/use_cases/valoracion/procesar_eventos_m02_use_case.py:85-86,411-425` registra la causa interna y forma el mensaje visible. La lectura de código no determina la causa raíz.\n\n' +
    '**Impacto y severidad:** ' + i.severidad + '. ' + limpio(i.justificacion) +
    ' Certeza CONFIRMADA de la discrepancia observada; causa raíz NO DETERMINADA.\n\n' +
    '**Primera atención:** Desarrollo, por ausencia observada en la bandeja pública del Contador; no implica atribución de causa.\n\n' +
    '**Evidencias:** `resultado.json` (línea base, lecturas y auditoría) y reporte Newman generado en este RUN, si corresponde.' :
    i.criterio === 'UI' ?
    '### ' + i.id + ' — El panel de medición muestra como Medido un activo con la medición del evento suspendida\n\n' +
    '**Requisito:** TC-M06-006, RF-86 paso 1a, CA-15 y postcondición 6: A debe quedar `MEDICION_PENDIENTE` para el evento suspendido y verse así en el panel de gestión M06; B con cadena completa se registra normalmente.\n\n' +
    '**Pasos para reproducir:** con A y B elegibles en el mismo período ABIERTO, procesar B; fijar temporalmente el costo de venta de la especie al 100 % en el sandbox y procesar el evento de A; comprobar la suspensión y la auditoría por API; abrir `/finanzas/medicion` como Contador y seleccionar el período ' + val(p.periodo) + '; observar ambas filas con el RUN abierto; restaurar costos y cerrar el RUN.\n\n' +
    '**Esperado:** A visible como `MEDICION_PENDIENTE` por el evento ' + val(p.A?.evento) + ' suspendido; B visible como `Medido` por el evento ' + val(p.B?.evento) + ' completado.\n\n' +
    '**Obtenido:** A (activo ' + val(p.A?.activo) + ') mostró `' + val(r.cypress?.fila_a) +
    '` y B (activo ' + val(p.B?.activo) + ') mostró `' + val(r.cypress?.fila_b) +
    '`. B se mostró correctamente; A no expuso el pendiente del evento. Acta Cypress: ' + val(r.cypress?.total_pruebas) +
    ' prueba ejecutada, lectura HTTP ' + val(r.cypress?.mediciones_http) + ' de las mediciones del período y captura ' +
    val(r.cypress?.captura) + '.\n\n' +
    '**Apoyo de código leído, sin atribución causal:** `SGPMP-FRONT-END-PWA/src/financial_valuation/pages/MedicionView.tsx:35-55,62-66,133-150` combina mediciones y eventos pendientes. La lectura de código no determina la causa raíz.\n\n' +
    '**Impacto y severidad:** ' + i.severidad + '. ' + limpio(i.justificacion) +
    ' Certeza CONFIRMADA de la discrepancia observada; causa raíz NO DETERMINADA.\n\n' +
    '**Primera atención:** Desarrollo, por el estado incorrecto observado en la UI pública para A; revisar frontend/backend sin atribuir el origen técnico.\n\n' +
    '**Evidencias:** `cypress/G34-UI-006-01.json` (acta), `cypress/G34-cypress.json` (resumen), `cypress/screenshots/g34.cy.js/G34-UI-006-01.png` (captura real) y `resultado.json` (auditoría y ausencia de datos nuevos de A).' :
    '### ' + i.id + '\n\nCriterio ' + i.criterio + '. Primera discrepancia: ' + limpio(i.discrepancia) +
    '. Severidad ' + i.severidad + ': ' + limpio(i.justificacion) + '. Certeza CONFIRMADA del incumplimiento; ' +
    'equipo inicial Desarrollo por la respuesta pública; causa raíz NO DETERMINADA. Evidencia: resultado.json y Newman si aplica.').join('\n\n')
    : 'Ninguna incidencia de producto confirmada.';
  return '# TC-M06-G34 — ' + val(x.estado) + '\n\n## Identificación\n\n' +
    casoCompleto(CASO) + '; RF-86 paso 1a, CA-15 y postcondición 6; versión ' + c.version +
    '; RUN ' + c.runId + '; ambiente ' + (c.ensayo ? 'SIMULACION_LOCAL (NO TEST)' : 'TEST') + '; autorización ' + limpio(c.referencia) +
    '; commit TEST no verificado; Node ' + process.version + '; Newman ' + val(r.herramientas.newman?.version) +
    '; Cypress ' + val(r.cypress?.version) + '.\n\n## Resumen de veredictos\n\n| Caso | Estado | Motivo |\n|---|---|---|\n| ' +
    casoCompleto(CASO) + ' | ' + val(x.estado) + ' | ' + val(x.motivo) + ' |\n\n## Detalle por caso\n\n' +
    '### B (' + val(parte(IDS[1])?.estado) + ') — registro independiente\n\n' +
    '- **Preparación:** activo ' + val(p.B?.activo) + ', período ' + val(p.periodo) + ', evento ' + val(p.B?.evento) +
    '; rebase ' + val(p.B?.rebase) + '.\n' +
    '- **Esperado:** variación `GANANCIA_TRANSFORMACION_BIOLOGICA` por ' + val(o.B?.monto_esperado) +
    ', PM cero, medición `COMPLETADO` y línea contable.\n' +
    '- **Observado y decisión:** variación ' + val(o.B?.variaciones?.[0]?.id) + ' por ' +
    val(o.B?.variaciones?.[0]?.monto) + ', medición ' + val(o.B?.mediciones?.[0]?.id) +
    ' del evento en `' + val(o.B?.mediciones?.[0]?.estado) + '`, TB ' +
    val(o.B?.mediciones?.[0]?.tb) + ', PM ' + val(o.B?.mediciones?.[0]?.pm) +
    ' y línea ' + val(o.B?.lineas?.[0]) + '. ' +
    (parte(IDS[1])?.estado === 'APROBADO' ? 'B se registró normalmente' : 'B no cumplió toda la comprobación API') +
    '; su comprobación API queda ' +
    val(parte(IDS[1])?.estado) + '. En el panel se vio `' + val(r.cypress?.fila_b) + '`.\n\n' +
    '### A (' + val(parte(IDS[0])?.estado) + ') — suspensión del evento\n\n' +
    '- **Preparación:** activo ' + val(p.A?.activo) + ', período ' + val(p.periodo) + ', evento ' +
    val(p.A?.evento) + '; costo de venta temporal de la especie al 100 % para provocar valor neto no positivo.\n' +
    '- **Esperado:** cero variaciones, líneas, mediciones y cálculos nuevos; auditoría `MEDICION_PENDIENTE` con motivo y referencia al evento; evento en `eventos-pendientes`; exactamente un aviso nuevo al Contador con identificador de A y fecha del evento. `RF_83_NO_COMPLETADO` es la causa interna interpretada, no un texto obligatorio de la bandeja.\n' +
    '- **Cumplido:** variaciones ' + val(o.A?.nuevos?.variaciones?.length) + ', líneas ' +
    val(o.A?.nuevos?.lineas?.length) + ', mediciones ' + val(o.A?.nuevos?.mediciones?.length) +
    ', cálculos ' + val(o.A?.nuevos?.calculos?.length) + '; auditoría ' +
    val(o.A?.auditorias?.[0]?.id) + ' `' + val(o.A?.auditorias?.[0]?.tipo) + '` (`' +
    val(o.A?.auditorias?.[0]?.severidad) + '`, motivo `' + val(o.A?.auditorias?.[0]?.motivo) +
    '`, referencia ' + val(o.A?.auditorias?.[0]?.referencia) + '). ' +
    (sinParcialesA && auditoriaA ? 'La suspensión no dejó datos parciales y fue auditada.' :
      'Revisar ausencia de datos parciales y auditoría frente al oráculo.') + '\n' +
    '- **Aviso observado:** desde la línea base de bandeja id ' + val(o.A?.bandeja_linea_base?.id) +
    ', la lectura posterior completa halló ' + val(o.A?.avisos_relacionados) +
    ' avisos relacionados. ' + (o.A?.avisos_relacionados === 0 ?
      'No se acreditó la notificación exigida' : 'Se contrastó el texto con la suspensión, identificador y fecha del evento') +
    '; tipo_evento del aviso válido ' + val(o.A?.tipo_evento_aviso_valido) +
    (o.A?.tipo_contrastado_con_referencia_previa ? '; tipo contrastado con referencia previa' :
      '; tipo no contrastado con referencia previa') +
    '; la comprobación API de A queda ' + val(parte(IDS[0])?.estado) + '.\n\n' +
    '### UI (' + val(parte(IDS[2])?.estado) + ') — visibilidad del estado\n\n' +
    '- **Preparación y esperado:** abrir `/finanzas/medicion` con el período ' + val(p.periodo) +
    '; A debe verse `Medición pendiente` por su evento suspendido y B `Medido`.\n' +
    '- **Observado y decisión:** A mostró `' + val(r.cypress?.fila_a) + '` y B mostró `' +
    val(r.cypress?.fila_b) + '` en ' + val(r.cypress?.total_pruebas) +
    ' prueba Cypress. ' + (r.cypress?.fila_b === 'Medido' ? 'B fue correcto; ' : 'La fila de B requiere revisión; ') +
    (parte(IDS[2])?.estado === 'RECHAZADO' ? 'A no expuso el pendiente. ' : '') +
    'La comprobación UI queda ' + val(parte(IDS[2])?.estado) + '.\n\n' +
    '**Decisión de ' + CASO + ': ' + val(x.estado) + '**. Incidencias: ' +
    (r.incidencias.map(i => '`' + i.id + '`').join(', ') || 'ninguna') + '.\n\n' +
    '## Comprobaciones API y UI\n\n' + r.comprobaciones.map(z => '- ' + z.id + ' (' + z.fuente + '): ' +
      z.estado + '; ' + limpio(z.motivo) + '; evidencia ' + z.evidencia + '.').join('\n') +
    '\n\n## Evidencias reales\n\n' + (r.evidencias.map(z => '- ' + z).join('\n') || 'Ninguna.') +
    '\n\n## Observaciones y seguimiento V1\n\n' +
    (r.observaciones?.map(z=>'- '+z).join('\n') || 'Sin seguimiento V1 registrado.') +
    (r.efectos_persistentes_declarados?.length ? '\n' + r.efectos_persistentes_declarados.map(z =>
      '- Efecto persistente declarado bajo la autorización de este RUN (' + limpio(z.autorizacion) +
      ') y su SOL de V2: ' + limpio(z.descripcion) + '.').join('\n') : '') +
    '\n\n## Incidencias de producto\n\n' + incidencias +
    '\n\n## Problemas técnicos y análisis de causas\n\n' +
    (r.problemas_tecnicos.join('; ') || 'Ninguno observado.') +
    ' La causa raíz de cualquier discrepancia queda NO DETERMINADA; se decidirá con evidencia del RUN.\n\n## Cierre y rollback\n\n' +
    'Costos originales ' + val(r.cierre.costos?.originales) + '; restauración previa al DELETE ' +
    val(r.cierre.costos?.restaurados) + '; DELETE HTTP ' + val(r.cierre.run.cierre_http) +
    '; configuración poscierre ' + val(r.cierre.costos?.poscierre_original) +
    '; rollback del sandbox ' + val(r.cierre.rollback.verificado) + ': ' + val(r.cierre.rollback.motivo) +
    '. Este rollback se limita a datos del sandbox; el aviso de suspensión al Contador puede persistir fuera de él bajo la autorización ' +
    limpio(c.referencia) + ' y la SOL de V2' +
    '\n\n## Conclusión y acciones\n\n' + (x.estado === 'APROBADO' ?
      'Cadena B y suspensión A acreditadas por API y UI.' : x.estado === 'RECHAZADO' ?
      (parte(IDS[1])?.estado === 'APROBADO' ? 'La cadena completa de B cumple. ' :
        'El registro de B requiere revisión. ') +
      (sinParcialesA && auditoriaA ? 'A cumple la suspensión sin datos parciales y la auditoría. ' :
        'La suspensión o auditoría de A requiere revisión. ') +
      'Desarrollo atiende ' + (idsIncidencia.join(' e ') || 'las discrepancias registradas') +
      '; QA reevaluará con nueva autorización.' :
      'Comprobación pendiente: ' + val((parte(IDS[2])?.estado === 'NO_CONCLUYENTE' ? 'UI — ' : '') +
        x.motivo) +
      '. Resolver la causa antes de repetir con autorización.') +
    '\n\nOficial: ' + r.oficial + '; solicitudes API ' + r.solicitudes.length + '/' +
    PRESUPUESTO.solicitudes_totales + ' y Cypress ' + (r.cypress?.solicitudes ?? 0) + '/' +
    PRESUPUESTO.solicitudes_cypress + '. ' + (r.oficial ? '' :
      'Condiciones de oficialidad incumplidas: ' + (r.motivos_no_oficial ?? motivosNoOficial(r)).join('; ') + '. ') + '\n';
}
function cypressVersion() {
  try { return require(require.resolve('cypress/package.json', { paths: [RAIZ] })).version; }
  catch { return null; }
}
function ejecutarCypress(r, c, env, token, a, b, pid, identificadorA, identificadorB, sinArtefactos) {
  if (sinArtefactos) return r.cypress;
  const dir = path.join(c.directorio, 'cypress'); fs.mkdirSync(dir, { recursive: true });
  const pkg = require.resolve('cypress/package.json', { paths: [RAIZ] });
  const bin = path.join(path.dirname(pkg), require(pkg).bin.cypress);
  const restante = Math.min(150000, Math.max(1, r._limite - Date.now() - 90000));
  const out = spawnSync(process.execPath, [bin, 'run', '--headless', '--browser', 'electron',
    '--config-file', path.join(DIR,'g34.cypress.config.cjs'), '--spec', path.join(DIR,'g34.cy.js')], {
    cwd: DIR, windowsHide: true, timeout: restante, encoding:'utf8', maxBuffer: 1024*1024,
    env: { ...process.env, CYPRESS_API_BASE:'https://api.inmero.co/api-sgpmp-test',
      CYPRESS_FRONT_BASE:'https://api.inmero.co/sigab-test', CYPRESS_RUN_ID:c.runId,
      CYPRESS_ARTIFACTS_DIR:dir, CYPRESS_PROD_LOGIN_TOKEN:token, CYPRESS_SANDBOX_SECRET:env.QA_SANDBOX_SECRET,
      CYPRESS_ACTIVO_A:String(a), CYPRESS_ACTIVO_B:String(b), CYPRESS_PERIODO_ID:String(pid),
      CYPRESS_IDENTIFICADOR_A:String(identificadorA ?? ''), CYPRESS_IDENTIFICADOR_B:String(identificadorB ?? '') } });
  let acta = null, resumen = null;
  try { acta = JSON.parse(fs.readFileSync(path.join(dir,'G34-UI-006-01.json'),'utf8')); } catch {}
  try { resumen = JSON.parse(fs.readFileSync(path.join(dir,'G34-cypress.json'),'utf8')); } catch {}
  const captura = fs.existsSync(path.join(dir,'screenshots','g34.cy.js','G34-UI-006-01.png'));
  r.cypress = { ...acta, captura:acta?.captura === true && captura, version:cypressVersion(), total_pruebas:resumen?.totalTests ?? 0,
    total_failed:resumen?.totalFailed ?? null, codigo:out.status, error:out.error?.code ?? null };
  if (acta) r.evidencias.push('cypress/G34-UI-006-01.json');
  if (resumen) r.evidencias.push('cypress/G34-cypress.json');
  if (r.cypress.captura) r.evidencias.push('cypress/screenshots/g34.cy.js/G34-UI-006-01.png');
  if (!acta || !resumen || !resumen.totalTests) r.problemas_tecnicos.push('Cypress sin ejecución o acta; RUN no oficial.');
  return r.cypress;
}
async function rollbackG34(r, api, token, tokenM02, datos) {
  if (r.cierre.run.cierre_http !== 200) return { verificado:false, motivo:'DELETE sin HTTP 200.' };
  if (!datos.baseA?.completa || !datos.baseB?.completa) return { verificado:false, motivo:'Sin bases de A y B.' };
  for (const [aid, base] of [[datos.aidA,datos.baseA],[datos.aidB,datos.baseB]]) {
    const post = await instantanea(r,api,{token},aid,datos.pid,base);
    const e = await pedir(r,api,'GET','/activos-biologicos/'+aid+'/eventos',{token:tokenM02});
    if (!post.completa || e.http !== 200 || !Array.isArray(e.cuerpo?.eventos))
      return { verificado:false, motivo:'Lectura poscierre incompleta.' };
    if (datos.eventos.some(idEvento => e.cuerpo.eventos.some(x => Number(x.id_eventos) === idEvento)) ||
      ['variaciones','lineas','mediciones','calculos','auditoria'].some((k,i) =>
        soloNuevo(base[k],post[k],['id_variacion_valor_razonable','id_linea_asiento_nic41',
          'id_medicion_posterior','id_calculo_valor_razonable','id_evento'][i]).some(x =>
          String(x.id_activo_biologico) === String(aid))))
      return { verificado:false, motivo:'Persisten eventos o registros del RUN tras DELETE.' };
  }
  return { verificado:true, motivo:'Lecturas públicas poscierre sin eventos M02 ni registros financieros de A y B.' };
}
export async function evaluar(c, { env = leerEnv(), apiOverride = null, sinArtefactos = false,
  cypressOverride = null } = {}) {
  const api = apiOverride ?? String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/,'');
  const r = { grupo:'G34', run_id:c.runId, version:c.version, intento:c.intento, casos:{},
    comprobaciones:[], solicitudes:[], evidencias:[], incidencias:[], problemas_tecnicos:[],
    preflight_vivo:[], seguimiento_incidencias_v1:[], observaciones:[], efectos_persistentes_declarados:[],
    herramientas:{node:process.version,newman:null}, cypress:{total_pruebas:0},
    diagnostico_candidatos:{medido:false,total_recibido:0,bovino:0,individual:0,estado:0,
      sin_costo:0,valor_positivo:0,precio_vigente:0,periodo_destino:0,peso_kg:0,calculo_previo:0,
      pares_misma_especie_periodo:0,primera_condicion_fallida:null},
    cierre:{ costos:{originales:null,restaurados:false,poscierre_original:false,problema_critico:false},
      run:{cierre_http:null,cuerpo_saneado:null},rollback:{verificado:false,motivo:'No comprobado'} },
    oficial:false,consume_version:false,_seguidos5xx:0,_corte:false,
    _limite:Date.now()+PRESUPUESTO.duracion_segundos*1000 };
  const pf = preflight(c,env,sinArtefactos ? 'ensayo-local' : newmanVersion());
  if (!sinArtefactos && !(c.ensayo && cypressOverride) && !cypressVersion()) pf.barreras.push('CYPRESS_NO_DISPONIBLE');
  pf.ok = !pf.barreras.length; pf.herramientas.cypress = cypressVersion();
  r._secretos = [env.QA_SANDBOX_SECRET,env.QA_CONTADOR_EMAIL,env.QA_CONTADOR_PASSWORD,
    env.QA_ADMIN_EMAIL,env.QA_ADMIN_PASSWORD];
  if (!sinArtefactos) {
    if (!fs.existsSync(c.directorio)) throw Error('El lanzador debe crear el RUN');
    guardar(path.join(c.directorio,'preflight.json'),pf); r.evidencias.push('preflight.json');
  }
  const datos = {aidA:null,aidB:null,pid:null,baseA:null,baseB:null,eventos:[],especie:null,originales:null};
  let token=null,tokenM02=null,iniciado=false,costosTocados=false,decisionA=null,decisionB=null,decisionUI=null;
  let preparacion={periodo:null,A:{},B:{}};
  const concluir = (estado,motivo) => { r.casos[CASO] = {caso:casoCompleto(CASO),estado,motivo,
    preparacion,observados:{A:decisionA?.observado ?? null,B:decisionB?.observado ?? null}}; };
  try {
    if (!pf.ok) { concluir('BLOQUEADO','Preflight: '+pf.barreras.join(', ')); return r; }
    let x=await pedir(r,api,'POST','/sesiones/',{cuerpo:{correo_electronico:env.QA_CONTADOR_EMAIL,
      contrasena:env.QA_CONTADOR_PASSWORD},timeout:PRESUPUESTO.timeout_login_ms});
    token=x.cuerpo?.token ?? x.cuerpo?.access_token;
    if (x.http!==200 || !token) { concluir('NO_CONCLUYENTE','Login Contador sin sesión.'); return r; }
    x=await pedir(r,api,'POST','/sesiones/',{cuerpo:{correo_electronico:env.QA_ADMIN_EMAIL,
      contrasena:env.QA_ADMIN_PASSWORD},timeout:PRESUPUESTO.timeout_login_ms});
    tokenM02=x.cuerpo?.token ?? x.cuerpo?.access_token;
    if (x.http!==200 || !tokenM02) { concluir('NO_CONCLUYENTE','Login Administrador sin sesión.'); return r; }
    const opt={token,secreto:env.QA_SANDBOX_SECRET,runId:c.runId,caso:CASO};
    const mopt={...opt,token:tokenM02};
    const a=await pedir(r,api,'GET','/finanzas/activos',opt); iniciado=true;
    const p=await pedir(r,api,'GET','/finanzas/periodos',opt);
    if (a.http!==200 || p.http!==200 || !a.eco || !p.eco ||
      !Array.isArray(a.cuerpo) || !Array.isArray(p.cuerpo)) {
      concluir('NO_CONCLUYENTE','Catálogos públicos incompletos.'); return r; }
    const diag=r.diagnostico_candidatos;diag.medido=true;diag.total_recibido=a.cuerpo.length;
    let candidatos=a.cuerpo.filter(x=>/bovin/i.test(x.especie??''));diag.bovino=candidatos.length;
    candidatos=candidatos.filter(x=>x.tipo==='INDIVIDUAL');diag.individual=candidatos.length;
    candidatos=candidatos.filter(x=>x.estado==='ACTIVO');diag.estado=candidatos.length;
    candidatos=candidatos.filter(x=>!x.valorado_por_costo);diag.sin_costo=candidatos.length;
    candidatos=candidatos.filter(x=>Number(x.valor_razonable_neto)>0);diag.valor_positivo=candidatos.length;
    // Datos conocidos de NIT-D se examinan primero; todas las condiciones siguen verificándose por API.
    const conocidos=new Set([1627,1831,1832,1833]);
    candidatos.sort((a,b)=>Number(conocidos.has(id(b.id_activo_biologico)))-
      Number(conocidos.has(id(a.id_activo_biologico))));
    const precios=new Map(),posibles=[];let falloLectura=false,periodosDescartados=[];
    for (const activo of candidatos.slice(0,8)) {
      const aid=id(activo.id_activo_biologico),esp=id(activo.id_especie);
      if (!precios.has(esp)) {
        const pr=await pedir(r,api,'GET','/finanzas/precios?id_especie='+esp,opt);
        if (pr.http>=500 || pr.http==null) falloLectura=true;
        precios.set(esp,pr.http===200 && pr.eco && Array.isArray(pr.cuerpo)?preciosVigentes(pr.cuerpo,esp):null);
      }
      const precio=precios.get(esp);if (!precio) continue;diag.precio_vigente++;
      const d=await pedir(r,api,'GET','/finanzas/activos/'+aid,opt);
      if (d.http>=500 || d.http==null) falloLectura=true;
      if (d.http!==200 || !d.eco) continue;
      const destino=periodoDestino(p.cuerpo,d.cuerpo?.activo?.numero_id_tributaria);
      const periodo=destino.periodo;
      if (!periodo) periodosDescartados.push({activo:aid,motivo:destino.motivo});
      if (!periodo) continue;diag.periodo_destino++;
      const f=await pedir(r,api,'GET','/activos-biologicos/'+aid+'/ficha-integral',mopt);
      if (f.http>=500 || f.http==null) falloLectura=true;
      if (f.http!==200 || !f.eco || f.cuerpo?.unidad_peso!=='kg' || !(Number(f.cuerpo.peso_actual)>0)) continue;
      diag.peso_kg++;
      const calculo=ultimoCalculo(d.cuerpo);if (!calculo || !(Number(calculo.valor_neto)>0)) continue;
      diag.calculo_previo++;posibles.push({activo,periodo,precio,peso:Number(f.cuerpo.peso_actual),calculo});
    }
    diag.primera_condicion_fallida=Object.entries(diag).find(([k,v])=>['bovino','individual','estado',
      'sin_costo','valor_positivo','precio_vigente','periodo_destino','peso_kg','calculo_previo'].includes(k)&&v===0)?.[0]??null;
    r.preflight_vivo.push({requisito:'Período de hoy ABIERTO',esperado:'Titular con período que contiene hoy en America/Bogota y ABIERTO',
      observado:{elegibles:diag.periodo_destino,descartados:periodosDescartados},cumple:diag.periodo_destino>0,bloqueante:true});
    r.preflight_vivo.push({requisito:'Precio vigente',esperado:'Precio PESO_KG vigente de la especie bovina',
      observado:diag.precio_vigente,cumple:diag.precio_vigente>0,bloqueante:true});
    const pares=[];
    for (const B of posibles) for (const A of posibles) if (A!==B &&
      id(A.activo.id_especie)===id(B.activo.id_especie) &&
      id(A.periodo.id_periodo_contable)===id(B.periodo.id_periodo_contable)) pares.push({A,B});
    diag.pares_misma_especie_periodo=pares.length;
    const medicionesPorPeriodo=new Map();
    for (const pid of [...new Set(pares.map(x=>id(x.A.periodo.id_periodo_contable)))]) {
      const lectura=await pedir(r,api,'GET','/finanzas/periodos/'+pid+'/mediciones',opt);
      medicionesPorPeriodo.set(pid,lectura.http===200 && lectura.eco && Array.isArray(lectura.cuerpo)?lectura.cuerpo:null);
      if (medicionesPorPeriodo.get(pid)===null) falloLectura=true;
    }
    const paresA=pares.filter(({A})=>{
      const lista=medicionesPorPeriodo.get(id(A.periodo.id_periodo_contable));
      return lista && !lista.some(x=>String(x.id_activo_biologico)===String(A.activo.id_activo_biologico));
    });
    r.preflight_vivo.push({requisito:'Dos bovinos elegibles, A sin mediciones del período',
      esperado:'A sin filas en GET mediciones antes de escribir; B bovino elegible',
      observado:{pares:pares.length,pares_con_A_sin_mediciones:paresA.length,lectura_completa:!falloLectura},
      cumple:paresA.length>0,bloqueante:true});
    paresA.sort((x,y)=>Number(id(y.B.calculo.id_precio_mercado)===id(y.B.precio.id_precio_mercado))-
      Number(id(x.B.calculo.id_precio_mercado)===id(x.B.precio.id_precio_mercado)));
    const par=paresA[0];
    if (!par) { concluir('NO_CONCLUYENTE',
      'Preflight bloqueante: faltan dos bovinos elegibles con A sin mediciones del período actual ABIERTO; primera condición '+diag.primera_condicion_fallida);return r; }
    const {A,B}=par, aidA=id(A.activo.id_activo_biologico),aidB=id(B.activo.id_activo_biologico);
    const pid=id(B.periodo.id_periodo_contable),esp=id(B.activo.id_especie);
    Object.assign(datos,{aidA,aidB,pid,especie:esp});
    preparacion={periodo:pid,A:{activo:aidA,precio:id(A.precio.id_precio_mercado)},
      B:{activo:aidB,precio:id(B.precio.id_precio_mercado),rebase:'no requerido'}};
    const conf=await pedir(r,api,'GET','/finanzas/configuracion',opt);
    const originales=conf.http===200 && conf.eco?costosDe(conf.cuerpo,esp):null;
    const matriz=Array.isArray(conf.cuerpo?.matriz)?conf.cuerpo.matriz:null;
    const tiene=tipo=>matriz?.some(x=>x.tipo_hecho===tipo &&
      (x.id_especie==null || id(x.id_especie)===esp));
    const matrizOk=Boolean(tiene('VARIACION_VR_TB') && tiene('VARIACION_VR_PM'));
    r.preflight_vivo.push({requisito:'Matriz TB/PM',esperado:'Asignaciones activas presentes en lista de configuración',
      observado:{lista_leida:!!matriz,tb:!!tiene('VARIACION_VR_TB'),pm:!!tiene('VARIACION_VR_PM')},
      cumple:matrizOk,bloqueante:true});
    r.preflight_vivo.push({requisito:'Costos de venta restaurables',esperado:'Fracciones GENERAL activas legibles',
      observado:originales??'No disponibles',cumple:!!originales,bloqueante:true});
    if (!matrizOk || !originales) {concluir('NO_CONCLUYENTE','Preflight bloqueante: matriz TB/PM o costos originales incompletos.');return r;}
    datos.originales=originales;r.cierre.costos.originales=originales;
    const basesEventos=new Map();
    for (const aid of [aidB,aidA]) {
      const e=await pedir(r,api,'GET','/activos-biologicos/'+aid+'/eventos',mopt);
      if (e.http!==200 || !e.eco || !Array.isArray(e.cuerpo?.eventos)) {
        concluir('NO_CONCLUYENTE','Sin línea base M02 de '+aid);return r; }
      basesEventos.set(aid,new Set(ids(e.cuerpo.eventos,'id_eventos')));
    }
    const crear=async (aid,peso,descripcion)=>{
      const e=await pedir(r,api,'POST','/activos-biologicos/'+aid+'/eventos/crecimiento',{
        ...mopt,cuerpo:{tipo_medicion:'PESO',valor_medicion:peso,unidad_medida:'kg',descripcion}});
      let eid=id(e.cuerpo?.evento?.id_eventos);
      if (e.http==null || !eid) eid=await conciliarEvento(r,api,mopt,aid,basesEventos.get(aid));
      if (eid) {datos.eventos.push(eid);basesEventos.get(aid).add(String(eid));}
      return {e,eid};
    };
    if (id(B.calculo.id_precio_mercado)!==id(B.precio.id_precio_mercado) || !igualMonto(B.calculo.magnitud,B.peso)) {
      const reb=await crear(aidB,B.peso,'Rebase B QA '+c.runId);
      if (!reb.eid) {concluir('NO_CONCLUYENTE','Rebase B sin ID conciliable.');return r;}
      const proc=await pedir(r,api,'POST','/finanzas/eventos/procesar',opt);
      const det=await pedir(r,api,'GET','/finanzas/activos/'+aidB,opt);
      const ultimo=det.http===200 && det.eco?ultimoCalculo(det.cuerpo):null;
      if (!ultimo || id(ultimo.id_precio_mercado)!==id(B.precio.id_precio_mercado) ||
        !igualMonto(ultimo.magnitud,B.peso) || !(Number(ultimo.valor_neto)>0)) {
        concluir(proc.http>=500 || proc.http==null?'NO_CONCLUYENTE':'BLOQUEADO','No se acreditó rebase B.');return r; }
      B.calculo=ultimo;preparacion.B.rebase='evento '+reb.eid;
    }
    datos.baseB=await instantanea(r,api,opt,aidB,pid);
    if (!datos.baseB.completa) {concluir('NO_CONCLUYENTE','Sin línea base B: '+datos.baseB.motivo);return r;}
    const pesoB=Number((B.peso*1.02).toFixed(3));
    if (!(pesoB>B.peso)) {concluir('BLOQUEADO','BLOQUEO_DATOS: +2 % no modifica peso admisible.');return r;}
    const evB=await crear(aidB,pesoB,'B +2% QA '+c.runId);
    if (!evB.eid) {concluir('NO_CONCLUYENTE','Evento B sin ID conciliable.');return r;}
    preparacion.B.evento=evB.eid;preparacion.B.peso_nuevo=pesoB;
    const procB=await pedir(r,api,'POST','/finanzas/eventos/procesar',opt);
    const postB=await instantanea(r,api,opt,aidB,pid,datos.baseB);
    decisionB=evaluarB(datos.baseB,postB,{activo:aidB,evento:evB.eid,periodo:pid,
      calculoPrevio:B.calculo,pesoNuevo:pesoB});
    if (procB.http!==200) decisionB={estado:'NO_CONCLUYENTE',fallos:['Procesamiento B con error ajeno al oráculo: HTTP '+procB.http+', código '+(procB.fila?.codigo||'sin código')+'.']};
    registrarParte(r,IDS[1],'API',decisionB,'resultado.json');
    if (decisionB.estado==='RECHAZADO') incidencia(r,'B',decisionB.fallos.join(' '),'ALTA',
      'La variación normal de otro activo del período quedó impedida o incorrecta.');
    datos.baseA=await instantanea(r,api,opt,aidA,pid);
    if (!datos.baseA.completa) {concluir('NO_CONCLUYENTE','Sin línea base A.');return r;}
    costosTocados=true;
    const cambio=await pedir(r,api,'PUT','/finanzas/configuracion/costos-venta/'+esp,{
      ...opt,cuerpo:{pct_transporte:1,pct_comisiones:0,pct_impuestos:0}});
    const confAlta=await pedir(r,api,'GET','/finanzas/configuracion',opt);
    if (cambio.http!==200 || !cambio.eco || confAlta.http!==200 || !confAlta.eco ||
      !mismosCostos(costosDe(confAlta.cuerpo,esp),{pct_transporte:1,pct_comisiones:0,pct_impuestos:0})) {
      r.problemas_tecnicos.push('Cambio de costos sin confirmación pública (PUT '+cambio.http+').');
      concluir('NO_CONCLUYENTE','No se acreditó costo 100 % para A.');return r;
    }
    const evA=await crear(aidA,A.peso,'A pendiente QA '+c.runId);
    if (!evA.eid) {concluir('NO_CONCLUYENTE','Evento A sin ID conciliable.');return r;}
    preparacion.A.evento=evA.eid;
    r.efectos_persistentes_declarados.push({ autorizacion:c.referencia, version:c.version,
      descripcion:'El aviso ALERTA_FINANCIERA_NIC41 de suspensión a los Contadores de la finca se envía en otra sesión con commit propio; puede permanecer en la bandeja aunque DELETE cierre el RUN. Su persistencia no forma parte del rollback verificado del sandbox.' });
    const procA=await pedir(r,api,'POST','/finanzas/eventos/procesar',opt);
    const postA=await instantanea(r,api,opt,aidA,pid,datos.baseA);
    const hoyEvento=fecha();
    const fechaEvento=hoyEvento.slice(8,10)+'/'+hoyEvento.slice(5,7)+'/'+hoyEvento.slice(0,4);
    const tipoAlerta=datos.baseA.bandeja.find(x=>/No se pudo completar la medición|quedó suspendido/i.test(String(x.mensaje)))?.tipo_evento ?? null;
    decisionA=evaluarA(datos.baseA,postA,{activo:aidA,periodo:pid,evento:evA.eid,
      identificador:A.activo.identificador??A.activo.identificador_activo,fechaEvento,tipoAlerta});
    if (procA.http!==200) decisionA={estado:'NO_CONCLUYENTE',fallos:['Procesamiento A con error ajeno al oráculo: HTTP '+procA.http+', código '+(procA.fila?.codigo||'sin código')+'.']};
    registrarParte(r,IDS[0],'API',decisionA,'resultado.json');
    if (decisionA.estado==='RECHAZADO') {
      for (const fallo of decisionA.fallos) incidencia(r,/aviso/i.test(fallo)?'A_AVISO':/auditoría/i.test(fallo)?'A_AUDITORIA':'A_DATOS',
        fallo,/variación|línea|aviso|cálculo|medición/i.test(fallo)?'ALTA':'MEDIA',
        /variación|línea/i.test(fallo)?'Registro contable indebido para A.':
          /aviso/i.test(fallo)?'El Contador no recibe la suspensión ni su causa; debe consultar auditoría y la variación queda sin registrar.':
            'Trazabilidad incompleta para A.');
    }
    if (sinArtefactos) r.cypress=cypressOverride??{estado:'APROBADO',fila_a:'Medición pendiente',fila_b:'Medido',total_pruebas:1,total_failed:0,captura:true};
    else if (c.ensayo && cypressOverride) {
      const dir=path.join(c.directorio,'cypress');
      const png=path.join(dir,'screenshots','g34.cy.js','G34-UI-006-01.png');
      fs.mkdirSync(path.dirname(png),{recursive:true});
      fs.writeFileSync(path.join(dir,'G34-UI-006-01.json'),JSON.stringify({...cypressOverride,
        origen:'SIMULACION_LOCAL; NO EVIDENCIA TEST'},null,2));
      fs.writeFileSync(path.join(dir,'G34-cypress.json'),JSON.stringify({totalTests:1,totalFailed:0,
        origen:'SIMULACION_LOCAL; NO EVIDENCIA TEST'},null,2));
      // Imagen mínima identificada como marcador local; el RUN real usa captura Cypress.
      fs.writeFileSync(png,Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/pXcAAAAASUVORK5CYII=','base64'));
      r.cypress={...cypressOverride,version:'simulador-local',codigo:0};
      r.evidencias.push('cypress/G34-UI-006-01.json','cypress/G34-cypress.json',
        'cypress/screenshots/g34.cy.js/G34-UI-006-01.png');
    } else ejecutarCypress(r,c,env,token,aidA,aidB,pid,
      A.activo.identificador??A.activo.identificador_activo,
      B.activo.identificador??B.activo.identificador_activo,sinArtefactos);
    decisionUI={estado:(!r.cypress?.fila_b || r.cypress.fila_b === 'SIN_FILA' || r.cypress?.total_pruebas===0) ? 'NO_CONCLUYENTE' :
      r.cypress.estado??'NO_CONCLUYENTE',fallos:[r.cypress.motivo??'UI conforme']};
    registrarParte(r,IDS[2],'UI',decisionUI,'cypress/G34-UI-006-01.json');
    if (decisionUI.estado==='RECHAZADO') incidencia(r,'UI',
      r.cypress?.fila_b === 'Medido' ?
        'En /finanzas/medicion, período '+pid+', A (activo '+aidA+') aparece Medido aunque el evento '+evA.eid+
        ' quedó suspendido y debía verse MEDICION_PENDIENTE; B (activo '+aidB+') aparece Medido correctamente.' :
        decisionUI.fallos.join(' '),'MEDIA',
      r.cypress?.fila_b === 'Medido' ?
        'Impacto parcial: el Contador no ve en el panel que la variación del evento de A quedó suspendida; B se muestra correctamente. La auditoría conserva la trazabilidad y no hay dato parcial de A.' :
        'El panel M06 no refleja correctamente el estado esperado de los activos; requiere revisión del acta UI.');
    if (!sinArtefactos) {
      const sintesis=await newmanLecturas(r,c,env,token,aidA,aidB,pid,evA.eid,evB.eid,
        decisionB.observado?.variaciones?.[0]?.id,datos.baseA,
        [token,tokenM02,...r._secretos]);
      if (!sintesis || r.herramientas.newman?.iteraciones!==1)
        r.problemas_tecnicos.push('Newman sin dos lecturas completas.');
      else if (r.herramientas.newman.fallos>0 && [decisionA.estado,decisionB.estado,decisionUI.estado]
        .every(x=>x==='APROBADO')) r.problemas_tecnicos.push('Newman contradice las lecturas semánticas; requiere revisión QA.');
    } else r.herramientas.newman={version:'ensayo-local',iteraciones:1,codigo:0,fallos:0};
    const estados=[decisionA.estado,decisionB.estado,decisionUI.estado];
    if (c.version===2 && ['reevaluar','reintentar'].includes(c.operacion)) {
      const lecturasCompletas=Boolean(datos.baseA?.completa && postA?.completa);
      r.seguimiento_incidencias_v1=[
        {id:'INC-M06-G34-01',caso:CASO,descripcion_v1:'Falta aviso al Contador',estado_v2:!lecturasCompletas?'NO_CONCLUYENTE':
          decisionA.observado?.avisos_validos===1?'CORREGIDA':decisionA.observado?.avisos_validos===0?'REPRODUCIDA':'NO_CONCLUYENTE'},
        {id:'INC-M06-G34-02',caso:CASO,descripcion_v1:'Panel muestra Medido para A',estado_v2:r.cypress.total_pruebas===0?'NO_CONCLUYENTE':
          r.cypress.fila_a==='Medición pendiente'?'CORREGIDA':r.cypress.fila_a==='Medido'?'REPRODUCIDA':'NO_CONCLUYENTE'}];
      r.observaciones=[...r.seguimiento_incidencias_v1.map(x=>`${x.id}: ${x.estado_v2}`),
        ...r.incidencias.filter(x=>!['A_AVISO','UI'].includes(x.criterio)).map(x=>`${x.id}: nueva en V2`)];
    }
    concluir(estados.includes('NO_CONCLUYENTE') ||
      (!sinArtefactos && r.herramientas.newman?.iteraciones!==1) ||
      (!sinArtefactos && r.herramientas.newman?.fallos>0 && estados.every(x=>x==='APROBADO'))?
      'NO_CONCLUYENTE':estados.includes('RECHAZADO')?'RECHAZADO':'APROBADO',
      [...decisionA.fallos,...decisionB.fallos,...(decisionUI.estado==='NO_CONCLUYENTE'?
        [r.cypress.total_pruebas===0?'Comprobación UI sin pruebas ejecutadas.':
          decisionUI.fallos.join(' ')]:
        decisionUI.estado==='RECHAZADO'?decisionUI.fallos:[])].join(' ')||
        (r.problemas_tecnicos.length?'Evidencia instrumental discrepante o incompleta.':'Oráculo API y UI completo.'));
  } catch(e) {
    r.problemas_tecnicos.push('Excepción del ejecutor: '+limpio(e.code??e.name??'ERROR'));
    concluir('NO_CONCLUYENTE','Excepción técnica; revisar problema técnico.');
  } finally {
    if (iniciado) {
      const opt={token,secreto:env.QA_SANDBOX_SECRET,runId:c.runId,caso:CASO};
      if (costosTocados && datos.originales && datos.especie) {
        let restaurar=await pedir(r,api,'PUT','/finanzas/configuracion/costos-venta/'+datos.especie,
          {...opt,cuerpo:datos.originales});
        let lectura=await pedir(r,api,'GET','/finanzas/configuracion',opt);
        let bien=restaurar.http===200 && restaurar.eco && lectura.http===200 && lectura.eco &&
          mismosCostos(costosDe(lectura.cuerpo,datos.especie),datos.originales);
        if (!bien && restaurar.http!==403 && r.solicitudes.length<PRESUPUESTO.solicitudes_totales-5) {
          // Reserva: solo tras lectura discrepante, sin repetición ciega.
          restaurar=await pedir(r,api,'PUT','/finanzas/configuracion/costos-venta/'+datos.especie,
            {...opt,cuerpo:datos.originales});
          lectura=await pedir(r,api,'GET','/finanzas/configuracion',opt);
          bien=restaurar.http===200 && restaurar.eco && lectura.http===200 && lectura.eco &&
            mismosCostos(costosDe(lectura.cuerpo,datos.especie),datos.originales);
        }
        r.cierre.costos.restaurados=!!bien;
        if (!bien) {r.cierre.costos.problema_critico=true;
          r.problemas_tecnicos.push('CRÍTICA: restauración explícita de costos sin confirmar antes del DELETE.');}
      } else r.cierre.costos.restaurados=!costosTocados;
      const del=await pedir(r,api,'DELETE','/test-control/runs/'+encodeURIComponent(c.runId),
        {token,secreto:env.QA_SANDBOX_SECRET,timeout:PRESUPUESTO.timeout_ms});
      r.cierre.run.cierre_http=del.http;r.cierre.run.cuerpo_saneado=del.fila?.cuerpo_saneado??null;
      if (del.http===200 && datos.originales) {
        const post=await pedir(r,api,'GET','/finanzas/configuracion',{token});
        r.cierre.costos.poscierre_original=post.http===200 &&
          mismosCostos(costosDe(post.cuerpo,datos.especie),datos.originales);
        if (!r.cierre.costos.poscierre_original) {
          r.cierre.costos.problema_critico=true;
          r.problemas_tecnicos.push('CRÍTICA: configuración poscierre distinta de la original o ilegible.');
        }
      }
      r.cierre.rollback=del.http===200?await rollbackG34(r,api,token,tokenM02,datos):
        {verificado:false,motivo:'DELETE HTTP '+(del.http??'sin respuesta')+'; sin verificación poscierre.'};
      if (!r.cierre.costos.poscierre_original && datos.originales) r.cierre.rollback.verificado=false;
    }
    if (!r.casos[CASO]) concluir('NO_CONCLUYENTE','Caso inconcluso.');
    if (c.version===2 && ['reevaluar','reintentar'].includes(c.operacion) && r.seguimiento_incidencias_v1.length===0) {
      r.seguimiento_incidencias_v1=[
        {id:'INC-M06-G34-01',caso:CASO,descripcion_v1:'Falta aviso al Contador',estado_v2:'NO_CONCLUYENTE'},
        {id:'INC-M06-G34-02',caso:CASO,descripcion_v1:'Panel muestra Medido para A',estado_v2:'NO_CONCLUYENTE'}];
      r.observaciones=r.seguimiento_incidencias_v1.map(x=>`${x.id}: ${x.estado_v2}`);
    }
    if (r.cypress.total_pruebas===0 && r.casos[CASO].estado==='APROBADO')
      concluir('NO_CONCLUYENTE','Cypress con cero pruebas.');
    if ((!r.cierre.costos.restaurados || (datos.originales && !r.cierre.costos.poscierre_original) ||
      !r.cierre.rollback.verificado) && r.casos[CASO].estado==='APROBADO')
      concluir('NO_CONCLUYENTE','Compensación, configuración poscierre o rollback sin verificar.');
    r.motivos_no_oficial=motivosNoOficial(r,sinArtefactos);
    r.oficial=r.motivos_no_oficial.length===0;
    r.consume_version=r.oficial;r.estado_ejecucion=r.oficial?(c.ensayo?'OFICIAL_LOCAL':'OFICIAL'):'NO_OFICIAL';
    if (!sinArtefactos && fs.existsSync(c.directorio)) {
      const secretos=[token,tokenM02,...r._secretos];
      guardar(path.join(c.directorio,'preflight.json'),JSON.parse(sanear(JSON.stringify({
        ...pf,vivo:r.preflight_vivo,apto_para_escrituras:r.preflight_vivo.length>=5 &&
          r.preflight_vivo.every(x=>!x.bloqueante || x.cumple)
      }),secretos)));
      r.evidencias.push('resultado.json',informeNombre(c.version));
      if (r.herramientas.newman) r.evidencias.push('newman/newman-G34.json','newman/newman-G34.html');
      const pub={...r};for(const k of ['_limite','_corte','_seguidos5xx','_secretos']) delete pub[k];
      fs.writeFileSync(path.join(c.directorio,'resultado.json'),sanear(JSON.stringify(pub,null,2),secretos));
      fs.writeFileSync(path.join(c.directorio,informeNombre(c.version)),sanear(informe(c,r),secretos));
    }
    delete r._secretos;
  }
  return r;
}
if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES,null,2));
else if (process.argv.includes('--comprobar')) process.exitCode=comprobar();
else if (process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  try { const c=contexto(process.argv.slice(2));const r=await evaluar(c);
    console.log(JSON.stringify({grupo:'G34',run_id:c.runId,oficial:r.oficial,casos:r.casos}));
    if (!r.oficial) process.exitCode=2;
  } catch(e) {console.error(limpio(e.message));process.exitCode=2;}
}
