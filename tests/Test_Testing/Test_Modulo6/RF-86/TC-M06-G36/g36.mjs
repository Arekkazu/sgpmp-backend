#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { CASOS, IDS, PRESUPUESTO, CAPACIDADES, id, monto, igualMonto, nuevos, igualCampos,
  periodoDestino, precioVigente, calculoVigente, operacionesCorrectivas, evaluar009, evaluar010,
  unaIncidencia, rollback, requiereRebase, elegirCandidato, datosPaso, aislarTransformacion } from './lib/g36_core.mjs';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const require = createRequire(import.meta.url);
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION = path.join(DIR, 'G36.postman_collection.json');
const ARCHIVOS = ['g36.mjs', 'lib/g36_core.mjs', 'G36.postman_collection.json', 'README.md',
  'pruebas/g36_env.test.mjs', 'pruebas/g36_ensayo.mjs', 'pruebas/newman_hijo.mjs', 'pruebas/registro_qa.mjs'];
const nombreInforme = v => v === 1 ? 'TC-M06-G36_resultado.md' : `TC-M06-G36_reevaluacion_V${v}.md`;
const canon = x => Array.isArray(x) ? x.map(canon) : x && typeof x === 'object' ?
  Object.fromEntries(Object.keys(x).sort().map(k => [k, canon(x[k])])) : x;
const huella = x => createHash('sha256').update(JSON.stringify(canon(x))).digest('hex');
const texto = x => String(x ?? '').replace(/[\r\n|]/g, ' ').slice(0, 300);
const html = x => String(x).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
export function sanear(x, secretos = []) {
  let s = String(x);
  for (const v of secretos.filter(x => typeof x === 'string' && x.length > 3)) s = s.split(v).join('[REDACTADO]');
  return s.replace(/eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}/g, '[JWT_REDACTADO]')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[CORREO_REDACTADO]')
    .replace(/("(?:numero_id_tributaria|nit_titular|documento|cedula|telefono|celular)"\s*:\s*)(?:"[^"]*"|\d+)/gi,
      '$1"[DATO_PERSONAL_REDACTADO]"');
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
  catch { const p = path.join(path.dirname(process.execPath), 'node_modules', 'newman', 'package.json');
    return fs.existsSync(p) ? path.dirname(p) : null; }
}
const newmanVersion = () => { try { return require(path.join(newmanDir(), 'package.json')).version; } catch { return null; } };
const LECTURAS_NEWMAN = [
  { caso: CASOS[0], id: IDS[CASOS[0]][0], url: '{{base_url}}/finanzas/periodos/{{periodo_id}}/variaciones', token: 'token' },
  { caso: CASOS[0], id: IDS[CASOS[0]][1], url: '{{base_url}}/finanzas/lineas?id_periodo_contable={{periodo_id}}', token: 'token' },
  { caso: CASOS[1], id: IDS[CASOS[1]][0], url: '{{base_url}}/openapi.json', token: null },
];
export function validarColeccionPermisos(c) {
  return c.item?.length === LECTURAS_NEWMAN.length && c.item.every((x, i) => {
    const e = LECTURAS_NEWMAN[i];
    const auth = x.request?.header?.filter(h => h.key.toLowerCase() === 'authorization') ?? [];
    return x.name === e.id && x.request?.method === 'GET' && x.request?.url === e.url &&
      (e.token ? auth.length === 1 && auth[0].value === `Bearer {{${e.token}}}` : auth.length === 0);
  });
}
export function comprobar() {
  const faltantes = ARCHIVOS.filter(x => !fs.existsSync(path.join(DIR, x)));
  let coleccion = false;
  try { coleccion = validarColeccionPermisos(JSON.parse(fs.readFileSync(COLECCION, 'utf8'))); } catch { /* inválida */ }
  const superior = fs.existsSync(path.join(DIR, 'Resultados')) && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const ok = !faltantes.length && coleccion && !superior && PRESUPUESTO.timeout_post_ms === 120000;
  console.log(JSON.stringify({ grupo: 'G36', ok, faltantes, coleccion, markdown_superior: superior,
    newman_local: !!newmanVersion(), presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}
export function contexto(args) {
  const v = k => args.includes(k) ? args[args.indexOf(k) + 1] : undefined;
  const operacion = v('--operacion'), version = Number(v('--version')), intento = Number(v('--intento')),
    runId = v('--run-id'), referencia = v('--autorizacion'), archivo = v('--contexto');
  if (!CAPACIDADES.operaciones.includes(operacion) || !Number.isInteger(version) || version < 1 || version > 99 ||
      !Number.isInteger(intento) || intento < 1 || !referencia || !archivo ||
      !new RegExp(`^RUN-G36-V${version}-\\d{8}-\\d{6}$`).test(runId ?? '')) throw Error('Contexto incompleto');
  const destino = path.join(DIR, ...(version === 1 ? ['Resultados', runId] : [`EvaluacionV${version}`, 'Resultados', runId]));
  const ruta = path.resolve(archivo);
  if (path.dirname(ruta) !== destino || path.basename(ruta) !== 'contexto_operacion.json') throw Error('Contexto fuera del RUN');
  const c = JSON.parse(fs.readFileSync(ruta, 'utf8'));
  if (c.grupo !== 'G36' || c.run_id !== runId || c.version !== version || c.intento !== intento ||
      c.operacion !== operacion.toUpperCase() || c.referencia !== referencia ||
      JSON.stringify(c.casos) !== JSON.stringify(CASOS) ||
      (version > 1 && (operacion !== 'reevaluar' || c.version_anterior !== version - 1 || !c.alcance_reevaluacion)) ||
      (version === 1 && operacion === 'reevaluar')) throw Error('Contexto incoherente');
  return { operacion, version, intento, runId, referencia, directorio: destino, ensayo: false };
}
export function preflight(c, env, n = newmanVersion()) {
  const barreras = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_CONTADOR_EMAIL', 'QA_CONTADOR_PASSWORD',
    'QA_ADMIN_EMAIL', 'QA_ADMIN_PASSWORD'].filter(k => !String(env[k] ?? '').trim());
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (c.ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(String(env.SIGAB_API_TEST_BASE)) :
    String(env.SIGAB_API_TEST_BASE).replace(/\/+$/, '') !== API) barreras.push('API_NO_CANONICA');
  if (!n) barreras.push('NEWMAN_NO_DISPONIBLE');
  return { grupo: 'G36', run_id: c.runId, ok: !barreras.length, barreras, presupuesto: PRESUPUESTO,
    herramientas: { node: process.version, newman: n }, efectos_externos: [
      'M02 puede registrar bitácora RF-52 fuera de la transacción del RUN.',
      'Procesar eventos M06 puede incluir backlog ajeno; comprobar antes de autorizar TEST.',
      'DELETE del sandbox requiere lecturas poscierre; no prueba reversión de archivos o notificaciones externas.' ] };
}
function errorPublico(b) {
  const o = b?.detail && typeof b.detail === 'object' ? b.detail : b;
  return { codigo: texto(o?.error_code ?? o?.code ?? o?.codigo ?? ''),
    mensaje: texto(typeof o?.message === 'string' ? o.message : typeof o?.mensaje === 'string' ? o.mensaje :
      typeof o?.detail === 'string' ? o.detail : '') };
}
export async function pedir(r, api, metodo, ruta, { token, secreto, runId, cuerpo, timeout, fetcher = fetch, fuera = false, cierre = false } = {}) {
  if (r._corte && !cierre) return { http: null, fallo: 'CORTE_POLITICA' };
  if (!fuera && r._solicitudesRun >= PRESUPUESTO.solicitudes_totales - (cierre ? 0 : 7))
    return { http: null, fallo: 'PRESUPUESTO_AGOTADO' };
  if (!fuera) r._solicitudesRun++;
  const fila = { metodo, ruta: ruta.split('?')[0], http: null, fuera_run: fuera };
  r.solicitudes.push(fila); const inicio = Date.now();
  try {
    if (inicio > r._limite && !cierre) throw Error('DURACION_EXCEDIDA');
    const res = await fetcher(api + ruta, { method: metodo, redirect: 'manual',
      headers: { ...(cuerpo ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(runId ? { 'X-Test-Run-Id': runId, 'X-Zona-Horaria': 'America/Bogota' } : {}),
        ...(secreto ? { 'X-Sandbox-Secret': secreto } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      signal: AbortSignal.timeout(Math.max(1, Math.min(timeout ?? (metodo === 'POST' ? 120000 : 30000),
        cierre ? 30000 : r._limite - inicio))) });
    const b = await res.json().catch(() => null); const err = errorPublico(b);
    fila.http = res.status; fila.duracion_ms = Date.now() - inicio;
    fila.eco = runId ? res.headers.get('x-test-run-id') === runId : null;
    fila.codigo = sanear(err.codigo, r._secretos);
    fila.mensaje_saneado = sanear(err.mensaje, r._secretos);
    r._seguidos5xx = res.status >= 500 ? r._seguidos5xx + 1 : 0;
    if (res.status === 403 || r._seguidos5xx >= 3) r._corte = true;
    return { http: res.status, cuerpo: b, eco: fila.eco, codigo: fila.codigo, mensaje: fila.mensaje_saneado, fila };
  } catch (e) {
    fila.fallo = e.name === 'TimeoutError' || e.name === 'AbortError' ? 'TIMEOUT' : 'SIN_RESPUESTA';
    fila.duracion_ms = Date.now() - inicio;
    return { http: null, fallo: fila.fallo, fila };
  }
}
const ok = x => x?.http === 200 && x.eco !== false;
const req = (r, api, metodo, ruta, opts) => pedir(r, api, metodo, ruta, { ...opts, fetcher: r._fetcher });
const resumenProcesamiento = x => ({ http: x?.http ?? null, eco: x?.eco ?? null,
  eventos: x?.cuerpo?.eventos && typeof x.cuerpo.eventos === 'object' ? x.cuerpo.eventos : null,
  provisiones_m05: x?.cuerpo?.provisiones_m05 && typeof x.cuerpo.provisiones_m05 === 'object' ?
    x.cuerpo.provisiones_m05 : null });
async function leerAuditoria(r, api, opts, aid, pid) {
  const eventos = [], vistos = new Set();
  for (let pagina = 1; pagina <= 4 && !r._corte; pagina++) {
    const x = await req(r, api, 'GET', `/finanzas/auditoria?id_activo_biologico=${aid}&id_periodo_contable=${pid}&formato=TECNICO&tamano=500&pagina=${pagina}`, opts);
    if (!ok(x) || !Array.isArray(x.cuerpo?.eventos) || !Number.isSafeInteger(x.cuerpo?.total_registros)) return null;
    for (const e of x.cuerpo.eventos) {
      const k = id(e.id_evento); if (!k || vistos.has(k)) return null;
      vistos.add(k); eventos.push(e);
    }
    if (eventos.length === x.cuerpo.total_registros) return eventos;
    if (!x.cuerpo.eventos.length || eventos.length > x.cuerpo.total_registros) return null;
  }
  return null;
}
async function instantanea(r, api, opts, aid, pid, { poscierre = false } = {}) {
  const m06 = poscierre ? { token: opts.m06.token, cierre: true } : opts.m06;
  const m02 = poscierre ? { token: opts.m02.token, cierre: true } : opts.m02;
  const rutas = [`/finanzas/periodos/${pid}/variaciones`, `/finanzas/lineas?id_periodo_contable=${pid}`,
    `/finanzas/activos/${aid}`, `/activos-biologicos/${aid}/eventos`, `/activos-biologicos/${aid}/ficha-integral`];
  const v = await req(r, api, 'GET', rutas[0], m06);
  const l = await req(r, api, 'GET', rutas[1], m06);
  const d = await req(r, api, 'GET', rutas[2], m06);
  const e = await req(r, api, 'GET', rutas[3], m02);
  const f = await req(r, api, 'GET', rutas[4], m02);
  const auditoria = await leerAuditoria(r, api, m06, aid, pid);
  const completa = [v, l, d, e, f].every(ok) && Array.isArray(v.cuerpo) && Array.isArray(l.cuerpo) &&
    Array.isArray(d.cuerpo?.calculos) && Array.isArray(d.cuerpo?.mediciones) &&
    Array.isArray(e.cuerpo?.eventos) && Array.isArray(auditoria);
  return { completa, variaciones: v.cuerpo, lineas: l.cuerpo, calculos: d.cuerpo?.calculos,
    mediciones: d.cuerpo?.mediciones,
    eventos: e.cuerpo?.eventos, auditoria, estado: f.cuerpo?.estado_actual, peso: f.cuerpo?.peso_actual,
    http: [v.http, l.http, d.http, e.http, f.http] };
}
async function conciliarEvento(r, api, opts, aid, baseIds) {
  const e = await req(r, api, 'GET', `/activos-biologicos/${aid}/eventos`, opts);
  if (!ok(e) || !Array.isArray(e.cuerpo?.eventos)) return null;
  const encontrados = e.cuerpo.eventos.filter(x => !baseIds.has(String(x.id_eventos)));
  return encontrados.length === 1 ? id(encontrados[0].id_eventos) : null;
}
function rutaOperacion(plantilla, { variacionId, periodoId, correctivoId }) {
  if (!/^\/finanzas\//.test(plantilla)) return null;
  let desconocido = false;
  const ruta = plantilla.replace(/\{([^}]+)\}/g, (_, clave) => {
    if (/periodo/i.test(clave)) return String(periodoId);
    if (/correctiv/i.test(clave)) return String(correctivoId ?? (desconocido = true));
    if (/variaci/i.test(clave)) return String(variacionId);
    if (clave === 'id') return String(variacionId);
    desconocido = true; return '';
  });
  return desconocido ? null : ruta;
}
function schemaJson(spec, contrato) {
  let schema = spec.requestBody?.content?.['application/json']?.schema;
  if (schema?.$ref) schema = contrato.components?.schemas?.[schema.$ref.split('/').at(-1)];
  return schema;
}
function cuerpoCorrectivo(spec, contrato, original) {
  if (!spec.requestBody) return undefined;
  const schema = schemaJson(spec, contrato);
  if (!schema) return null;
  const props = schema.properties ?? {};
  const valores = { id_variacion_corregida: original.uuid ?? original.id_variacion_uuid ?? original.id_variacion ?? id(original.id_variacion_valor_razonable),
    monto_variacion: -monto(original.monto_variacion), justificacion: 'Corrección QA dentro de RUN autorizado' };
  const obligatorias = schema.required ?? [];
  if (obligatorias.some(k => !(k in valores)) || !obligatorias.includes('id_variacion_corregida')) return null;
  return Object.fromEntries(Object.entries(valores).filter(([k]) => k in props));
}
async function intentarCorrectivo(r, api, opts, contrato, operaciones, original, lineaOriginal, pid, aid) {
  if (r._solicitudesRun + 19 > PRESUPUESTO.solicitudes_totales)
    return { estado: 'NO_CONCLUYENTE', motivo: 'Presupuesto insuficiente para crear, aprobar, conciliar y cerrar el correctivo.' };
  const crear = operaciones.find(x => x.metodo === 'POST' && /correctiv|correcci|corregid/i.test(x.ruta + x.nombre) && !/aprob/i.test(x.ruta + x.nombre));
  const aprobar = operaciones.find(x => /aprob/i.test(x.ruta + x.nombre));
  if (!crear || !aprobar) return { estado: 'RECHAZADO', motivo: 'El contrato público no expone ambas operaciones: crear y aprobar correctivo.' };
  const rutaCrear = rutaOperacion(crear.ruta, { variacionId: id(original.id_variacion_valor_razonable), periodoId: pid });
  const cuerpo = cuerpoCorrectivo(crear, contrato, original);
  if (!rutaCrear || cuerpo === null) return { estado: 'NO_CONCLUYENTE', motivo: 'Esquema de creación correctiva no permite construir cuerpo seguro desde el oráculo.' };
  const antes = await instantanea(r, api, opts, aid, pid);
  if (!antes.completa) return { estado: 'NO_CONCLUYENTE', motivo: 'Lectura anterior al correctivo incompleta.' };
  const c = await req(r, api, crear.metodo, rutaCrear, { ...opts.m06, cuerpo });
  const pendiente = await instantanea(r, api, opts, aid, pid);
  if (!pendiente.completa) return { estado: 'NO_CONCLUYENTE', motivo: 'No se pudo conciliar el correctivo tras crear.' };
  const referenciaOriginal = original.uuid ?? original.id_variacion_uuid ?? original.id_variacion ?? id(original.id_variacion_valor_razonable);
  const nuevosReg = nuevos(antes.variaciones, pendiente.variaciones, 'id_variacion_valor_razonable')
    .filter(x => id(x.id_activo_biologico) === aid && String(x.id_variacion_corregida) === String(referenciaOriginal));
  if (c.http >= 500 || c.http == null) return { estado: 'NO_CONCLUYENTE', motivo: 'POST correctivo sin respuesta concluyente; lectura conciliada sin reintento.' };
  if (c.http >= 400 || nuevosReg.length !== 1) return { estado: 'RECHAZADO', motivo: `Crear correctivo devolvió HTTP ${c.http}; registros vinculados nuevos ${nuevosReg.length}.` };
  const nuevo = nuevosReg[0];
  const lineaPrevia = pendiente.lineas.find(x => x.tabla_origen === 'variaciones_valor_razonable' && id(x.id_origen) === id(nuevo.id_variacion_valor_razonable));
  const efectivoAntes = /APROBADO|EFECTIVO|REGISTRADO/i.test(String(nuevo.estado ?? '')) || lineaPrevia?.estado === 'REGISTRADA';
  const rutaAprobar = rutaOperacion(aprobar.ruta, { variacionId: id(nuevo.id_variacion_valor_razonable),
    correctivoId: id(nuevo.id_variacion_valor_razonable), periodoId: pid });
  if (!rutaAprobar) return { estado: 'NO_CONCLUYENTE', motivo: 'Ruta de aprobación no admite parámetros identificables del oráculo.' };
  const esquemaAprobacion = schemaJson(aprobar, contrato);
  const requeridos = esquemaAprobacion?.required ?? [];
  const valoresAprobacion = { aprobar: true, aprobado: true, confirmacion: true };
  if (aprobar.requestBody && (!esquemaAprobacion || requeridos.some(k => !(k in valoresAprobacion))))
    return { estado: 'NO_CONCLUYENTE', motivo: 'Esquema de aprobación requiere datos ajenos al oráculo; no se inventa una petición.' };
  const cuerpoAprobacion = aprobar.requestBody ? Object.fromEntries(Object.entries(valoresAprobacion)
    .filter(([k]) => k in (esquemaAprobacion.properties ?? {}))) : undefined;
  const a = await req(r, api, aprobar.metodo, rutaAprobar, { ...opts.m06, cuerpo: cuerpoAprobacion });
  const final = await instantanea(r, api, opts, aid, pid);
  if (!final.completa) return { estado: 'NO_CONCLUYENTE', motivo: 'Lectura posterior a aprobación incompleta.' };
  const nuevoFinal = final.variaciones.find(x => id(x.id_variacion_valor_razonable) === id(nuevo.id_variacion_valor_razonable));
  const linea = final.lineas.find(x => x.tabla_origen === 'variaciones_valor_razonable' && id(x.id_origen) === id(nuevo.id_variacion_valor_razonable));
  const decision = evaluar010({ contrato: operaciones, original, pendiente: nuevo, lineaOriginal, lineaCorrectiva: linea,
    previo: { efectivo: efectivoAntes }, aprobado: { efectivo: /APROBADO|EFECTIVO|REGISTRADO/i.test(String(nuevoFinal?.estado ?? '')) || Boolean(linea),
      original_visible: final.variaciones.some(x => id(x.id_variacion_valor_razonable) === id(original.id_variacion_valor_razonable)),
      correctivo_visible: Boolean(nuevoFinal) }, aprobacionHttp: a.http });
  return { ...decision, observados: { creacion_http: c.http, aprobacion_http: a.http,
    original_id: id(original.id_variacion_valor_razonable), correctivo_id: id(nuevo.id_variacion_valor_razonable),
    monto_opuesto: igualMonto(nuevo.monto_variacion, -monto(original.monto_variacion)),
    referencia_uuid: String(nuevo.id_variacion_corregida) === String(original.uuid ?? original.id_variacion_uuid ?? original.id_variacion),
    efectivo_antes: efectivoAntes, original_visible: final.variaciones.some(x => id(x.id_variacion_valor_razonable) === id(original.id_variacion_valor_razonable)),
    correctivo_visible: Boolean(nuevoFinal), linea_inversa: Boolean(linea && linea.valor > 0 &&
      linea.cuenta_debito === lineaOriginal.cuenta_credito && linea.cuenta_credito === lineaOriginal.cuenta_debito) } };
}
async function newmanLecturas(r, c, env, token, pid) {
  if (r._solicitudesRun + LECTURAS_NEWMAN.length + 7 > PRESUPUESTO.solicitudes_totales) return null;
  const vars = { base_url: String(env.SIGAB_API_TEST_BASE).replace(/\/+$/, ''), run_id: c.runId,
    sandbox_secret: env.QA_SANDBOX_SECRET, token, periodo_id: String(pid) };
  const environment = { values: Object.entries(vars).map(([key, value]) => ({ key, value, enabled: true })) };
  const out = spawnSync(process.execPath, [path.join(DIR, 'pruebas/newman_hijo.mjs')], {
    input: JSON.stringify({ coleccion: JSON.parse(fs.readFileSync(COLECCION, 'utf8')), environment, timeout: 30000 }),
    timeout: 160000, encoding: 'utf8', windowsHide: true, maxBuffer: 1024 * 1024 });
  let hijo; try { hijo = JSON.parse(out.stdout); } catch { hijo = { error: out.error?.code ?? 'SIN_RESPUESTA_HIJO', solicitudes: [] }; }
  const sintesis = { version: newmanVersion(), codigo: out.status, error: hijo.error ?? null,
    estadisticas: hijo.estadisticas ?? null, solicitudes: hijo.solicitudes ?? [] };
  const dir = path.join(c.directorio, 'newman'); fs.mkdirSync(dir, { recursive: true });
  const limpio = sanear(JSON.stringify(sintesis, null, 2), [token, ...r._secretos]);
  fs.writeFileSync(path.join(dir, 'newman-G36.json'), limpio);
  fs.writeFileSync(path.join(dir, 'newman-G36.html'), '<!doctype html><meta charset="utf-8"><title>G36 Newman</title><h1>G36 Newman</h1><pre>' + html(limpio) + '</pre>');
  r._solicitudesRun += sintesis.solicitudes.length;
  for (const s of sintesis.solicitudes) r.solicitudes.push({ metodo: 'GET', ruta: s.nombre, http: s.http, herramienta: 'Newman' });
  const fallos = sintesis.solicitudes.flatMap(s => s.aserciones?.filter(x => x.error) ?? []).length;
  r.herramientas.newman = { version: sintesis.version, iteraciones: sintesis.solicitudes.length === LECTURAS_NEWMAN.length ? 1 : 0,
    solicitudes: sintesis.solicitudes.length, fallos, codigo: out.status,
    problema: out.status !== 0 || fallos > 0 || sintesis.solicitudes.some(x => x.http === 401 || x.http === 403) };
  return sintesis;
}
function registrar(r, caso, decision, evidencia) {
  r.casos[caso] = decision;
  for (const clave of IDS[caso]) r.comprobaciones.push({ caso, fuente: 'API', id: clave, tipo: 'ASSERT',
    estado: decision.estado, motivo: texto(decision.motivo), evidencia });
}
export function informe(c, r) {
  const estados = CASOS.map(k => r.casos[k]?.estado ?? 'NO_CONCLUYENTE');
  const estadoAgregado = estados.includes('RECHAZADO') ? 'RECHAZADO' :
    estados.every(x => x === 'APROBADO') ? 'APROBADO' :
    estados.includes('BLOQUEADO') ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
  const esperado = {
    'TC-M06-009': 'PUT, PATCH y DELETE bloqueados sobre variación y línea; respuesta orienta al correctivo; ambos registros idénticos campo a campo.',
    'TC-M06-010': 'Nuevo correctivo con monto opuesto y referencia explícita al UUID original; ineficaz antes de aprobación del Contador; ambos visibles sin eliminación; línea inversa de valor positivo.' };
  const detalle = CASOS.map(k => {
    const x = r.casos[k];
    const correctivas = r.contrato?.correctivas;
    const operaciones = Array.isArray(correctivas) ?
      (correctivas.length ? correctivas.map(z => `${texto(z.operationId ?? z.ruta)} (${texto(z.metodo)})`).join('; ') : 'ninguna') :
      'no acreditadas';
    const flujo = x?.observados ?
      ` Flujo correctivo: creación HTTP ${x.observados.creacion_http ?? 'sin respuesta'}, aprobación HTTP ${x.observados.aprobacion_http ?? 'sin respuesta'}; original ${x.observados.original_id ?? 'sin acreditar'}, correctivo ${x.observados.correctivo_id ?? 'sin acreditar'}; monto opuesto ${x.observados.monto_opuesto ?? 'sin acreditar'}, referencia UUID ${x.observados.referencia_uuid ?? 'sin acreditar'}, efectivo antes ${x.observados.efectivo_antes ?? 'sin acreditar'}, original visible ${x.observados.original_visible ?? 'sin acreditar'}, correctivo visible ${x.observados.correctivo_visible ?? 'sin acreditar'}, línea inversa ${x.observados.linea_inversa ?? 'sin acreditar'}.` : '';
    const intentos = x?.observados?.intentos ?? [];
    const rutas = [...new Set(intentos.map(z => z.ruta))];
    const codigos = [...new Set(intentos.map(z => z.http ?? 'sin respuesta'))];
    const mensajes = [...new Set(intentos.map(z => z.mensaje).filter(Boolean))];
    const huellas = x?.comparacion_campo_a_campo;
    const obs = k === CASOS[0] ?
      (intentos.length ? `${intentos.length} intentos PUT, PATCH y DELETE sobre ${rutas.join(', ')}: ${codigos.length === 1 ? 'todos HTTP' : 'respuestas HTTP'} ${codigos.join('/')} ${mensajes.join('/')}${intentos.every(z => !z.codigo) ? ', sin código de error' : ''}${x?.observados?.orientados === 0 ? ' ni mensaje que mencione el registro correctivo' : ''}.` : 'Sin intentos completos.') +
      (huellas ? ` Comparación campo a campo: variación (${huellas.variacion.campos.length} campos), SHA-256 ${huellas.variacion.sha256_antes === huellas.variacion.sha256_despues ? 'idéntica' : 'distinta'} antes y después; línea (${huellas.linea.campos.length} campos), SHA-256 ${huellas.linea.sha256_antes === huellas.linea.sha256_despues ? 'idéntica' : 'distinta'} antes y después.` : '') :
      `Contrato ${r.contrato?.ruta ?? '/openapi.json'}: HTTP ${r.contrato?.http ?? 'sin lectura'}; operaciones M06 ${r.contrato?.operaciones_m06?.length ?? 'no acreditadas'}; operaciones correctivas ${operaciones}; huella SHA-256 ${r.contrato?.sha256 ?? 'no acreditada'}.${flujo}`;
    const cumplido = k === CASOS[0] && intentos.length && huellas && x?.observados?.bloqueados === intentos.length && Array.isArray(x?.observados?.campos_alterados) && !x.observados.campos_alterados.length ?
      `Los ${intentos.length} intentos quedaron bloqueados y no alteraron ningún campo: se cumplió la inmutabilidad append-only de la variación y su línea.` :
      k === CASOS[1] && r.contrato?.http === 200 ? 'Se completó la lectura del contrato público; no se acreditó la ejecución de un correctivo.' : texto(x?.cumplido ?? 'No acreditado.');
    const fallo = x?.estado === 'RECHAZADO' ? `${k === CASOS[0] ? 'CA-12' : 'CA-13'}: ${texto(x.motivo)}${k === CASOS[0] ? ' El bloqueo por sí solo no satisface la orientación exigida.' : ' Sin operaciones públicas de creación y aprobación, no se pudo ejecutar el mecanismo exigido.'}` :
      x?.estado === 'APROBADO' ? 'Ningún incumplimiento observado.' : `No decidido: ${texto(x?.motivo)}`;
    const preparacion = `Activo ${r.preparacion?.activo_id ?? 'sin seleccionar'}, período ${r.preparacion?.periodo_id ?? 'sin seleccionar'} ABIERTO, evento ${r.preparacion?.evento_id ?? 'sin crear'}, variación ${r.preparacion?.variacion_id ?? 'sin crear'} y línea ${r.preparacion?.linea_id ?? 'sin crear'}; precio vigente ${r.preparacion?.precio_id ?? 'sin acreditar'}, ${r.preparacion?.rebase === false ? 'sin rebase' : r.preparacion?.rebase === true ? 'con rebase' : 'rebase no evaluado'}.`;
    return `### ${k}\n\n- **Preparación:** ${preparacion}\n- **Esperado:** ${esperado[k]}\n- **Observado:** ${obs}\n- **Qué se cumplió:** ${cumplido}\n- **Qué falló y por qué:** ${fallo}\n- **Decisión:** ${x?.estado ?? 'NO_CONCLUYENTE'}.`;
  }).join('\n\n');
  const incidencias = r.incidencias.length ? r.incidencias.map(x => `### ${x.id}${x.titulo ? ` — ${x.titulo}` : ''}\n\n**Casos:** ${x.casos.join(', ')}.\n\n**Requisito:** ${x.requisito}.\n\n**Pasos para reproducir:** ${x.pasos}\n\n**Esperado:** ${x.esperado}\n\n**Obtenido:** ${x.obtenido}\n\n${x.apoyo_codigo ? `**Apoyo de código leído, sin atribución causal:** ${x.apoyo_codigo}\n\n` : ''}**Impacto y severidad:** ${x.severidad}. ${x.impacto} ${x.justificacion_severidad} Certeza ${x.certeza} de la discrepancia observada; causa raíz ${x.causa_raiz}.\n\n**Primera atención:** ${x.equipo_inicial}. ${x.fundamento_equipo}\n\n**Evidencias:** ${x.evidencias.map(e => '`' + e + '`').join(', ')}.`).join('\n\n') : 'Ninguna discrepancia de producto comprobada.';
  const conclusion = r.oficial && r.incidencias.length === 1 && r.incidencias[0].casos.length === 2 && estados.every(x => x === 'RECHAZADO') && Array.isArray(r.contrato?.correctivas) && r.contrato.correctivas.length === 0 ?
    'TC-M06-009: bloqueo e inmutabilidad cumplen, pero falla la orientación al correctivo exigida por CA-12. TC-M06-010: el contrato público no ofrece crear ni aprobar el mecanismo exigido por CA-13. Ambos incumplimientos se agrupan en una sola incidencia. Desarrollo implementa el mecanismo y la orientación; QA reevalúa con nueva autorización.' :
    r.oficial ? 'Conservar el RUN y derivar las incidencias al equipo inicial indicado; QA decide reevaluación con nueva autorización.' : 'RUN no oficial: resolver la evidencia o el cierre pendiente antes de un veredicto.';
  return `# TC-M06-G36 — ${estadoAgregado}\n\n## Identificación\n\nGrupo G36; casos ${CASOS.join(', ')}; RF-86 CA-12/13, Restricción 5; versión ${c.version}, intento ${c.intento}; RUN ${c.runId}; ambiente TEST; autorización ${c.referencia}; commit TEST no verificado; Node ${r.herramientas.node}; Newman ${r.herramientas.newman?.version ?? 'no ejecutado'}; Cypress 0 (matriz solo API).\n\n## Decisión del caso\n\n| Caso | Estado | Motivo |\n|---|---|---|\n${CASOS.map(k => `| ${k} | ${r.casos[k]?.estado ?? 'NO_CONCLUYENTE'} | ${texto(r.casos[k]?.motivo)} |`).join('\n')}\n\nOficial: ${r.oficial}.\n\n## Preparación y candidatos\n\nActivo ${r.preparacion?.activo_id ?? 'sin seleccionar'}, período ${r.preparacion?.periodo_id ?? 'sin seleccionar'}, precio vigente ${r.preparacion?.precio_id ?? 'sin acreditar'}, rebase ${r.preparacion?.rebase ?? 'no evaluado'}, evento ${r.preparacion?.evento_id ?? 'sin crear'}, variación ${r.preparacion?.variacion_id ?? 'sin crear'}, línea ${r.preparacion?.linea_id ?? 'sin crear'}.\n\n${r.candidatos.map(x => `- Activo ${x.activo_id ?? 'sin ID'}: ${x.estado}. ${texto(x.motivo)}`).join('\n') || 'Sin candidatos recibidos o lectura incompleta.'}\n\n## Detalle por caso\n\n${detalle}\n\n## Comprobaciones API\n\n${r.comprobaciones.map(x => `- ${x.id} (${x.caso}): ${x.estado}; ${texto(x.motivo)}; evidencia ${x.evidencia}.`).join('\n') || 'Ninguna comprobación ejecutada.'}\n\n## Evidencias reales\n\n${r.evidencias.map(x => '- ' + x).join('\n') || 'Ninguna.'}\n\n## Incidencias de producto\n\n${incidencias}\n\n## Problemas técnicos\n\n${r.problemas_tecnicos.map(x => '- ' + texto(x)).join('\n') || 'Ninguno observado.'}\n\nLas rutas de código local consultadas figuran en README; no prueban la versión desplegada ni la causa raíz.\n\n## Cierre y rollback\n\nDELETE HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}; rollback ${r.cierre.rollback.verificado ? 'verificado mediante lecturas públicas poscierre' : 'no verificado'}. ${r.cierre.rollback.motivo} Los efectos RF-52 o backlog fuera de la transacción no quedan cubiertos por estas lecturas.\n\n## Conclusión y acciones\n\n${conclusion} Solicitudes dentro del RUN: ${r._solicitudesRun}/${PRESUPUESTO.solicitudes_totales}.\n`;
}
export async function evaluar(c, { env = leerEnv(), fetcher = fetch, sinArtefactos = false } = {}) {
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G36', run_id: c.runId, autorizacion_referencia: c.referencia,
    version: c.version, intento: c.intento, casos: {},
    comprobaciones: [], solicitudes: [], incidencias: [], problemas_tecnicos: [], evidencias: [],
    candidatos: [], herramientas: { node: process.version, newman: null }, cypress: { total_pruebas: 0 },
    cierre: { run: { cierre_http: null }, rollback: { verificado: false, motivo: 'No comprobado.' } },
    oficial: false, consume_version: false, _limite: Date.now() + 900000, _corte: false,
    _seguidos5xx: 0, _solicitudesRun: 0, _fetcher: fetcher };
  const pf = preflight(c, env, sinArtefactos ? 'ensayo-local' : newmanVersion());
  r._secretos = [env.QA_SANDBOX_SECRET, env.QA_CONTADOR_EMAIL, env.QA_CONTADOR_PASSWORD,
    env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD];
  if (!sinArtefactos) {
    if (!fs.existsSync(c.directorio)) throw Error('El lanzador debe crear el RUN antes de evaluar');
    fs.writeFileSync(path.join(c.directorio, 'preflight.json'), JSON.stringify(pf, null, 2));
    r.evidencias.push('preflight.json');
  }
  let token = null, admin = null, iniciado = false, base = null, aid = null, pid = null;
  const eventosRun = []; let variacionId = null, lineaId = null, mutado = false;
  let contrato = null, operaciones = null;
  const terminar = (caso, estado, motivo, extra = {}) => registrar(r, caso, { estado, motivo, ...extra },
    sinArtefactos ? 'ensayo-local' : 'resultado.json');
  try {
    if (!pf.ok) { for (const caso of CASOS) terminar(caso, 'BLOQUEADO', 'Preflight local: ' + pf.barreras.join(', ')); return r; }
    const login = await req(r, api, 'POST', '/sesiones/', { fuera: true,
      cuerpo: { correo_electronico: env.QA_CONTADOR_EMAIL, contrasena: env.QA_CONTADOR_PASSWORD }, timeout: 120000 });
    token = login.cuerpo?.token ?? login.cuerpo?.access_token ?? null;
    const lm = await req(r, api, 'POST', '/sesiones/', { fuera: true,
      cuerpo: { correo_electronico: env.QA_ADMIN_EMAIL, contrasena: env.QA_ADMIN_PASSWORD }, timeout: 120000 });
    admin = lm.cuerpo?.token ?? lm.cuerpo?.access_token ?? null;
    if (login.http !== 200 || lm.http !== 200 || !token || !admin) {
      for (const caso of CASOS) terminar(caso, 'NO_CONCLUYENTE', 'No se obtuvieron ambas sesiones QA.'); return r; }
    const opts = { m06: { token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId },
      m02: { token: admin, secreto: env.QA_SANDBOX_SECRET, runId: c.runId } };
    const op = await req(r, api, 'GET', '/openapi.json', {}); iniciado = true;
    if (ok(op) && op.cuerpo?.openapi && op.cuerpo?.paths) {
      contrato = op.cuerpo; operaciones = operacionesCorrectivas(contrato);
      r.contrato = { ruta: '/openapi.json', http: op.http, sha256: huella(contrato),
        operaciones_m06: Object.entries(contrato.paths).filter(([ruta]) => ruta.startsWith('/finanzas/'))
          .flatMap(([ruta, metodos]) => Object.keys(metodos).filter(m => ['get', 'post', 'put', 'patch', 'delete'].includes(m))
            .map(metodo => ({ ruta, metodo: metodo.toUpperCase() }))),
        correctivas: operaciones.map(x => ({ ruta: x.ruta, metodo: x.metodo, operationId: x.operationId })) };
      const tieneCrear = operaciones.some(x => x.metodo === 'POST' && /correctiv|correcci|corregid/i.test(x.ruta + x.nombre) && !/aprob/i.test(x.ruta + x.nombre));
      const tieneAprobar = operaciones.some(x => /aprob/i.test(x.ruta + x.nombre));
      if (!tieneCrear || !tieneAprobar) terminar(CASOS[1], 'RECHAZADO', 'El contrato OpenAPI desplegado no expone ambas operaciones: crear y aprobar correctivo de variación.',
        { cumplido: 'Contrato público leído; ausencia observada.' });
    } else terminar(CASOS[1], 'NO_CONCLUYENTE', `Contrato OpenAPI ilegible: HTTP ${op.http ?? 'sin respuesta'}.`);
    if (r._corte) { terminar(CASOS[0], 'NO_CONCLUYENTE', 'Corte por 403 o tres 5xx consecutivos.'); return r; }
    const a = await req(r, api, 'GET', '/finanzas/activos', opts.m06);
    const p = await req(r, api, 'GET', '/finanzas/periodos', opts.m06);
    const cfg = await req(r, api, 'GET', '/finanzas/configuracion', opts.m06);
    if (![a, p, cfg].every(ok) || !Array.isArray(a.cuerpo) || !Array.isArray(p.cuerpo) || !Array.isArray(cfg.cuerpo?.matriz)) {
      terminar(CASOS[0], 'NO_CONCLUYENTE', 'Catálogos públicos de activos, períodos o matriz incompletos.'); return r; }
    const candidatos = [];
    for (const x of a.cuerpo) {
      const fila = { activo_id: id(x.id_activo_biologico), estado: 'DESCARTADO', motivo: null };
      r.candidatos.push(fila);
      if (!/bovin/i.test(x.especie ?? '')) fila.motivo = 'Especie no bovina.';
      else if (x.tipo !== 'INDIVIDUAL') fila.motivo = 'Activo no INDIVIDUAL.';
      else if (x.estado !== 'ACTIVO') fila.motivo = 'Activo no ACTIVO.';
      else if (x.valorado_por_costo) fila.motivo = 'Valoración por costo activa.';
      else if (!(monto(x.valor_razonable_neto) > 0)) fila.motivo = 'Valor razonable no positivo.';
      else candidatos.push({ x, fila });
    }
    const precios = new Map(); const elegibles = []; let lecturaFallida = false;
    for (const { x, fila } of candidatos) {
      const n = id(x.id_activo_biologico), especie = id(x.id_especie);
      if (r._solicitudesRun > 40) { fila.motivo = 'Sin evaluar: presupuesto reservado para oráculo y cierre.'; continue; }
      if (!n || !especie) { fila.motivo = 'ID de activo o especie inválido.'; continue; }
      if (!precios.has(especie)) {
        const pr = await req(r, api, 'GET', '/finanzas/precios?id_especie=' + especie, opts.m06);
        if (!ok(pr) || !Array.isArray(pr.cuerpo)) { lecturaFallida = true; fila.motivo = `Precio ilegible: HTTP ${pr.http}.`; continue; }
        precios.set(especie, precioVigente(pr.cuerpo, especie));
      }
      const precio = precios.get(especie); if (!precio) { fila.motivo = 'Sin precio PESO_KG vigente.'; continue; }
      const d = await req(r, api, 'GET', '/finanzas/activos/' + n, opts.m06);
      const f = await req(r, api, 'GET', '/activos-biologicos/' + n + '/ficha-integral', opts.m02);
      if (!ok(d) || !ok(f)) { lecturaFallida = true; fila.motivo = 'Detalle financiero o ficha M02 ilegible.'; continue; }
      const periodo = periodoDestino(p.cuerpo, d.cuerpo?.activo?.numero_id_tributaria);
      if (!periodo) { fila.motivo = 'Sin período destino ABIERTO para titular tributario.'; continue; }
      if (!d.cuerpo?.reconocimientos?.some(y => y.estado === 'CONFIRMADO')) { fila.motivo = 'Sin reconocimiento CONFIRMADO.'; continue; }
      const calc = calculoVigente(d.cuerpo);
      if (!calc) { fila.motivo = 'Sin cálculo CALCULADO positivo.'; continue; }
      if (f.cuerpo?.estado_actual !== 'ACTIVO' || f.cuerpo?.unidad_peso !== 'kg' || !(monto(f.cuerpo?.peso_actual) > 0)) {
        fila.motivo = 'Ficha sin ACTIVO o peso kg positivo.'; continue; }
      if (Math.round(monto(f.cuerpo.peso_actual) * 1.02 * 100) / 100 <= monto(f.cuerpo.peso_actual)) {
        fila.motivo = 'Pesaje +2 % no cambia el valor tras redondeo a centésimas.'; continue; }
      const matriz = cfg.cuerpo.matriz.some(y => y.tipo_hecho === 'VARIACION_VR_TB' && y.sentido === 'GANANCIA' &&
        (y.id_especie == null || id(y.id_especie) === especie) && y.cuenta_debito && y.cuenta_credito);
      if (!matriz) { fila.motivo = 'Sin matriz RF-109 para VARIACION_VR_TB/GANANCIA.'; continue; }
      elegibles.push({ x, fila, n, especie, precio, periodo, calc, peso: monto(f.cuerpo.peso_actual) });
    }
    const sinEvaluar = r.candidatos.some(x => x.motivo?.startsWith('Sin evaluar'));
    const eleccionIncierta = sinEvaluar && !elegibles.some(x => !requiereRebase(x));
    if (eleccionIncierta) for (const x of elegibles)
      x.fila.motivo = 'Elegible con rebase; no se seleccionó porque quedan candidatos sin evaluar.';
    const elegido = eleccionIncierta ? null : elegirCandidato(elegibles);
    if (!elegido) {
      terminar(CASOS[0], lecturaFallida || sinEvaluar ? 'NO_CONCLUYENTE' : 'BLOQUEADO',
        'Sin candidato acreditado; revisar motivos individuales y lecturas.' ); return r;
    }
    aid = elegido.n; pid = id(elegido.periodo.id_periodo_contable);
    r.preparacion = { activo_id: aid, periodo_id: pid, precio_id: id(elegido.precio.id_precio_mercado),
      peso_kg: elegido.peso, rebase: false };
    base = await instantanea(r, api, opts, aid, pid);
    r.observaciones_preparacion = { linea_base: { completa: base.completa, datos: datosPaso(base, null, aid, pid),
      procesamiento: null } };
    if (!base.completa) { terminar(CASOS[0], 'NO_CONCLUYENTE', 'Línea base de rollback incompleta.'); return r; }
    let eventosBase = new Set(base.eventos.map(x => String(x.id_eventos)));
    const evento = async (peso, descripcion) => {
      const x = await req(r, api, 'POST', `/activos-biologicos/${aid}/eventos/crecimiento`, {
        ...opts.m02, cuerpo: { tipo_medicion: 'PESO', valor_medicion: peso, unidad_medida: 'kg', descripcion } });
      mutado = true;
      let eid = id(x.cuerpo?.evento?.id_eventos);
      if (!eid) eid = await conciliarEvento(r, api, opts.m02, aid, eventosBase);
      if (eid) { eventosRun.push(eid); eventosBase.add(String(eid)); }
      return { x, eid };
    };
    let preCaso = base;
    if (requiereRebase(elegido)) {
      const reb = await evento(elegido.peso, 'Rebase QA G36 ' + c.runId);
      if (!reb.eid) { terminar(CASOS[0], 'NO_CONCLUYENTE', 'Rebase sin evento conciliable; no se reintenta.'); return r; }
      const procRebase = await req(r, api, 'POST', '/finanzas/eventos/procesar', opts.m06);
      preCaso = await instantanea(r, api, opts, aid, pid);
      r.observaciones_preparacion.rebase = { evento_id: reb.eid, completa: preCaso.completa,
        datos: datosPaso(preCaso, base, aid, pid), procesamiento: resumenProcesamiento(procRebase) };
      if (!preCaso.completa || procRebase.http !== 200) {
        terminar(CASOS[0], 'NO_CONCLUYENTE', 'Procesamiento o lectura tras rebase incompletos.'); return r; }
      const det = await req(r, api, 'GET', '/finanzas/activos/' + aid, opts.m06);
      const calc = ok(det) ? calculoVigente(det.cuerpo) : null;
      if (!calc || id(calc.id_precio_mercado) !== id(elegido.precio.id_precio_mercado) ||
          !igualMonto(calc.magnitud, elegido.peso)) {
        terminar(CASOS[0], 'NO_CONCLUYENTE', 'No se acreditó cálculo previo con precio y peso vigentes.'); return r; }
      r.preparacion.rebase = true;
    }
    if (!preCaso.completa) { terminar(CASOS[0], 'NO_CONCLUYENTE', 'Línea base antes del pesaje incompleta.'); return r; }
    const pr = await req(r, api, 'GET', '/finanzas/precios?id_especie=' + elegido.especie, opts.m06);
    const fi = await req(r, api, 'GET', `/activos-biologicos/${aid}/ficha-integral`, opts.m02);
    if (!ok(pr) || !ok(fi) || !Array.isArray(pr.cuerpo) ||
        id(precioVigente(pr.cuerpo, elegido.especie)?.id_precio_mercado) !== id(elegido.precio.id_precio_mercado) ||
        fi.cuerpo?.estado_actual !== 'ACTIVO' || !igualMonto(fi.cuerpo?.peso_actual, elegido.peso)) {
      terminar(CASOS[0], 'NO_CONCLUYENTE', 'Precio, estado o peso cambió antes del pesaje.'); return r; }
    const pesaje = await evento(Math.round(elegido.peso * 1.02 * 100) / 100, 'Pesaje +2 % QA G36 ' + c.runId);
    if (!pesaje.eid) { terminar(CASOS[0], 'NO_CONCLUYENTE', 'Pesaje sin evento conciliable; no se reintenta.'); return r; }
    const proc = await req(r, api, 'POST', '/finanzas/eventos/procesar', opts.m06);
    const creado = await instantanea(r, api, opts, aid, pid);
    r.observaciones_preparacion.pesaje = { evento_id: pesaje.eid, completa: creado.completa,
      datos: datosPaso(creado, preCaso, aid, pid), procesamiento: resumenProcesamiento(proc) };
    if (!creado.completa || proc.http !== 200) {
      terminar(CASOS[0], 'NO_CONCLUYENTE', 'Procesamiento o lectura de variación incompletos; sin reintento.'); return r; }
    const aislamiento = aislarTransformacion(preCaso, creado, aid, pesaje.eid);
    if (aislamiento.estado !== 'AISLADA') {
      terminar(CASOS[0], 'NO_CONCLUYENTE', aislamiento.motivo + ' Revisar observaciones_preparacion.'); return r; }
    const variacion = aislamiento.variacion; variacionId = id(variacion.id_variacion_valor_razonable);
    const linea = creado.lineas.find(x => x.tabla_origen === 'variaciones_valor_razonable' && id(x.id_origen) === variacionId);
    if (!linea) { terminar(CASOS[0], 'NO_CONCLUYENTE', 'No se obtuvo línea de asiento vinculada a variación.'); return r; }
    lineaId = id(linea.id_linea_asiento_nic41);
    r.preparacion.variacion_id = variacionId; r.preparacion.linea_id = lineaId; r.preparacion.evento_id = pesaje.eid;
    const rutas = [`/finanzas/variaciones/${variacionId}`, `/finanzas/periodos/${pid}/variaciones/${variacionId}`,
      `/finanzas/lineas/${lineaId}`];
    const intentos = [];
    for (const ruta of rutas) for (const metodo of ['PUT', 'PATCH', 'DELETE']) {
      if (r._corte || intentos.length >= PRESUPUESTO.intentos_modificacion) break;
      const respuesta = await req(r, api, metodo, ruta, { ...opts.m06,
        cuerpo: metodo === 'DELETE' ? undefined : ruta.includes('/lineas/') ? { valor: monto(linea.valor) + 1 } :
          { monto_variacion: monto(variacion.monto_variacion) + 1 } });
      intentos.push({ metodo, ruta, http: respuesta.http, codigo: respuesta.codigo ?? null,
        mensaje: respuesta.mensaje ?? null });
      if (respuesta.http >= 200 && respuesta.http < 300) break;
    }
    const despues = await instantanea(r, api, opts, aid, pid);
    const va = despues.variaciones?.find(x => id(x.id_variacion_valor_razonable) === variacionId);
    const la = despues.lineas?.find(x => id(x.id_linea_asiento_nic41) === lineaId);
    if (!despues.completa) {
      terminar(CASOS[0], 'NO_CONCLUYENTE', 'Lectura posterior a intentos incompleta; no se declara inmutabilidad.');
    } else if (!va || !la) {
      terminar(CASOS[0], 'RECHAZADO', 'La variación o su línea desapareció tras los intentos de modificación.');
    } else {
      const d = evaluar009(intentos, { variacion, linea }, { variacion: va, linea: la });
      terminar(CASOS[0], d.estado, d.motivo, { observados: d.observados,
        comparacion_campo_a_campo: { variacion: { campos: Object.keys(variacion).sort(),
          sha256_antes: huella(variacion), sha256_despues: huella(va) },
        linea: { campos: Object.keys(linea).sort(), sha256_antes: huella(linea), sha256_despues: huella(la) } },
        cumplido: `${d.observados.bloqueados} intentos bloqueados; campos alterados ${d.observados.campos_alterados.length}.` });
    }
    if (!r.casos[CASOS[1]] && operaciones) {
      const d = await intentarCorrectivo(r, api, opts, contrato, operaciones, variacion, linea, pid, aid);
      terminar(CASOS[1], d.estado, d.motivo, { observados: d.observados ?? null,
        cumplido: d.estado === 'APROBADO' ? 'Oráculo completo.' : 'Contrato público y respuesta de mecanismo examinados.' });
    }
    if (!sinArtefactos && !r._corte) await newmanLecturas(r, c, env, token, pid);
    else if (sinArtefactos) r.herramientas.newman = { iteraciones: 1, fallos: 0, codigo: 0, version: 'ensayo-local', problema: false };
    if (!sinArtefactos && (r.herramientas.newman?.problema || r.herramientas.newman?.iteraciones !== 1))
      r.problemas_tecnicos.push('Newman incompleto, con actor rechazado o aserción contradictoria.');
  } catch (e) {
    r.problemas_tecnicos.push(texto(e.message));
    for (const caso of CASOS) if (!r.casos[caso]) terminar(caso, 'NO_CONCLUYENTE', 'Error de automatización sin evidencia de producto.');
  } finally {
    if (iniciado) {
      const del = await req(r, api, 'DELETE', '/test-control/runs/' + encodeURIComponent(c.runId), {
        token, secreto: env.QA_SANDBOX_SECRET, timeout: 30000, cierre: true });
      r.cierre.run.cierre_http = del.http;
      if (del.http === 200 && !mutado) r.cierre.rollback = { verificado: true, motivo: 'Sin escrituras de producto antes de DELETE.' };
      else if (del.http === 200 && aid && pid && base?.completa) {
        r._corte = false; r._seguidos5xx = 0;
        const pos = await instantanea(r, api, { m06: { token }, m02: { token: admin } }, aid, pid, { poscierre: true });
        r.cierre.rollback = rollback(base, pos, eventosRun, variacionId, lineaId);
      } else r.cierre.rollback = { verificado: false, motivo: 'DELETE o línea base sin lecturas poscierre suficientes.' };
      if (mutado && !r.cierre.rollback.verificado) r.problemas_tecnicos.push('CRÍTICA: rollback de eventos y registros del RUN no verificado.');
    }
    for (const caso of CASOS) if (!r.casos[caso]) terminar(caso, 'NO_CONCLUYENTE', 'Caso sin evidencia completa.');
    r.incidencias = unaIncidencia(r.casos, { preparacion: r.preparacion, contrato: r.contrato,
      newman: Boolean(r.herramientas.newman?.iteraciones) });
    r.oficial = !sinArtefactos && r.cierre.rollback.verificado && CASOS.every(x => ['APROBADO', 'RECHAZADO'].includes(r.casos[x].estado)) &&
      r.herramientas.newman?.iteraciones === 1 && !r.herramientas.newman.problema;
    r.consume_version = r.oficial; r.estado_ejecucion = r.oficial ? 'OFICIAL' : 'NO_OFICIAL';
    if (!sinArtefactos && fs.existsSync(c.directorio)) {
      r.evidencias.push('resultado.json', nombreInforme(c.version));
      if (r.herramientas.newman) r.evidencias.push('newman/newman-G36.json', 'newman/newman-G36.html');
      const pub = { ...r }; for (const k of ['_limite', '_corte', '_seguidos5xx', '_secretos', '_fetcher']) delete pub[k];
      fs.writeFileSync(path.join(c.directorio, 'resultado.json'), sanear(JSON.stringify(pub, null, 2), [token, admin, ...r._secretos]));
      fs.writeFileSync(path.join(c.directorio, nombreInforme(c.version)), sanear(informe(c, r), [token, admin, ...r._secretos]));
    }
    delete r._secretos; delete r._fetcher;
  }
  return r;
}
if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
else if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const c = contexto(process.argv.slice(2)); const r = await evaluar(c);
    console.log(JSON.stringify({ grupo: 'G36', run_id: c.runId, oficial: r.oficial, casos: r.casos }));
    if (!r.oficial) process.exitCode = 2;
  } catch (e) { console.error(texto(e.message)); process.exitCode = 2; }
}
