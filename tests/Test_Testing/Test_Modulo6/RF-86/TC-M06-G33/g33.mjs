#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { CASOS, IDS, PRESUPUESTO, CAPACIDADES, casoCompleto, evaluarOraculo, igualMonto, oficialidadLocal } from './lib/g33_core.mjs';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const require = createRequire(import.meta.url);
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION = path.join(DIR, 'G33.postman_collection.json');
const ARCHIVOS = ['g33.mjs', 'G33.postman_collection.json', 'README.md', 'lib/g33_core.mjs',
  'pruebas/g33_env.test.mjs', 'pruebas/g33_ensayo.mjs', 'pruebas/registro_qa.mjs',
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
  console.log(JSON.stringify({ grupo: 'G33', ok, faltantes, coleccion, markdown_superior: markdownSuperior,
    newman_local: !!newmanVersion(), presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}
export function contexto(args) {
  const v = k => args.includes(k) ? args[args.indexOf(k) + 1] : undefined;
  const operacion = v('--operacion'), version = Number(v('--version')), intento = Number(v('--intento')),
    runId = v('--run-id'), referencia = v('--autorizacion'), archivo = v('--contexto');
  if (!CAPACIDADES.operaciones.includes(operacion) || !Number.isInteger(version) || version < 1 || version > 99 ||
      !Number.isInteger(intento) || intento < 1 || !referencia || !archivo ||
      !new RegExp(`^RUN-G33-V${version}-\\d{8}-\\d{6}$`).test(runId ?? '')) throw Error('Contexto incompleto');
  const destino = path.join(DIR, ...(version === 1 ? ['Resultados', runId] : [`EvaluacionV${version}`, 'Resultados', runId]));
  const ruta = path.resolve(archivo);
  if (path.dirname(ruta) !== destino || path.basename(ruta) !== 'contexto_operacion.json') throw Error('Contexto fuera del RUN');
  const c = JSON.parse(fs.readFileSync(ruta, 'utf8'));
  if (c.grupo !== 'G33' || c.run_id !== runId || c.version !== version || c.intento !== intento ||
      c.operacion !== operacion.toUpperCase() || c.referencia !== referencia ||
      JSON.stringify(c.casos) !== JSON.stringify(CASOS) ||
      (version > 1 && (operacion !== 'reevaluar' || c.version_anterior !== version - 1 || !c.alcance_reevaluacion)) ||
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
  return { grupo: 'G33', run_id: c.runId, fase: 'PREFLIGHT_LOCAL', ok: !barreras.length,
    barreras, presupuesto: PRESUPUESTO, herramientas: { node: process.version, newman: n },
    efectos: ['Login de Contador y Administrador fuera del RUN', 'Uno o dos eventos M02 de crecimiento con peso constante',
      'No se registran precios ni se cambia el estado M02',
      'Uno o dos procesamientos M06 y auditoría dentro del sandbox',
      'DELETE de RUN intenta rollback; el HTTP 200 no prueba reversión de efectos externos'] };
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
const nombreInforme = v => v === 1 ? 'TC-M06-G33_resultado.md' : `TC-M06-G33_reevaluacion_V${v}.md`;
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
  if (actual?.estado === 'EN_CIERRE') return { motivo: 'período que contiene hoy EN_CIERRE' };
  const desde = actual ? actual.fecha_fin : hoy;
  const posterior = propios.filter(p => p.estado === 'ABIERTO' && p.fecha_inicio > desde)
    .sort((a, b) => String(a.fecha_inicio).localeCompare(String(b.fecha_inicio)) || id(a.id_periodo_contable) - id(b.id_periodo_contable))[0];
  return posterior ? { periodo: posterior, correccion: actual?.estado === 'CERRADO' } :
    { motivo: actual?.estado === 'CERRADO' ? 'período actual CERRADO sin posterior ABIERTO visible' : 'sin período ABIERTO posterior visible' };
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
const informeNombre = v => v === 1 ? 'TC-M06-G33_resultado.md' : 'TC-M06-G33_reevaluacion_V' + v + '.md';
const ids = (lista, clave) => lista.map(x => String(x[clave]));
const soloNuevo = (antes, despues, clave) => { const base = new Set(ids(antes, clave)); return despues.filter(x => !base.has(String(x[clave]))); };
const recencia = x => ({ fecha: String(x?.fecha_envio ?? ''), id: id(x?.id_notificacion) });
const compararRecencia = (a, b) => a.fecha.localeCompare(b.fecha) || a.id - b.id;
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
      if (!clave.fecha || !clave.id || vistos.has(clave.id)) return { completa: false, items };
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
    '/finanzas/activos/' + aid,
  ];
  const respuestas = [];
  for (const ruta of rutas) {
    if (r._corte) break;
    respuestas.push(await pedir(r, api, 'GET', ruta, opciones));
  }
  if (respuestas.length !== rutas.length) return { completa: false, motivo: 'Corte antes de completar las lecturas.' };
  const [v, l, m, d] = respuestas;
  const a = await leerAuditoria(r, api, opciones, aid, pid);
  const b = await leerBandeja(r, api, opciones, bandejaBase ? bandejaBase.bandejaLineaBase : undefined);
  if (![v, l, m, d].every(x => x.http === 200 && x.eco !== false) || !Array.isArray(v.cuerpo) ||
      !Array.isArray(l.cuerpo) || !Array.isArray(m.cuerpo) || !Array.isArray(d.cuerpo?.calculos) ||
      !Array.isArray(d.cuerpo?.mediciones) || !a.completa || !b.completa)
    return { completa: false, motivo: 'Lectura pública incompleta, 5xx, sin eco o página truncada.',
      http: respuestas.map(x => x.http), rutas, auditoriaCompleta: a.completa, bandejaCompleta: b.completa };
  const calculos = d.cuerpo.calculos;
  return { completa: true, variaciones: v.cuerpo, lineas: l.cuerpo, mediciones: m.cuerpo,
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

async function newmanLecturas(r, c, env, token, aid, pid, eventoId, base, secretos) {
  if (r.solicitudes.length + 2 > PRESUPUESTO.solicitudes_totales) return null;
  const vars = { base_url: String(env.SIGAB_API_TEST_BASE).replace(/\/+$/, ''), run_id: c.runId,
    sandbox_secret: env.QA_SANDBOX_SECRET, token, activo_id: String(aid), periodo_id: String(pid),
    evento_id: String(eventoId), ids_variaciones_base: JSON.stringify(ids(base.variaciones, 'id_variacion_valor_razonable')) };
  const environment = { values: Object.entries(vars).map(([key, value]) => ({ key, value, enabled: true })) };
  const out = spawnSync(process.execPath, [path.join(DIR, 'pruebas', 'newman_hijo.mjs')], {
    input: JSON.stringify({ coleccion: JSON.parse(fs.readFileSync(COLECCION, 'utf8')), environment,
      timeout: PRESUPUESTO.timeout_ms }), timeout: 120000, encoding: 'utf8', windowsHide: true, maxBuffer: 1024 * 1024 });
  let hijo = null; try { hijo = JSON.parse(out.stdout); } catch { /* hijo sin respuesta */ }
  const sintesis = { version: newmanVersion(), codigo: out.status, error: out.error?.code ?? hijo?.error ?? null,
    estadisticas: hijo?.estadisticas ?? null, solicitudes: hijo?.solicitudes ?? [] };
  const dir = path.join(c.directorio, 'newman'); fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'newman-G33.json'), sanear(JSON.stringify(sintesis, null, 2), secretos));
  fs.writeFileSync(path.join(dir, 'newman-G33.html'), '<!doctype html><meta charset="utf-8"><title>G33 Newman</title><h1>G33 Newman</h1><pre>' + esc(sanear(JSON.stringify(sintesis, null, 2), secretos)) + '</pre>', 'utf8');
  for (const s of sintesis.solicitudes) r.solicitudes.push({ caso: casoCompleto(CASO), metodo: 'GET',
    ruta: s.nombre === IDS[0] ? '/finanzas/periodos/{id}/variaciones' : '/finanzas/auditoria',
    http: s.http, duracion_ms: s.duracion_ms, herramienta: 'Newman' });
  const fallos = sintesis.solicitudes.flatMap(s => s.aserciones.filter(x => x.error)).length;
  r.herramientas.newman = { version: sintesis.version, iteraciones: sintesis.solicitudes.length === 2 ? 1 : 0,
    solicitudes: sintesis.solicitudes.length, fallos, codigo: out.status };
  return sintesis;
}

export function informe(c, r) {
  const x = r.casos[CASO], o = x.observados ?? {};
  const valor = v => v == null ? 'no observado' : limpio(v);
  const pre = x.preparacion ?? {};
  const observados = 'Variaciones nuevas ' + valor(o.variaciones) + '; líneas nuevas ' + valor(o.lineas) +
    '; mediciones nuevas ' + valor(o.mediciones) + '; cálculos nuevos ' + valor(o.calculos) +
    '; último cálculo ' + valor(o.calculo_ultimo_antes) + ' → ' + valor(o.calculo_ultimo_despues) +
    '; valor razonable ' + valor(o.valor_anterior) + ' → ' + valor(o.valor_nuevo) +
    '; auditorías conformes ' + valor(o.auditorias_sin_variacion) + '; alertas de auditoría ' +
    valor(o.alertas_auditoria) + '; avisos de error del caso ' + valor(o.avisos_error) +
    '; avisos ajenos observados ' + valor(o.avisos_ajenos) +
    '; avisos relacionados sin error ' + valor(o.avisos_relacionados_sin_error) + '.';
  const incidencias = r.incidencias.length ? r.incidencias.map(i => '### ' + i.id + '\n\n' +
    'Requisito: RF-86 paso 4 y CA-14. Primera discrepancia: ' + limpio(i.discrepancia) +
    '. Severidad ' + i.severidad + ': ' + limpio(i.justificacion) + '. Certeza ' + i.certeza +
    ' sobre el incumplimiento observado; causa raíz NO DETERMINADA. Equipo inicial: Desarrollo, por la primera respuesta pública discrepante. ' +
    'Acción: Desarrollo revisa; QA reevalúa con autorización. Evidencia: resultado.json y lecturas API del RUN.').join('\n\n') :
    'No se confirmaron incidencias de producto.';
  const decision = x.estado;
  return '# TC-M06-G33 — ' + decision + '\n\n## Identificación\n\n' + casoCompleto(CASO) +
    '; RF-86 v2.0; RUN ' + c.runId + '; versión ' + c.version + '; intento ' + c.intento +
    '; ambiente TEST; autorización ' + limpio(c.referencia) + '; commit de TEST no verificado; Node ' + process.version +
    '; Newman ' + valor(r.herramientas.newman?.version) + '; API únicamente.\n\n## Resumen de veredictos\n\n| Caso | Estado | Motivo |\n|---|---|---|\n| ' +
    casoCompleto(CASO) + ' | ' + decision + ' | ' + limpio(x.motivo) + ' |\n\n## Diagnóstico de candidatos\n\n' +
    Object.entries(r.diagnostico_candidatos).map(([k, v]) => k + ': ' + valor(v)).join('; ') +
    '\n\n## Detalle por caso\n\n### ' + casoCompleto(CASO) + '\n\n- **Preparación:** activo ' + valor(pre.activo) +
    ', período destino ' + valor(pre.periodo) + ', precio vigente ' + valor(pre.precio) +
    ', peso constante ' + valor(pre.peso_kg) + ' kg; rebase ' + valor(pre.rebase) +
    '. El rebase, si ocurrió, queda fuera del oráculo.\n- **Esperado:** no se crea variación ni línea de asiento; no se emite alerta de error; RF-94 registra exactamente una medición sin variación del activo. Valores razonables anterior y nuevo iguales y positivos.\n- **Observado:** ' +
    observados + ' Evento M02 ' + valor(pre.evento) + '.\n- **Cumplido:** ' + valor(x.cumplido) +
    '.\n- **Falló y por qué:** ' + (decision === 'APROBADO' ? 'Ningún incumplimiento observado' : limpio(x.motivo)) +
    '.\n- **Decisión:** ' + decision + '.\n\n## Comprobaciones API y evidencias\n\n' +
    r.comprobaciones.map(z => '- ' + z.id + ': ' + z.estado + '. ' + limpio(z.motivo) + ' Evidencia: ' + z.evidencia + '.').join('\n') +
    '\n\n## Incidencias de producto\n\n' + incidencias +
    '\n\n## Problemas técnicos y análisis de causas\n\n' + (r.problemas_tecnicos.map(limpio).join('; ') || 'Ninguno observado.') +
    ' Las respuestas HTTP por sí solas no prueban causa raíz.\n\n## Cierre y rollback\n\nDELETE HTTP ' +
    valor(r.cierre.run.cierre_http) + '; rollback ' + (r.cierre.rollback.verificado ? 'verificado' : 'NO verificado') +
    ': ' + limpio(r.cierre.rollback.motivo) + '. Lecturas poscierre de eventos M02 y auditoría RF-94 incluidas solo si DELETE fue 200.\n\n## Conclusión y acciones\n\n' +
    (decision === 'APROBADO' ? 'Oráculo completo demostrado por API pública.' :
      decision === 'RECHAZADO' ? 'Desarrollo debe revisar la discrepancia documentada; QA reevalúa con nueva autorización.' :
      'Resolver el impedimento o lectura faltante y solicitar nueva ejecución autorizada.') +
    '\n\n## Herramientas y cierre\n\nNewman: ' + valor(r.herramientas.newman?.solicitudes) +
    ' lecturas, ' + valor(r.herramientas.newman?.fallos) + ' aserciones fallidas. Cypress: 0, sin UI requerida.\n';
}

export async function evaluar(c, { env = leerEnv(), apiOverride = null, sinArtefactos = false } = {}) {
  const api = apiOverride ?? String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G33', run_id: c.runId, version: c.version, intento: c.intento, casos: {},
    comprobaciones: [], solicitudes: [], evidencias: [], incidencias: [], problemas_tecnicos: [],
    herramientas: { node: process.version, newman: null }, cypress: { total_pruebas: 0 },
    diagnostico_candidatos: { medido: false, total_recibido: 0, bovino: 0, individual: 0, estado: 0,
      sin_costo: 0, valor_positivo: 0, precio_vigente: 0, periodo_destino: 0, peso_kg: 0,
      calculo_previo: 0, primera_condicion_fallida: null },
    cierre: { run: { cierre_http: null, cuerpo_saneado: null }, rollback: { verificado: false, motivo: 'No comprobado' } },
    oficial: false, consume_version: false, _seguidos5xx: 0, _corte: false,
    _limite: Date.now() + PRESUPUESTO.duracion_segundos * 1000 };
  const pf = preflight(c, env, sinArtefactos ? 'ensayo-local' : newmanVersion());
  r.herramientas.newman_preflight_version = pf.herramientas.newman;
  r._secretos = [env.QA_SANDBOX_SECRET, env.QA_CONTADOR_EMAIL, env.QA_CONTADOR_PASSWORD,
    env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD];
  if (!sinArtefactos) {
    if (!fs.existsSync(c.directorio)) throw Error('El lanzador debe crear el RUN antes de evaluar');
    guardar(path.join(c.directorio, 'preflight.json'), pf); r.evidencias.push('preflight.json');
  }
  const terminar = (estado, motivo, extra = {}) => {
    r.casos[CASO] = { ...extra, caso: casoCompleto(CASO), estado, motivo: limpio(motivo) };
    for (const clave of IDS) r.comprobaciones.push({ caso: CASO, fuente: 'API', id: clave,
      tipo: 'ASSERT', estado, motivo: limpio(motivo), evidencia: sinArtefactos ? 'ensayo-local' : 'resultado.json' });
    if (estado === 'RECHAZADO') r.incidencias = [{ id: 'INC-M06-G33-01', caso: casoCompleto(CASO),
      discrepancia: motivo, severidad: /Se creó variación|Se creó línea de asiento/.test(motivo) ? 'ALTA' : 'MEDIA',
      justificacion: /Se creó variación|Se creó línea de asiento/.test(motivo) ?
        'Se registró un hecho contable indebido para un activo sin variación; afecta una funcionalidad financiera relevante sin corrección automática observada.' :
        'La trazabilidad o ausencia de alerta de una medición sin variación quedó incumplida en este activo.',
      certeza: 'CONFIRMADA', equipo_inicial: 'Desarrollo', causa_raiz: 'NO DETERMINADA' }];
  };
  let token = null, tokenM02 = null, iniciado = false;
  const datos = { aid: null, pid: null, base: null, rollbackBase: null, eventos: [] };
  try {
    if (!pf.ok) { terminar('BLOQUEADO', 'Preflight local: ' + pf.barreras.join(', ')); return r; }
    const login = await pedir(r, api, 'POST', '/sesiones/', { cuerpo: { correo_electronico: env.QA_CONTADOR_EMAIL,
      contrasena: env.QA_CONTADOR_PASSWORD }, timeout: PRESUPUESTO.timeout_login_ms });
    token = login.cuerpo?.token ?? login.cuerpo?.access_token ?? null;
    if (login.http !== 200 || !token) { terminar('NO_CONCLUYENTE', 'No se obtuvo sesión del Contador QA.'); return r; }
    const lm = await pedir(r, api, 'POST', '/sesiones/', { cuerpo: { correo_electronico: env.QA_ADMIN_EMAIL,
      contrasena: env.QA_ADMIN_PASSWORD }, timeout: PRESUPUESTO.timeout_login_ms });
    tokenM02 = lm.cuerpo?.token ?? lm.cuerpo?.access_token ?? null;
    if (lm.http !== 200 || !tokenM02) { terminar('NO_CONCLUYENTE', 'No se obtuvo sesión de Administrador QA.'); return r; }
    const opts = { token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, caso: CASO };
    const mopts = { ...opts, token: tokenM02 };
    const a = await pedir(r, api, 'GET', '/finanzas/activos', opts); iniciado = true;
    if (r._corte) { terminar('BLOQUEADO', 'Corte por HTTP 403 o tres 5xx consecutivos.'); return r; }
    const p = await pedir(r, api, 'GET', '/finanzas/periodos', opts);
    if (r._corte) { terminar('BLOQUEADO', 'Corte por HTTP 403 o tres 5xx consecutivos.'); return r; }
    if (a.http !== 200 || p.http !== 200 || !a.eco || !p.eco || !Array.isArray(a.cuerpo) || !Array.isArray(p.cuerpo)) {
      terminar('NO_CONCLUYENTE', 'Catálogos públicos incompletos; no se puede identificar activo y período.'); return r;
    }
    const diag = r.diagnostico_candidatos; diag.medido = true; diag.total_recibido = a.cuerpo.length;
    let candidatos = a.cuerpo.filter(x => /bovin/i.test(x.especie ?? '')); diag.bovino = candidatos.length;
    candidatos = candidatos.filter(x => x.tipo === 'INDIVIDUAL'); diag.individual = candidatos.length;
    candidatos = candidatos.filter(x => x.estado === 'ACTIVO'); diag.estado = candidatos.length;
    candidatos = candidatos.filter(x => !x.valorado_por_costo); diag.sin_costo = candidatos.length;
    candidatos = candidatos.filter(x => Number(x.valor_razonable_neto) > 0); diag.valor_positivo = candidatos.length;
    const precios = new Map(); const posibles = []; let lectura5xx = false;
    for (const x of candidatos.slice(0, 6)) {
      if (r._corte) break;
      const especie = id(x.id_especie), aid = id(x.id_activo_biologico);
      if (!precios.has(especie)) {
        const pr = await pedir(r, api, 'GET', '/finanzas/precios?id_especie=' + especie, opts);
        if (pr.http >= 500 || pr.http == null) lectura5xx = true;
        precios.set(especie, pr.http === 200 && pr.eco && Array.isArray(pr.cuerpo) ? preciosVigentes(pr.cuerpo, especie) : null);
      }
      const precio = precios.get(especie); if (!precio) continue; diag.precio_vigente++;
      const d = await pedir(r, api, 'GET', '/finanzas/activos/' + aid, opts);
      if (d.http >= 500 || d.http == null) lectura5xx = true;
      if (d.http !== 200 || !d.eco) continue;
      const periodo = periodoDestino(p.cuerpo, d.cuerpo?.activo?.numero_id_tributaria);
      if (!periodo.periodo) continue; diag.periodo_destino++;
      const f = await pedir(r, api, 'GET', '/activos-biologicos/' + aid + '/ficha-integral', mopts);
      if (f.http >= 500 || f.http == null) lectura5xx = true;
      if (f.http !== 200 || !f.eco || f.cuerpo?.unidad_peso !== 'kg' || !(Number(f.cuerpo.peso_actual) > 0)) continue;
      diag.peso_kg++;
      const calculo = ultimoCalculo(d.cuerpo);
      if (!calculo || !(Number(calculo.valor_neto) > 0)) continue; diag.calculo_previo++;
      posibles.push({ activo: x, periodo: periodo.periodo, precio, peso: Number(f.cuerpo.peso_actual), calculo });
    }
    if (r._corte) { terminar('BLOQUEADO', 'Corte por HTTP 403 o tres 5xx consecutivos.'); return r; }
    const condiciones = [['bovino', 'bovino'], ['individual', 'INDIVIDUAL'], ['estado', 'ACTIVO'],
      ['sin_costo', 'sin valoración por costo'], ['valor_positivo', 'valor razonable positivo'],
      ['precio_vigente', 'precio PESO_KG vigente'], ['periodo_destino', 'período destino ABIERTO'],
      ['peso_kg', 'peso actual kg'], ['calculo_previo', 'cálculo previo CALCULADO positivo']];
    diag.primera_condicion_fallida = condiciones.find(([k]) => diag[k] === 0)?.[1] ?? null;
    posibles.sort((x, y) => Number(id(y.calculo.id_precio_mercado) === id(y.precio.id_precio_mercado)) -
      Number(id(x.calculo.id_precio_mercado) === id(x.precio.id_precio_mercado)));
    const s = posibles[0];
    if (!s) { terminar(lectura5xx ? 'NO_CONCLUYENTE' : 'BLOQUEADO',
      lectura5xx ? 'Lectura 5xx o sin respuesta impidió diagnosticar el candidato.' :
        'BLOQUEO_DATOS: falta ' + (diag.primera_condicion_fallida ?? 'activo elegible') + '.'); return r; }
    const aid = id(s.activo.id_activo_biologico), pid = id(s.periodo.id_periodo_contable);
    datos.aid = aid; datos.pid = pid;
    const preparacion = { activo: aid, periodo: pid, precio: id(s.precio.id_precio_mercado), peso_kg: s.peso, rebase: 'no requerido' };
    const eventosBaseResp = await pedir(r, api, 'GET', '/activos-biologicos/' + aid + '/eventos', mopts);
    if (eventosBaseResp.http !== 200 || !eventosBaseResp.eco || !Array.isArray(eventosBaseResp.cuerpo?.eventos)) {
      terminar('NO_CONCLUYENTE', 'No se pudo fijar línea base de eventos M02.', { preparacion }); return r;
    }
    let eventosBase = new Set(ids(eventosBaseResp.cuerpo.eventos, 'id_eventos'));
    datos.rollbackBase = await instantanea(r, api, opts, aid, pid);
    if (!datos.rollbackBase.completa) { terminar('NO_CONCLUYENTE', 'No se pudo fijar línea base de rollback.', { preparacion }); return r; }
    const crearEvento = async descripcion => {
      const e = await pedir(r, api, 'POST', '/activos-biologicos/' + aid + '/eventos/crecimiento', { ...mopts,
        cuerpo: { tipo_medicion: 'PESO', valor_medicion: s.peso, unidad_medida: 'kg', descripcion } });
      let eid = id(e.cuerpo?.evento?.id_eventos);
      if (e.http == null || !eid) eid = await conciliarEvento(r, api, mopts, aid, eventosBase);
      if (eid) { datos.eventos.push(eid); eventosBase.add(String(eid)); }
      return { respuesta: e, eid };
    };
    if (id(s.calculo.id_precio_mercado) !== id(s.precio.id_precio_mercado) || !igualMonto(s.calculo.magnitud, s.peso)) {
      const rebase = await crearEvento('Rebase previo QA ' + c.runId);
      if (!rebase.eid) { terminar('NO_CONCLUYENTE', 'Evento de rebase sin ID conciliable; no se reintenta.', { preparacion }); return r; }
      const proc = await pedir(r, api, 'POST', '/finanzas/eventos/procesar', opts);
      const det = await pedir(r, api, 'GET', '/finanzas/activos/' + aid, opts);
      const ultimo = det.http === 200 && det.eco ? ultimoCalculo(det.cuerpo) : null;
      if (!ultimo || id(ultimo.id_precio_mercado) !== id(s.precio.id_precio_mercado) ||
          !igualMonto(ultimo.magnitud, s.peso) || !(Number(ultimo.valor_neto) > 0)) {
        terminar(proc.http >= 500 || proc.http == null ? 'NO_CONCLUYENTE' : 'BLOQUEADO',
          'No se acreditó el rebase de precio y peso previo al caso.', { preparacion }); return r;
      }
      s.calculo = ultimo; preparacion.rebase = 'evento M02 ' + rebase.eid + ', cálculo ' + id(ultimo.id_calculo_valor_razonable);
    }
    const base = await instantanea(r, api, opts, aid, pid); datos.base = base;
    if (!base.completa) { terminar('NO_CONCLUYENTE', 'No se pudo fijar línea base completa: ' + base.motivo, { preparacion }); return r; }
    const precioActual = await pedir(r, api, 'GET', '/finanzas/precios?id_especie=' + id(s.activo.id_especie), opts);
    const fichaActual = await pedir(r, api, 'GET', '/activos-biologicos/' + aid + '/ficha-integral', mopts);
    if (precioActual.http !== 200 || fichaActual.http !== 200 || !precioActual.eco || !fichaActual.eco ||
        !Array.isArray(precioActual.cuerpo)) {
      terminar('NO_CONCLUYENTE', 'No se pudo reconfirmar precio y estado antes del evento.', { preparacion }); return r;
    }
    if (id(preciosVigentes(precioActual.cuerpo, s.activo.id_especie)?.id_precio_mercado) !== id(s.precio.id_precio_mercado) ||
        fichaActual.cuerpo?.estado_actual !== 'ACTIVO' || !igualMonto(fichaActual.cuerpo?.peso_actual, s.peso)) {
      terminar('BLOQUEADO', 'Cambió el precio vigente, el estado ACTIVO o el peso antes del evento; falta condición estable.', { preparacion }); return r;
    }
    const evento = await crearEvento('Medición sin variación QA ' + c.runId);
    if (!evento.eid) { terminar('NO_CONCLUYENTE', 'Evento del caso sin ID conciliable; no se reintenta.', { preparacion }); return r; }
    preparacion.evento = evento.eid;
    const proc = await pedir(r, api, 'POST', '/finanzas/eventos/procesar', opts);
    const posterior = await instantanea(r, api, opts, aid, pid, base);
    if (!posterior.completa) { terminar('NO_CONCLUYENTE', 'Lectura posterior incompleta: ' + posterior.motivo, { preparacion }); return r; }
    const decision = evaluarOraculo({ anterior: base, posterior, eventoId: evento.eid, activoId: aid,
      identificadorActivo: s.activo.identificador ?? s.activo.identificador_activo, periodoId: pid });
    if (proc.http !== 200 && decision.estado !== 'RECHAZADO') {
      terminar('NO_CONCLUYENTE', 'Procesamiento sin HTTP 200; lectura conciliada, sin reintento. ' + decision.motivo,
        { preparacion, observados: decision.observados });
    } else terminar(decision.estado, decision.motivo, { preparacion, observados: decision.observados,
      cumplido: 'Lecturas de variaciones, líneas, mediciones, historial, RF-94 y bandeja contrastadas' });
    if (!sinArtefactos) {
      const sintesis = await newmanLecturas(r, c, env, token, aid, pid, evento.eid, base,
        [token, tokenM02, ...r._secretos]);
      if (!sintesis || r.herramientas.newman?.iteraciones !== 1) {
        r.problemas_tecnicos.push('Newman no produjo dos lecturas completas.');
        if (r.casos[CASO].estado === 'APROBADO') terminar('NO_CONCLUYENTE', 'Falta evidencia Newman completa.', { preparacion, observados: decision.observados });
      } else if (r.herramientas.newman.fallos > 0 && r.casos[CASO].estado === 'APROBADO') {
        r.problemas_tecnicos.push('Newman discrepa de las lecturas paginadas del ejecutor; revisar respuesta y cobertura de la colección.');
        terminar('NO_CONCLUYENTE', 'Evidencia Newman contradictoria con las lecturas paginadas.',
          { preparacion, observados: decision.observados });
      }
    }
  } finally {
    if (iniciado) {
      const del = await pedir(r, api, 'DELETE', '/test-control/runs/' + encodeURIComponent(c.runId),
        { token, secreto: env.QA_SANDBOX_SECRET, timeout: PRESUPUESTO.timeout_ms });
      r.cierre.run.cierre_http = del.http; r.cierre.run.cuerpo_saneado = del.fila?.cuerpo_saneado ?? null;
      r.cierre.rollback = del.http === 200 ? await comprobarRollback(r, api, env, token, tokenM02, datos) :
        { verificado: false, motivo: 'DELETE HTTP ' + (del.http ?? 'sin respuesta') + '; sin lecturas poscierre.' };
    }
    if (!r.casos[CASO]) terminar('NO_CONCLUYENTE', 'No se completó el caso; revisar lecturas saneadas.');
    r.oficial = oficialidadLocal(r, sinArtefactos);
    r.consume_version = r.oficial;
    r.estado_ejecucion = r.oficial ? (c.ensayo ? 'OFICIAL_LOCAL' : 'OFICIAL') : 'NO_OFICIAL';
    if (!sinArtefactos && fs.existsSync(c.directorio)) {
      const secretos = [token, tokenM02, ...r._secretos];
      r.evidencias.push('resultado.json', informeNombre(c.version));
      if (r.herramientas.newman) r.evidencias.push('newman/newman-G33.json', 'newman/newman-G33.html');
      const pub = { ...r }; for (const k of ['_limite', '_corte', '_seguidos5xx', '_secretos']) delete pub[k];
      fs.writeFileSync(path.join(c.directorio, 'resultado.json'), sanear(JSON.stringify(pub, null, 2), secretos));
      fs.writeFileSync(path.join(c.directorio, informeNombre(c.version)), sanear(informe(c, r), secretos));
    }
    delete r._secretos;
  }
  return r;
}
if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
else if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const c = contexto(process.argv.slice(2)); const r = await evaluar(c);
    console.log(JSON.stringify({ grupo: 'G33', run_id: c.runId, oficial: r.oficial, casos: r.casos }));
    if (!r.oficial) process.exitCode = 2;
  } catch (e) { console.error(limpio(e.message)); process.exitCode = 2; }
}
