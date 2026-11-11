#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { CASOS, IDS, PRESUPUESTO, CAPACIDADES, casoCompleto, evaluarOraculo, valoresEsperados, igualMonto, oficialidadLocal } from './lib/g32_core.mjs';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const require = createRequire(import.meta.url);
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION = path.join(DIR, 'G32.postman_collection.json');
const ARCHIVOS = ['g32.mjs', 'G32.postman_collection.json', 'README.md', 'lib/g32_core.mjs',
  'pruebas/g32_env.test.mjs', 'pruebas/g32_ensayo.mjs', 'pruebas/registro_qa.mjs',
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
    coleccion = col.item?.length === 4 && col.item.every((x, i) => x.name === IDS[i] && x.request.method === 'GET');
  } catch { /* colección inválida */ }
  const markdownSuperior = fs.existsSync(path.join(DIR, 'Resultados')) &&
    fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const ok = !faltantes.length && coleccion && !markdownSuperior && PRESUPUESTO.timeout_post_ms === 120000;
  console.log(JSON.stringify({ grupo: 'G32', ok, faltantes, coleccion, markdown_superior: markdownSuperior,
    newman_local: !!newmanVersion(), presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}
export function contexto(args) {
  const v = k => args.includes(k) ? args[args.indexOf(k) + 1] : undefined;
  const operacion = v('--operacion'), version = Number(v('--version')), intento = Number(v('--intento')),
    runId = v('--run-id'), referencia = v('--autorizacion'), archivo = v('--contexto');
  if (!CAPACIDADES.operaciones.includes(operacion) || !Number.isInteger(version) || version < 1 || version > 99 ||
      !Number.isInteger(intento) || intento < 1 || !referencia || !archivo ||
      !new RegExp(`^RUN-G32-V${version}-\\d{8}-\\d{6}$`).test(runId ?? '')) throw Error('Contexto incompleto');
  const destino = path.join(DIR, ...(version === 1 ? ['Resultados', runId] : [`EvaluacionV${version}`, 'Resultados', runId]));
  const ruta = path.resolve(archivo);
  if (path.dirname(ruta) !== destino || path.basename(ruta) !== 'contexto_operacion.json') throw Error('Contexto fuera del RUN');
  const c = JSON.parse(fs.readFileSync(ruta, 'utf8'));
  if (c.grupo !== 'G32' || c.run_id !== runId || c.version !== version || c.intento !== intento ||
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
  return { grupo: 'G32', run_id: c.runId, fase: 'PREFLIGHT_LOCAL', ok: !barreras.length,
    barreras, presupuesto: PRESUPUESTO, herramientas: { node: process.version, newman: n },
    efectos: ['Login de Contador y Administrador fuera del RUN', 'Eventos de crecimiento M02 y eventual cambio de estado',
      'Dos precios RF-89 con notificación M01 fuera de la sesión sandbox',
      'Procesamiento M06, líneas y auditoría dentro de la sesión sandbox; cadena por GET tras una verificacion RF-91 por periodo',
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
      signal: AbortSignal.timeout(timeout ?? (metodo === 'POST' ? PRESUPUESTO.timeout_post_ms : PRESUPUESTO.timeout_ms)) });
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
const nombreInforme = v => v === 1 ? 'TC-M06-G32_resultado.md' : `TC-M06-G32_reevaluacion_V${v}.md`;
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
function seleccionar(activos, periodos, precios, fallosPrecio = new Map()) {
  const hoy = fecha();
  const elegibles = activos.filter(a => a._periodo?.periodo && a._pesoKg && a._calculo &&
    (preciosVigentes(precios, a.id_especie) || fallosPrecio.has(id(a.id_especie))))
    .sort((a, b) => Number(!!preciosVigentes(precios, b.id_especie)) - Number(!!preciosVigentes(precios, a.id_especie)) ||
      Number(id(b._calculo.id_precio_mercado) === id(preciosVigentes(precios, b.id_especie)?.id_precio_mercado)) -
      Number(id(a._calculo.id_precio_mercado) === id(preciosVigentes(precios, a.id_especie)?.id_precio_mercado)));
  const usados = new Set(), salida = [];
  for (let i = 0; i < 4; i++) {
    const disponibles = elegibles.filter(x => !usados.has(x.id_activo_biologico) && x.estado === 'ACTIVO');
    const coincide = x => id(x._calculo.id_precio_mercado) === id(preciosVigentes(precios, x.id_especie)?.id_precio_mercado);
    const a = i === 0 && disponibles.filter(coincide).length === 1 ?
      disponibles.find(x => !coincide(x)) ?? disponibles[0] : disponibles[0];
    const requiereTratamiento = i === 1;
    if (!a) { salida.push(null); continue; }
    usados.add(a.id_activo_biologico);
    salida.push({ activo: a, periodo: a._periodo.periodo, precio: preciosVigentes(precios, a.id_especie), requiereTratamiento,
      calculoPrevio: a._calculo, peso: a._pesoKg });
  }
  return salida;
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
async function comprobarRollback(r, api, env, token, tokenM02, hechos) {
  if (r.cierre.run.cierre_http !== 200) return { verificado: false, motivo: 'DELETE no confirmó cierre del sandbox.' };
  const opciones = t => ({ token: t, timeout: PRESUPUESTO.timeout_ms });
  const precios = hechos.filter(x => x.tipo === 'precio');
  const eventos = hechos.filter(x => x.tipo === 'evento');
  const variaciones = hechos.filter(x => x.tipo === 'variacion');
  const bases = hechos.filter(x => x.tipo === 'linea_base');
  const estados = hechos.filter(x => x.tipo === 'estado');
  const fallos = [];
  if (hechos.some(x => x.tipo === 'escritura_incierta' || x.tipo === 'precio_sin_id'))
    fallos.push('una escritura del sandbox no tiene identificador o respuesta conciliable');
  for (const especie of [...new Set(precios.map(x => x.especie))]) {
    const x = await pedir(r, api, 'GET', `/finanzas/precios?id_especie=${especie}`, opciones(token));
    if (x.http !== 200 || !Array.isArray(x.cuerpo)) fallos.push(`precios de especie ${especie}: lectura pública incompleta`);
    else if (x.cuerpo.some(p => precios.some(h => h.id === id(p.id_precio_mercado)))) fallos.push('precio del RUN aún visible');
  }
  for (const pid of [...new Set([...variaciones.map(x => x.periodo), ...bases.map(x => x.periodo)])]) {
    const x = await pedir(r, api, 'GET', `/finanzas/periodos/${pid}/variaciones`, opciones(token));
    if (x.http !== 200 || !Array.isArray(x.cuerpo)) fallos.push(`variaciones del período ${pid}: lectura incompleta`);
    else {
      if (x.cuerpo.some(v => variaciones.some(h => h.id === id(v.id_variacion_valor_razonable))))
        fallos.push(`variación del RUN aún visible en período ${pid}`);
      if (bases.some(b => b.periodo === pid && x.cuerpo.some(v =>
        id(v.id_activo_biologico) === b.activo && !b.ids.includes(String(v.id_variacion_valor_razonable)))))
        fallos.push(`variación posterior a la línea base aún visible en período ${pid}`);
    }
  }
  for (const aid of [...new Set(eventos.map(x => x.activo))]) {
    const x = await pedir(r, api, 'GET', `/activos-biologicos/${aid}/eventos`, opciones(tokenM02));
    if (x.http !== 200 || !Array.isArray(x.cuerpo?.eventos)) fallos.push(`eventos M02 del activo ${aid}: lectura incompleta`);
    else if (x.cuerpo.eventos.some(e => eventos.some(h => h.activo === aid && h.id === id(e.id_eventos))))
      fallos.push(`evento M02 del RUN aún visible para activo ${aid}`);
  }
  for (const h of estados) {
    const x = await pedir(r, api, 'GET', `/activos-biologicos/${h.activo}/ficha-integral`, opciones(tokenM02));
    if (x.http !== 200 || x.cuerpo?.estado_actual !== h.anterior)
      fallos.push(`estado previo del activo ${h.activo} no confirmado`);
  }
  return { verificado: !fallos.length,
    motivo: fallos.length ? fallos.join('; ') : 'DELETE 200 y ausencia pública poscierre de los registros del RUN; estado M02 restaurado si se preparó.' };
}
async function newmanLecturas(r, c, env, token, seleccion, secretos) {
  if (r.solicitudes.length + 4 > PRESUPUESTO.solicitudes_totales) {
    r.problemas_tecnicos.push('Presupuesto agotado antes de las cuatro lecturas Newman.');
    for (const k of CASOS) if (r.casos[k]?.estado === 'APROBADO') {
      r.casos[k] = casoRegistro(k, 'NO_CONCLUYENTE', 'No hubo margen para la lectura Newman obligatoria.', r.casos[k]);
      const comp = r.comprobaciones.find(x => x.caso === k);
      if (comp) { comp.estado = 'NO_CONCLUYENTE'; comp.motivo = 'Sin lectura Newman por presupuesto.'; }
    }
    return null;
  }
  const base = String(env.SIGAB_API_TEST_BASE).replace(/\/+$/, '');
  const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
  const vars = { base_url: base, run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET, token };
  for (let i = 0; i < 4; i++) vars[`periodo_${i + 1}`] = String(seleccion[i]?.periodo?.id_periodo_contable ?? 0);
  const environment = { values: Object.entries(vars).map(([key, value]) => ({ key, value, enabled: true })) };
  const sub = path.join(c.directorio, 'newman'); fs.mkdirSync(sub, { recursive: true });
  const out = spawnSync(process.execPath, [path.join(DIR, 'pruebas', 'newman_hijo.mjs')], {
    input: JSON.stringify({ coleccion: JSON.parse(fs.readFileSync(COLECCION, 'utf8')), environment,
      timeout: PRESUPUESTO.timeout_ms }), timeout: 180000, encoding: 'utf8', windowsHide: true,
    maxBuffer: 1024 * 1024 });
  let hijo = null; try { hijo = JSON.parse(out.stdout); } catch { /* proceso hijo sin salida válida */ }
  const sintesis = { version: newmanVersion(), codigo: out.status, error: out.error?.code ?? hijo?.error ?? null,
    estadisticas: hijo?.estadisticas ?? null, solicitudes: hijo?.solicitudes ?? [] };
  for (const s of sintesis.solicitudes) r.solicitudes.push({ caso: s.nombre ? casoCompleto(CASOS[IDS.indexOf(s.nombre)]) : null,
    metodo: 'GET', ruta: '/finanzas/periodos/{id}/variaciones', http: s.http,
    duracion_ms: s.duracion_ms, herramienta: 'Newman' });
  fs.writeFileSync(path.join(sub, 'newman-G32.json'), sanear(JSON.stringify(sintesis, null, 2), secretos));
  fs.writeFileSync(path.join(sub, 'newman-G32.html'), `<!doctype html><meta charset="utf-8"><title>G32 Newman</title><h1>G32 Newman</h1><pre>${esc(sanear(JSON.stringify(sintesis, null, 2), secretos))}</pre>`, 'utf8');
  r.herramientas.newman = { version: sintesis.version, iteraciones: sintesis.solicitudes.length ? 1 : 0,
    solicitudes: sintesis.solicitudes.length,
    fallos: sintesis.solicitudes.flatMap(x => x.aserciones.filter(a => a.error)).length, codigo: out.status };
  if (out.status !== 0 || sintesis.solicitudes.length !== 4) {
    r.problemas_tecnicos.push('Newman no produjo cuatro lecturas completas; falta evidencia obligatoria.');
    for (const k of CASOS) if (r.casos[k]?.estado === 'APROBADO') {
      r.casos[k] = casoRegistro(k, 'NO_CONCLUYENTE', 'Newman no produjo evidencia completa.', r.casos[k]);
      const comp = r.comprobaciones.find(x => x.caso === k);
      if (comp) { comp.estado = 'NO_CONCLUYENTE'; comp.motivo = 'Newman no produjo evidencia completa.'; }
    }
  }
  for (const s of sintesis.solicitudes) {
    if (!s.aserciones.some(a => a.error)) continue;
    const i = IDS.indexOf(s.nombre), k = CASOS[i];
    if (i >= 0 && r.casos[k]?.estado === 'APROBADO') {
      if (s.http == null || s.http >= 500 || s.http === 403) {
        const estado = s.http == null ? 'NO_CONCLUYENTE' : 'BLOQUEADO';
        const motivo = `Lectura Newman con HTTP ${s.http ?? 'sin respuesta'}.`;
        r.casos[k] = casoRegistro(k, estado, motivo, r.casos[k]);
        const comp = r.comprobaciones.find(x => x.id === s.nombre);
        if (comp) { comp.estado = estado; comp.motivo = motivo; }
        continue;
      }
      const motivo = `Aserción Newman fallida en ${s.nombre}, HTTP ${s.http ?? 'sin respuesta'}.`;
      r.casos[k] = casoRegistro(k, 'RECHAZADO', motivo, r.casos[k]);
      const comp = r.comprobaciones.find(x => x.id === s.nombre); if (comp) { comp.estado = 'RECHAZADO'; comp.motivo = motivo; }
      r.incidencias.push({ id: `INC-M06-G32-${String(i + 1).padStart(2, '0')}`, caso: casoCompleto(k),
        discrepancia: motivo, severidad: 'MEDIA', justificacion: 'La respuesta pública no satisface la lectura obligatoria.' });
    }
  }
  return sintesis;
}
export function informe(c, r) {
  const filas = CASOS.map(k => { const x = r.casos[k]; return `| ${casoCompleto(k)} | ${x.estado} | ${limpio(x.motivo)} |`; }).join('\n');
  const dato = x => x === undefined || x === null ? 'no observado' : limpio(x);
  const esperado = [
    'una ganancia por transformación del componente RF-83 y ningún registro de precio, con precio sin cambio',
    'una pérdida por transformación en EN_TRATAMIENTO y ningún registro de precio',
    'dos registros separados: ganancia por transformación y pérdida por precio, cada uno con su origen',
    'solo una ganancia por precio, sin transformación porque no cambia la magnitud física',
  ];
  const detalle = CASOS.map((k, i) => {
    const x = r.casos[k], m = x.medicion_rf83, e = x.valores_esperados_calculados;
    const variaciones = x.variaciones_observadas?.length ? x.variaciones_observadas.map(v =>
      `  - Variación ${dato(v.id)}: ${dato(v.tipo)}, monto ${dato(v.monto)}, VR ${dato(v.valor_razonable_anterior)} → ${dato(v.valor_razonable_nuevo)}, estado ${dato(v.estado)}.`).join('\n') : '  - Sin lectura completa de variaciones.';
    const medicion = m ? `transformación ${dato(m.transformacion)}, precio ${dato(m.precio_mercado)}, total ${dato(m.total)}, VR ${dato(m.valor_razonable_anterior)} → ${dato(m.valor_razonable_nuevo)}; estado ${dato(m.estado)}` : 'no observada';
    const calculados = e ? `transformación ${dato(e.transformacion)}, precio ${dato(e.precio_mercado)}, total ${dato(e.total)}; magnitud ${dato(e.magnitud_anterior)} → ${dato(e.magnitud_nueva)}` : 'no calculables';
    const rebase = x.rebase_precio ? `Rebase previo con peso ${dato(x.rebase_precio.peso_kg)} kg, evento M02 ${dato(x.rebase_precio.evento_m02_id)} y precio vigente ${dato(x.rebase_precio.precio_vigente_id)}; quedó fuera del oráculo del evento evaluado.` : '';
    const desviacion001 = i === 0 && m && Number(m.precio_mercado) !== 0 ?
      'La precondición de precio sin cambio no se cumplió; el registro de precio observado corresponde a esa diferencia y la ausencia de registro de precio no quedó comprobada en este caso. ' : '';
    const cumplido = x.oraculo_inicial?.estado === 'APROBADO' ?
      `Los tipos, montos, período y estado inicial observados coincidieron con los componentes medidos; ${desviacion001}la consulta del origen quedó pendiente.` :
      x.estado === 'BLOQUEADO' || x.estado === 'NO_CONCLUYENTE' ? 'Sin comprobación concluyente del producto.' :
        `Comprobación inicial: ${dato(x.oraculo_inicial?.motivo ?? x.motivo).replace(/\.+$/, '')}.`;
    const fallo = x.estado === 'APROBADO' ? 'Ninguno confirmado.' :
      x.hallazgos?.length ? x.hallazgos.map(limpio).join('; ') : dato(x.motivo);
    return `### ${casoCompleto(k)}\n\n- **Preparación:** activo ${dato(x.activo)}, evento M02 ${dato(x.evento_m02_id)}, precio vigente ${dato(x.precio_rf89_id)}, período destino ${dato(x.periodo)}; estado al pesaje ${dato(x.estado_al_pesaje)} y al procesar ${dato(x.estado_al_procesar)}. ${rebase}\n- **Esperado:** ${esperado[i]}; origen navegable por la cadena de trazabilidad.\n- **Observado:**\n${variaciones}\n  - Medición RF-83: ${medicion}.\n  - Valores contrastados: ${calculados}.\n- **Cumplido:** ${cumplido}\n- **Fallo y motivo:** ${fallo}\n- **Decisión:** ${x.estado}.\n`;
  }).join('\n');
  const incidencias = r.incidencias.length ? r.incidencias.map(x => {
    const origen = x.clave === 'ORIGEN';
    const verificaciones = r.verificaciones_trazabilidad.map(v => `período ${v.periodo}: HTTP ${v.http ?? 'sin respuesta'}, código ${v.codigo ?? 'ninguno'}`).join('; ') || 'sin verificación observada';
    const cadenas = r.consultas_cadena.map(v => `línea ${v.linea_id}: HTTP ${v.http ?? 'sin respuesta'}, eslabones ${v.ids_observados?.id_evento == null && v.ids_observados?.id_precio_mercado == null ? 'sin IDs consultables' : 'con lectura'}`).join('; ') || 'sin consultas de cadena';
    return `### ${x.id}: ${origen ? 'la verificación de trazabilidad del período impide consultar el origen de las variaciones' : 'discrepancia en el registro de variaciones'}\n\n- **Requisito afectado:** ${origen ? 'RF-86 Salida y CA-6 exigen origen obligatorio y navegable para el Contador y auditores mediante RF-91; RF-91 R4 protege las cadenas de variaciones de períodos cerrados' : 'RF-86 exige registrar los componentes medidos con tipo, monto, período y origen verificables'}.\n- **Pasos para reproducir:** ${origen ? 'registrar variaciones en un período abierto; como Contador, ejecutar POST /finanzas/periodos/{id}/trazabilidad y consultar GET /finanzas/lineas/{id}/cadena' : 'preparar el activo y evento indicados en el detalle del caso, procesar el evento y consultar las variaciones y su cadena'}.\n- **Resultado esperado:** ${origen ? 'origen consultable para las variaciones del período abierto, respetando la inmutabilidad de períodos cerrados' : 'variaciones conformes a los componentes y condiciones del caso'}.\n- **Resultado obtenido:** ${limpio(x.discrepancia)} ${origen ? `Verificación: ${verificaciones}. Cadenas: ${cadenas}.` : ''}\n- **Causa:** ${dato(x.causa_raiz ?? 'NO DETERMINADA')}. ${x.descripcion ? limpio(x.descripcion) : 'No hay evidencia suficiente para atribuir la causa técnica.'}\n- **Dato a revisar:** ${dato(x.dato_a_revisar ?? 'No determinado en este RUN')}.\n- **Impacto y severidad:** ${x.severidad}. ${limpio(x.justificacion)}\n- **Certeza:** ${dato(x.certeza)} para la discrepancia observada; la causa técnica requiere su propia evidencia.\n- **Equipo inicial:** ${dato(x.equipo_inicial ?? 'Desarrollo')}, por la primera respuesta pública discrepante; la derivación no atribuye por sí sola la causa raíz.\n- **Evidencias:** RUN ${c.runId}, resultado.json${origen ? ', verificaciones_trazabilidad y consultas_cadena' : ' y detalle del caso'}.\n- **Acción:** Desarrollo revisa la incidencia; QA reevalúa con nueva autorización.`;
  }).join('\n\n') : 'No se confirmaron incidencias de producto.';
  const decision = Object.values(r.casos).some(x => x.estado === 'RECHAZADO') ? 'RECHAZADO' :
    Object.values(r.casos).every(x => x.estado === 'APROBADO') && r.cierre.rollback.verificado ? 'APROBADO' :
      Object.values(r.casos).every(x => x.estado === 'BLOQUEADO') ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
  const efecto = r.efectos_persistentes_declarados;
  const efectoTexto = `Efecto persistente aceptado por responsable QA (2026-11-07): ${efecto.precios_registrados} precios de mercado registrados, id_precio_mercado ${efecto.id_precio_mercado.join(', ') || 'ninguno'}. Cada precio ACTIVO no PRODUCTO puede dejar un evento M01 y un aviso ALERTA_FINANCIERA_NIC41 por Contador en bandeja interna, con referencia a un precio ${efecto.referencia_revertida ? 'revertido por el sandbox' : 'cuyo rollback aún no está verificado'}. Si falta ID de precio, registros sin conciliar: ${efecto.registros_sin_id}. Bandeja del Contador QA: ${efecto.bandeja_contador_qa.estado}; avisos observados ${efecto.bandeja_contador_qa.avisos_observados ?? 'no verificable'}. Es informativo; no altera veredictos ni oficialidad.`;
  const impedimentosTexto = r.impedimentos_precios.length ? r.impedimentos_precios.map(x =>
    `- GET ${x.ruta} → HTTP ${x.http}; cuerpo saneado ${x.cuerpo_saneado}. El impedimento de precio vigente impide comprobar RF-86 para esa especie. Equipo inicial de atención: Desarrollo, por la primera respuesta pública 5xx. Causa raíz: NO DETERMINADA; certeza: ${x.certeza}.`).join('\n') : 'Ninguno observado.';
  const escriturasRun = r.solicitudes.filter(x => ['POST', 'PATCH', 'PUT'].includes(x.metodo) && x.ruta !== '/sesiones/').length;
  const cierreTexto = r.cierre.run.cierre_http === 200 ? '' :
    ` Cuerpo saneado del DELETE: ${r.cierre.run.cuerpo_saneado ?? '{}'}; no se hicieron lecturas poscierre. El sandbox queda sujeto a cierre por inactividad; cierre explícito no confirmado. Bitácora: ${escriturasRun === 0 ? 'ningún intento de escritura dentro del RUN' : `${escriturasRun} solicitudes de escritura dentro del RUN, con efectos pendientes de comprobación`}.`;
  const diag = r.diagnostico_candidatos;
  const diagnostico = Object.entries(diag).map(([k, v]) => `${k}: ${v ?? 'ninguna'}`).join('; ');
  const estadoNewman = r.herramientas.newman?.version ??
    (r.herramientas.newman_preflight_version ? `${r.herramientas.newman_preflight_version} (detectado en preflight; sin ejecución)` :
      'no disponible en preflight');
  const conclusion = decision === 'APROBADO' ? 'Los cuatro oráculos se demostraron con API pública.' :
    escriturasRun === 0 ? 'Resolver la condición de bloqueo y repetir con autorización; no hubo escrituras dentro del RUN.' :
      CASOS.every(k => r.casos[k].estado === 'RECHAZADO') && r.incidencias.some(x => x.clave === 'ORIGEN') ?
        'Los cuatro casos cumplen los tipos, montos, período y estado inicial observados; falla la consulta del origen. Desarrollo revisa la incidencia de trazabilidad y QA hará la reevaluación V2 con nueva autorización.' :
        'Resolver las discrepancias o impedimentos y comprobar los efectos del RUN antes de una nueva ejecución autorizada.';
  return `# TC-M06-G32 — ${decision}\n\n## Identificación\n\n${CASOS.map(casoCompleto).join(', ')}; RF-86 v2.0; RUN ${c.runId}; versión ${c.version}; intento ${c.intento}; ambiente TEST; autorización ${limpio(c.referencia)}. Node ${process.version}; Newman ${estadoNewman}. Código de TEST: no verificado por este ejecutor. Solo API.\n\n## Decisión del caso\n\n| Caso | Estado | Motivo |\n|---|---|---|\n${filas}\n\n## Diagnóstico de candidatos\n\n${diag.medido ? `Conteos acumulados, sin titular tributario ni datos personales: ${diagnostico}.` : 'No se leyeron catálogos; conteos no medidos.'}\n\n## Datos y método\n\nSe usaron activos reconocidos ya existentes. Según contabilizador.py:39-66 y la regla de período destino, un hecho con período CERRADO se registra en el primer período ABIERTO posterior del titular; la línea base y la variación se leen allí. La selección del precio sigue precios.py:38-52. El oráculo TB/PM compara el último cálculo previo con el nuevo valor neto y las magnitudes según medidor.py:62-75, valorador.py:88-112 y nic41.py:129-148. La regla M02 permite registrar eventos de crecimiento únicamente para activos ACTIVO (Especificacion-Requerimientos-Modulo2.md:2194); en TC-M06-002 se registra el pesaje en ACTIVO, luego PATCH a EN_TRATAMIENTO y después POST /finanzas/eventos/procesar dentro del RUN. El proceso de fondo usa otra sesión y no ve la escritura sin confirmar del sandbox. No se ingresaron datos contables manuales. Tras comprobar importes y estado inicial se invoca una verificacion RF-91 por periodo destino y luego se consulta cada cadena.\n\n## Verificacion RF-91 y origen\n\n${r.verificaciones_trazabilidad.map(x => `- Periodo ${x.periodo}: POST ${x.ruta} -> HTTP ${x.http ?? 'sin respuesta'}; codigo ${x.codigo ?? 'ninguno'}; cuerpo saneado ${x.cuerpo_saneado}; eco RUN ${x.eco}.`).join('\n') || 'No hubo variaciones elegibles para verificar.'}\n\n## Consultas de cadena RF-91\n\n${r.consultas_cadena.map(x => `- ${x.caso}, variacion ${x.variacion_id}, linea ${x.linea_id}: GET cadena HTTP ${x.http ?? 'sin respuesta'}; codigo ${x.codigo ?? 'ninguno'}; cuerpo saneado ${x.cuerpo_saneado}; ids ${JSON.stringify(x.ids_observados)}.`).join('\n') || 'Sin consultas de cadena.'}\n\n## Detalle por caso\n\n${detalle}\n## Comprobaciones API y evidencias\n\n${r.comprobaciones.map(x => `- ${x.id}: ${x.estado}. ${limpio(x.motivo)} Evidencia: ${x.evidencia}.`).join('\n')}\n\n## Observaciones auxiliares\n\n${r.observaciones_auxiliares.length ? r.observaciones_auxiliares.map(x => `- ${x.caso}: GET ${x.ruta} → HTTP ${x.http ?? 'sin respuesta'}; cuerpo saneado ${x.cuerpo_saneado ?? 'no disponible'}.`).join('\n') : 'Ninguna.'}\n\n## Observaciones\n\n${efectoTexto}\n\n## Impedimentos observados en precios de mercado\n\n${impedimentosTexto}\n\n## Observación de identificadores\n\nRF-86 define UUID para variación, activo, origen y período; las rutas y objetos observados en el backend usan enteros. Se registra como observación independiente; no modifica por sí sola la decisión.\n\n## Incidencias de producto\n\n${incidencias}\n\n## Problemas técnicos y análisis de causas\n\n${r.problemas_tecnicos.map(limpio).join('; ') || 'Ninguno.'} Los códigos de error no prueban causa raíz por sí solos.\n\n## Cierre y rollback\n\nDELETE HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. Rollback ${r.cierre.rollback.verificado ? 'verificado' : 'NO verificado'}: ${limpio(r.cierre.rollback.motivo)}${cierreTexto} ${efectoTexto} El rollback verificado se limita a los datos del sandbox.\n\n## Conclusión y acciones\n\n${conclusion}\n\n## Herramientas y cierre\n\nNewman: ${r.herramientas.newman ? `${r.herramientas.newman.solicitudes ?? 0} solicitudes y ${r.herramientas.newman.fallos ?? 0} aserciones fallidas` : r.solicitudes.some(x => x.ruta === '/finanzas/eventos/procesar') ? 'no produjo reporte; revisar problema técnico' : 'no se ejecutó porque no hubo casos ejecutables'}. Cypress: 0 pruebas, sin UI requerida.\n`.replaceAll('precio RF-89', 'precio de mercado').replaceAll('RF-89', 'precios de mercado');
}
export async function evaluar(c, { env = leerEnv(), apiOverride = null, sinArtefactos = false } = {}) {
  const api = apiOverride ?? String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G32', run_id: c.runId, version: c.version, intento: c.intento,
    casos: {}, comprobaciones: [], solicitudes: [], evidencias: [], incidencias: [], problemas_tecnicos: [],
    herramientas: { node: process.version, newman: null }, cypress: { total_pruebas: 0 },
    efectos_persistentes_declarados: { tipo: 'ALERTA_FINANCIERA_NIC41',
      precios_registrados: 0, id_precio_mercado: [], alcance: 'Evento M01 y aviso interno por Contador; fuera del sandbox.',
      referencia_revertida: false, registros_sin_id: 0,
      bandeja_contador_qa: { estado: 'NO_VERIFICABLE', avisos_observados: null } },
    cierre: { run: { cierre_http: null, cuerpo_saneado: null }, rollback: { verificado: false, motivo: 'No comprobado' } },
    impedimentos_precios: [], observaciones_auxiliares: [], verificaciones_trazabilidad: [], consultas_cadena: [], diagnostico_candidatos: { medido: false, total_recibido: 0, bovino: 0, individual: 0,
      estado: 0, sin_costo: 0, valor_positivo: 0, precio_vigente: 0, periodo_destino: 0,
      peso_kg: 0, calculo_previo: 0, primera_condicion_fallida: null },
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
  const avances = Array.from({ length: 4 }, () => ({}));
  const terminarCaso = (i, estado, motivo, extra = {}) => {
    const k = CASOS[i]; r.casos[k] = casoRegistro(k, estado, motivo, { ...avances[i], ...extra });
    r.comprobaciones.push({ caso: k, fuente: 'API', id: IDS[i], tipo: 'ASSERT',
      estado, motivo: limpio(motivo), evidencia: sinArtefactos ? 'ensayo-local' : 'resultado.json' });
    if (estado === 'RECHAZADO') {
      const clave = /único origen|traza al evento|origen no consultable|no tiene como único origen|no traza al evento/i.test(motivo) ? 'ORIGEN' :
        /no creó la variación/i.test(motivo) ? 'AUSENCIA' :
        /Monto/i.test(motivo) ? 'MONTO' : `CASO_${i}`;
      const previa = r.incidencias.find(x => x.clave === clave);
      if (previa) previa.caso += `, ${casoCompleto(k)}`;
      else r.incidencias.push({ id: `INC-M06-G32-${String(i + 1).padStart(2, '0')}`,
        caso: casoCompleto(k), clave, discrepancia: motivo, severidad: 'ALTA',
        equipo_inicial: 'Desarrollo', certeza: 'CONFIRMADA', causa_raiz: 'NO DETERMINADA',
        justificacion: clave === 'ORIGEN' ?
          'La trazabilidad NIC 41 obligatoria para el Contador y auditores no es consultable por la cadena RF-91; funcionalidad relevante sin alternativa pública observada.' :
          'La clasificación o trazabilidad de un componente relevante queda incumplida.' });
    }
  };
  let token = null, tokenM02 = null, iniciado = false, bandejaInicial = null; const hechos = [];
  try {
    if (!pf.ok) {
      r.problemas_tecnicos.push(`Preflight: ${pf.barreras.join(', ')}`);
      for (let i = 0; i < 4; i++) terminarCaso(i, 'BLOQUEADO', `Preflight: ${pf.barreras[0]}.`);
      return r;
    }
    const login = await pedir(r, api, 'POST', '/sesiones/', {
      cuerpo: { correo_electronico: env.QA_CONTADOR_EMAIL, contrasena: env.QA_CONTADOR_PASSWORD },
      timeout: PRESUPUESTO.timeout_login_ms });
    token = login.cuerpo?.token ?? login.cuerpo?.access_token ?? null;
    if (login.http !== 200 || !token) {
      for (let i = 0; i < 4; i++) terminarCaso(i, login.http == null ? 'NO_CONCLUYENTE' : 'BLOQUEADO',
        `No se obtuvo sesión del Contador QA: HTTP ${login.http ?? 'sin respuesta'}.`);
      return r;
    }
    const loginM02 = await pedir(r, api, 'POST', '/sesiones/', {
      cuerpo: { correo_electronico: env.QA_ADMIN_EMAIL, contrasena: env.QA_ADMIN_PASSWORD },
      timeout: PRESUPUESTO.timeout_login_ms });
    tokenM02 = loginM02.cuerpo?.token ?? loginM02.cuerpo?.access_token ?? null;
    if (loginM02.http !== 200 || !tokenM02) {
      for (let i = 0; i < 4; i++) terminarCaso(i, loginM02.http == null ? 'NO_CONCLUYENTE' : 'BLOQUEADO',
        `No se obtuvo sesión de Administrador QA para M02: HTTP ${loginM02.http ?? 'sin respuesta'}.`);
      return r;
    }
    const opts = (caso = null) => ({ token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, caso });
    const optsM02 = (caso = null) => ({ ...opts(caso), token: tokenM02 });
    const [a, p] = await Promise.all([
      pedir(r, api, 'GET', '/finanzas/activos', opts()),
      pedir(r, api, 'GET', '/finanzas/periodos', opts()),
    ]);
    iniciado = true;
    bandejaInicial = await bandejaPropia(r, api, token, c.runId, env.QA_SANDBOX_SECRET);
    if (![a, p].every(x => x.http === 200 && x.eco && Array.isArray(x.cuerpo))) {
      const faltante = a.http !== 200 || !a.eco || !Array.isArray(a.cuerpo) ? '/finanzas/activos' : '/finanzas/periodos';
      for (let i = 0; i < 4; i++) terminarCaso(i, 'BLOQUEADO', `Catálogo público ${faltante} incompleto o sin eco del RUN.`);
      return r;
    }
    const diag = r.diagnostico_candidatos;
    diag.medido = true;
    diag.total_recibido = a.cuerpo.length;
    const bovinos = a.cuerpo.filter(x => /bovin/i.test(x.especie ?? '')); diag.bovino = bovinos.length;
    const individuales = bovinos.filter(x => x.tipo === 'INDIVIDUAL'); diag.individual = individuales.length;
    const estados = individuales.filter(x => ['ACTIVO', 'EN_TRATAMIENTO'].includes(x.estado)); diag.estado = estados.length;
    const sinCosto = estados.filter(x => !x.valorado_por_costo); diag.sin_costo = sinCosto.length;
    const candidatos = sinCosto.filter(x => Number(x.valor_razonable_neto) > 0).slice(0, 20);
    diag.valor_positivo = sinCosto.filter(x => Number(x.valor_razonable_neto) > 0).length;
    const precios = [], fallosPrecio = new Map();
    for (const especie of [...new Set(candidatos.map(x => id(x.id_especie)).filter(Boolean))]) {
      const ruta = `/finanzas/precios?id_especie=${especie}`;
      const pr = await pedir(r, api, 'GET', ruta, opts());
      if (pr.http >= 500) {
        const impedimento = { id_especie: especie, ruta, http: pr.http,
          cuerpo_saneado: pr.fila.cuerpo_saneado, equipo_inicial: 'Desarrollo',
          certeza: 'CONFIRMADA para la respuesta HTTP; causa raíz NO DETERMINADA' };
        fallosPrecio.set(especie, impedimento); r.impedimentos_precios.push(impedimento);
      } else if (pr.http === 200 && pr.eco && Array.isArray(pr.cuerpo)) precios.push(...pr.cuerpo);
      if (r._corte) break;
    }
    for (const x of candidatos) {
      const d = await pedir(r, api, 'GET', `/finanzas/activos/${id(x.id_activo_biologico)}`, opts());
      if (d.http === 200 && d.eco) {
        x._periodo = periodoDestino(p.cuerpo, d.cuerpo?.activo?.numero_id_tributaria);
        x._calculo = ultimoCalculo(d.cuerpo);
      }
      if (r._corte) break;
    }
    diag.precio_vigente = candidatos.filter(x => !!preciosVigentes(precios, x.id_especie)).length;
    diag.periodo_destino = candidatos.filter(x => preciosVigentes(precios, x.id_especie) && x._periodo?.periodo).length;
    for (const x of candidatos.filter(x => x._periodo?.periodo &&
      (preciosVigentes(precios, x.id_especie) || fallosPrecio.has(id(x.id_especie))))) {
      const f = await pedir(r, api, 'GET', `/activos-biologicos/${id(x.id_activo_biologico)}/ficha-integral`, optsM02());
      if (f.http === 200 && f.eco && f.cuerpo?.unidad_peso === 'kg' && Number(f.cuerpo.peso_actual) > 0)
        x._pesoKg = Number(f.cuerpo.peso_actual);
      if (r._corte) break;
    }
    diag.peso_kg = candidatos.filter(x => x._periodo?.periodo && x._pesoKg && preciosVigentes(precios, x.id_especie)).length;
    diag.calculo_previo = candidatos.filter(x => x._periodo?.periodo && x._pesoKg && x._calculo &&
      preciosVigentes(precios, x.id_especie)).length;
    const condiciones = [['bovino', 'especie Bovino'], ['individual', 'tipo INDIVIDUAL'],
      ['estado', 'estado ACTIVO o EN_TRATAMIENTO'], ['sin_costo', 'sin valoración por costo'],
      ['valor_positivo', 'valor razonable neto positivo'], ['precio_vigente', 'precio PESO_KG vigente'],
      ['periodo_destino', candidatos.some(x => x._periodo?.motivo?.includes('EN_CIERRE')) ?
        'período que contiene hoy EN_CIERRE' : 'período destino ABIERTO visible'],
      ['peso_kg', 'peso actual en kg'], ['calculo_previo', 'último cálculo previo CALCULADO']];
    diag.primera_condicion_fallida = condiciones.find(([clave]) => diag[clave] < 4)?.[1] ?? null;
    const sel = seleccionar(candidatos, p.cuerpo, precios, fallosPrecio);
    const pendientes = [];
    for (let i = 0; i < 4; i++) {
      if (r._corte) { terminarCaso(i, 'BLOQUEADO', 'Corte por HTTP 403 o tres respuestas 5xx consecutivas.'); continue; }
      const s = sel[i], k = CASOS[i];
      if (!s) { terminarCaso(i, 'BLOQUEADO', `BLOQUEO_DATOS: ${diag.primera_condicion_fallida ?? 'cuatro activos independientes con estado requerido'}.`); continue; }
      const falloPrecio = fallosPrecio.get(id(s.activo.id_especie));
      if (falloPrecio) { terminarCaso(i, 'BLOQUEADO',
        `Impedimento observado en RF-89: GET ${falloPrecio.ruta} → HTTP ${falloPrecio.http}; cuerpo saneado ${falloPrecio.cuerpo_saneado}. No se puede comprobar RF-86 sin precio vigente. Atención inicial: Desarrollo; causa raíz no determinada.`); continue; }
      const aid = id(s.activo.id_activo_biologico), pid = id(s.periodo.id_periodo_contable);
      avances[i] = { activo: aid, periodo: pid, precio_rf89_id: id(s.precio?.id_precio_mercado),
        estado_al_pesaje: s.activo.estado, estado_al_procesar: s.activo.estado };
      const peso = s.peso;
      if (i <= 1 && id(s.calculoPrevio.id_precio_mercado) !== id(s.precio?.id_precio_mercado)) {
        const rebase = await pedir(r, api, 'POST', `/activos-biologicos/${aid}/eventos/crecimiento`, { ...optsM02(k), cuerpo: {
          tipo_medicion: 'PESO', valor_medicion: peso, unidad_medida: 'kg',
          descripcion: `Rebase precio vigente QA ${c.runId} ${k}` } });
        const errRebase = estadoRespuesta(rebase);
        if (errRebase) { if (rebase.http == null) hechos.push({ tipo: 'escritura_incierta' });
          terminarCaso(i, ...errRebase); continue; }
        const rebaseId = id(rebase.cuerpo?.evento?.id_eventos);
        if (!rebaseId) { hechos.push({ tipo: 'escritura_incierta' });
          terminarCaso(i, 'NO_CONCLUYENTE', 'Evento de rebase M02 sin id; conciliar sin reintento.'); continue; }
        hechos.push({ tipo: 'evento', id: rebaseId, activo: aid });
        const procesoRebase = await pedir(r, api, 'POST', '/finanzas/eventos/procesar', opts(k));
        const errProcesoRebase = estadoRespuesta(procesoRebase);
        if (errProcesoRebase) { if (procesoRebase.http == null) hechos.push({ tipo: 'escritura_incierta' });
          terminarCaso(i, ...errProcesoRebase); continue; }
        const detalleRebase = await pedir(r, api, 'GET', `/finanzas/activos/${aid}`, opts(k));
        const calculoRebase = detalleRebase.http === 200 && detalleRebase.eco ? ultimoCalculo(detalleRebase.cuerpo) : null;
        if (id(calculoRebase?.id_precio_mercado) !== id(s.precio.id_precio_mercado) ||
            !igualMonto(Number(calculoRebase?.magnitud), peso)) {
          terminarCaso(i, 'BLOQUEADO', 'No se acreditó rebase al precio vigente con peso constante; no se ejecuta el pesaje del caso.');
          continue;
        }
        s.calculoPrevio = calculoRebase;
        avances[i].rebase_precio = { evento_m02_id: rebaseId, precio_vigente_id: id(s.precio.id_precio_mercado),
          peso_kg: peso, procesamiento_http: procesoRebase.http, calculo_id: id(calculoRebase.id_calculo_valor_razonable) };
      }
      const base = await pedir(r, api, 'GET', `/finanzas/periodos/${pid}/variaciones`, opts(k));
      if (estadoRespuesta(base) || !Array.isArray(base.cuerpo)) { terminarCaso(i, 'BLOQUEADO', `No se pudo fijar línea base del período ${pid}.`); continue; }
      hechos.push({ tipo: 'linea_base', periodo: pid, activo: aid,
        ids: base.cuerpo.filter(v => id(v.id_activo_biologico) === aid)
          .map(v => String(v.id_variacion_valor_razonable)) });
      let precioId = id(s.precio?.id_precio_mercado);
      if (i >= 2) {
        const vigente = s.precio;
        if (!vigente || vigente.fuente !== 'MERCADO_ACTIVO') {
          terminarCaso(i, 'BLOQUEADO', 'BLOQUEO_DATOS: falta precio vigente de fuente MERCADO_ACTIVO compatible con el activo.'); continue;
        }
        const precioNuevo = Number((Number(vigente.precio_unitario) * (i === 2 ? 0.95 : 1.05)).toFixed(2));
        const nuevo = await pedir(r, api, 'POST', '/finanzas/precios', { ...opts(k), cuerpo: {
          id_especie: id(s.activo.id_especie), categoria: 'PESO_KG', precio_unitario: precioNuevo,
          fecha_vigencia: fecha(), fuente: 'MERCADO_ACTIVO', evidencia_documental: `Ensayo QA ${c.runId}`,
          confirmar_desviacion: true } });
        const err = estadoRespuesta(nuevo);
        if (err) { if (nuevo.http == null) hechos.push({ tipo: 'escritura_incierta' });
          terminarCaso(i, ...err); continue; }
        precioId = id(nuevo.cuerpo?.id_precio_mercado);
        if (!precioId) { hechos.push({ tipo: 'precio_sin_id' });
          terminarCaso(i, 'NO_CONCLUYENTE', 'POST de precio no devolvió id; conciliar por lectura, sin reintento.'); continue; }
        hechos.push({ tipo: 'precio', id: precioId, especie: id(s.activo.id_especie) });
        avances[i].precio_rf89_id = precioId;
      }
      const factor = [1.02, 0.98, 1.1, 1][i];
      const pesoNuevo = Number((peso * factor).toFixed(2));
      if (pesoNuevo <= 0) { terminarCaso(i, 'BLOQUEADO', 'Peso propuesto fuera de rango.'); continue; }
      const evento = await pedir(r, api, 'POST', `/activos-biologicos/${aid}/eventos/crecimiento`, { ...optsM02(k), cuerpo: {
        tipo_medicion: 'PESO', valor_medicion: pesoNuevo, unidad_medida: 'kg',
        descripcion: `Ensayo QA ${c.runId} ${k}` } });
      const errEvento = estadoRespuesta(evento);
      if (errEvento) { if (evento.http == null) hechos.push({ tipo: 'escritura_incierta' });
        terminarCaso(i, ...errEvento); continue; }
      const eventoId = id(evento.cuerpo?.evento?.id_eventos);
      if (!eventoId) { hechos.push({ tipo: 'escritura_incierta' });
        terminarCaso(i, 'NO_CONCLUYENTE', 'Evento M02 sin id; conciliar por lectura sin reintento.'); continue; }
      hechos.push({ tipo: 'evento', id: eventoId, activo: aid });
      avances[i].evento_m02_id = eventoId;
      if (s.requiereTratamiento) {
        const cambio = await pedir(r, api, 'PATCH', `/activos-biologicos/${aid}/estado`, { ...optsM02(k),
          cuerpo: { estado_nuevo: 'EN_TRATAMIENTO', fecha_cambio_estado: fecha(),
            motivo_cambio: `Preparación QA ${c.runId}` } });
        const errCambio = estadoRespuesta(cambio);
        if (errCambio) { if (cambio.http == null) hechos.push({ tipo: 'escritura_incierta' });
          terminarCaso(i, ...errCambio); continue; }
        hechos.push({ tipo: 'estado', activo: aid, anterior: s.activo.estado });
        avances[i].estado_al_procesar = 'EN_TRATAMIENTO';
      }
      const proc = await pedir(r, api, 'POST', '/finanzas/eventos/procesar', opts(k));
      if (proc.http == null) hechos.push({ tipo: 'escritura_incierta' });
      if (proc.http >= 400 && proc.http < 500 && proc.http !== 403) {
        terminarCaso(i, 'RECHAZADO', `El procesamiento M06 rechazó el evento con el activo ${avances[i].estado_al_procesar}: HTTP ${proc.http}, código ${proc.fila?.codigo || 'sin código'}.`);
        continue;
      }
      const errProc = estadoRespuesta(proc);
      if (errProc?.[0] === 'BLOQUEADO') { terminarCaso(i, ...errProc); continue; }
      const vars = await pedir(r, api, 'GET', `/finanzas/periodos/${pid}/variaciones`, opts(k));
      const hist = await pedir(r, api, 'GET', `/finanzas/activos/${aid}`, opts(k));
      const meds = await pedir(r, api, 'GET', `/finanzas/periodos/${pid}/mediciones`, opts(k));
      const falloLectura = [vars, hist, meds].find(x => x.http >= 500 || x.http === 403);
      if (falloLectura) { terminarCaso(i, ...estadoRespuesta(falloLectura)); continue; }
      if (estadoRespuesta(vars) || estadoRespuesta(hist) || estadoRespuesta(meds) ||
          !Array.isArray(vars.cuerpo) || !Array.isArray(meds.cuerpo)) {
        terminarCaso(i, 'NO_CONCLUYENTE', 'Lecturas posteriores incompletas.'); continue;
      }
      const baseIds = new Set(base.cuerpo.map(v => String(v.id_variacion_valor_razonable)));
      const nuevas = vars.cuerpo.filter(v => id(v.id_activo_biologico) === aid &&
        !baseIds.has(String(v.id_variacion_valor_razonable)));
      hechos.push(...nuevas.map(v => ({ tipo: 'variacion', id: id(v.id_variacion_valor_razonable), periodo: pid })));
      const medicionHist = hist.cuerpo?.mediciones?.find(m => id(m.id_evento) === eventoId);
      const medicionPeriodo = meds.cuerpo.find(m => id(m.id_medicion_posterior) === id(medicionHist?.id_medicion_posterior));
      const medicion = medicionHist && medicionPeriodo ? { ...medicionHist, estado: medicionPeriodo.estado } : null;
      const magnitudNueva = medicion?.supuestos_aplicados?.magnitud ?? pesoNuevo;
      const preliminar = proc.http === 200 && nuevas.length === 0 ?
        { estado: 'RECHAZADO', motivo: 'El procesamiento respondió correctamente pero no creó la variación exigida.' } :
        evaluarOraculo(i, { variaciones: nuevas, medicion, evento: eventoId, precio: precioId,
          cadenas: [], auditorias: null, periodoAbierto: s.periodo.estado === 'ABIERTO',
          estadoActivo: avances[i].estado_al_procesar, lineaPorVariacion: {},
          calculoPrevio: s.calculoPrevio, magnitudNueva, comprobarOrigen: false });
      avances[i].variaciones_observadas = nuevas.map(v => ({
        id: v.id_variacion_valor_razonable, tipo: v.tipo, monto: v.monto_variacion,
        valor_razonable_anterior: v.valor_razonable_anterior, valor_razonable_nuevo: v.valor_razonable_nuevo,
        evento_origen_id: v.evento_origen_id ?? v.id_evento ?? null,
        id_precio_mercado: v.id_precio_mercado ?? null,
        estado: v.estado_trazabilidad ?? v.estado_inicial ?? null, fecha: v.fecha_registro ?? null }));
      avances[i].medicion_rf83 = medicion ? {
        id: medicion.id_medicion_posterior, estado: medicion.estado,
        transformacion: medicion.ganancia_perdida_transformacion,
        precio_mercado: medicion.ganancia_perdida_precio_mercado, total: medicion.variacion_total,
        valor_razonable_anterior: medicion.valor_razonable_anterior,
        valor_razonable_nuevo: medicion.valor_razonable_actual } : null;
      avances[i].valores_esperados_calculados = valoresEsperados(s.calculoPrevio, medicion, magnitudNueva);
      avances[i].oraculo_inicial = preliminar;
      pendientes.push({ i, k, aid, pid, s, nuevas, medicion, eventoId, precioId,
        magnitudNueva, preliminar, errProc });
    }
    const verificaciones = new Map();
    for (const p of pendientes) if (!verificaciones.has(p.pid)) {
      const ruta = `/finanzas/periodos/${p.pid}/trazabilidad`;
      const v = await pedir(r, api, 'POST', ruta, opts(p.k));
      verificaciones.set(p.pid, v);
      r.verificaciones_trazabilidad.push({ periodo: p.pid, ruta, http: v.http,
        codigo: v.fila?.codigo || null,
        cuerpo_saneado: cuerpoErrorSaneado(v.cuerpo, [token, tokenM02, ...(r._secretos ?? [])]),
        eco: v.eco });
    }
    for (const p of pendientes) {
      const { i, k, aid, pid, s, nuevas, medicion, eventoId, precioId,
        magnitudNueva, preliminar, errProc } = p;
      const verificacion = verificaciones.get(pid);
      const lns = await pedir(r, api, 'GET', `/finanzas/lineas?id_periodo_contable=${pid}`, { ...opts(k), auxiliar: true });
      if (lns.http !== 200 || !lns.eco || !Array.isArray(lns.cuerpo))
        r.observaciones_auxiliares.push({ caso: k, ruta: `/finanzas/lineas?id_periodo_contable=${pid}`,
          http: lns.http, cuerpo_saneado: lns.fila?.cuerpo_saneado ?? null });
      const cadenas = [];
      for (const v of nuevas) {
        if (!id(v.id_linea)) continue;
        const ch = await pedir(r, api, 'GET', `/finanzas/lineas/${id(v.id_linea)}/cadena`, { ...opts(k), auxiliar: true });
        r.consultas_cadena.push({ caso: k, variacion_id: id(v.id_variacion_valor_razonable),
          linea_id: id(v.id_linea), http: ch.http, codigo: ch.fila?.codigo || null,
          cuerpo_saneado: cuerpoErrorSaneado(ch.cuerpo, [token, tokenM02, ...(r._secretos ?? [])]),
          ids_observados: ch.http === 200 && ch.eco ? {
            id_evento: ch.cuerpo?.eslabones?.ids?.id_evento ?? null,
            id_precio_mercado: ch.cuerpo?.eslabones?.ids?.id_precio_mercado ?? null } : null });
        if (ch.http !== 200 || !ch.eco)
          r.observaciones_auxiliares.push({ caso: k, ruta: `/finanzas/lineas/${id(v.id_linea)}/cadena`,
            http: ch.http, cuerpo_saneado: ch.fila?.cuerpo_saneado ?? null });
        if (ch.http === 200 && ch.eco) cadenas.push(ch.cuerpo);
      }
      for (const v of avances[i].variaciones_observadas) {
        const cadena = cadenas.find(x => String(x.id_origen) === String(v.id));
        const ids = cadena?.eslabones?.ids;
        v.evento_origen_id = ids?.id_evento ?? null;
        v.id_precio_mercado = ids?.id_precio_mercado ?? null;
        v.origen_fuente = 'GET /finanzas/lineas/{id}/cadena tras POST RF-91';
      }
      const aud = await pedir(r, api, 'GET', `/finanzas/auditoria?id_periodo_contable=${pid}&id_activo_biologico=${aid}&tipo_evento=VARIACION_REGISTRADA&formato=TECNICO&tamano=500`, { ...opts(k), auxiliar: true });
      if (aud.http !== 200 || !aud.eco) r.observaciones_auxiliares.push({ caso: k,
        ruta: `/finanzas/auditoria?id_periodo_contable=${pid}&id_activo_biologico=${aid}`,
        http: aud.http, cuerpo_saneado: aud.fila?.cuerpo_saneado ?? null });
      const auditorias = aud.http === 200 && aud.eco ? (aud.cuerpo?.eventos ?? aud.cuerpo?.items ?? null) : null;
      const lineas = Object.fromEntries(nuevas.map(v => [String(v.id_variacion_valor_razonable),
        (Array.isArray(lns.cuerpo) ? lns.cuerpo : []).some(l => id(l.id_linea_asiento_nic41) === id(v.id_linea) &&
          id(l.id_origen) === id(v.id_variacion_valor_razonable) &&
          ['VARIACION_VR_TB', 'VARIACION_VR_PM'].includes(l.tipo_hecho))]));
      let decision = preliminar.estado === 'RECHAZADO' ? preliminar :
        evaluarOraculo(i, { variaciones: nuevas, medicion, evento: eventoId, precio: precioId,
          cadenas, auditorias, periodoAbierto: s.periodo.estado === 'ABIERTO',
          estadoActivo: avances[i].estado_al_procesar, lineaPorVariacion: lineas,
          calculoPrevio: s.calculoPrevio, magnitudNueva });
      if (preliminar.estado !== 'RECHAZADO' && verificacion.http >= 500)
        decision = { estado: 'RECHAZADO', motivo: `Origen no consultable por cadena RF-91: POST /finanzas/periodos/${pid}/trazabilidad HTTP ${verificacion.http}, código ${verificacion.fila?.codigo || 'sin código'}.` };
      else if (preliminar.estado !== 'RECHAZADO' && verificacion.http !== 200)
        decision = { estado: 'NO_CONCLUYENTE', motivo: `Verificación RF-91 sin HTTP 200 (${verificacion.http ?? 'sin respuesta'}); revisar autorización o transporte.` };
      const estado = errProc?.[0] === 'NO_CONCLUYENTE' && decision.estado !== 'RECHAZADO' ? 'NO_CONCLUYENTE' : decision.estado;
      avances[i].hallazgos = decision.estado === 'APROBADO' ? [] : [decision.motivo];
      avances[i].oraculo = { estado, motivo: decision.motivo };
      terminarCaso(i, estado, errProc?.[0] === 'NO_CONCLUYENTE' && decision.estado !== 'RECHAZADO' ?
        `${errProc[1]} ${decision.motivo}` : decision.motivo,
        { preparacion: `activo ${aid}, período ${pid}, evento ${eventoId}${precioId ? `, precio ${precioId}` : ''}`,
          observado: `${nuevas.length} variaciones: ${nuevas.map(v => `${v.tipo}=${v.monto_variacion}`).join(', ') || 'ninguna'}` });
    }
    if (!sinArtefactos && sel.some(Boolean)) await newmanLecturas(r, c, env, token, sel, [token, tokenM02,
      env.QA_SANDBOX_SECRET, env.QA_CONTADOR_EMAIL, env.QA_CONTADOR_PASSWORD,
      env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD]);
  } finally {
    const preciosCreados = hechos.filter(x => x.tipo === 'precio').map(x => x.id);
    r.efectos_persistentes_declarados.precios_registrados = preciosCreados.length;
    r.efectos_persistentes_declarados.id_precio_mercado = preciosCreados;
    r.efectos_persistentes_declarados.registros_sin_id = hechos.filter(x => x.tipo === 'precio_sin_id').length;
    if (iniciado) {
      const del = await pedir(r, api, 'DELETE', `/test-control/runs/${encodeURIComponent(c.runId)}`,
        { token, secreto: env.QA_SANDBOX_SECRET, timeout: PRESUPUESTO.timeout_ms });
      r.cierre.run.cierre_http = del.http;
      r.cierre.run.cuerpo_saneado = del.fila?.cuerpo_saneado ?? null;
      if (del.http === 200) r.cierre.rollback = await comprobarRollback(r, api, env, token, tokenM02, hechos);
      else r.cierre.rollback = { verificado: false,
        motivo: `DELETE no confirmó cierre: HTTP ${del.http ?? 'sin respuesta'}; cuerpo saneado ${del.fila?.cuerpo_saneado ?? '{}'}; sin lecturas poscierre.` };
      r.efectos_persistentes_declarados.referencia_revertida = r.cierre.rollback.verificado;
      if (del.http === 200 && bandejaInicial) {
        const posterior = await bandejaPropia(r, api, token);
        const ultimo = Math.max(0, ...bandejaInicial.map(x => id(x.id_notificacion) ?? 0));
        if (posterior && (posterior.some(x => id(x.id_notificacion) === ultimo) ||
            (ultimo === 0 && posterior.length < 50))) {
          r.efectos_persistentes_declarados.bandeja_contador_qa = { estado: 'OBSERVADO',
            avisos_observados: posterior.filter(x => id(x.id_notificacion) > ultimo && avisoNic41(x)).length,
            metodo: 'Bandeja pública propia; IDs posteriores a la línea base y mensaje NIC41.' };
        }
      }
    }
    for (let i = 0; i < 4; i++) if (!r.casos[CASOS[i]]) terminarCaso(i, 'NO_CONCLUYENTE', 'No se completó el subcaso; revisar solicitudes saneadas.');
    r.oficial = oficialidadLocal(r, sinArtefactos);
    r.consume_version = r.oficial;
    r.estado_ejecucion = r.oficial ? (c.ensayo ? 'OFICIAL_LOCAL' : 'OFICIAL') : 'NO_OFICIAL';
    if (!sinArtefactos && fs.existsSync(c.directorio)) {
      const secretos = [token, tokenM02, env.QA_SANDBOX_SECRET, env.QA_CONTADOR_EMAIL,
        env.QA_CONTADOR_PASSWORD, env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD];
      r.evidencias.push('resultado.json', nombreInforme(c.version));
      if (r.herramientas.newman) r.evidencias.push('newman/newman-G32.json', 'newman/newman-G32.html');
      const pub = { ...r }; delete pub._limite; delete pub._corte; delete pub._seguidos5xx; delete pub._secretos;
      fs.writeFileSync(path.join(c.directorio, 'resultado.json'), sanear(JSON.stringify(pub, null, 2), secretos));
      fs.writeFileSync(path.join(c.directorio, nombreInforme(c.version)), sanear(informe(c, r), secretos));
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
    console.log(JSON.stringify({ grupo: 'G32', run_id: c.runId, oficial: r.oficial, casos: r.casos }));
    if (!r.oficial) process.exitCode = 2;
  } catch (e) { console.error(limpio(e.message)); process.exitCode = 2; }
}
