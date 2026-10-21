#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { args, gate, parseEnv, ENV_PATH, ROOT, evidence, request, verdict } from '../TC-M03-G108/qa_lote6_base.mjs';

export const CASOS = ['TC-M03-263'];
const DIR = path.dirname(fileURLToPath(import.meta.url));
const COLLECTION = path.join(DIR, 'TC-M03-G110.postman_collection.json');
const require = createRequire(path.join(ROOT, 'package.json'));
function newmanModule() {
  try { return require('newman'); } catch {
    const npm = spawnSync('npm', ['root', '-g'], { encoding: 'utf8', shell: process.platform === 'win32' });
    if (npm.status) throw Error('Newman no disponible');
    return require(path.join(npm.stdout.trim(), 'newman'));
  }
}
export function witnessSql(serial) {
  if (!/^[A-Za-z0-9_-]{1,50}$/.test(serial)) throw Error('Serial inválido');
  return `SELECT count(*) AS n FROM auditoria.logs_dml WHERE esquema_afectado='modulo9' AND tabla_afectada='dispositivos_iot' AND tipo_operacion='INSERT' AND datos_nuevos->>'serial'='${serial}'`;
}
export function seriesSql(id, sensor) {
  if (![id, sensor].every(x => Number.isSafeInteger(Number(x)) && Number(x) > 0)) throw Error('IDs inválidos');
  return `SELECT id_telemetria, id_sensor, COALESCE(valor_ajustado,valor_crudo) AS valor, unidad_medida, timestamp_captura FROM modulo3.telemetrias WHERE id_telemetria=${Number(id)} AND id_sensor=${Number(sensor)} ORDER BY timestamp_captura DESC LIMIT 1`;
}
export function same(a, b) { return !!a && !!b && Number(a.valor) === Number(b.valor) && a.unidad === b.unidad && Date.parse(a.timestamp) === Date.parse(b.timestamp); }
export function bitacoraPath(paths) {
  return Object.entries(paths || {}).find(([p, methods]) => /bitacora|auditoria/i.test(p) && /monitoreo|consistencia|historial/i.test(p + JSON.stringify(methods.get || {})) && !p.includes('{') && methods.get && !(methods.get.parameters || []).some(x => x.required))?.[0] || null;
}
function local() {
  const v = parseEnv(fs.readFileSync(ENV_PATH, 'utf8'));
  const col = JSON.parse(fs.readFileSync(COLLECTION, 'utf8'));
  const c = []; const ck = (n, ok) => c.push([n, !!ok]);
  ck('caso y RF oficiales', CASOS.join() === 'TC-M03-263' && col.item.length === 2);
  ck('autorización desactivada', v.QA_AUTORIZADO === 'NO');
  ck('barrera ejecutor', !gate(v, { ambiente: 'TEST', autorizacion: 'DEV-12345678', tipo: 'evaluacion', efectos: ['notificacion-login'] }, { login: true, sandbox: true }).ok);
  ck('barrera DEV', !gate({ ...v, QA_AUTORIZADO: 'SI' }, { ambiente: 'DEV', autorizacion: 'DEV-12345678', tipo: 'evaluacion', efectos: ['notificacion-login'] }, { login: true, sandbox: true }).ok);
  ck('guardia Newman', JSON.stringify(col.event).includes('BLOQUEO_G110'));
  ck('valor, unidad, timestamp en ambas vistas', col.item.every(i => ['expected_value', 'expected_unit', 'expected_ts'].every(x => JSON.stringify(i).includes(x))));
  try { for (const e of [...col.event, ...col.item.flatMap(i => i.event || [])]) new Function(e.script.exec.join('\n')); ck('scripts Postman', true); } catch { ck('scripts Postman', false); }
  ck('SQL limita sensor y lectura', /id_telemetria=2 AND id_sensor=3/.test(seriesSql(2, 3)));
  ck('SQL testigo de RUN', witnessSql('QA-G110-123').includes('QA-G110-123'));
  ck('comparación temporal y unidad', same({ valor: 1, unidad: '°C', timestamp: '2026-01-01T00:00:00Z' }, { valor: '1', unidad: '°C', timestamp: '2025-12-31T19:00:00-05:00' }) && !same({ valor: 1, unidad: '°C', timestamp: '2026-01-01' }, { valor: 2, unidad: '°C', timestamp: '2026-01-01' }));
  ck('bitácora solo por contrato', bitacoraPath({ '/iot/monitoreo/dashboard': { get: {} } }) === null && bitacoraPath({ '/iot/monitoreo/bitacora-consistencia': { get: {} } }) !== null);
  ck('PRE prevalece sobre ASSERT', verdict('CONCLUIDA', [{ ok: false }], [{ ok: false, observado: true }]) === 'BLOQUEADO');
  ck('sintaxis Node', spawnSync(process.execPath, ['--check', fileURLToPath(import.meta.url)]).status === 0);
  ck('sin RESULTADOS', !fs.existsSync(path.join(DIR, 'RESULTADOS')));
  ck('sin secretos literales', [COLLECTION, fileURLToPath(import.meta.url)].every(p => ![v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_PROD_PASSWORD].filter(x => x?.length > 5).some(x => fs.readFileSync(p, 'utf8').includes(x))));
  c.forEach(([n, ok]) => console.log(`${ok ? 'OK' : 'FALLO'} ${n}`));
  console.log(`G110 ${c.filter(x => x[1]).length}/${c.length}`);
  return c.every(x => x[1]) ? 0 : 1;
}
async function execute(a) {
  const v = parseEnv(fs.readFileSync(ENV_PATH, 'utf8'));
  const g = gate(v, a, { login: true, sandbox: true });
  if (!(v.QA_SETUP_EMAIL && (v.QA_SETUP_PASSWORD || v.QA_COMMON_PASSWORD))) g.errores.push('credenciales preparador QA');
  g.ok = !g.errores.length;
  if (!g.ok) { console.error(`EJECUCIÓN NO AUTORIZADA: ${g.errores.join(', ')}`); return 2; }
  const c = evidence(DIR, 110, CASOS, a, v); const { ev, run } = c;
  ev.rf = 'RF-58 / RF-59'; ev.cu = 'CU04';
  const stamp = new Date().toISOString().replace(/\D/g, '').slice(0, 14);
  const serial = `${v.QA_DEVICE_PREFIX || 'QAAUTO'}-G110-${stamp}`.slice(0, 50);
  c.secrets.push(serial);
  const req = (method, route, options = {}) => request(g.api, run, v.QA_SANDBOX_SECRET, method, route, options);
  const sql = (query, rid = run) => request(g.api, rid, v.QA_SANDBOX_SECRET, 'POST', '/test-control/query', { body: { query } });
  const outside = async (query, suffix) => { const rid = `${run}-${suffix}`; try { return await sql(query, rid); } finally { await req('DELETE', `/test-control/runs/${rid}`, { control: true }); } };
  const need = (r, status, name) => { if (r.status !== status) throw Error(`PRE: ${name} HTTP ${r.status}`); return r.data; };
  const count = r => r.status === 200 && Number.isSafeInteger(Number(r.data?.data?.[0]?.n)) ? Number(r.data.data[0].n) : null;
  let opened = false, created = false, sensorId;
  try {
    const probe = await req('DELETE', `/test-control/runs/${run}-PREFLIGHT`, { control: true });
    if (probe.status !== 404) throw Error('PRE: sandbox de TEST no verificable');
    opened = true;
    const login = async (email, pass) => { const d = need(await req('POST', '/sesiones/', { body: { correo_electronico: email, contrasena: pass } }), 200, 'login QA'); if (!d?.token) throw Error('PRE: token QA'); c.secrets.push(d.token); return d.token; };
    const setup = await login(v.QA_SETUP_EMAIL, v.QA_SETUP_PASSWORD || v.QA_COMMON_PASSWORD);
    const prod = await login(v.QA_PROD_EMAIL, v.QA_PROD_PASSWORD || v.QA_COMMON_PASSWORD);
    const me = need(await req('GET', '/usuarios/me', { token: prod }), 200, 'Productor');
    const admin = need(await req('GET', '/usuarios/me', { token: setup }), 200, 'Preparador');
    if (!/productor/i.test(me.nombre_rol || '') || !/administrador/i.test(admin.nombre_rol || '')) throw Error('PRE: roles QA insuficientes');
    const metaSql = "SELECT c.relrowsecurity AS rls, has_table_privilege(current_user,'auditoria.logs_dml','SELECT') AS lectura, EXISTS (SELECT 1 FROM pg_trigger t WHERE t.tgrelid='modulo9.dispositivos_iot'::regclass AND NOT t.tgisinternal AND t.tgenabled<>'D' AND pg_get_triggerdef(t.oid) ILIKE '%audit%') AS trigger_activo FROM pg_class c WHERE c.oid='auditoria.logs_dml'::regclass";
    const meta = need(await outside(metaSql, 'META'), 200, 'permisos testigo')?.data?.[0];
    const control = count(await outside('SELECT count(*) AS n FROM auditoria.logs_dml', 'CONTROL'));
    if (meta?.rls !== false || meta?.lectura !== true || meta?.trigger_activo !== true || control === null || control < 1) throw Error('PRE: testigo externo sin control positivo y permisos comprobados');
    const fp = new Set((need(await req('GET', '/configuracion/fincas', { token: prod }), 200, 'fincas Productor').items || []).map(x => Number(x.id_finca)));
    const fa = (need(await req('GET', '/configuracion/fincas', { token: setup }), 200, 'fincas Preparador').items || []).map(x => Number(x.id_finca));
    let finca = fa.find(id => fp.has(id));
    if (!finca) finca = need(await req('POST', '/configuracion/fincas', { token: setup, body: { nombre: `QA G110 ${stamp}`.replace(/\d/g, d => 'abcdefghij'[Number(d)]), ubicacion: { departamento: 'Huila', municipio: 'Neiva', vereda: 'QA', latitud: 2.9273, longitud: -75.2819 }, tamano_h: 1, id_usuario: me.id_usuario } }), 201, 'crear finca').id_finca;
    const tipo = (need(await req('GET', '/configuracion/tipos-area?solo_activos=true', { token: setup }), 200, 'tipos área').items || []).find(x => x.es_activo);
    const especie = (need(await req('GET', '/configuracion/especies?solo_activas=true', { token: setup }), 200, 'especies').items || []).find(x => x.es_activo);
    const tipoDisp = (need(await req('GET', '/configuracion/tipos-dispositivo-iot', { token: setup }), 200, 'tipos dispositivo').items || []).find(x => x.categoria === 'SENSOR');
    const rango = (need(await req('GET', '/configuracion/sensores/rangos-calibracion', { token: setup }), 200, 'rango calibración').items || []).find(x => x.categoria === 'TEMPERATURA');
    if (![tipo, especie, tipoDisp, rango].every(Boolean)) throw Error('PRE: faltan catálogos de sensor');
    const area = need(await req('POST', '/configuracion/infraestructuras', { token: setup, body: { nombre_infraestructura: `QA G110 ${stamp}`, tipo_area: tipo.nombre, superficie: 25, finca_id: finca, descripcion_infraestructura: `QA ${run}`, especie_id: especie.id_especie } }), 201, 'crear área');
    const disp = need(await req('POST', '/configuracion/dispositivos-iot', { token: setup, body: { serial, descripcion: `QA ${run}`, id_infraestructura: area.id_infraestructura, id_tipo_dispositivo: tipoDisp.id_tipo_dispositivo, es_activo: true } }), 201, 'crear dispositivo');
    created = true;
    const inside = count(await sql(witnessSql(serial)));
    const external = count(await outside(witnessSql(serial), 'SONDA'));
    ev.sandbox.aislamiento = { dentro: inside, fuera: external, control };
    if (inside !== 1 || external !== 0) throw Error('PRE: aislamiento del testigo no verificado');
    const sensor = need(await req('POST', `/configuracion/dispositivos-iot/${disp.id_dispositivo_iot}/sensores`, { token: setup, body: { nombre: `QA G110 ${stamp} S1`, categoria: 'TEMPERATURA' } }), 201, 'crear sensor');
    sensorId = sensor.id_sensores;
    need(await req('POST', `/configuracion/sensores/${sensorId}/asociar`, { token: setup, body: { id_dispositivo_iot: disp.id_dispositivo_iot, id_infraestructura: area.id_infraestructura, punto_instalacion: 'QA G110' } }), 201, 'asociar sensor');
    need(await req('POST', `/configuracion/sensores/${sensorId}/calibrar`, { token: setup, body: { id_dispositivo_iot: disp.id_dispositivo_iot, id_infraestructura: area.id_infraestructura, valor_referencia: Number(((Number(rango.valor_min) + Number(rango.valor_max)) / 2).toFixed(2)), ganancia: 1, offset: 0, fecha_calibracion: new Date(Date.now() - 600000).toISOString(), observaciones: `QA ${run}`, modo_calibracion: 'SENSOR' } }), 201, 'calibrar sensor');
    need(await req('GET', `/configuracion/infraestructuras/${area.id_infraestructura}`, { token: prod }), 200, 'visibilidad Productor');
    const fecha = new Date().toISOString();
    const ing = await req('POST', '/iot/telemetria', { body: { device_id: disp.id_dispositivo_iot, sensor_id: sensorId, tipo_variable: 'TEMPERATURA_AMBIENTAL', valor: 25, unidad: '°C', timestamp_captura: fecha, access_key: serial, origen: 'TIEMPO_REAL', estado_conectividad: true } });
    const ingesta = need(ing, 201, 'ingesta oficial');
    const row = need(await sql(seriesSql(ingesta.id_telemetria, sensorId)), 200, 'serie temporal persistida')?.data?.[0];
    if (!row || Number(row.id_telemetria) !== Number(ingesta.id_telemetria)) throw Error('PRE: lectura del RUN no consultable en serie temporal');
    const model = need(await sql(`SELECT id_sensor FROM modulo3.estados_actuales_sensores WHERE id_sensor=${Number(sensorId)} LIMIT 1`), 200, 'modelo de lectura actual')?.data?.[0];
    if (Number(model?.id_sensor) !== Number(sensorId)) throw Error('PRE: modelo de lectura actual del RUN no materializado dentro del sandbox; un proceso post-commit externo puede no ver la transacción aislada');
    ev.pre.push({ nombre: 'sensor, lectura y serie temporal del RUN preparados mediante API', ok: true });
    ev.info.push({ nombre: 'fuente persistente del RUN', id_sensor: sensorId, id_telemetria: row.id_telemetria, valor: row.valor, unidad: row.unidad_medida, timestamp: row.timestamp_captura });
    const dashPath = `/iot/monitoreo/dashboard/${area.id_infraestructura}?pagina=1&por_pagina=50`;
    const histPath = `/iot/monitoreo/historial?fecha_inicio=${fecha.slice(0, 10)}&fecha_fin=${fecha.slice(0, 10)}&sensor_id=${sensorId}&pagina=1&por_pagina=100&orden=DESC`;
    const firstDash = await req('GET', dashPath, { token: prod });
    const firstHist = await req('GET', histPath, { token: prod });
    const d = firstDash.data?.sensores?.find(x => Number(x.id_sensor) === Number(sensorId));
    const h = firstHist.data?.items?.find(x => Number(x.id_telemetria) === Number(row.id_telemetria));
    const expected = { valor: row.valor, unidad: row.unidad_medida, timestamp: row.timestamp_captura };
    ev.info.push({ nombre: 'vistas iniciales', dashboard: d && { valor: d.ultimo_valor, unidad: d.ultima_unidad, timestamp: d.ultimo_timestamp_captura }, historial: h && { valor: h.valor, unidad: h.unidad_medida, timestamp: h.timestamp_captura } });
    const initialDifference = firstDash.status === 200 && firstHist.status === 200 && d && h && (!same({ valor: d.ultimo_valor, unidad: d.ultima_unidad, timestamp: d.ultimo_timestamp_captura }, expected) || !same({ valor: h.valor, unidad: h.unidad_medida, timestamp: h.timestamp_captura }, expected));
    ev.info.push({ nombre: 'discrepancia inicial observable', valor: !!initialDifference });
    if (initialDifference) await new Promise(resolve => setTimeout(resolve, 2000));
    const vars = { base_url: g.api, test_base_url: g.api, qa_autorizado: v.QA_AUTORIZADO, ambiente: a.ambiente, autorizacion: a.autorizacion, autorizado_run: 'SI', run_id: run, sandbox_secret: v.QA_SANDBOX_SECRET, token: prod, id_infraestructura: String(area.id_infraestructura), sensor_id: String(sensorId), id_telemetria: String(row.id_telemetria), expected_value: String(row.valor), expected_unit: row.unidad_medida, expected_ts: row.timestamp_captura, fecha_inicio: fecha.slice(0, 10), fecha_fin: fecha.slice(0, 10) };
    const collection = JSON.parse(fs.readFileSync(COLLECTION, 'utf8'));
    const nr = await new Promise(resolve => newmanModule().run({ collection, environment: { values: Object.entries(vars).map(([key, value]) => ({ key, value })) }, reporters: [], silent: true }, (error, summary) => resolve({ error, summary })));
    if (nr.error) throw Error(`AUTOMATIZACION: Newman ${nr.error.message}`);
    if ((nr.summary?.run?.failures || []).some(x => x.error?.name !== 'AssertionError')) throw Error('AUTOMATIZACION: fallo técnico Newman');
    for (const x of nr.summary?.run?.executions || []) for (const y of x.assertions || []) (y.assertion.includes('[PRE]') ? ev.pre : ev.asserts).push({ nombre: `${x.item.name}: ${y.assertion}`, ok: !y.error, observado: !y.assertion.includes('[PRE]'), detalle: y.error?.message });
    if (ev.asserts.length !== 7) throw Error('AUTOMATIZACION: faltan aserciones de API');
    // La rama FA-12 requiere una discrepancia real. No se altera el read-model ni la serie para fabricarla.
    ev.pre.push({ nombre: 'discrepancia real observada para evaluar FA-12/E8', ok: !!initialDifference || ev.asserts.some(x => !x.ok) });
    if (initialDifference) {
      ev.asserts.push({ nombre: '[TC-M03-263][ASSERT] vista inconsistente corregida desde la serie persistente', ok: ev.asserts.every(x => x.ok), observado: true });
      const openapi = await req('GET', '/openapi.json');
      const route = openapi.status === 200 ? bitacoraPath(openapi.data?.paths) : null;
      if (!route) { ev.pre.push({ nombre: 'bitácora oficial de consistencia consultable', ok: false }); ev.dependencias.push('Falta ruta GET oficial de bitácora de consistencia para verificar el registro de FA-12/E8.'); }
      else {
        const log = await req('GET', route, { token: prod });
        const rows = Array.isArray(log.data) ? log.data : ['items', 'eventos', 'data', 'registros'].map(k => log.data?.[k]).find(Array.isArray);
        const correlatable = Array.isArray(rows) && rows.some(x => Number.isSafeInteger(Number(x.id_sensor ?? x.sensor_id)) && !Number.isNaN(Date.parse(x.fecha_evento ?? x.timestamp ?? x.created_at)) && !!(x.tipo_evento ?? x.evento ?? x.codigo));
        if (log.status !== 200 || !correlatable) ev.pre.push({ nombre: 'bitácora oficial legible con control correlacionable', ok: false });
        else ev.asserts.push({ nombre: '[TC-M03-263][ASSERT] evento de corrección registrado para sensor y RUN', ok: rows.some(x => Number(x.id_sensor ?? x.sensor_id) === Number(sensorId) && Date.parse(x.fecha_evento ?? x.timestamp ?? x.created_at) >= Date.parse(fecha) && /consisten|discrepan|correc|reconcil|reparac/i.test(String(x.tipo_evento ?? x.evento ?? x.codigo) + ' ' + String(x.detalle ?? x.descripcion ?? ''))), observado: true });
      }
    } else ev.dependencias.push('FA-12/E8: falta mecanismo oficial para provocar una discrepancia aislada; la coherencia basal sí se compara contra la serie persistente.');
    ev.estado = 'CONCLUIDA';
  } catch (e) { ev.estado = 'INTERRUMPIDA'; ev.dependencias.push(String(e.message)); }
  finally {
    if (opened) try {
      const x = await req('DELETE', `/test-control/runs/${run}`, { control: true });
      const y = await req('DELETE', `/test-control/runs/${run}`, { control: true });
      const after = created ? count(await outside(witnessSql(serial), 'POST')) : 0;
      ev.sandbox.rollback = x.status === 200 && y.status === 404 && after === 0;
    } catch { ev.sandbox.rollback = false; }
    c.finish();
  }
  return ev.veredicto === 'APROBADO' ? 0 : 4;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { const a = args(process.argv.slice(2)); process.exitCode = a.modo === 'local' ? local() : await execute(a); }
  catch (e) { console.error(e.message); process.exitCode = 2; }
}
