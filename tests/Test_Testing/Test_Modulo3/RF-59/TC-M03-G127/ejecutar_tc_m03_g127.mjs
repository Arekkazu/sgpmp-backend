#!/usr/bin/env node
// TC-M03-256 (RF-59 CA-16, Fase 8, Postcondición 6): toda consulta histórica genera trazabilidad
// (usuario, filtros, rango temporal, cantidad de registros y timestamp); cuando la operación es una
// exportación, el registro incluye además el formato.
//
// - Variante CONSULTA (siempre evaluable): consulta del historial con filtros y periodo conocidos.
// - Variante EXPORTACION (cuando aplique): exportación filtrada. Si el servicio responde 503
//   M08_NO_DISPONIBLE, la variante "no aplica" (INFO + dependencia M08) y la consulta se evalúa igual;
//   la matriz verifica el formato "únicamente cuando exista una operación de exportación".
// - Las operaciones las hace el Ingeniero de Campo con Newman, sobre un escenario construido en el sandbox.
// - Mecanismo de auditoría: no hay uno propio del historial en el código actual. Se buscan los
//   registros en las bitácoras oficiales existentes, RF-10 (GET /auditoria/) y RF-63 (GET /iot/auditoria),
//   con la cuenta de preparación (Administrador), desde un ancla temporal del servidor y correlacionando
//   usuario, ventana y el sensor del RUN. Testigo positivo: la bitácora RF-10 debe reflejar eventos del
//   propio RUN; si no, su ausencia no se interpreta (BLOQUEADO).
// - Esto no es el trigger auditoria.logs_dml, que solo se usa como testigo de aislamiento del sandbox.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  leerEnv, autorizar, version, carpetaResultados, runId, nombreInforme, argumentos, newmanModulo, sello, serialQa, nombreSensor,
  sandbox, catalogos, fincaConAcceso, construirUnidad, cuerpoLectura, correrNewman, redactor, informe,
  veredictoCasos, sintaxisColeccion, nombresDeTests, casoDeTexto, tipoDeTexto, consultaTestigoDispositivo,
} from './monitoreo_lib.mjs';

export const GRUPO = 'TC-M03-G127';
export const CASOS = ['TC-M03-256'];
export const ATRIBUTOS = [['API-256-01', 'existe un registro de auditoría de la operación', 'registro'], ['API-256-02', 'registra el usuario', 'usuario'], ['API-256-03', 'registra los filtros aplicados', 'filtros'], ['API-256-04', 'registra el rango temporal', 'rango'], ['API-256-05', 'registra la cantidad de registros', 'cantidad'], ['API-256-06', 'registra el timestamp', 'timestamp']];
export const FORMATO = ['API-256-07', 'registra el formato de exportación', 'formato'];
export const FORMATO_EXPORTACION = 'EXCEL';
/** La exportación solo es requerida cuando la operación existe (no cuando M08 no está disponible). */
export function requeridas(exportacionAplica) {
  return { 'TC-M03-256': [...ATRIBUTOS.map(([id]) => `${id}@CONSULTA`), ...(exportacionAplica ? [...ATRIBUTOS, FORMATO].map(([id]) => `${id}@EXPORTACION`) : [])] };
}
/** 503 M08_NO_DISPONIBLE = la exportación no existe todavía; 2xx = aplica; otro = no se pudo determinar. */
export function estadoExportacion(http, errorCode) {
  if (http >= 200 && http < 300) return 'APLICA';
  if (http === 503 && errorCode === 'M08_NO_DISPONIBLE') return 'NO_DISPONIBLE';
  return 'INDETERMINADA';
}

const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const ENV = path.join(ROOT, '.env.qa');
const COLLECTION = path.join(DIR, `${GRUPO}.postman_collection.json`);

/** Pares clave/valor escalares de un registro (recorrido profundo). */
export function pares(obj, out = []) {
  if (obj && typeof obj === 'object') for (const [k, v] of Object.entries(obj)) { if (v !== null && typeof v !== 'object') out.push([k, v]); pares(v, out); }
  return out;
}
/**
 * Atributos que un registro de bitácora documenta para la operación `op`
 * ({ id_usuario, filtros: { sensor_id, id_infraestructura, estado_dato }, fecha_inicio, fecha_fin, total, formato?, desde }).
 */
export function evaluarRegistro(r, op) {
  const kv = pares(r);
  const valor = (re, x) => kv.some(([k, v]) => re.test(k) && String(v) === String(x));
  const texto = JSON.stringify(r);
  const usuario = Number(r?.id_usuario) === op.id_usuario;
  const filtros = valor(/sensor/i, op.filtros.sensor_id) && valor(/infraestructura|unidad/i, op.filtros.id_infraestructura) && valor(/estado/i, op.filtros.estado_dato);
  // El rango consultado, no la marca de tiempo del propio evento (fecha_evento, fecha_hora, creación).
  const rango = [op.fecha_inicio, op.fecha_fin].every(f => kv.some(([k, v]) => /inicio|fin|desde|hasta|rango|periodo/i.test(k) && !/evento|hora|creaci/i.test(k) && String(v).startsWith(f)));
  const cantidad = kv.some(([k, v]) => /total|cantidad|registros|count/i.test(k) && Number(v) === Number(op.total) && op.total != null);
  const t = Date.parse(r?.fecha_evento || r?.fecha_hora || '');
  const timestamp = Number.isFinite(t) && (!op.desde || t >= Date.parse(op.desde) - 5000);
  const formato = op.formato ? valor(/formato/i, op.formato) : undefined;
  const relacionado = usuario && (/historial|exporta/i.test(texto) || valor(/sensor/i, op.filtros.sensor_id));
  return { relacionado, usuario, filtros, rango, cantidad, timestamp, formato };
}
/** El registro relacionado que documenta más atributos (o null). */
export function mejorRegistro(registros, op) {
  let mejor = null, puntos = -1;
  for (const r of registros) {
    const e = evaluarRegistro(r, op);
    if (!e.relacionado) continue;
    const p = Object.values(e).filter(x => x === true).length;
    if (p > puntos) { mejor = { registro: r, atributos: e }; puntos = p; }
  }
  return mejor;
}

function local() {
  const checks = []; const ck = (n, x) => checks.push([n, !!x]);
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const col = JSON.parse(fs.readFileSync(COLLECTION, 'utf8'));
  const texto = JSON.stringify(col);
  const fuente = fs.readFileSync(fileURLToPath(import.meta.url), 'utf8');
  const futuras = { ambiente: 'TEST', autorizacion: 'REF-DESARROLLO', efectos: ['notificacion-login'] };
  ck('Matriz: TC-M03-256', CASOS.join() === 'TC-M03-256');
  ck('Atributos de la matriz: usuario, filtros, rango, cantidad, timestamp y formato en exportación', ATRIBUTOS.map(a => a[2]).join() === 'registro,usuario,filtros,rango,cantidad,timestamp' && FORMATO[2] === 'formato');
  ck('La consulta se evalúa aunque M08 no esté disponible', requeridas(false)['TC-M03-256'].length === 6 && requeridas(true)['TC-M03-256'].length === 13 && estadoExportacion(503, 'M08_NO_DISPONIBLE') === 'NO_DISPONIBLE');
  ck('Configuración compartida y QA_AUTORIZADO=NO', fs.existsSync(ENV) && v.QA_AUTORIZADO === 'NO');
  ck('Barrera rechaza la ejecución actual', !autorizar(v, { ambiente: 'TEST', autorizacion: '', efectos: [] }).ok);
  ck('Barrera acepta condiciones futuras válidas', autorizar({ ...v, QA_AUTORIZADO: 'SI' }, futuras).ok);
  ck('Barrera rechaza DEV', !autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ...futuras, ambiente: 'DEV' }).ok);
  ck('Cuentas de preparación (Administrador) e Ingeniero resueltas', ['SETUP', 'ENG'].every(r => !!v[`QA_${r}_EMAIL`] && !!(v[`QA_${r}_PASSWORD`] || v.QA_COMMON_PASSWORD)) && !!v.QA_SANDBOX_SECRET);
  ck('Bitácoras oficiales existentes (RF-10 y RF-63), sin tablas ni endpoints inventados', /['`]\/auditoria\/\?/.test(fuente) && /['`]\/iot\/auditoria\?/.test(fuente) && !/FROM modulo\d\.\w*audit/i.test(fuente));
  ck('Testigo positivo de la bitácora antes de interpretar ausencias', /testigo positivo/.test(fuente));
  ck('Colección: consulta y exportación filtradas por el Ingeniero', col.item.length === 2 && col.item.every(i => i.request.method === 'GET') && texto.includes('historial/exportar') && texto.includes(`formato=${FORMATO_EXPORTACION}`));
  ck('Cada petición declara caso y variante', col.item.every(i => casoDeTexto(i.name) && /\[V:(CONSULTA|EXPORTACION)\]/.test(i.name)));
  ck('Cada test de la colección declara PRE, ASSERT o INFO', nombresDeTests(col).every(n => tipoDeTexto(n) !== null));
  const vars = new Set([...texto.matchAll(/\{\{([a-z0-9_]+)\}\}/g)].map(x => x[1]));
  ck('Variables Newman resueltas por el ejecutor', [...vars].every(x => ['base_url', 'run_id', 'sandbox_secret', 'token', 'fecha_inicio', 'fecha_fin', 'id_area', 'id_sensor'].includes(x)));
  ck('Barrera propia de Newman (nivel colección)', (col.event || []).some(e => e.listen === 'prerequest' && e.script.exec.join('\n').includes('BLOQUEO_G127')));
  try { sintaxisColeccion(col); ck('Sintaxis Postman (colección e ítems)', true); } catch { ck('Sintaxis Postman (colección e ítems)', false); }
  ck('Sintaxis ejecutor', spawnSync(process.execPath, ['--check', fileURLToPath(import.meta.url)]).status === 0);
  ck('Sintaxis librería', spawnSync(process.execPath, ['--check', path.join(DIR, 'monitoreo_lib.mjs')]).status === 0);
  ck('Testigo de aislamiento sin RLS (distinto de la auditoría evaluada)', /FROM auditoria\.logs_dml/.test(consultaTestigoDispositivo('QAAUTO-G127-1')));
  ck('Sin peticiones concurrentes al sandbox', !new RegExp(['Promise', 'all'].join('\\.')).test(fuente));
  ck('Sin carpetas RESULTADOS de construcción', !fs.existsSync(path.join(DIR, 'RESULTADOS')) && !fs.readdirSync(DIR).some(x => /^EvaluacionV\d+$/.test(x)));
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD].filter(x => x?.length > 4);
  ck('Sin secretos literales', [fileURLToPath(import.meta.url), COLLECTION, path.join(DIR, 'monitoreo_lib.mjs')].every(f => !secretos.some(s => fs.readFileSync(f, 'utf8').includes(s))));
  ck('Pruebas unitarias locales', spawnSync(process.execPath, ['--test', path.join(DIR, 'validar_local_g127.mjs')], { encoding: 'utf8' }).status === 0);
  try { newmanModulo(ROOT); ck('Newman disponible', true); } catch { ck('Newman disponible', false); }
  for (const [n, ok] of checks) console.log(`${ok ? 'OK' : 'FALLO'} ${n}`);
  console.log(`G127 local ${checks.filter(x => x[1]).length}/${checks.length}`);
  return checks.every(x => x[1]) ? 0 : 1;
}

async function ejecutar(a) {
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const gate = autorizar(v, a);
  if (!gate.ok) { console.error(`EJECUCIÓN NO AUTORIZADA: ${gate.motivos.join('; ')}`); return 2; }
  if (!['evaluacion', 'reintento'].includes(a.tipo)) { console.error('Indique --tipo evaluacion|reintento'); return 2; }
  const n = version(DIR, a.tipo, a.version), newman = newmanModulo(ROOT);
  const marca = sello(), run = runId(GRUPO, n, marca);
  const base = carpetaResultados(DIR, n), out = path.join(base, run);
  fs.mkdirSync(base, { recursive: true }); fs.mkdirSync(out);
  const serial = serialQa(v, 'G127', marca, 'U');
  const ev = { grupo: GRUPO, rf: 'RF-59', cu: 'CU04', casos: CASOS, version: n, run_id: run, estado: 'EN_CURSO', fase: 'PREFLIGHT', autorizacion: a.autorizacion, actor_operaciones: 'Ingeniero de Campo', consulta_bitacora: 'Administrador (cuenta de preparación)', dependencias: [], bloqueos: {}, aserciones: [], sandbox: {}, datos: {}, inicio: new Date().toISOString() };
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_ENG_PASSWORD, serial];
  let limpiar = redactor(secretos);
  const guardar = () => fs.writeFileSync(path.join(out, 'evidencia.json'), limpiar(JSON.stringify(ev, null, 2)));
  const pre = (variante, nombre, ok, detalle) => ev.aserciones.push({ herramienta: 'Ejecutor', caso: 'TC-M03-256', tipo: 'PRE', id: null, variante, nombre: `[TC-M03-256][PRE]${variante ? `[V:${variante}]` : ''} ${nombre}`, ok: !!ok, evidencia: false, error: ok ? undefined : detalle });
  const sb = sandbox({ api: gate.api, run, secreto: v.QA_SANDBOX_SECRET });
  let abierto = false, dispositivo = false, exportacion = 'INDETERMINADA';
  try {
    await sb.abrir(); abierto = true;
    const setup = await sb.login(v.QA_SETUP_EMAIL, v.QA_SETUP_PASSWORD || v.QA_COMMON_PASSWORD, 'preparación', /administrador/i);
    secretos.push(setup.token); limpiar = redactor(secretos);
    const S = setup.token;
    // Ancla temporal del servidor, anterior al login del Ingeniero (testigo positivo).
    const ancla = await sb.req('GET', '/auditoria/?tamano=1', { token: S });
    const desde = [200, 206].includes(ancla.status) ? ancla.data?.fecha_hasta : null;
    const eng = await sb.login(v.QA_ENG_EMAIL, v.QA_ENG_PASSWORD || v.QA_COMMON_PASSWORD, 'Ingeniero', /ingeniero/i);
    secretos.push(eng.token); limpiar = redactor(secretos);

    // ---- PREPARACIÓN ----------------------------------------------------------------------------
    ev.fase = 'PREPARACION';
    const cat = await catalogos(sb, S);
    const finca = await fincaConAcceso(sb, { tokSetup: S, tokActor: eng.token, idActor: eng.id, nombre: `QA Historial G Ciento Veintisiete ${marca}` });
    const unidad = await construirUnidad(sb, { tok: S, cat, finca: finca.id, run, nombreUnidad: `QA G127 ${marca} U`, serial, nombres: [nombreSensor(`QA G127 ${marca}`, 'U', 1)], alCrearDispositivo: async () => { dispositivo = true; ev.sandbox.aislamiento = await sb.aislamiento(serial); } });
    const s = unidad.sensores[0];
    for (let k = 1; k <= 2; k++) sb.need(await sb.req('POST', '/iot/telemetria', { body: cuerpoLectura({ idDispositivo: unidad.id_dispositivo, idSensor: s.id, serial, timestamp: new Date(Date.now() - (30 + k * 120) * 1000).toISOString(), valor: 20 + k }) }), 201, `Lectura ${k + 1}`);
    const hoyUtc = new Date().toISOString().slice(0, 10);
    const prueba = await sb.req('GET', `/iot/monitoreo/historial?fecha_inicio=${hoyUtc}&fecha_fin=${hoyUtc}&sensor_id=${s.id}`, { token: eng.token });
    const fechaFin = prueba.status !== 200 && /FECHA_FIN_FUTURA/.test(JSON.stringify(prueba.data ?? '')) ? new Date(Date.now() - 86400000).toISOString().slice(0, 10) : hoyUtc;
    const fechaInicio = new Date(Date.parse(fechaFin) - 2 * 86400000).toISOString().slice(0, 10);
    const filtros = { sensor_id: s.id, id_infraestructura: unidad.id, estado_dato: 'LECTURA_VALIDA' };
    ev.datos = { finca, id_infraestructura: unidad.id, id_sensor: s.id, lecturas: 3, periodo: { fecha_inicio: fechaInicio, fecha_fin: fechaFin }, filtros, formato_exportacion: FORMATO_EXPORTACION, origen: 'construido en el RUN con APIs oficiales' };

    // ---- OPERACIONES AUDITADAS (Newman, Ingeniero) -------------------------------------------------
    ev.fase = 'ESCENARIOS'; guardar();
    const vars = { base_url: gate.api, run_id: run, sandbox_secret: v.QA_SANDBOX_SECRET, autorizado_run: 'SI', token: eng.token, fecha_inicio: fechaInicio, fecha_fin: fechaFin, id_area: unidad.id, id_sensor: s.id };
    const nw = await correrNewman(newman, JSON.parse(fs.readFileSync(COLLECTION, 'utf8')), vars, { limpiar });
    ev.aserciones.push(...nw.aserciones); ev.operaciones = nw.muestras;
    for (const e of nw.errores) { ev.dependencias.push(e.mensaje); (ev.bloqueos['TC-M03-256'] ??= []).push(e.mensaje); }
    const infoDe = re => (nw.aserciones.map(x => x.nombre).find(x => re.test(x)) || '').match(re);
    const total = Number((infoDe(/\[V:CONSULTA\] total=(\d+)/) || [])[1]);
    const exp = infoDe(/\[V:EXPORTACION\] HTTP (\d+) ([A-Z0-9_]*)/) || [];
    exportacion = estadoExportacion(Number(exp[1]), exp[2]);
    ev.datos.total_consulta = Number.isFinite(total) ? total : null;
    ev.datos.exportacion = { http: Number(exp[1]) || null, codigo: exp[2] || null, estado: exportacion };
    if (exportacion === 'NO_DISPONIBLE') {
      ev.dependencias.push('EXPORTACION no aplica todavía: el servicio responde 503 M08_NO_DISPONIBLE. La auditoría de la exportación (incluido el formato) se evaluará cuando M08 esté disponible; la de la consulta se evalúa ahora.');
      ev.aserciones.push({ herramienta: 'Ejecutor', caso: 'TC-M03-256', tipo: 'INFO', id: null, variante: 'EXPORTACION', nombre: '[TC-M03-256][INFO][V:EXPORTACION] exportación no disponible (M08): variante no aplica en este RUN', ok: true, evidencia: false });
    } else if (exportacion === 'INDETERMINADA') pre('EXPORTACION', 'la exportación filtrada se ejecutó o se identificó como no disponible', false, `HTTP ${exp[1] ?? '—'} ${exp[2] ?? ''}`.trim());

    // ---- BITÁCORAS: búsqueda con reintentos -------------------------------------------------------
    const buscar = async () => {
      const regs = []; let rf10 = !!desde;
      let hasta = null;
      for (let p = 1; p <= 10 && desde; p++) {
        const r = await sb.req('GET', `/auditoria/?id_usuario=${eng.id}&fecha_desde=${encodeURIComponent(desde)}${hasta ? `&fecha_hasta=${encodeURIComponent(hasta)}` : ''}&pagina=${p}&tamano=50`, { token: S });
        if (![200, 206].includes(r.status)) { rf10 = false; break; }
        hasta ??= r.data?.fecha_hasta;
        regs.push(...(r.data?.items || []).map(x => ({ ...x, _bitacora: 'RF-10' })));
        if ((r.data?.items || []).length < 50) break;
      }
      let iot = !!desde;
      for (let p = 1; p <= 5 && desde; p++) {
        const r = await sb.req('GET', `/iot/auditoria?fecha_desde=${encodeURIComponent(desde)}&pagina=${p}&por_pagina=200`, { token: S });
        if (r.status !== 200) { iot = false; break; }
        regs.push(...(r.data?.items || []).filter(x => Number(x.id_usuario) === eng.id).map(x => ({ ...x, _bitacora: 'RF-63' })));
        if ((r.data?.items || []).length < 200) break;
      }
      return { regs, rf10, iot };
    };
    const opConsulta = { id_usuario: eng.id, filtros, fecha_inicio: fechaInicio, fecha_fin: fechaFin, total: ev.datos.total_consulta, desde };
    const opExport = { ...opConsulta, formato: FORMATO_EXPORTACION };
    let b, mc = null, me = null;
    for (let intento = 0; intento < 3; intento++) {
      if (intento) await new Promise(r => setTimeout(r, 10000));
      b = await buscar();
      mc = mejorRegistro(b.regs.filter(r => !/exporta/i.test(JSON.stringify(r))), opConsulta);
      me = exportacion === 'APLICA' ? mejorRegistro(b.regs.filter(r => /exporta/i.test(JSON.stringify(r))), opExport) : null;
      if (mc && (exportacion !== 'APLICA' || me)) break;
    }
    // Testigo positivo: la bitácora RF-10 refleja eventos del propio RUN (inicio de sesión del Ingeniero).
    const testigo = b.rf10 && b.regs.some(r => r._bitacora === 'RF-10' && Number(r.id_usuario) === eng.id);
    pre(null, 'testigo positivo: la bitácora RF-10 es consultable y refleja eventos del propio RUN', testigo, b.rf10 ? 'sin eventos del RUN: la bitácora no es observable dentro del sandbox; la ausencia no se interpreta' : 'bitácora RF-10 no consultable');
    pre(null, 'la consulta auditada se ejecutó y su cantidad de registros es conocida', Number.isFinite(total) && total > 0, `total=${ev.datos.total_consulta}`);
    if (!b.iot) ev.dependencias.push('Bitácora IoT (RF-63) no consultable con la cuenta de preparación; se revisó solo RF-10.');
    ev.datos.bitacora = { desde, registros_revisados: b.regs.length, rf10_consultable: b.rf10, iot_consultable: b.iot };
    const asertar = (variante, m, lista) => {
      for (const [id, nombre, campo] of lista) {
        const ok = campo === 'registro' ? !!m : !!m?.atributos?.[campo];
        ev.aserciones.push({ herramienta: 'Ejecutor', caso: 'TC-M03-256', tipo: 'ASSERT', id, variante, nombre: `[TC-M03-256][ASSERT][${id}][V:${variante}] ${nombre}`, ok, evidencia: b.rf10, error: ok ? undefined : (m ? `registro ${m.registro._bitacora} ${m.registro.id_evento ?? ''} sin ${campo}` : 'no hay registro de auditoría de la operación') });
      }
    };
    asertar('CONSULTA', mc, ATRIBUTOS);
    if (exportacion !== 'NO_DISPONIBLE') asertar('EXPORTACION', me, [...ATRIBUTOS, FORMATO]);
    ev.datos.registros = { consulta: mc ? { bitacora: mc.registro._bitacora, id: mc.registro.id_evento ?? null, atributos: mc.atributos } : null, exportacion: me ? { bitacora: me.registro._bitacora, id: me.registro.id_evento ?? null, atributos: me.atributos } : null };
    ev.estado = 'CONCLUIDA';
  } catch (e) { ev.estado = ev.fase === 'ESCENARIOS' ? 'INTERRUMPIDA' : 'ABORTADA_PREFLIGHT'; ev.dependencias.push(limpiar(e.message)); }
  finally {
    try {
      if (abierto) {
        const c = await sb.cerrar(dispositivo ? serial : null);
        ev.sandbox.cierre = c; ev.sandbox.rollback = c.rollback;
        if (dispositivo && c.sonda_posterior === null) ev.dependencias.push('Rollback no confirmable: testigo auditoria.logs_dml no consultable.');
      }
    } catch (e) { ev.sandbox.rollback = false; ev.dependencias.push(limpiar(e.message)); }
    ev.veredicto = veredictoCasos({ casos: CASOS, requeridas: requeridas(exportacion !== 'NO_DISPONIBLE'), estado: ev.estado, rollback: !!ev.sandbox.rollback, aserciones: ev.aserciones, bloqueos: ev.bloqueos });
    ev.fin = new Date().toISOString(); guardar();
    fs.writeFileSync(path.join(out, nombreInforme(GRUPO, n)), limpiar(informe({ grupo: GRUPO, n, run, ev, casos: CASOS, extra: `\nExportación: ${exportacion}${exportacion === 'NO_DISPONIBLE' ? ' (variante no aplica; resultado basado en la consulta)' : ''}.\n` })));
  }
  console.log(`${GRUPO}: ${ev.estado} — ${out}`); return ev.estado === 'CONCLUIDA' ? 0 : 4;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let code; try { const a = argumentos(process.argv.slice(2)); code = a.modo === 'local' ? local() : await ejecutar(a); } catch (e) { console.error(e.message); code = 2; } process.exitCode = code;
}
