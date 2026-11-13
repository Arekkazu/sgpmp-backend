#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { CASOS, IDS, PRESUPUESTO, CAPACIDADES, id, monto, igualMonto, nuevos, igualCampos,
  periodoDestino, hoy, precioVigente, calculoVigente, evaluar009, evaluar010,
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
  { caso: CASOS[1], id: IDS[CASOS[1]][0], url: '{{base_url}}/finanzas/periodos/{{periodo_010_id}}/variaciones', token: 'token' },
  { caso: CASOS[1], id: IDS[CASOS[1]][1], url: '{{base_url}}/finanzas/lineas?id_periodo_contable={{periodo_010_id}}', token: 'token' },
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
  try { coleccion = validarColeccionPermisos(JSON.parse(fs.readFileSync(COLECCION, 'utf8'))); } catch { /* invÃ¡lida */ }
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
      (version > 1 && !(operacion === 'reevaluar' && c.version_anterior === version - 1 && c.alcance_reevaluacion ||
        operacion === 'reintentar' && (c.version_anterior === null || c.version_anterior === version - 1) &&
        typeof c.alcance_reevaluacion?.motivo === 'string' && c.alcance_reevaluacion.motivo.trim())) ||
      (version === 1 && operacion === 'reevaluar')) throw Error('Contexto incoherente');
  return { operacion, version, intento, runId, referencia, directorio: destino, ensayo: false };
}
export function preflight(c, env, n = newmanVersion()) {
  const barreras = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_CONTADOR_EMAIL', 'QA_CONTADOR_PASSWORD',
    'QA_ADMIN_EMAIL', 'QA_ADMIN_PASSWORD', 'QA_CONTADOR2_EMAIL', 'QA_CONTADOR2_PASSWORD'].filter(k => !String(env[k] ?? '').trim());
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (c.ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(String(env.SIGAB_API_TEST_BASE)) :
    String(env.SIGAB_API_TEST_BASE).replace(/\/+$/, '') !== API) barreras.push('API_NO_CANONICA');
  if (!n) barreras.push('NEWMAN_NO_DISPONIBLE');
  return { grupo: 'G36', run_id: c.runId, ok: !barreras.length, barreras, presupuesto: PRESUPUESTO,
    herramientas: { node: process.version, newman: n }, efectos_externos: [
      'M02 puede registrar bitÃ¡cora RF-52 fuera de la transacciÃ³n del RUN.',
      'Procesar eventos M06 puede incluir backlog ajeno; comprobar antes de autorizar TEST.',
      'DELETE del sandbox requiere lecturas poscierre; no prueba reversiÃ³n de archivos o notificaciones externas.' ] };
}
function errorPublico(b) {
  const o = b?.detail && typeof b.detail === 'object' ? b.detail : b;
  return { codigo: texto(o?.error_code ?? o?.code ?? o?.codigo ?? ''),
    mensaje: texto(typeof o?.message === 'string' ? o.message : typeof o?.mensaje === 'string' ? o.mensaje :
      typeof o?.detail === 'string' ? o.detail : '') };
}
export async function pedir(r, api, metodo, ruta, { token, secreto, runId, cuerpo, timeout, fetcher = fetch, fuera = false, cierre = false, permitir403 = false } = {}) {
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
    if ((res.status === 403 && !permitir403) || r._seguidos5xx >= 3) r._corte = true;
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
    `/finanzas/activos/${aid}`, `/activos-biologicos/${aid}/eventos`, `/activos-biologicos/${aid}/ficha-integral`,
    `/finanzas/correctivos?id_periodo_contable=${pid}&id_activo_biologico=${aid}`];
  const v = await req(r, api, 'GET', rutas[0], m06);
  const l = await req(r, api, 'GET', rutas[1], m06);
  const d = await req(r, api, 'GET', rutas[2], m06);
  const e = await req(r, api, 'GET', rutas[3], m02);
  const f = await req(r, api, 'GET', rutas[4], m02);
  const correctivos = await req(r, api, 'GET', rutas[5], m06);
  const auditoria = await leerAuditoria(r, api, m06, aid, pid);
  const completa = [v, l, d, e, f, correctivos].every(ok) && Array.isArray(v.cuerpo) && Array.isArray(l.cuerpo) &&
    Array.isArray(correctivos.cuerpo) &&
    Array.isArray(d.cuerpo?.calculos) && Array.isArray(d.cuerpo?.mediciones) &&
    Array.isArray(e.cuerpo?.eventos) && Array.isArray(auditoria);
  return { completa, variaciones: v.cuerpo, lineas: l.cuerpo, correctivos: correctivos.cuerpo,
    calculos: d.cuerpo?.calculos,
    mediciones: d.cuerpo?.mediciones,
    eventos: e.cuerpo?.eventos, auditoria, estado: f.cuerpo?.estado_actual, peso: f.cuerpo?.peso_actual,
    http: [v.http, l.http, d.http, e.http, f.http, correctivos.http] };
}
async function conciliarEvento(r, api, opts, aid, baseIds) {
  const e = await req(r, api, 'GET', `/activos-biologicos/${aid}/eventos`, opts);
  if (!ok(e) || !Array.isArray(e.cuerpo?.eventos)) return null;
  const encontrados = e.cuerpo.eventos.filter(x => !baseIds.has(String(x.id_eventos)));
  return encontrados.length === 1 ? id(encontrados[0].id_eventos) : null;
}
async function intentarCorrectivo(r, api, opts, original, lineaOriginal, pid, aid) {
  const oid = id(original.id_variacion_valor_razonable);
  const antes = await instantanea(r, api, opts, aid, pid);
  if (!antes.completa) return { estado: 'NO_CONCLUYENTE', motivo: 'Lectura anterior al correctivo incompleta.' };
  const c = await req(r, api, 'POST', '/finanzas/variaciones/' + oid + '/correctivos',
    { ...opts.m06, cuerpo: { motivo: 'Correccion QA de variacion durante reevaluacion autorizada.' } });
  if (c.http !== 201) return { estado: c.codigo === 'MOTIVO_REQUERIDO' || c.http === 403 ? 'NO_CONCLUYENTE' : 'RECHAZADO',
    severidad: 'ALTA', motivo: 'Solicitud correctiva HTTP ' + c.http + ', codigo ' + c.codigo,
    observados: { creacion_http: c.http, codigo: c.codigo } };
  const sid = id(c.cuerpo?.id_solicitud_correctivo_variacion);
  if (!sid) return { estado: 'NO_CONCLUYENTE', motivo: 'La solicitud no devolvio ID conciliable.' };
  const pendiente = await instantanea(r, api, opts, aid, pid);
  if (!pendiente.completa) return { estado: 'NO_CONCLUYENTE', motivo: 'Lectura pendiente incompleta.' };
  const nuevas = nuevos(antes.variaciones, pendiente.variaciones, 'id_variacion_valor_razonable');
  const lineasNuevas = nuevos(antes.lineas, pendiente.lineas, 'id_linea_asiento_nic41');
  const previo = { efectivo: nuevas.length > 0 || lineasNuevas.length > 0,
    original_visible: pendiente.variaciones.some(x => id(x.id_variacion_valor_razonable) === oid) };
  if (previo.efectivo || !previo.original_visible) return { estado: 'RECHAZADO', severidad: 'ALTA',
    motivo: previo.efectivo ? 'Correctivo efectivo antes de aprobar.' : 'Variacion original ausente antes de aprobar.',
    observados: { creacion_http: c.http, efectivo_antes: previo.efectivo,
      original_visible: previo.original_visible } };
  const doble = await req(r, api, 'POST', '/finanzas/correctivos/' + sid + '/aprobacion', { ...opts.m06, permitir403: true });
  const autoaprobado = doble.http >= 200 && doble.http < 300;
  const dobleControl = doble.http === 403 && doble.codigo === 'APROBADOR_DEBE_SER_OTRO' ?
    'Doble control activo: el solicitante no pudo aprobar.' : autoaprobado ?
      'El producto permitio la autoaprobacion (sin doble control).' :
      'Autoaprobacion respondio HTTP ' + doble.http + ', codigo ' + doble.codigo + '; se intento con el Contador 2.';
  const a = autoaprobado ? doble : await req(r, api, 'POST', '/finanzas/correctivos/' + sid + '/aprobacion', opts.m06Aprobador);
  if (!autoaprobado && a.http !== 200) return { estado: a.codigo === 'MOTIVO_REQUERIDO' ||
      (a.http === 403 && a.codigo !== 'APROBADOR_DEBE_SER_OTRO') ? 'NO_CONCLUYENTE' : 'RECHAZADO',
    severidad: 'ALTA', motivo: 'Aprobacion correctiva HTTP ' + a.http + ', codigo ' + a.codigo,
    observados: { creacion_http: c.http, doble_control: dobleControl, doble_control_http: doble.http, aprobacion_http: a.http } };
  const final = await instantanea(r, api, opts, aid, pid);
  if (!final.completa) return { estado: 'NO_CONCLUYENTE', motivo: 'Lectura posterior a aprobacion incompleta.',
    observados: { doble_control: dobleControl, doble_control_http: doble.http, aprobacion_http: a.http } };
  const decision = evaluar010({ original, solicitud: c.cuerpo, previo, aprobacion: a.cuerpo,
    historial: final.variaciones, lineas: final.lineas, lineaOriginal });
  return { ...decision, observados: { creacion_http: c.http, doble_control: dobleControl, doble_control_http: doble.http,
    doble_control_codigo: doble.codigo, aprobacion_http: a.http, solicitud_id: sid,
    original_id: oid, correctivo_id: id(a.cuerpo?.id_variacion_correctiva), efectivo_antes: previo.efectivo,
    original_visible: final.variaciones.some(x => id(x.id_variacion_valor_razonable) === oid),
    correctivo_visible: final.variaciones.some(x => id(x.id_variacion_valor_razonable) === id(a.cuerpo?.id_variacion_correctiva)),
    linea_inversa: Array.isArray(a.cuerpo?.lineas_inversas) && a.cuerpo.lineas_inversas.length > 0 } };
}
async function newmanLecturas(r, c, env, token, pid, pid010) {
  if (r._solicitudesRun + LECTURAS_NEWMAN.length + 7 > PRESUPUESTO.solicitudes_totales) return null;
  const vars = { base_url: String(env.SIGAB_API_TEST_BASE).replace(/\/+$/, ''), run_id: c.runId,
    sandbox_secret: env.QA_SANDBOX_SECRET, token, periodo_id: String(pid), periodo_010_id: String(pid010) };
  const environment = { values: Object.entries(vars).map(([key, value]) => ({ key, value, enabled: true })) };
  const out = spawnSync(process.execPath, [path.join(DIR, 'pruebas/newman_hijo.mjs')], {
    input: JSON.stringify({ coleccion: JSON.parse(fs.readFileSync(COLECCION, 'utf8')), environment, timeout: 30000 }),
    timeout: 160000, encoding: 'utf8', windowsHide: true, maxBuffer: 20 * 1024 * 1024 });
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
  const agregado = estados.includes('RECHAZADO') ? 'RECHAZADO' :
    estados.every(x => x === 'APROBADO') ? 'APROBADO' : 'NO_CONCLUYENTE';
  const detalles = CASOS.map(k => {
    const x = r.casos[k] ?? {};
    const prep = r.preparacion?.[k] ?? {};
    const esperado = k === CASOS[0] ?
      'Nueve PUT/PATCH/DELETE bloqueados con 409 y orientacion al correctivo; variacion y linea identicas campo a campo.' :
      'Solicitud pendiente con monto opuesto; sin efecto previo; aprobacion del Contador; original y correctivo visibles, linea inversa positiva.';
    return '### ' + k + '\n\n**Esperado:** ' + esperado + '\n\n**Preparacion:** ' +
      JSON.stringify(prep) + '\n\n**Observado:** ' + texto(x.motivo) + '; ' +
      JSON.stringify(x.observados ?? {}) + '\n\n**Decision:** ' + (x.estado ?? 'NO_CONCLUYENTE') + '.';
  }).join('\n\n');
  const incidentes = r.incidencias.map(x => '### ' + x.id + '\n\nCasos: ' + x.casos.join(', ') +
    '. Origen: ' + x.origen + '. Esperado: ' + x.esperado + ' Observado: ' + x.obtenido + ' Severidad: ' + x.severidad +
    ' (' + x.justificacion_severidad + '). Certeza: ' + x.certeza + '. Atencion inicial: ' +
    x.equipo_inicial + '. ' + x.fundamento_equipo + ' Causa raiz: ' + x.causa_raiz + '.').join('\n\n');
  return '# TC-M06-G36 - ' + agregado + '\n\n## Identificacion\n\nGrupo G36; TC-M06-009 y TC-M06-010; ' +
    'RF-86 restriccion 5, CA-12 y CA-13; version ' + c.version + '; RUN ' + c.runId +
    '; ambiente ' + (c.ensayo ? 'SIMULADOR_LOCAL' : 'TEST') + '; autorizacion ' + c.referencia +
    '; commit TEST informado 453277e4, no comprobado en vivo; Node ' + r.herramientas.node +
    '; Newman ' + (r.herramientas.newman?.version ?? 'no ejecutado') + '; Cypress 0 (solo API).\n\n' +
    '## Veredictos\n\n' + CASOS.map(k => '- ' + k + ': ' + (r.casos[k]?.estado ?? 'NO_CONCLUYENTE')).join('\n') +
    '\n\nOficial: ' + r.oficial + '. Condiciones: ' + JSON.stringify(r.condiciones_oficialidad) +
    '. Solicitudes API del ejecutor y Newman: ' + r._solicitudesRun + '/' + PRESUPUESTO.solicitudes_totales +
    '. Tres logins se ejecutan antes del RUN.\n\n## Preflight vivo\n\n' +
    (r.preflight_vivo?.requisitos ?? []).map(x => '- ' + x.requisito + ': esperado ' + JSON.stringify(x.esperado) +
      ', observado ' + JSON.stringify(x.observado) + ', cumple ' + x.cumple + ', bloqueante ' + x.bloqueante).join('\n') +
    '\n\n## Detalle por caso\n\n' + detalles + '\n\n## Comprobaciones API\n\n' +
    r.comprobaciones.map(x => '- ' + x.id + ' (' + x.caso + '): ' + x.estado + '; ' + texto(x.motivo) +
      '; evidencia ' + x.evidencia).join('\n') + '\n\n## Evidencias reales\n\n' +
    r.evidencias.map(x => '- ' + x).join('\n') + '\n\n## Observaciones: seguimiento de incidencias V1\n\n' +
    (r.seguimiento_incidencias_v1 ?? []).map(x => '- ' + x.id + ': ' + x.estado_v2 + '. ' + x.motivo).join('\n') +
    '\n\nLa cuenta aprobadora 169 fue preparada por SQL con autorizacion del responsable QA; el Contador 2 se usa cuando el producto impide la autoaprobacion. ' +
    'Las incidencias distintas se registran como nuevas en V2.\n\n## Incidencias de producto\n\n' +
    (incidentes || 'Ninguna comprobada.') + '\n\n## Problemas tecnicos\n\n' +
    (r.problemas_tecnicos.join('\n') || 'Ninguno observado.') + '\n\n## Cierre y rollback\n\nDELETE HTTP ' +
    (r.cierre.run.cierre_http ?? 'sin respuesta') + '; rollback ' +
    (r.cierre.rollback.verificado ? 'verificado por lecturas publicas poscierre' : 'no verificado') +
    '. ' + r.cierre.rollback.motivo + '\n\n## Conclusion y acciones\n\n' +
    (r.oficial ? 'Conservar evidencias y derivar incidencias comprobadas a Desarrollo.' :
      'RUN no oficial: revisar las condiciones de oficialidad incumplidas antes de decidir una reevaluacion.') + '\n';
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
    env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD, env.QA_CONTADOR2_EMAIL, env.QA_CONTADOR2_PASSWORD];
  if (!sinArtefactos) {
    if (!fs.existsSync(c.directorio)) throw Error('El lanzador debe crear el RUN antes de evaluar');
    fs.writeFileSync(path.join(c.directorio, 'preflight.json'), JSON.stringify(pf, null, 2));
    r.evidencias.push('preflight.json');
  }
  let token = null, admin = null, iniciado = false, base = null, aid = null, pid = null;
  const eventosRun = []; const bases = []; let variacionId = null, lineaId = null, mutado = false;
  let contrato = null, operaciones = null;
  const terminar = (caso, estado, motivo, extra = {}) => registrar(r, caso, { estado, motivo, ...extra },
    sinArtefactos ? 'ensayo-local' : 'resultado.json');
  try {
    if (!pf.ok) {
      for (const caso of CASOS) terminar(caso, 'NO_CONCLUYENTE', 'Preflight local: ' + pf.barreras.join(', '));
      return r;
    }
    const login = async (email, password) => req(r, api, 'POST', '/sesiones/', { fuera: true,
      cuerpo: { correo_electronico: email, contrasena: password }, timeout: 120000 });
    const l1 = await login(env.QA_CONTADOR_EMAIL, env.QA_CONTADOR_PASSWORD);
    const l2 = await login(env.QA_CONTADOR2_EMAIL, env.QA_CONTADOR2_PASSWORD);
    const l3 = await login(env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD);
    token = l1.cuerpo?.token ?? l1.cuerpo?.access_token;
    const aprobador = l2.cuerpo?.token ?? l2.cuerpo?.access_token;
    admin = l3.cuerpo?.token ?? l3.cuerpo?.access_token;
    if (aprobador) r._secretos.push(aprobador);
    if ([l1,l2,l3].some(x => x.http !== 200) || !token || !aprobador || !admin || token === aprobador) {
      for (const caso of CASOS) terminar(caso, 'NO_CONCLUYENTE', 'No se obtuvieron tres sesiones QA.');
      return r;
    }
    const opts = { m06: { token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId },
      m06Aprobador: { token: aprobador, secreto: env.QA_SANDBOX_SECRET, runId: c.runId },
      m02: { token: admin, secreto: env.QA_SANDBOX_SECRET, runId: c.runId } };
    iniciado = true;
    const a = await req(r, api, 'GET', '/finanzas/activos', opts.m06);
    const p = await req(r, api, 'GET', '/finanzas/periodos', opts.m06);
    const cfg = await req(r, api, 'GET', '/finanzas/configuracion', opts.m06);
    const requisito = (nombre, esperado, observado, cumple) => r.preflight_vivo.requisitos.push({
      requisito: nombre, esperado, observado, cumple: Boolean(cumple), bloqueante: true });
    r.preflight_vivo = { requisitos: [] };
    if (![a,p,cfg].every(ok) || !Array.isArray(a.cuerpo) || !Array.isArray(p.cuerpo) ||
        !Array.isArray(cfg.cuerpo?.matriz)) {
      requisito('catalogos', 'Activos, periodos y matriz legibles', [a.http,p.http,cfg.http], false);
    } else {
      const candidatos = [];
      const precios = new Map();
      for (const x of a.cuerpo) {
        const fila = { activo_id: id(x.id_activo_biologico), estado: 'DESCARTADO', motivo: '' };
        r.candidatos.push(fila);
        if (!/bovin/i.test(x.especie ?? '') || x.tipo !== 'INDIVIDUAL' || x.estado !== 'ACTIVO' ||
            x.valorado_por_costo || !(monto(x.valor_razonable_neto) > 0)) { fila.motivo = 'Activo no elegible'; continue; }
        if (candidatos.length >= 2) break;
        const n = id(x.id_activo_biologico), especie = id(x.id_especie);
        if (!n || !especie) continue;
        if (!precios.has(especie)) {
          const pr = await req(r, api, 'GET', '/finanzas/precios?id_especie=' + especie, opts.m06);
          precios.set(especie, ok(pr) && Array.isArray(pr.cuerpo) ? precioVigente(pr.cuerpo, especie) : null);
        }
        const precio = precios.get(especie);
        const d = await req(r, api, 'GET', '/finanzas/activos/' + n, opts.m06);
        const f = await req(r, api, 'GET', '/activos-biologicos/' + n + '/ficha-integral', opts.m02);
        const acceso = await req(r, api, 'GET', '/finanzas/activos/' + n, opts.m06Aprobador);
        const periodo = periodoDestino(p.cuerpo, d.cuerpo?.activo?.numero_id_tributaria);
        const calc = calculoVigente(d.cuerpo);
        const matriz = cfg.cuerpo.matriz.some(y => y.tipo_hecho === 'VARIACION_VR_TB' && y.sentido === 'GANANCIA' &&
          (y.id_especie == null || id(y.id_especie) === especie) && y.cuenta_debito && y.cuenta_credito);
        if (!precio || !ok(d) || !ok(f) || !ok(acceso) || !periodo || !calc || !matriz ||
            !d.cuerpo?.reconocimientos?.some(y => y.estado === 'CONFIRMADO') ||
            f.cuerpo?.estado_actual !== 'ACTIVO' || f.cuerpo?.unidad_peso !== 'kg' ||
            !(monto(f.cuerpo?.peso_actual) > 0) || requiereRebase({ calc, precio, peso: monto(f.cuerpo.peso_actual) })) {
          fila.motivo = 'Precio, periodo, matriz, acceso, reconocimiento o calculo no acreditado'; continue;
        }
        fila.estado = 'SELECCIONADO'; fila.motivo = 'Precondiciones acreditadas';
        candidatos.push({ n, especie, precio, periodo, peso: monto(f.cuerpo.peso_actual), matriz });
      }
      const actual = p.cuerpo.filter(x => x.fecha_inicio <= hoy() && x.fecha_fin >= hoy());
      requisito('periodo_hoy_abierto', 'Periodo actual ABIERTO', actual.map(x => x.estado),
        candidatos.length >= 2 && candidatos.every(x => x.periodo.estado === 'ABIERTO'));
      requisito('dos_bovinos_elegibles', 'Al menos dos bovinos', candidatos.map(x => x.n), candidatos.length >= 2);
      requisito('precio_vigente', 'PESO_KG vigente', candidatos.map(x => id(x.precio.id_precio_mercado)), candidatos.length >= 2);
      requisito('matriz_tb_pm', 'TB y PM presentes', cfg.cuerpo.matriz.map(x => x.tipo_hecho),
        ['VARIACION_VR_TB','VARIACION_VR_PM'].every(tipo => cfg.cuerpo.matriz.some(y => y.tipo_hecho === tipo)));
      requisito('contador2_acceso', 'GET activo 200', candidatos.map(x => x.n), candidatos.length >= 2);
      r._candidatos = candidatos;
    }
    if (r.preflight_vivo.requisitos.some(x => x.bloqueante && !x.cumple)) {
      for (const caso of CASOS) terminar(caso, 'NO_CONCLUYENTE',
        'Preflight vivo: ' + r.preflight_vivo.requisitos.filter(x => !x.cumple).map(x => x.requisito).join(', '));
      return r;
    }
    const preparados = [];
    for (let i = 0; i < CASOS.length; i++) {
      const caso = CASOS[i], candidato = r._candidatos[i];
      aid = candidato.n; pid = id(candidato.periodo.id_periodo_contable);
      const antes = await instantanea(r, api, opts, aid, pid);
      bases.push({ aid, pid, antes });
      if (!antes.completa) { terminar(caso, 'NO_CONCLUYENTE', 'Linea base incompleta.'); continue; }
      const pesaje = await req(r, api, 'POST', '/activos-biologicos/' + aid + '/eventos/crecimiento', {
        ...opts.m02, cuerpo: { tipo_medicion: 'PESO', valor_medicion: Math.round(candidato.peso * 1.02 * 100)/100,
          unidad_medida: 'kg', descripcion: 'Pesaje +2 % QA G36 ' + c.runId } });
      mutado = true;
      let eid = id(pesaje.cuerpo?.evento?.id_eventos);
      if (!eid) eid = await conciliarEvento(r, api, opts.m02, aid, new Set(antes.eventos.map(x => String(x.id_eventos))));
      if (eid) eventosRun.push(eid);
      if (!eid) { terminar(caso, 'NO_CONCLUYENTE', 'Pesaje sin evento conciliable.'); continue; }
      const proc = await req(r, api, 'POST', '/finanzas/eventos/procesar', opts.m06);
      const despues = await instantanea(r, api, opts, aid, pid);
      const aislada = aislarTransformacion(antes, despues, aid, eid);
      if (proc.http !== 200 || aislada.estado !== 'AISLADA') {
        terminar(caso, 'NO_CONCLUYENTE', 'Procesamiento o variacion aislada incompletos. ' + aislada.motivo); continue;
      }
      const variacion = aislada.variacion, vid = id(variacion.id_variacion_valor_razonable);
      const linea = despues.lineas.find(x => x.tabla_origen === 'variaciones_valor_razonable' && id(x.id_origen) === vid);
      if (!linea) { terminar(caso, 'NO_CONCLUYENTE', 'Linea de variacion ausente.'); continue; }
      preparados.push({ caso, aid, pid, variacion, linea, eid, antes });
      r.preparacion = r.preparacion ?? {};
      r.preparacion[caso] = { activo_id: aid, periodo_id: pid, precio_id: id(candidato.precio.id_precio_mercado),
        evento_id: eid, variacion_id: vid, linea_id: id(linea.id_linea_asiento_nic41) };
    }
    const c009 = preparados.find(x => x.caso === CASOS[0]);
    if (c009) {
      const vid = id(c009.variacion.id_variacion_valor_razonable), lid = id(c009.linea.id_linea_asiento_nic41);
      const rutas = ['/finanzas/variaciones/' + vid, '/finanzas/periodos/' + c009.pid + '/variaciones/' + vid,
        '/finanzas/lineas/' + lid];
      const intentos = [];
      intentosDirectos: for (const ruta of rutas) for (const metodo of ['PUT','PATCH','DELETE']) {
        const x = await req(r, api, metodo, ruta, { ...opts.m06, permitir403: true,
          cuerpo: metodo === 'DELETE' ? undefined : ruta.includes('/lineas/') ? { valor: monto(c009.linea.valor) + 1 } :
            { monto_variacion: monto(c009.variacion.monto_variacion) + 1 } });
        intentos.push({ ruta, metodo, http: x.http, codigo: x.codigo, mensaje: x.mensaje });
        if (x.http >= 200 && x.http < 300) break intentosDirectos;
      }
      const despues = await instantanea(r, api, opts, c009.aid, c009.pid);
      const va = despues.variaciones?.find(x => id(x.id_variacion_valor_razonable) === vid);
      const ln = despues.lineas?.find(x => id(x.id_linea_asiento_nic41) === lid);
      const decision = evaluar009(intentos, { variacion: c009.variacion, linea: c009.linea }, { variacion: va, linea: ln });
      terminar(CASOS[0], decision.estado, decision.motivo, { observados: decision.observados,
        severidad: decision.severidad,
        comparacion_campo_a_campo: { variacion: { campos: Object.keys(c009.variacion).sort(),
          sha256_antes: huella(c009.variacion), sha256_despues: huella(va) },
          linea: { campos: Object.keys(c009.linea).sort(), sha256_antes: huella(c009.linea),
            sha256_despues: huella(ln) } } });
    }
    const c010 = preparados.find(x => x.caso === CASOS[1]);
    if (c010) {
      const d = await intentarCorrectivo(r, api, opts, c010.variacion, c010.linea, c010.pid, c010.aid);
      terminar(CASOS[1], d.estado, d.motivo, { observados: d.observados ?? null, severidad: d.severidad });
    }
    if (!sinArtefactos && !r._corte) await newmanLecturas(r, c, env, token, c009?.pid ?? pid, c010?.pid ?? pid);
    else if (sinArtefactos) r.herramientas.newman = { iteraciones: 1, fallos: 0, codigo: 0, version: 'ensayo-local', problema: false };
    if (!sinArtefactos && (r.herramientas.newman?.problema || r.herramientas.newman?.iteraciones !== 1))
      r.problemas_tecnicos.push('Newman incompleto o con asercion fallida.');
  } catch (e) {
    r.problemas_tecnicos.push(texto(e.message));
    for (const caso of CASOS) if (!r.casos[caso]) terminar(caso, 'NO_CONCLUYENTE', 'Error de automatizaciÃ³n sin evidencia de producto.');
  } finally {
    if (iniciado) {
      const del = await req(r, api, 'DELETE', '/test-control/runs/' + encodeURIComponent(c.runId), {
        token, secreto: env.QA_SANDBOX_SECRET, timeout: 30000, cierre: true });
      r.cierre.run.cierre_http = del.http;
      if (del.http === 200 && !mutado) r.cierre.rollback = { verificado: true, motivo: 'Sin escrituras de producto antes de DELETE.' };
      else if (del.http === 200 && bases.length && bases.every(x => x.antes?.completa)) {
        r._corte = false; r._seguidos5xx = 0;
        const cierres = [];
        for (const x of bases) {
          const pos = await instantanea(r, api, { m06: { token }, m02: { token: admin } },
            x.aid, x.pid, { poscierre: true });
          const ids = r.preparacion && Object.values(r.preparacion).find(y => y.activo_id === x.aid);
          cierres.push(rollback(x.antes, pos, ids?.evento_id ? [ids.evento_id] : [],
            ids?.variacion_id, ids?.linea_id));
        }
        r.cierre.rollback = { verificado: cierres.every(x => x.verificado), casos: cierres,
          motivo: cierres.every(x => x.verificado) ? 'Ambos activos restaurados tras DELETE.' : 'Lecturas poscierre incompletas o residuos.' };
      } else r.cierre.rollback = { verificado: false, motivo: 'DELETE o lineas base insuficientes.' };
      if (mutado && !r.cierre.rollback.verificado) r.problemas_tecnicos.push('CRÃTICA: rollback de eventos y registros del RUN no verificado.');
    }
    for (const caso of CASOS) if (!r.casos[caso]) terminar(caso, 'NO_CONCLUYENTE', 'Caso sin evidencia completa.');
    if (!sinArtefactos && fs.existsSync(c.directorio))
      fs.writeFileSync(path.join(c.directorio, 'preflight.json'),
        sanear(JSON.stringify({ ...pf, vivo: r.preflight_vivo }, null, 2), [token, admin, ...r._secretos]));
    r.incidencias = unaIncidencia(r.casos, { preparacion: r.preparacion,
      newman: Boolean(r.herramientas.newman?.iteraciones) });
    r.seguimiento_incidencias_v1 = [{ id: 'INC-M06-G36-01',
      estado_v2: CASOS.every(x => r.casos[x].estado === 'APROBADO') ? 'CORREGIDA' :
        (r.casos[CASOS[0]].estado === 'RECHAZADO' &&
          (r.casos[CASOS[0]].severidad === 'MEDIA' || /orientaci|bloqueo/i.test(r.casos[CASOS[0]].motivo))) ||
        (r.casos[CASOS[1]].estado === 'RECHAZADO' &&
          /solicitud|aprobaci|correctiv/i.test(r.casos[CASOS[1]].motivo)) ? 'REPRODUCIDA' : 'NO_CONCLUYENTE',
      motivo: CASOS.map(x => x + ': ' + r.casos[x].estado).join('; ') }];
    r.condiciones_oficialidad = {
      rollback: r.cierre.rollback.verificado,
      casos_decididos: CASOS.every(x => ['APROBADO', 'RECHAZADO'].includes(r.casos[x].estado)),
      newman: r.herramientas.newman?.iteraciones === 1 && !r.herramientas.newman.problema,
      presupuesto: r._solicitudesRun <= PRESUPUESTO.solicitudes_totales };
    delete r._candidatos;
    r.oficial = Object.values(r.condiciones_oficialidad).every(Boolean);
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


