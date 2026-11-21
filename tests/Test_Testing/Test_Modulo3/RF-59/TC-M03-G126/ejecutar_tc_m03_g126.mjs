#!/usr/bin/env node
// TC-M03-255 (RF-59 CA-14, Restricción 1, Postcondición 1): consultar, filtrar y paginar el historial
// no crea, modifica ni elimina lecturas históricas.
//
// - Conjunto controlado CONSTRUIDO en el sandbox con APIs oficiales: unidad QA con 3 sensores y 6 lecturas
//   válidas por sensor (RF-53). Dentro del sandbox ningún proceso externo ve estas filas: solo las
//   consultas del RUN pueden alterarlas.
// - Snapshot de solo lectura (SELECT por /test-control/query; modulo3 no tiene RLS): row_to_json de cada
//   fila de telemetrias del conjunto (por sensor, de modo que también se detectan lecturas creadas), de sus
//   vinculaciones_lecturas y de su telemetria_calidad, ordenadas por clave primaria. Forma canónica
//   (claves ordenadas) y hash SHA-256 por tabla; la comparación es por fila y por campo.
// - Entre ambos snapshots solo se ejecutan consultas GET /iot/monitoreo/historial (Newman) con distintos
//   filtros y varias páginas. La exportación queda fuera (matriz: evita la dependencia con M08).
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  leerEnv, autorizar, version, carpetaResultados, runId, nombreInforme, argumentos, newmanModulo, sello, serialQa, nombreSensor,
  sandbox, catalogos, fincaConAcceso, construirUnidad, cuerpoLectura, correrNewman, redactor, informe, filas,
  veredictoCasos, sintaxisColeccion, nombresDeTests, casoDeTexto, tipoDeTexto, consultaTestigoDispositivo,
} from './monitoreo_lib.mjs';

export const GRUPO = 'TC-M03-G126';
export const CASOS = ['TC-M03-255'];
export const SENSORES = 3, LECTURAS_POR_SENSOR = 6;
export const REQUERIDAS = { 'TC-M03-255': ['API-255-01', 'API-255-02', 'API-255-03', 'API-255-04'] };
/** Tablas del snapshot: clave primaria y filtro sobre el conjunto controlado. */
export const TABLAS = {
  telemetrias: { pk: 'id_telemetria', donde: ids => `id_sensor IN (${ids})` },
  vinculaciones_lecturas: { pk: 'id_vinculacion_lectura', donde: ids => `id_telemetria IN (SELECT id_telemetria FROM modulo3.telemetrias WHERE id_sensor IN (${ids}))` },
  telemetria_calidad: { pk: 'id_evaluacion', donde: ids => `id_telemetria IN (SELECT id_telemetria FROM modulo3.telemetrias WHERE id_sensor IN (${ids}))` },
};

const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const ENV = path.join(ROOT, '.env.qa');
const COLLECTION = path.join(DIR, `${GRUPO}.postman_collection.json`);

/** SELECT de solo lectura de una tabla del snapshot (ids de sensor validados como enteros). */
export function consultaSnapshot(tabla, idsSensor) {
  const t = TABLAS[tabla];
  if (!t || !idsSensor.length || !idsSensor.every(x => Number.isSafeInteger(x) && x > 0)) throw Error('Snapshot con parámetros no aptos');
  return `SELECT row_to_json(x)::text AS fila FROM modulo3.${tabla} x WHERE ${t.donde(idsSensor.join(','))} ORDER BY x.${t.pk}`;
}
/** Forma canónica: claves ordenadas en todos los niveles (el orden de columnas o de claves JSON no altera el hash). */
export function canonico(v) {
  if (Array.isArray(v)) return `[${v.map(canonico).join(',')}]`;
  if (v && typeof v === 'object') return `{${Object.keys(v).sort().map(k => `${JSON.stringify(k)}:${canonico(v[k])}`).join(',')}}`;
  return JSON.stringify(v);
}
/** Snapshot de una tabla a partir de la respuesta de /test-control/query; null = no verificable. */
export function snapshotTabla(respuesta, pk) {
  const f = filas(respuesta);
  if (!f) return null;
  const porId = new Map();
  for (const r of f) {
    let o; try { o = JSON.parse(r.fila); } catch { return null; }
    if (o?.[pk] == null || porId.has(String(o[pk]))) return null;
    porId.set(String(o[pk]), o);
  }
  const ids = [...porId.keys()].sort((a, b) => Number(a) - Number(b));
  const texto = ids.map(id => canonico(porId.get(id))).join('\n');
  return { filas: Object.fromEntries(ids.map(id => [id, porId.get(id)])), n: ids.length, hash: crypto.createHash('sha256').update(texto).digest('hex') };
}
/** Diferencias por fila y campo entre dos snapshots de una tabla. */
export function compararTabla(antes, despues) {
  const a = antes.filas, d = despues.filas;
  const creadas = Object.keys(d).filter(id => !(id in a));
  const eliminadas = Object.keys(a).filter(id => !(id in d));
  const modificadas = Object.keys(a).filter(id => id in d).map(id => {
    const campos = [...new Set([...Object.keys(a[id]), ...Object.keys(d[id])])].filter(k => canonico(a[id][k]) !== canonico(d[id][k]));
    return campos.length ? { id, campos } : null;
  }).filter(Boolean);
  return { creadas, eliminadas, modificadas, identicas: antes.hash === despues.hash && !creadas.length && !eliminadas.length && !modificadas.length };
}

function local() {
  const checks = []; const ck = (n, x) => checks.push([n, !!x]);
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const col = JSON.parse(fs.readFileSync(COLLECTION, 'utf8'));
  const texto = JSON.stringify(col);
  const fuente = fs.readFileSync(fileURLToPath(import.meta.url), 'utf8');
  const futuras = { ambiente: 'TEST', autorizacion: 'REF-DESARROLLO', efectos: ['notificacion-login'] };
  ck('Matriz: TC-M03-255', CASOS.join() === 'TC-M03-255');
  ck('Configuración compartida y QA_AUTORIZADO=NO', fs.existsSync(ENV) && v.QA_AUTORIZADO === 'NO');
  ck('Barrera rechaza la ejecución actual', !autorizar(v, { ambiente: 'TEST', autorizacion: '', efectos: [] }).ok);
  ck('Barrera acepta condiciones futuras válidas', autorizar({ ...v, QA_AUTORIZADO: 'SI' }, futuras).ok);
  ck('Barrera rechaza DEV', !autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ...futuras, ambiente: 'DEV' }).ok);
  ck('Cuentas de preparación (Administrador) e Ingeniero resueltas', ['SETUP', 'ENG'].every(r => !!v[`QA_${r}_EMAIL`] && !!(v[`QA_${r}_PASSWORD`] || v.QA_COMMON_PASSWORD)) && !!v.QA_SANDBOX_SECRET);
  ck('Snapshot de solo lectura (SELECT) sobre las tres tablas, ordenado por clave primaria', Object.keys(TABLAS).every(t => /^SELECT row_to_json\(x\)::text AS fila FROM modulo3\.\w+ x WHERE .* ORDER BY x\.\w+$/.test(consultaSnapshot(t, [1, 2]))) && !Object.keys(TABLAS).some(t => /\b(UPDATE|INSERT|DELETE|ALTER|DROP)\b/i.test(consultaSnapshot(t, [1]))));
  ck('Sin SQL de escritura en el ejecutor', !/(UPDATE|INSERT INTO|DELETE FROM)\s+modulo/i.test(fuente));
  ck('Solo consultas de historial entre snapshots (sin exportación)', col.item.every(i => i.request.method === 'GET' && i.request.url.path.join('/') === 'iot/monitoreo/historial'));
  ck('Varias combinaciones de filtros y recorrido de páginas', col.item.length >= 5 && texto.includes('setNextRequest') && ['sensor_id', 'tipo_variable', 'estado_dato', 'origen_dato', 'orden'].every(f => texto.includes(`${f}=`)));
  ck('Cada petición declara su caso', col.item.every(i => casoDeTexto(i.name)));
  ck('Cada test de la colección declara PRE, ASSERT o INFO', nombresDeTests(col).every(n => tipoDeTexto(n) !== null));
  const vars = new Set([...texto.matchAll(/\{\{([a-z0-9_]+)\}\}/g)].map(x => x[1]));
  ck('Variables Newman resueltas por el ejecutor', [...vars].every(x => ['base_url', 'run_id', 'sandbox_secret', 'token', 'fecha_inicio', 'fecha_fin', 'id_area', 'id_sensor', 'pagina'].includes(x)));
  ck('Barrera propia de Newman (nivel colección)', (col.event || []).some(e => e.listen === 'prerequest' && e.script.exec.join('\n').includes('BLOQUEO_G126')));
  try { sintaxisColeccion(col); ck('Sintaxis Postman (colección e ítems)', true); } catch { ck('Sintaxis Postman (colección e ítems)', false); }
  ck('Sintaxis ejecutor', spawnSync(process.execPath, ['--check', fileURLToPath(import.meta.url)]).status === 0);
  ck('Sintaxis librería', spawnSync(process.execPath, ['--check', path.join(DIR, 'monitoreo_lib.mjs')]).status === 0);
  ck('Testigo de aislamiento sin RLS', /FROM auditoria\.logs_dml/.test(consultaTestigoDispositivo('QAAUTO-G126-1')));
  ck('Sin peticiones concurrentes al sandbox', !new RegExp(['Promise', 'all'].join('\\.')).test(fuente));
  ck('Sin carpetas RESULTADOS de construcción', !fs.existsSync(path.join(DIR, 'RESULTADOS')) && !fs.readdirSync(DIR).some(x => /^EvaluacionV\d+$/.test(x)));
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD].filter(x => x?.length > 4);
  ck('Sin secretos literales', [fileURLToPath(import.meta.url), COLLECTION, path.join(DIR, 'monitoreo_lib.mjs')].every(f => !secretos.some(s => fs.readFileSync(f, 'utf8').includes(s))));
  ck('Pruebas unitarias locales', spawnSync(process.execPath, ['--test', path.join(DIR, 'validar_local_g126.mjs')], { encoding: 'utf8' }).status === 0);
  try { newmanModulo(ROOT); ck('Newman disponible', true); } catch { ck('Newman disponible', false); }
  for (const [n, ok] of checks) console.log(`${ok ? 'OK' : 'FALLO'} ${n}`);
  console.log(`G126 local ${checks.filter(x => x[1]).length}/${checks.length}`);
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
  const serial = serialQa(v, 'G126', marca, 'U');
  const ev = { grupo: GRUPO, rf: 'RF-59', cu: 'CU04', casos: CASOS, version: n, run_id: run, estado: 'EN_CURSO', fase: 'PREFLIGHT', autorizacion: a.autorizacion, actor_historial: 'Ingeniero de Campo', dependencias: [], bloqueos: {}, aserciones: [], sandbox: {}, datos: {}, inicio: new Date().toISOString() };
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_ENG_PASSWORD, serial];
  let limpiar = redactor(secretos);
  const guardar = () => fs.writeFileSync(path.join(out, 'evidencia.json'), limpiar(JSON.stringify(ev, null, 2)));
  const pre = (nombre, ok, detalle) => ev.aserciones.push({ herramienta: 'Ejecutor', caso: 'TC-M03-255', tipo: 'PRE', id: null, variante: null, nombre: `[TC-M03-255][PRE] ${nombre}`, ok: !!ok, evidencia: false, error: ok ? undefined : detalle });
  const sb = sandbox({ api: gate.api, run, secreto: v.QA_SANDBOX_SECRET });
  let abierto = false, dispositivo = false;
  try {
    await sb.abrir(); abierto = true;
    const setup = await sb.login(v.QA_SETUP_EMAIL, v.QA_SETUP_PASSWORD || v.QA_COMMON_PASSWORD, 'preparación', /administrador/i);
    const eng = await sb.login(v.QA_ENG_EMAIL, v.QA_ENG_PASSWORD || v.QA_COMMON_PASSWORD, 'Ingeniero', /ingeniero/i);
    secretos.push(setup.token, eng.token); limpiar = redactor(secretos);

    // ---- PREPARACIÓN: conjunto controlado de lecturas -----------------------------------------
    ev.fase = 'PREPARACION';
    const cat = await catalogos(sb, setup.token);
    const finca = await fincaConAcceso(sb, { tokSetup: setup.token, tokActor: eng.token, idActor: eng.id, nombre: `QA Historial G Ciento Veintiseis ${marca}` });
    const unidad = await construirUnidad(sb, {
      tok: setup.token, cat, finca: finca.id, run, nombreUnidad: `QA G126 ${marca} U`, serial,
      nombres: Array.from({ length: SENSORES }, (_, i) => nombreSensor(`QA G126 ${marca}`, 'U', i + 1)),
      alCrearDispositivo: async () => { dispositivo = true; ev.sandbox.aislamiento = await sb.aislamiento(serial); },
    });
    // Lecturas adicionales por sensor con timestamps y valores distintos (RF-53, contrato actual).
    for (const s of unidad.sensores) for (let k = 1; k < LECTURAS_POR_SENSOR; k++) {
      const l = sb.need(await sb.req('POST', '/iot/telemetria', { body: cuerpoLectura({ idDispositivo: unidad.id_dispositivo, idSensor: s.id, serial, timestamp: new Date(Date.now() - (30 + k * 120) * 1000).toISOString(), valor: 20 + k }) }), 201, `Lectura ${k + 1} de ${s.nombre}`);
      if (l.estado_calidad !== 'LECTURA_VALIDA') throw Error(`Lectura adicional no quedó LECTURA_VALIDA (${l.estado_calidad})`);
    }
    const idsSensor = unidad.sensores.map(s => Number(s.id));
    const esperadas = SENSORES * LECTURAS_POR_SENSOR;
    ev.datos = { finca, id_infraestructura: unidad.id, sensores: idsSensor, lecturas_controladas: esperadas, origen: 'construido en el RUN con APIs oficiales' };
    // Periodo: fecha_fin no puede ser futura para el servidor; si su fecha local va por detrás de UTC se usa el día anterior.
    const hoyUtc = new Date().toISOString().slice(0, 10);
    const ayerUtc = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
    let fechaFin = hoyUtc;
    const sonda = q => sb.req('GET', `/iot/monitoreo/historial?fecha_inicio=${q.ini}&fecha_fin=${q.fin}&id_infraestructura=${unidad.id}&por_pagina=500`, { token: eng.token });
    let r = await sonda({ ini: new Date(Date.now() - 2 * 86400000).toISOString().slice(0, 10), fin: fechaFin });
    if (r.status !== 200 && /FECHA_FIN_FUTURA/.test(JSON.stringify(r.data ?? ''))) { fechaFin = ayerUtc; r = await sonda({ ini: new Date(Date.now() - 3 * 86400000).toISOString().slice(0, 10), fin: fechaFin }); }
    const fechaInicio = new Date(Date.parse(fechaFin) - 2 * 86400000).toISOString().slice(0, 10);
    const visibles = (r.data?.items || []).filter(x => idsSensor.includes(Number(x.id_sensor))).length;
    ev.datos.periodo = { fecha_inicio: fechaInicio, fecha_fin: fechaFin, lecturas_visibles_en_historial: visibles };
    pre('el historial del Ingeniero devuelve las lecturas del conjunto controlado', r.status === 200 && visibles === esperadas, `HTTP ${r.status}; visibles ${visibles} de ${esperadas}`);

    // ---- SNAPSHOT 1 ----------------------------------------------------------------------------
    const snapshot = async () => {
      const out = {};
      for (const [t, { pk }] of Object.entries(TABLAS)) out[t] = snapshotTabla(await sb.sql(consultaSnapshot(t, idsSensor)), pk);
      return out;
    };
    const antes = await snapshot();
    pre('snapshot inicial consultable y con visibilidad completa del conjunto (sin RLS en modulo3)', Object.values(antes).every(Boolean) && antes.telemetrias.n === esperadas, `tablas no consultables o telemetrias=${antes.telemetrias?.n ?? 'null'} de ${esperadas}`);

    // ---- CONSULTAS DE HISTORIAL (Newman) ---------------------------------------------------------
    ev.fase = 'ESCENARIOS'; guardar();
    const vars = { base_url: gate.api, run_id: run, sandbox_secret: v.QA_SANDBOX_SECRET, autorizado_run: 'SI', token: eng.token, fecha_inicio: fechaInicio, fecha_fin: fechaFin, id_area: unidad.id, id_sensor: idsSensor[0], pagina: '1', ids_sensores: JSON.stringify(idsSensor) };
    const nw = await correrNewman(newman, JSON.parse(fs.readFileSync(COLLECTION, 'utf8')), vars, { limpiar });
    ev.aserciones.push(...nw.aserciones); ev.consultas = nw.muestras;
    for (const e of nw.errores) { ev.dependencias.push(e.mensaje); (ev.bloqueos['TC-M03-255'] ??= []).push(e.mensaje); }

    // ---- SNAPSHOT 2 y comparación ----------------------------------------------------------------
    const despues = await snapshot();
    pre('snapshot final consultable', Object.values(despues).every(Boolean), 'alguna tabla no fue consultable');
    if (Object.values(antes).every(Boolean) && Object.values(despues).every(Boolean)) {
      const dif = Object.fromEntries(Object.keys(TABLAS).map(t => [t, compararTabla(antes[t], despues[t])]));
      ev.snapshots = Object.fromEntries(Object.keys(TABLAS).map(t => [t, { filas_antes: antes[t].n, filas_despues: despues[t].n, hash_antes: antes[t].hash, hash_despues: despues[t].hash, ...dif[t] }]));
      const tel = dif.telemetrias;
      const asociadas = ['vinculaciones_lecturas', 'telemetria_calidad'].map(t => dif[t]);
      const asercion = (id, nombre, ok, detalle) => ev.aserciones.push({ herramienta: 'Ejecutor', caso: 'TC-M03-255', tipo: 'ASSERT', id, variante: null, nombre: `[TC-M03-255][ASSERT][${id}] ${nombre}`, ok, evidencia: true, error: ok ? undefined : detalle });
      asercion('API-255-01', 'las consultas no crean lecturas históricas', !tel.creadas.length, `lecturas nuevas: ${tel.creadas.join(', ')}`);
      asercion('API-255-02', 'las consultas no eliminan lecturas históricas', !tel.eliminadas.length, `lecturas eliminadas: ${tel.eliminadas.join(', ')}`);
      asercion('API-255-03', 'las consultas no modifican valores ni atributos de las lecturas (snapshot idéntico)', !tel.modificadas.length && tel.identicas, `modificadas: ${JSON.stringify(tel.modificadas)}`);
      asercion('API-255-04', 'vinculaciones y evaluaciones de calidad de esas lecturas idénticas', asociadas.every(x => x.identicas), JSON.stringify(Object.fromEntries(['vinculaciones_lecturas', 'telemetria_calidad'].map((t, i) => [t, asociadas[i]]))));
    }
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
    ev.veredicto = veredictoCasos({ casos: CASOS, requeridas: REQUERIDAS, estado: ev.estado, rollback: !!ev.sandbox.rollback, aserciones: ev.aserciones, bloqueos: ev.bloqueos });
    ev.fin = new Date().toISOString(); guardar();
    fs.writeFileSync(path.join(out, nombreInforme(GRUPO, n)), limpiar(informe({ grupo: GRUPO, n, run, ev, casos: CASOS, extra: ev.snapshots ? `\n## Snapshots\n${Object.entries(ev.snapshots).map(([t, s]) => `- ${t}: ${s.filas_antes} → ${s.filas_despues} filas · SHA-256 ${s.hash_antes.slice(0, 16)}… → ${s.hash_despues.slice(0, 16)}… · creadas ${s.creadas.length}, eliminadas ${s.eliminadas.length}, modificadas ${s.modificadas.length}`).join('\n')}\n` : '' })));
  }
  console.log(`${GRUPO}: ${ev.estado} — ${out}`); return ev.estado === 'CONCLUIDA' ? 0 : 4;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let code; try { const a = argumentos(process.argv.slice(2)); code = a.modo === 'local' ? local() : await ejecutar(a); } catch (e) { console.error(e.message); code = 2; } process.exitCode = code;
}
