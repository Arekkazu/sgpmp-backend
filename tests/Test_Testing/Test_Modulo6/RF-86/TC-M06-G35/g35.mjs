#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { CASO, IDS, CAPACIDADES, PRESUPUESTO, id, hoy, nuevos, periodoDestino,
  calculoVigente, evaluarPaso, resultadoFinal, rollback, oficialidad } from './lib/g35_core.mjs';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const require = createRequire(import.meta.url);
const COLECCION = path.join(DIR, 'G35.postman_collection.json');
const LECTURAS_NEWMAN = [
  { ruta: '{{base_url}}/finanzas/lineas?id_periodo_contable={{periodo_id}}', token: 'token', permiso: 'valoracion_activos:Leer' },
  { ruta: '{{base_url}}/activos-biologicos/{{activo_id}}/ficha-integral', token: 'token_m02', permiso: 'activos_biologicos:Leer' },
  { ruta: '{{base_url}}/finanzas/periodos/{{periodo_id}}/variaciones', token: 'token', permiso: 'valoracion_activos:Leer' },
];
export function validarColeccionPermisos(c) {
  return c.item?.length === LECTURAS_NEWMAN.length && c.item.every((x, i) => {
    const esperado = LECTURAS_NEWMAN[i];
    const autorizaciones = x.request?.header?.filter(h => h.key.toLowerCase() === 'authorization') ?? [];
    return x.name === IDS[i] && x.request?.method === 'GET' && x.request?.url === esperado.ruta &&
      autorizaciones.length === 1 && autorizaciones[0].value === `Bearer {{${esperado.token}}}`;
  });
}
export function entornoNewman(env, c, token, tokenM02, aid, pid, eventoId, valorBaja) {
  const vars = { base_url: env.SIGAB_API_TEST_BASE, run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET,
    token, token_m02: tokenM02, activo_id: String(aid), periodo_id: String(pid),
    evento_id: String(eventoId), valor_baja: String(valorBaja) };
  return { values: Object.entries(vars).map(([key, value]) => ({ key, value, enabled: true })) };
}
export function evaluarEvidenciaNewman(solicitudes, codigo) {
  const fallos = solicitudes.flatMap(x => x.aserciones?.filter(a => a.error) ?? []).length;
  const accesos_denegados = solicitudes.filter(x => x.http === 401 || x.http === 403).length;
  const iteraciones = solicitudes.length === IDS.length ? 1 : 0;
  const problema = !iteraciones || fallos > 0 || accesos_denegados > 0 || codigo !== 0;
  return { iteraciones, solicitudes: solicitudes.length, fallos, accesos_denegados, codigo,
    problema, estado: problema ? 'NO_CONCLUYENTE' : 'CONCLUYENTE',
    problema_tecnico: !problema ? null : accesos_denegados ?
      'Newman recibió 401/403 en una lectura; revisar actor y permisos de la ruta.' :
      'Newman incompleto o contradictorio.' };
}
const ARCHIVOS = ['g35.mjs', 'lib/g35_core.mjs', 'G35.postman_collection.json', 'README.md',
  'pruebas/g35_env.test.mjs', 'pruebas/g35_ensayo.mjs', 'pruebas/newman_hijo.mjs', 'pruebas/registro_qa.mjs'];
const nombreInforme = v => v === 1 ? 'TC-M06-G35_resultado.md' : `TC-M06-G35_reevaluacion_V${v}.md`;
const texto = x => String(x ?? '').replace(/[\r\n|]/g, ' ').slice(0, 300);
const html = x => String(x).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
export function sanear(x, secretos = []) {
  let s = String(x);
  for (const v of secretos.filter(x => typeof x === 'string' && x.length > 3)) s = s.split(v).join('[REDACTADO]');
  return s.replace(/eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}/g, '[JWT_REDACTADO]')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[CORREO_REDACTADO]');
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
const newmanVersion = () => { try { return require(path.join(newmanDir(), 'package.json')).version; } catch { return null; } };
export function comprobar() {
  const faltantes = ARCHIVOS.filter(x => !fs.existsSync(path.join(DIR, x)));
  let coleccion = false;
  try { const c = JSON.parse(fs.readFileSync(COLECCION, 'utf8')); coleccion = validarColeccionPermisos(c); } catch { /* inválida */ }
  const superior = fs.existsSync(path.join(DIR, 'Resultados')) && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const ok = !faltantes.length && coleccion && !superior && PRESUPUESTO.timeout_post_ms === 120000;
  console.log(JSON.stringify({ grupo: 'G35', ok, faltantes, coleccion, markdown_superior: superior,
    newman_local: !!newmanVersion(), presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}
export function contexto(args) {
  const v = k => args.includes(k) ? args[args.indexOf(k) + 1] : undefined;
  const operacion = v('--operacion'), version = Number(v('--version')), intento = Number(v('--intento')),
    runId = v('--run-id'), referencia = v('--autorizacion'), archivo = v('--contexto');
  if (!CAPACIDADES.operaciones.includes(operacion) || !Number.isInteger(version) || version < 1 || version > 99 ||
      !Number.isInteger(intento) || intento < 1 || !referencia || !archivo ||
      !new RegExp(`^RUN-G35-V${version}-\\d{8}-\\d{6}$`).test(runId ?? '')) throw Error('Contexto incompleto');
  const destino = path.join(DIR, ...(version === 1 ? ['Resultados', runId] : [`EvaluacionV${version}`, 'Resultados', runId]));
  const ruta = path.resolve(archivo);
  if (path.dirname(ruta) !== destino || path.basename(ruta) !== 'contexto_operacion.json') throw Error('Contexto fuera del RUN');
  const c = JSON.parse(fs.readFileSync(ruta, 'utf8'));
  if (c.grupo !== 'G35' || c.run_id !== runId || c.version !== version || c.intento !== intento ||
      c.operacion !== operacion.toUpperCase() || c.referencia !== referencia ||
      JSON.stringify(c.casos) !== JSON.stringify([CASO]) ||
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
  return { grupo: 'G35', run_id: c.runId, ok: !barreras.length, barreras, presupuesto: PRESUPUESTO,
    herramientas: { node: process.version, newman: n }, efectos_externos: [
      'RF-52 puede escribir logs/audit_buffer_M02.jsonl o logs de aplicación; DELETE no revierte archivos.',
      'Las notificaciones y auditorías fuera de la transacción del RUN requieren comprobación independiente.',
      'La baja tipo perdida no solicita venta ni facturación; la línea BAJA_ACTIVO queda dentro del RUN.' ] };
}
function errorPublico(b) {
  const o = b?.detail && typeof b.detail === 'object' ? b.detail : b;
  return { codigo: texto(o?.error_code ?? o?.code ?? o?.codigo ?? ''),
    mensaje: texto(typeof o?.message === 'string' ? o.message : typeof o?.mensaje === 'string' ? o.mensaje :
      typeof o?.detail === 'string' ? o.detail : '') };
}
export async function pedir(r, api, metodo, ruta, { token, secreto, runId, cuerpo, timeout, fetcher = fetch } = {}) {
  if (r._corte && metodo !== 'DELETE') return { http: null, fallo: 'CORTE_POLITICA' };
  if (r.solicitudes.length >= PRESUPUESTO.solicitudes_totales - 1 && metodo !== 'DELETE')
    return { http: null, fallo: 'PRESUPUESTO_AGOTADO' };
  const fila = { metodo, ruta: ruta.split('?')[0], http: null }; r.solicitudes.push(fila);
  const inicio = Date.now();
  try {
    if (inicio > r._limite && metodo !== 'DELETE') throw Error('DURACION_EXCEDIDA');
    const res = await fetcher(api + ruta, { method: metodo, redirect: 'manual',
      headers: { ...(cuerpo ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(runId ? { 'X-Test-Run-Id': runId, 'X-Zona-Horaria': 'America/Bogota' } : {}),
        ...(secreto ? { 'X-Sandbox-Secret': secreto } : {}) }, body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      signal: AbortSignal.timeout(Math.max(1, Math.min(timeout ?? (metodo === 'POST' ? 120000 : 30000),
        metodo === 'DELETE' ? 30000 : r._limite - inicio))) });
    const b = await res.json().catch(() => null); const err = errorPublico(b);
    fila.http = res.status; fila.duracion_ms = Date.now() - inicio;
    fila.eco = runId ? res.headers.get('x-test-run-id') === runId : null;
    fila.codigo = err.codigo; fila.mensaje_saneado = sanear(err.mensaje, r._secretos);
    r._seguidos5xx = res.status >= 500 ? r._seguidos5xx + 1 : 0;
    if (res.status === 403 || r._seguidos5xx >= 3) r._corte = true;
    return { http: res.status, cuerpo: b, eco: fila.eco, codigo: err.codigo,
      mensaje: fila.mensaje_saneado, fila };
  } catch (e) {
    fila.fallo = e.name === 'TimeoutError' || e.name === 'AbortError' ? 'TIMEOUT' : 'SIN_RESPUESTA';
    fila.duracion_ms = Date.now() - inicio;
    return { http: null, fallo: fila.fallo, fila };
  }
}
const ok = x => x?.http === 200 && x.eco !== false;
async function paginar(r, api, ruta, campo, totalCampo, opts) {
  const items = [], vistos = new Set();
  for (let pagina = 1; pagina <= 4 && !r._corte; pagina++) {
    const x = await pedir(r, api, 'GET', ruta + (ruta.includes('?') ? '&' : '?') + 'pagina=' + pagina, opts);
    if (!ok(x) || !Array.isArray(x.cuerpo?.[campo]) || !Number.isSafeInteger(x.cuerpo?.[totalCampo])) return null;
    for (const v of x.cuerpo[campo]) {
      const k = JSON.stringify(v); if (vistos.has(k)) return null; vistos.add(k); items.push(v);
    }
    if (items.length === x.cuerpo[totalCampo]) return items;
    if (!x.cuerpo[campo].length || items.length > x.cuerpo[totalCampo]) return null;
  }
  return null;
}
async function instantanea(r, api, opts, aid, pid, { inexistente = false } = {}) {
  const ficha = inexistente ? null : await pedir(r, api, 'GET', '/activos-biologicos/' + aid + '/ficha-integral', opts.m02);
  const eventos = inexistente ? null : await pedir(r, api, 'GET', '/activos-biologicos/' + aid + '/eventos', opts.m02);
  const rutas = ['/finanzas/periodos/' + pid + '/variaciones', '/finanzas/lineas?id_periodo_contable=' + pid,
    '/finanzas/periodos/' + pid + '/mediciones', '/finanzas/activos/' + opts.activo];
  const resp = [];
  for (const ruta of rutas) resp.push(await pedir(r, api, 'GET', ruta, opts.m06));
  const auditoria = inexistente ? [] : await paginar(r, api,
    '/finanzas/auditoria?id_activo_biologico=' + aid + '&id_periodo_contable=' + pid + '&formato=TECNICO&tamano=500',
    'eventos', 'total_registros', opts.m06);
  const [v, l, m, d] = resp;
  const completa = (inexistente || (ok(ficha) && ok(eventos) && Array.isArray(eventos.cuerpo?.eventos))) &&
    resp.every(ok) && [v, l, m].every(x => Array.isArray(x.cuerpo)) && Array.isArray(d.cuerpo?.calculos) &&
    Array.isArray(d.cuerpo?.mediciones) && Array.isArray(auditoria);
  return { completa, estado: inexistente ? null : ficha?.cuerpo?.estado_actual,
    eventos: inexistente ? [] : eventos?.cuerpo?.eventos, variaciones: v?.cuerpo?.filter(x => id(x.id_activo_biologico) === aid),
    lineas: l?.cuerpo?.filter(x => id(x.id_activo_biologico) === aid),
    mediciones: m?.cuerpo?.filter(x => id(x.id_activo_biologico) === aid),
    periodo_variaciones: v?.cuerpo, periodo_lineas: l?.cuerpo, periodo_mediciones: m?.cuerpo,
    calculos: d?.cuerpo?.calculos, historial: d?.cuerpo?.mediciones, auditoria };
}
function resumenInstantanea(s) {
  return { completa: s?.completa, estado: s?.estado, eventos: s?.eventos?.map(x => id(x.id_eventos)),
    variaciones: s?.variaciones?.map(x => id(x.id_variacion_valor_razonable)),
    lineas: s?.lineas?.map(x => ({ id: id(x.id_linea_asiento_nic41), tipo: x.tipo_hecho, origen: id(x.id_origen), valor: x.valor })),
    mediciones: s?.mediciones?.map(x => id(x.id_medicion_posterior)),
    calculos: s?.calculos?.map(x => id(x.id_calculo_valor_razonable)),
    auditoria: s?.auditoria?.map(x => id(x.id_evento)) };
}
function incidencia(subcaso, motivo, evidencias) {
  const esperado = {
    baja: 'Estado BAJA, evento RF-45 y línea BAJA_ACTIVO ligada; cero variaciones posteriores.',
    baja_rechazo: 'Rechazo 4xx específico por BAJA; cero evento, variación, línea y medición.',
    inexistente: 'Rechazo 404 o 4xx equivalente por activo inexistente; cero datos nuevos.' }[subcaso];
  return { id: 'INC-M06-G35-' + ({ baja: '01', baja_rechazo: '02', inexistente: '03' }[subcaso]),
    caso: CASO, subcaso, requisito: 'RF-86 FA-2 y precondiciones 1 y 7; RF-45',
    pasos: 'Seleccionar activo elegible; ejecutar baja RF-45, procesar M06 e intentar crecimientos sobre BAJA e id inexistente.',
    esperado, obtenido: motivo, apoyo_codigo: 'procesar_eventos_m02_use_case.py:129-160; registrar_evento_baja_use_case.py:127-251',
    impacto: 'Puede alterarse la contabilidad o aceptarse un evento inválido.', severidad: 'ALTA',
    justificacion_severidad: 'Una regla contable relevante queda incumplida en el escenario comprobado sin alternativa automática observada.',
    certeza: 'CONFIRMADA', equipo_inicial: 'Desarrollo', fundamento_equipo: 'La primera discrepancia se observó en API pública.',
    causa_raiz: 'NO DETERMINADA', evidencias };
}
async function newmanLecturas(r, c, env, token, tokenM02, aid, pid, eventoId, valorBaja) {
  const environment = entornoNewman(env, c, token, tokenM02, aid, pid, eventoId, valorBaja);
  const out = spawnSync(process.execPath, [path.join(DIR, 'pruebas/newman_hijo.mjs')], {
    input: JSON.stringify({ coleccion: JSON.parse(fs.readFileSync(COLECCION, 'utf8')), environment, timeout: 30000 }),
    timeout: 160000, encoding: 'utf8', windowsHide: true, maxBuffer: 1024 * 1024 });
  let hijo; try { hijo = JSON.parse(out.stdout); } catch { hijo = { error: out.error?.code ?? 'SIN_RESPUESTA_HIJO', solicitudes: [] }; }
  const sintesis = { version: newmanVersion(), codigo: out.status, error: hijo.error ?? null,
    estadisticas: hijo.estadisticas ?? null, solicitudes: hijo.solicitudes ?? [] };
  const dir = path.join(c.directorio, 'newman'); fs.mkdirSync(dir, { recursive: true });
  const limpio = sanear(JSON.stringify(sintesis, null, 2), [token, tokenM02, ...r._secretos]);
  fs.writeFileSync(path.join(dir, 'newman-G35.json'), limpio);
  fs.writeFileSync(path.join(dir, 'newman-G35.html'), '<!doctype html><meta charset="utf-8"><title>G35 Newman</title><h1>G35 Newman</h1><pre>' + html(limpio) + '</pre>');
  for (const s of sintesis.solicitudes) r.solicitudes.push({ metodo: 'GET', ruta: s.nombre, http: s.http, herramienta: 'Newman' });
  r.herramientas.newman = { version: sintesis.version,
    ...evaluarEvidenciaNewman(sintesis.solicitudes, out.status) };
}
export function informe(c, r) {
  const caso = r.casos[CASO];
  const esperados = { baja: 'Activo BAJA; evento RF-45 y línea BAJA_ACTIVO ligada; sin variación posterior.',
    baja_rechazo: '4xx específico por BAJA; sin evento, variación, línea ni medición.',
    inexistente: '404 o 4xx equivalente por inexistencia; sin datos nuevos.' };
  const nombres = { baja: 'Baja RF-45 y efecto contable', baja_rechazo: 'Crecimiento sobre activo en BAJA',
    inexistente: 'Crecimiento sobre activo inexistente' };
  const lista = x => Array.isArray(x) ? (x.length ? x.join(', ') : 'ninguno') : 'sin lectura concluyente';
  const dato = x => x ?? 'no acreditado';
  const lineasBase = caso.snapshots?.base?.lineas;
  const lineasBaja = caso.snapshots?.baja?.lineas;
  const lineaBaja = Array.isArray(lineasBase) && Array.isArray(lineasBaja) && caso.evento_baja_id
    ? lineasBaja.filter(x => !lineasBase.some(y => y.id === x.id) && x.tipo === 'BAJA_ACTIVO' && x.origen === caso.evento_baja_id)
    : null;
  const detalle = ['baja', 'baja_rechazo', 'inexistente'].map(k => {
    const x = caso.subcasos?.[k] ?? { estado: 'NO_CONCLUYENTE', motivo: 'Subcaso sin ejecución concluyente.' };
    const o = x.observados;
    const preparado = k === 'inexistente'
      ? `ID inexistente ${dato(o?.inexistente_id ?? caso.inexistente_id)}${caso.inexistente_id ? ', contrastado por GET previo' : ', sin comprobación previa acreditada'}; activo de control ${dato(o?.activo_id ?? caso.activo_id)} y período ${dato(caso.periodo_id)}.`
      : `Activo ${dato(o?.activo_id ?? caso.activo_id)}, período ${dato(caso.periodo_id)} y evento de baja RF-45 ${dato(o?.evento_baja_id ?? caso.evento_baja_id)}.`;
    const respuesta = o
      ? `HTTP ${dato(o.http)}${o.codigo_error ? `, código ${texto(o.codigo_error)}` : ''}${o.mensaje_saneado ? `, mensaje saneado «${texto(o.mensaje_saneado)}»` : ''}. Estado del activo ${dato(o.estado_antes)} → ${dato(o.estado_despues)}. Eventos nuevos: ${lista(o.eventos_nuevos)}; variaciones: ${lista(o.variaciones_nuevas)}; líneas: ${lista(o.lineas_nuevas)}; mediciones: ${lista(o.mediciones_nuevas)}.${k === 'inexistente' ? ` Datos financieros creados para el ID inexistente: ${Array.isArray(o.datos_creados_para_inexistente) ? o.datos_creados_para_inexistente.length : 'sin lectura concluyente'}.` : ''}`
      : 'No hay respuesta y lecturas suficientes para describir el resultado de este paso.';
    const cumplido = !o ? 'No acreditado.' : k === 'baja'
      ? `Estado BAJA: ${o.estado_despues === 'BAJA' ? 'sí' : 'no'}; evento RF-45 nuevo: ${o.eventos_nuevos?.includes(o.evento_baja_id) ? 'sí' : 'no'}; línea BAJA_ACTIVO vinculada: ${lineaBaja ? lista(lineaBaja.map(x => x.id)) : 'sin lectura concluyente'}; valor en libros esperado: ${dato(caso.valor_baja_esperado)}; valor de línea observado: ${lineaBaja ? lista(lineaBaja.map(x => x.valor)) : 'sin lectura concluyente'}; ausencia de variación posterior: ${o.variaciones_nuevas?.length === 0 ? 'sí' : 'no'}.`
      : `Rechazo 4xx: ${o.http >= 400 && o.http < 500 ? 'sí' : 'no'}; ausencia de evento, variación, línea y medición nuevos: ${[o.eventos_nuevos, o.variaciones_nuevas, o.lineas_nuevas, o.mediciones_nuevas].every(a => Array.isArray(a) && a.length === 0) ? 'sí' : 'no'}. La causa específica se decide con el código y mensaje observados.`;
    const falla = x.estado === 'APROBADO' ? 'Ningún incumplimiento comprobado en este subcaso.' :
      x.estado === 'RECHAZADO' ? texto(x.motivo) : `No se puede decidir el cumplimiento: ${texto(x.motivo)}`;
    return `### ${k} — ${nombres[k]}\n\n- **Preparación:** ${preparado}\n- **Esperado:** ${esperados[k]}\n- **Observado:** ${respuesta}\n- **Qué se cumplió:** ${cumplido}\n- **Qué falló y por qué:** ${falla}\n- **Decisión:** ${x.estado}. ${texto(x.motivo)}`;
  }).join('\n\n');
  const inc = r.incidencias.length ? r.incidencias.map(x => `### ${x.id} — ${nombres[x.subcaso] ?? x.subcaso}\n\n**Requisito:** ${x.requisito}.\n\n**Pasos para reproducir:** ${x.pasos}\n\n**Esperado:** ${x.esperado}\n\n**Obtenido:** ${x.obtenido}\n\n**Apoyo de código leído, sin atribución causal:** ${x.apoyo_codigo}; estas rutas locales no acreditan la versión desplegada ni la causa raíz.\n\n**Impacto y severidad:** ${x.severidad}. ${x.impacto} ${x.justificacion_severidad} Certeza ${x.certeza} de la discrepancia observada; causa raíz ${x.causa_raiz}.\n\n**Primera atención:** ${x.equipo_inicial}, porque ${x.fundamento_equipo} Esta derivación no atribuye causa técnica.\n\n**Evidencias:** ${x.evidencias.join(', ')}.`).join('\n\n') : 'Ninguna discrepancia de producto comprobada.';
  const rb = r.cierre.rollback;
  const cierre = rb.verificado && rb.estado_final
    ? `Activo ${dato(rb.estado_original)} restaurado a ${dato(rb.estado_final)}; evento RF-45, línea BAJA_ACTIVO y datos nuevos del RUN ausentes en las lecturas públicas poscierre.`
    : rb.verificado ? `No hubo escrituras de producto antes del DELETE; ${rb.motivo} El estado del activo y la ausencia de evento y línea poscierre no se comprobaron porque no se ejecutó la baja.`
      : `Estado del activo tras cierre: ${dato(rb.estado_final)}; restauración a ACTIVO, ausencia del evento RF-45 y de la línea BAJA_ACTIVO sin verificar. ${rb.motivo}`;
  const accion = !r.oficial
    ? 'El RUN no es oficial; QA debe resolver el cierre o la evidencia técnica pendiente antes de emitir un veredicto oficial.'
    : r.incidencias.length
    ? `Desarrollo debe revisar ${r.incidencias.map(x => x.id).join(', ')} y QA debe repetir las comprobaciones afectadas con autorización propia.`
    : caso.estado === 'APROBADO' ? 'Las tres reglas comprobadas cumplen; conservar la evidencia del RUN y cerrar el caso.'
      : 'QA debe resolver los impedimentos indicados y repetir solo las comprobaciones no concluyentes con autorización propia.';
  return `# TC-M06-G35 — ${caso.estado}\n\n## Identificación\n\nGrupo G35; caso ${CASO}; RF-86 FA-2 y precondiciones 1 y 7, RF-45; versión ${c.version}, intento ${c.intento}; RUN ${c.runId}; ambiente TEST; autorización ${c.referencia}; commit TEST no verificado; Node ${r.herramientas.node ?? process.version}; Newman ${r.herramientas.newman?.version ?? 'no ejecutado'}; solo API.\n\n## Decisión del caso\n\n| Caso | Estado | Motivo |\n|---|---|---|\n| ${CASO} | ${caso.estado} | ${texto(caso.motivo)} |\n\nOficial: ${r.oficial}.\n\n## Detalle por caso\n\n${detalle}\n\n## Comprobaciones API\n\n${r.comprobaciones.map(x => `- ${x.id} (${x.caso}): ${x.estado}; ${texto(x.motivo)}; evidencia ${x.evidencia}.`).join('\n') || 'Ninguna comprobación ejecutada.'}\n\n## Evidencias reales\n\n${r.evidencias.map(x => '- ' + x).join('\n') || 'Ningún artefacto generado.'}\n\n## Incidencias de producto\n\n${inc}\n\n## Problemas técnicos\n\n${r.problemas_tecnicos.length ? r.problemas_tecnicos.map(x => '- ' + texto(x)).join('\n') : 'Ninguno observado.'}\n\nLas lecturas de código local no demuestran causa raíz de producto.\n\n## Cierre y rollback\n\nDELETE HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}; rollback ${rb.verificado ? 'verificado' : 'no verificado'}. ${cierre} RF-52 puede dejar archivo de bitácora o logs fuera de la base; este efecto no queda cubierto por el DELETE ni por las lecturas poscierre.\n\n## Conclusión y acciones\n\n${caso.estado}: ${texto(caso.motivo)} ${accion} Solicitudes registradas: ${r.solicitudes.length}/${PRESUPUESTO.solicitudes_totales}.\n`;
}
export async function evaluar(c, { env = leerEnv(), fetcher = fetch, sinArtefactos = false } = {}) {
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G35', run_id: c.runId, version: c.version, intento: c.intento,
    casos: {}, comprobaciones: [], solicitudes: [], incidencias: [], problemas_tecnicos: [], evidencias: [],
    herramientas: { node: process.version, newman: null }, cypress: { total_pruebas: 0 },
    cierre: { run: { cierre_http: null }, rollback: { verificado: false, motivo: 'No comprobado.' } },
    oficial: false, consume_version: false, _limite: Date.now() + 900000, _corte: false, _seguidos5xx: 0 };
  const pf = preflight(c, env, sinArtefactos ? 'ensayo-local' : newmanVersion());
  r._secretos = [env.QA_SANDBOX_SECRET, env.QA_CONTADOR_EMAIL, env.QA_CONTADOR_PASSWORD,
    env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD];
  if (!sinArtefactos) {
    if (!fs.existsSync(c.directorio)) throw Error('El lanzador debe crear el RUN antes de evaluar');
    fs.writeFileSync(path.join(c.directorio, 'preflight.json'), JSON.stringify(pf, null, 2)); r.evidencias.push('preflight.json');
  }
  let token = null, admin = null, iniciado = false, mutado = false, aid = null, pid = null, eventoBaja = null, base = null;
  let opts, datos = { subcasos: {}, activo_id: null, periodo_id: null, inexistente_id: null, evento_baja_id: null, snapshots: {}, diagnostico_por_candidato: [] };
  const finalizar = (estado, motivo) => { r.casos[CASO] = { caso: CASO, estado, motivo: texto(motivo), ...datos }; };
  const get = (ruta, o) => pedir(r, api, 'GET', ruta, { ...o, fetcher });
  const post = (ruta, o) => pedir(r, api, 'POST', ruta, { ...o, fetcher });
  try {
    if (!pf.ok) { finalizar('BLOQUEADO', 'Preflight: ' + pf.barreras.join(', ')); return r; }
    const login = await post('/sesiones/', { cuerpo: { correo_electronico: env.QA_CONTADOR_EMAIL,
      contrasena: env.QA_CONTADOR_PASSWORD }, timeout: 120000 });
    token = login.cuerpo?.token ?? login.cuerpo?.access_token;
    const lm = await post('/sesiones/', { cuerpo: { correo_electronico: env.QA_ADMIN_EMAIL,
      contrasena: env.QA_ADMIN_PASSWORD }, timeout: 120000 });
    admin = lm.cuerpo?.token ?? lm.cuerpo?.access_token;
    if (login.http !== 200 || lm.http !== 200 || !token || !admin) {
      finalizar('NO_CONCLUYENTE', 'No se obtuvieron las dos sesiones QA.'); return r;
    }
    opts = { m06: { token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, fetcher },
      m02: { token: admin, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, fetcher }, activo: null };
    const a = await get('/finanzas/activos', opts.m06); iniciado = true;
    const p = await get('/finanzas/periodos', opts.m06);
    if (!ok(a) || !ok(p) || !Array.isArray(a.cuerpo) || !Array.isArray(p.cuerpo)) {
      finalizar('NO_CONCLUYENTE', 'Catálogos de activos o períodos ilegibles.'); return r;
    }
    const config = await get('/finanzas/configuracion', opts.m06);
    if (!ok(config) || !Array.isArray(config.cuerpo?.matriz)) {
      finalizar('NO_CONCLUYENTE', 'No se pudo comprobar la matriz contable RF-109 por API pública.'); return r;
    }
    const diag = { total: a.cuerpo.length, bovinos: 0, individuales: 0, activos: 0,
      reconocidos: 0, periodo: 0, calculo: 0, peso: 0, matriz: 0 };
    let candidatos = a.cuerpo.filter(x => /bovin/i.test(x.especie ?? '')); diag.bovinos = candidatos.length;
    candidatos = candidatos.filter(x => x.tipo === 'INDIVIDUAL'); diag.individuales = candidatos.length;
    candidatos = candidatos.filter(x => x.estado === 'ACTIVO'); diag.activos = candidatos.length;
    diag.evaluados_maximo = Math.min(candidatos.length, 5); diag.omitidos_por_limite = Math.max(0, candidatos.length - 5);
    for (const x of candidatos.slice(0, 5)) {
      const idActivo = id(x.id_activo_biologico), idEspecie = id(x.id_especie);
      const candidato = { activo_id: idActivo, estado: 'DESCARTADO', motivo: null };
      datos.diagnostico_por_candidato.push(candidato);
      if (!idActivo || !idEspecie) { candidato.motivo = 'Identificador de activo o especie inválido.'; continue; }
      const d = await get('/finanzas/activos/' + idActivo, opts.m06);
      if (!ok(d)) { candidato.motivo = `Historial financiero ilegible: ${d.fallo ?? `HTTP ${d.http}`}.`; continue; }
      if (!d.cuerpo?.activo?.numero_id_tributaria) { candidato.motivo = 'Historial financiero sin titular tributario.'; continue; }
      const periodo = periodoDestino(p.cuerpo, d.cuerpo?.activo?.numero_id_tributaria);
      if (!periodo) { candidato.motivo = 'No hay período destino ABIERTO para el titular.'; continue; } diag.periodo++;
      const tieneMatriz = config.cuerpo.matriz.some(x => x.tipo_hecho === 'BAJA_ACTIVO' && x.sentido === 'PERDIDA' &&
        (x.id_especie == null || id(x.id_especie) === idEspecie) && x.cuenta_debito && x.cuenta_credito);
      if (!tieneMatriz) { candidato.motivo = 'Falta matriz RF-109 BAJA_ACTIVO/PERDIDA.'; continue; } diag.matriz++;
      if (!Array.isArray(d.cuerpo?.reconocimientos) ||
          !d.cuerpo.reconocimientos.some(x => x.estado === 'CONFIRMADO')) {
        candidato.motivo = 'No hay reconocimiento CONFIRMADO.'; continue;
      }
      diag.reconocidos++;
      const calc = calculoVigente(d.cuerpo);
      if (!calc) { candidato.motivo = 'No hay cálculo CALCULADO con valor neto positivo.'; continue; } diag.calculo++;
      const costo = d.cuerpo.valoracion_costo;
      const literalValor = String(costo?.es_activa === true ? costo.valor_contable_por_costo : calc.valor_neto);
      const partesValor = /^\d+(?:\.\d+)?$/.test(literalValor) ? literalValor.split('.') : null;
      const valorBajaEsperado = partesValor ? Number(`${partesValor[0]}.${(partesValor[1] ?? '').padEnd(2, '0').slice(0, 2)}`) : NaN;
      if (!(valorBajaEsperado > 0) || !Number.isFinite(valorBajaEsperado)) {
        candidato.motivo = 'Valor en libros de baja ausente o no positivo.'; continue;
      }
      const f = await get('/activos-biologicos/' + idActivo + '/ficha-integral', opts.m02);
      if (!ok(f)) { candidato.motivo = `Ficha integral ilegible: ${f.fallo ?? `HTTP ${f.http}`}.`; continue; }
      if (f.cuerpo?.estado_actual !== 'ACTIVO') { candidato.motivo = 'Ficha integral sin estado ACTIVO.'; continue; }
      if (f.cuerpo?.unidad_peso !== 'kg') { candidato.motivo = 'Ficha integral sin unidad de peso kg.'; continue; }
      if (!(Number(f.cuerpo?.peso_actual) > 0)) { candidato.motivo = 'Ficha integral sin peso positivo.'; continue; }
      diag.peso++;
      candidato.estado = aid ? 'ELEGIBLE' : 'SELECCIONADO'; candidato.motivo = aid ? 'Elegible; ya se seleccionó otro activo.' : 'Cumple condiciones de baja.';
      if (!aid) { aid = idActivo; pid = id(periodo.id_periodo_contable); opts.activo = aid;
        datos.peso_kg = Number(f.cuerpo.peso_actual); datos.valor_baja_esperado = valorBajaEsperado; }
    }
    datos.diagnostico_candidatos = diag;
    if (!aid || !pid) { finalizar(r._corte || r.solicitudes.some(x => x.http >= 500 || x.fallo) ? 'NO_CONCLUYENTE' : 'BLOQUEADO',
      'Sin candidato que reúna bovino INDIVIDUAL ACTIVO, reconocimiento CONFIRMADO, cálculo CALCULADO con valor positivo, período destino ABIERTO, matriz RF-109 y peso kg.'); return r; }
    datos.activo_id = aid; datos.periodo_id = pid;
    const max = Math.max(...a.cuerpo.map(x => id(x.id_activo_biologico) ?? 0));
    const inexistente = max + 100000; datos.inexistente_id = inexistente;
    const pre404 = await get('/activos-biologicos/' + inexistente, opts.m02);
    if (pre404.http !== 404 || !pre404.eco) { finalizar('NO_CONCLUYENTE', 'El id mayor al máximo visible no se acreditó inexistente por GET 404.'); return r; }
    base = await instantanea(r, api, opts, aid, pid); datos.snapshots.base = resumenInstantanea(base);
    if (!base.completa || base.estado !== 'ACTIVO') { finalizar('NO_CONCLUYENTE', 'Línea base de activo, período, historial o RF-94 incompleta.'); return r; }
    mutado = true;
    const baja = await post('/activos-biologicos/' + aid + '/eventos/baja', { ...opts.m02,
      cuerpo: { tipo_baja: 'perdida', fecha_baja: hoy(), motivo_baja: 'Baja QA ' + c.runId } });
    eventoBaja = id(baja.cuerpo?.evento?.id_eventos ?? baja.cuerpo?.id_eventos);
    if (!eventoBaja) {
      const ev = await get('/activos-biologicos/' + aid + '/eventos', opts.m02);
      const n = ok(ev) ? nuevos(base.eventos, ev.cuerpo?.eventos, 'id_eventos') : null;
      if (n?.length === 1) eventoBaja = id(n[0].id_eventos);
    }
    datos.evento_baja_id = eventoBaja;
    if (r._corte) { finalizar('NO_CONCLUYENTE', 'Corte por 403 o 5xx tras baja; se conserva conciliación para cierre.'); return r; }
    const proc = eventoBaja || baja.http === 201 ? await post('/finanzas/eventos/procesar', opts.m06) : null;
    datos.procesamiento_http = proc?.http ?? null;
    if (r._corte) { finalizar('NO_CONCLUYENTE', 'Corte por 403 o tres 5xx durante procesamiento M06.'); return r; }
    const sA = await instantanea(r, api, opts, aid, pid); datos.snapshots.baja = resumenInstantanea(sA);
    datos.subcasos.baja = evaluarPaso('baja', base, sA, baja, aid, eventoBaja, datos.valor_baja_esperado);
    if (proc?.http !== 200 && datos.subcasos.baja.estado === 'APROBADO')
      datos.subcasos.baja = { estado: 'NO_CONCLUYENTE', motivo: 'Procesamiento sin HTTP 200; lectura conciliada sin reintento.' };
    const crecimiento = { tipo_medicion: 'PESO', valor_medicion: datos.peso_kg, unidad_medida: 'kg',
      descripcion: 'Intento G35 ' + c.runId };
    let sB = sA;
    if (sA.completa && sA.estado === 'BAJA') {
      const b = await post('/activos-biologicos/' + aid + '/eventos/crecimiento', { ...opts.m02, cuerpo: crecimiento });
      if (r._corte) { finalizar('NO_CONCLUYENTE', 'Corte por 403 o tres 5xx en intento sobre BAJA.'); return r; }
      sB = await instantanea(r, api, opts, aid, pid); datos.snapshots.baja_rechazo = resumenInstantanea(sB);
      datos.subcasos.baja_rechazo = evaluarPaso('baja_rechazo', sA, sB, b, aid, eventoBaja);
    } else datos.subcasos.baja_rechazo = { estado: 'NO_CONCLUYENTE',
      motivo: 'No se acreditó estado BAJA; no se envía crecimiento que podría crear un evento sobre ACTIVO.' };
    const cResp = await post('/activos-biologicos/' + inexistente + '/eventos/crecimiento', { ...opts.m02, cuerpo: crecimiento });
    if (r._corte) { finalizar('NO_CONCLUYENTE', 'Corte por 403 o tres 5xx en intento sobre inexistente.'); return r; }
    const sC = await instantanea(r, api, opts, aid, pid); datos.snapshots.inexistente = resumenInstantanea(sC);
    datos.subcasos.inexistente = evaluarPaso('inexistente', sB, sC, cResp, aid, eventoBaja);
    const creadosParaInexistente = [
      ['periodo_variaciones', 'id_variacion_valor_razonable'], ['periodo_lineas', 'id_linea_asiento_nic41'],
      ['periodo_mediciones', 'id_medicion_posterior'] ].flatMap(([k, clave]) =>
      (nuevos(sB[k], sC[k], clave) ?? []).filter(x => id(x.id_activo_biologico) === inexistente)
        .map(x => ({ tipo: k, id: id(x[clave]) })));
    datos.subcasos.inexistente.observados = { ...datos.subcasos.inexistente.observados,
      inexistente_id: inexistente, datos_creados_para_inexistente: creadosParaInexistente };
    if (sB.completa && sC.completa && (cResp.http === 201 || creadosParaInexistente.length))
      datos.subcasos.inexistente = { ...datos.subcasos.inexistente, estado: 'RECHAZADO',
        motivo: datos.subcasos.inexistente.motivo + ' Se crearon datos para el ID inexistente.' };
    for (const [k, paso] of Object.entries(datos.subcasos)) if (paso.estado === 'RECHAZADO')
      r.incidencias.push(incidencia(k, paso.motivo, ['resultado.json']));
    finalizar(resultadoFinal(datos.subcasos), Object.entries(datos.subcasos).map(([k, x]) => `${k}: ${x.estado}, ${x.motivo}`).join(' '));
    if (!sinArtefactos && eventoBaja && sA.estado === 'BAJA' &&
        r.solicitudes.length + 3 + 9 <= PRESUPUESTO.solicitudes_totales)
      await newmanLecturas(r, c, env, token, admin, aid, pid, eventoBaja, datos.valor_baja_esperado);
    else if (!sinArtefactos) r.problemas_tecnicos.push(eventoBaja && sA.estado === 'BAJA' ?
      'Presupuesto insuficiente para Newman y nueve solicitudes de cierre; se prioriza DELETE.' :
      'Newman no se ejecutó porque el evento RF-45 o estado BAJA no quedó acreditado.');
    else r.herramientas.newman = { iteraciones: 1, fallos: 0, codigo: 0, version: 'ensayo-local' };
    if (r.herramientas.newman?.problema || r.herramientas.newman?.iteraciones !== 1) {
      r.problemas_tecnicos.push(r.herramientas.newman?.problema_tecnico ?? 'Newman incompleto o contradictorio.');
      finalizar('NO_CONCLUYENTE', 'Evidencia Newman incompleta o contradictoria.');
    }
  } catch (e) {
    r.problemas_tecnicos.push(texto(e.message));
    finalizar('NO_CONCLUYENTE', 'Error de automatización; no se atribuye defecto de producto.');
  } finally {
    if (iniciado) {
      const del = await pedir(r, api, 'DELETE', '/test-control/runs/' + encodeURIComponent(c.runId), {
        token, secreto: env.QA_SANDBOX_SECRET, timeout: 30000, fetcher });
      r.cierre.run.cierre_http = del.http;
      if (del.http === 200 && !mutado) {
        r.cierre.rollback = { verificado: true, motivo: 'Sin escrituras de producto antes del DELETE.' };
      } else if (del.http === 200 && aid && pid && base?.completa) {
        r._corte = false; r._seguidos5xx = 0;
        const postc = await instantanea(r, api, { ...opts, m06: { token, fetcher }, m02: { token: admin, fetcher } }, aid, pid);
        r.cierre.rollback = rollback(base, postc, eventoBaja); datos.snapshots.poscierre = resumenInstantanea(postc);
      } else r.cierre.rollback = { verificado: false, motivo: 'DELETE o línea base sin comprobación poscierre.' };
      if (mutado && !r.cierre.rollback.verificado) r.problemas_tecnicos.push('CRÍTICA: rollback del estado ACTIVO y datos del RUN no verificado; RUN no oficial.');
    }
    if (!r.casos[CASO]) finalizar('NO_CONCLUYENTE', 'Caso sin cierre lógico.');
    for (let i = 0; i < IDS.length; i++) r.comprobaciones.push({ caso: CASO, fuente: 'API', id: IDS[i], tipo: 'ASSERT',
      estado: r.casos[CASO].estado,
      motivo: datos.subcasos[['baja', 'baja_rechazo', 'inexistente'][i]]?.motivo ?? r.casos[CASO].motivo,
      evidencia: sinArtefactos ? 'ensayo-local' : 'resultado.json' });
    r.oficial = oficialidad(r) && !sinArtefactos; r.consume_version = r.oficial;
    r.estado_ejecucion = r.oficial ? 'OFICIAL' : 'NO_OFICIAL';
    if (!sinArtefactos && fs.existsSync(c.directorio)) {
      r.evidencias.push('resultado.json', nombreInforme(c.version));
      if (r.herramientas.newman) r.evidencias.push('newman/newman-G35.json', 'newman/newman-G35.html');
      const pub = { ...r }; for (const k of ['_limite', '_corte', '_seguidos5xx', '_secretos']) delete pub[k];
      fs.writeFileSync(path.join(c.directorio, 'resultado.json'), sanear(JSON.stringify(pub, null, 2), [token, admin, ...r._secretos]));
      fs.writeFileSync(path.join(c.directorio, nombreInforme(c.version)), sanear(informe(c, r), [token, admin, ...r._secretos]));
    }
    delete r._secretos;
  }
  return r;
}
if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
else if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { const c = contexto(process.argv.slice(2)); const r = await evaluar(c); console.log(JSON.stringify({ grupo: 'G35', estado: r.casos[CASO]?.estado, oficial: r.oficial, rollback: r.cierre.rollback.verificado }));
    process.exitCode = r.oficial ? 0 : 2; } catch (e) { console.error(texto(e.message)); process.exitCode = 2; }
}
