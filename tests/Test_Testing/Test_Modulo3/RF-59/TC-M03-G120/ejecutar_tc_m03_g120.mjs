#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { args, context, ENV_PATH, parseEnv, query, secretsFree, ROOT } from './rf59_base.mjs';

export const CASOS = ['TC-M03-241', 'TC-M03-242', 'TC-M03-243'];
const DIR = path.dirname(fileURLToPath(import.meta.url));
const HORA = 3_600_000;
export function fixture({ device, sensor, serial, capture, sent, origin = 'BUFFER_LOCAL', value = 25 }) {
  if (!Number.isSafeInteger(device) || !Number.isSafeInteger(sensor) || !Number.isFinite(Date.parse(capture))) throw Error('Fixture inválido');
  return { device_id: device, sensor_id: sensor, tipo_variable: 'TEMPERATURA_AMBIENTAL', valor: value, unidad: '°C', timestamp_captura: capture, ...(sent?{timestamp_envio:sent}:{}), access_key: serial, origen: origin, estado_conectividad: true };
}
export function rowsFor(items, sensor, capture) {
  return items.filter(x => Number(x.id_sensor) === sensor && Date.parse(x.timestamp_captura) === Date.parse(capture));
}
export function exactDelay(capture, send, hours) { return Date.parse(send) - Date.parse(capture) === hours * HORA; }
export function synchronizationField(openapi) {
  const resolve = schema => {
    if (!schema) return null;
    if (!schema.$ref) return schema;
    return schema.$ref.split('/').slice(1).reduce((v,k)=>v?.[k],openapi);
  };
  const response=openapi?.paths?.['/iot/telemetria/batch']?.post?.responses?.['200']?.content?.['application/json']?.schema;
  const detail=resolve(resolve(response)?.properties?.detalle?.items);
  return Object.keys(detail?.properties||{}).find(k=>/sincroniz/i.test(k)&&/fecha|hora|momento|timestamp/i.test(k))||null;
}
export function assess({ items, interval, real, duplicate, edges }) {
  const assert = [];
  const push = (caso, name, ok) => assert.push({ caso, nombre: `[${caso}][ASSERT] ${name}`, ok: !!ok, observado: true });
  push(CASOS[0], 'intervalo completo sin vacíos', interval.every(ts => rowsFor(items, real.sensor, ts).length === 1));
  push(CASOS[0], 'timestamp original de BUFFER_LOCAL', interval.every(ts => rowsFor(items, real.sensor, ts)[0]?.timestamp_captura && Date.parse(rowsFor(items, real.sensor, ts)[0].timestamp_captura) === Date.parse(ts)));
  push(CASOS[0], 'origen_dato BUFFER_LOCAL', interval.every(ts => rowsFor(items, real.sensor, ts)[0]?.origen_dato === 'BUFFER_LOCAL'));
  push(CASOS[0], 'distinción frente a TIEMPO_REAL', rowsFor(items, real.sensor, real.capture).some(x => x.origen_dato === 'TIEMPO_REAL'));
  const dup = rowsFor(items, real.sensor, duplicate);
  push(CASOS[1], 'única lectura lógica tras segunda sincronización', dup.length === 1);
  push(CASOS[1], 'timestamp original tras duplicado', dup.length === 1 && Date.parse(dup[0].timestamp_captura) === Date.parse(duplicate));
  for (const [index, hours] of [23, 24].entries()) {
    const ts = edges[index], rows = rowsFor(items, real.sensor, ts);
    push(CASOS[2], `integración de captura ${hours} h`, rows.length === 1);
    push(CASOS[2], `timestamp original ${hours} h`, rows.length === 1 && Date.parse(rows[0].timestamp_captura) === Date.parse(ts));
  }
  return assert;
}
function local() {
  const v = parseEnv(fs.readFileSync(ENV_PATH, 'utf8'));
  const router=fs.readFileSync(path.join(ROOT,'src/telemetry/infrastructure/routers/telemetria_router.py'),'utf8');
  const dto=fs.readFileSync(path.join(ROOT,'src/telemetry/infrastructure/dto/ingerir_telemetria_dto.py'),'utf8');
  const checks = [
    ['casos exactos', CASOS.join() === 'TC-M03-241,TC-M03-242,TC-M03-243'],
    ['QA desautorizado', v.QA_AUTORIZADO === 'NO'],
    ['fixture contrato batch', ['device_id','sensor_id','timestamp_captura','access_key','origen'].every(k => Object.hasOwn(fixture({ device: 1, sensor: 2, serial: 'QA', capture: new Date().toISOString() }), k))],
    ['contrato oficial flujo C y timestamp_envio',router.includes('"/batch"')&&dto.includes('class IngerirTelemetriaBatchDTO')&&dto.includes('timestamp_envio')],
    ['sin RESULTADOS', !fs.existsSync(path.join(DIR, 'RESULTADOS'))],
    ['sin secretos literales', [fileURLToPath(import.meta.url), path.join(DIR, 'rf59_base.mjs')].every(p => secretsFree(fs.readFileSync(p, 'utf8'), [v.QA_SANDBOX_SECRET,v.QA_COMMON_PASSWORD,v.QA_PROD_PASSWORD]))],
  ];
  checks.forEach(([n,ok]) => console.log(`${ok?'OK':'FALLO'} ${n}`));
  console.log(`G120 ${checks.filter(x => x[1]).length}/${checks.length}`);
  return checks.every(x => x[1]) ? 0 : 1;
}
async function execute(a) {
  const x = await context(120, CASOS, DIR, a);
  if (x.blocked) { console.error(`EJECUCIÓN NO AUTORIZADA: ${x.blocked.join(', ')}`); return 2; }
  const { c, req, open, actors, prepareSensor, close } = x;
  try {
    await open();
    const auth = await actors();
    const sensor = await prepareSensor(auth);
    c.ev.pre.push({ nombre: 'sensor QA aislado y visible al Productor', ok: true });
    const now = Date.now();
    const interval = Array.from({ length: 3 }, (_, i) => new Date(now - 12*HORA + i*60_000).toISOString());
    const duplicate = interval[1];
    const real = { sensor: sensor.sensor, capture: new Date(now - 30_000).toISOString() };
    const edges = [23,24].map(h => new Date(now - h*HORA).toISOString());
    const sendTime = new Date(now).toISOString();
    const f = (ts,sent=sendTime) => fixture({ device: sensor.device, sensor: sensor.sensor, serial: sensor.serial, capture: ts, sent });
    c.ev.pre.push({caso:CASOS[2],nombre:'capturas de 23 h y exactamente 24 h preparadas frente al envío',ok:exactDelay(edges[0],sendTime,23)&&exactDelay(edges[1],sendTime,24)});
    const batch = await req('POST', '/iot/telemetria/batch', { body: { registros: [...interval.map(ts=>f(ts)),...edges.map(ts=>f(ts))] } });
    if ([401,403,404,422].includes(batch.status)) throw Error(`PRE: contrato de sincronización BUFFER_LOCAL/DEV-06 no disponible HTTP ${batch.status}`);
    c.ev.asserts.push({ caso: CASOS[0], nombre: '[TC-M03-241][ASSERT] lote BUFFER_LOCAL aceptado', ok: batch.status === 200 && batch.data?.aceptados === 5 && batch.data?.rechazados === 0, observado: true });
    const second = await req('POST', '/iot/telemetria/batch', { body: { registros: [f(duplicate,new Date().toISOString())] } });
    if ([401,403,404,422].includes(second.status)) throw Error(`PRE: segunda sincronización no ejecutable HTTP ${second.status}`);
    c.ev.info.push({ nombre: 'segunda sincronización', status: second.status, aceptados: second.data?.aceptados, duplicados: second.data?.duplicados });
    const realtime = await req('POST', '/iot/telemetria', { body: fixture({ device: sensor.device, sensor: sensor.sensor, serial: sensor.serial, capture: real.capture, origin: 'TIEMPO_REAL' }) });
    if ([401,403,404,422].includes(realtime.status)) throw Error(`PRE: contraste TIEMPO_REAL no ejecutable HTTP ${realtime.status}`);
    c.ev.asserts.push({ caso: CASOS[0], nombre: '[TC-M03-241][ASSERT] contraste TIEMPO_REAL aceptado', ok: realtime.status === 201, observado: true });
    const start = edges[1].slice(0,10), end = new Date(now).toISOString().slice(0,10);
    const history = await req('GET', query('/iot/monitoreo/historial', { fecha_inicio:start, fecha_fin:end, sensor_id:sensor.sensor, por_pagina:100, pagina:1, orden:'ASC' }), { token: auth.prod });
    if (history.status !== 200 || !Array.isArray(history.data?.items)) throw Error(`PRE: historial consultable HTTP ${history.status}`);
    const openapi=await req('GET','/openapi.json');
    const field=openapi.status===200?synchronizationField(openapi.data):null;
    const syncRows=edges.map(ts=>batch.data?.detalle?.find(x=>Date.parse(x.timestamp_captura)===Date.parse(ts)));
    const syncTimes=syncRows.map(x=>field?x?.[field]:null);
    c.ev.pre.push({caso:CASOS[2],nombre:'momento de sincronización registrado por el contrato oficial',ok:syncTimes.every(x=>Number.isFinite(Date.parse(x)))});
    if(!c.ev.pre.at(-1).ok)c.ev.dependencias.push('TC-M03-243: el contrato de respuesta del flujo C no expone el momento de sincronización; timestamp_procesamiento de ingesta no equivale a sincronización RF-54.');
    else for(const [i,hours] of [23,24].entries())c.ev.asserts.push({caso:CASOS[2],nombre:`[TC-M03-243][ASSERT] retraso de ${hours} h comprobable con momento de sincronización`,ok:Date.parse(syncTimes[i])>=Date.parse(edges[i]) && Math.abs((Date.parse(syncTimes[i])-Date.parse(edges[i]))/HORA-hours)<1/60,observado:true});
    c.ev.info.push({ nombre: 'captura, envío y sincronización declarada', edges, sendTime, campo_sincronizacion:field, syncTimes });
    c.ev.asserts.push(...assess({ items: history.data.items, interval, real, duplicate, edges }));
    c.ev.estado = 'CONCLUIDA';
  } catch (e) { c.ev.estado = 'INTERRUMPIDA'; c.ev.dependencias.push(String(e.message)); }
  finally { await close(); c.finish(); }
  return c.ev.veredicto === 'APROBADO' ? 0 : 4;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { const a = args(process.argv.slice(2)); process.exitCode = a.modo === 'local' ? local() : await execute(a); }
  catch (e) { console.error(e.message); process.exitCode = 2; }
}
