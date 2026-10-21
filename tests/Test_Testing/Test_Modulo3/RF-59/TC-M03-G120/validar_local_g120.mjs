import test from 'node:test';
import assert from 'node:assert/strict';
import { CASOS, fixture, rowsFor, exactDelay, assess, synchronizationField } from './ejecutar_tc_m03_g120.mjs';
import { count, witness, query, verdict } from './rf59_base.mjs';

test('catálogo y fixture del flujo C', () => {
  assert.deepEqual(CASOS, ['TC-M03-241','TC-M03-242','TC-M03-243']);
  assert.equal(fixture({ device:1,sensor:2,serial:'QA',capture:'2026-10-16T00:00:00Z' }).origen, 'BUFFER_LOCAL');
  assert.throws(() => fixture({ device:1,sensor:2,serial:'QA',capture:'invalid' }));
});
test('timestamp y duplicados se comparan por sensor y tiempo real', () => {
  const rows = [{ id_sensor:2,timestamp_captura:'2026-10-16T00:00:00Z' },{ id_sensor:3,timestamp_captura:'2026-10-16T00:00:00Z' }];
  assert.equal(rowsFor(rows,2,'2026-10-15T19:00:00-05:00').length,1);
  assert.equal(exactDelay('2026-10-16T00:00:00Z','2026-10-17T00:00:00Z',24),true);
  assert.equal(exactDelay('2026-10-16T00:00:01Z','2026-10-17T00:00:00Z',24),false);
});
test('aserciones detectan huecos y duplicados sin alterar el esperado', () => {
  const interval = ['2026-10-16T12:00:00Z','2026-10-16T12:01:00Z','2026-10-16T12:02:00Z'];
  const edges = ['2026-10-16T01:00:00Z','2026-10-16T00:00:00Z'];
  const items = [...interval.map(ts => ({ id_sensor:2,timestamp_captura:ts,origen_dato:'BUFFER_LOCAL' })),
    { id_sensor:2,timestamp_captura:'2026-10-17T00:00:00Z',origen_dato:'TIEMPO_REAL' },
    { id_sensor:2,timestamp_captura:edges[0],origen_dato:'BUFFER_LOCAL' }];
  const input = { items, interval, real:{sensor:2,capture:'2026-10-17T00:00:00Z'},duplicate:interval[1],edges };
  assert.equal(assess(input).some(x => !x.ok),true);
  assert.equal(assess({...input,items:items.filter(x => x.timestamp_captura !== interval[2])}).find(x => x.nombre.includes('sin vacíos')).ok,false);
  assert.equal(assess({...input,items:[...items,items[1]]}).find(x => x.nombre.includes('única lectura')).ok,false);
});
test('testigo requiere control positivo; fallo SQL no equivale a cero', () => {
  assert.equal(count({status:403,data:{data:[]}}),null);
  assert.equal(count({status:200,data:{data:[{n:0}]}}),0);
  assert.match(witness('QA-G120-ABC'),/auditoria.logs_dml/);
  assert.throws(() => witness("x' OR true"));
  assert.equal(verdict('CONCLUIDA',[{ok:false}],[{ok:false,observado:true}],true),'BLOQUEADO');
});
test('consulta usa parámetros codificados', () => {
  assert.equal(query('/iot/monitoreo/historial',{ sensor_id:2, origen_dato:'BUFFER_LOCAL' }),'/iot/monitoreo/historial?sensor_id=2&origen_dato=BUFFER_LOCAL');
  assert.equal(synchronizationField({paths:{'/iot/telemetria/batch':{post:{responses:{'200':{content:{'application/json':{schema:{$ref:'#/components/schemas/Batch'}}}}}}}},components:{schemas:{Batch:{properties:{detalle:{items:{$ref:'#/components/schemas/Item'}}}},Item:{properties:{timestamp_captura:{},fecha_sincronizacion:{}}}}}}),'fecha_sincronizacion');
  assert.equal(synchronizationField({paths:{}}),null);
});
