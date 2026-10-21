import test from 'node:test';
import assert from 'node:assert/strict';
import { CASOS, plan250, codeOf, page2Valid, failureControlled, ratePlan, faultHook, ratePolicy, snapshotSql } from './ejecutar_tc_m03_g125.mjs';
import { verdict } from '../TC-M03-G120/rf59_base.mjs';

test('casos exactos y preparación de 250 lecturas por contrato batch',()=>{
  assert.deepEqual(CASOS,['TC-M03-251','TC-M03-252','TC-M03-253','TC-M03-265']);
  const rows=plan250({device:1,sensor:2,serial:'QA',at:'2026-10-17T00:00:00Z'});
  assert.equal(rows.length,250);
  assert.equal(new Set(rows.map(x=>x.sensor_id+':'+x.timestamp_captura)).size,250);
  assert.ok(rows.every(x=>x.device_id===1&&x.origen==='TIEMPO_REAL'));
});
test('la página visible se distingue del conjunto filtrado',()=>{
  assert.equal(page2Valid({pagina:2,por_pagina:100,total:250,items:Array(100).fill({})}),true);
  assert.equal(page2Valid({pagina:2,por_pagina:100,total:100,items:Array(100).fill({})}),false);
});
test('400 EXPORTAR_SIN_FILTROS conserva código y no archivo',()=>{
  assert.equal(codeOf({detail:{code:'EXPORTAR_SIN_FILTROS'}}),'EXPORTAR_SIN_FILTROS');
  assert.equal(codeOf({detail:'otro'}),null);
});
test('stub local de fallo, timeout y archivo parcial solo valida el harness',()=>{
  assert.equal(faultHook({'/test-control/export/fallo':{post:{summary:'Fallo exportación aislado en sandbox con rollback del RUN_ID'}}}),'/test-control/export/fallo');
  assert.equal(faultHook({'/export/fallo':{post:{summary:'Fallo exportación'}}}),null);
  assert.match(snapshotSql(7),/id_sensor=7/);
  assert.equal(failureControlled({status:500,bytes:Buffer.alloc(0),visible:false,unchanged:true,informed:true}),true);
  assert.equal(failureControlled({status:504,bytes:Buffer.alloc(0),visible:false,unchanged:true,informed:true}),true);
  assert.equal(failureControlled({status:500,bytes:Buffer.from('PK'),visible:true,unchanged:true,informed:true}),false);
  assert.equal(failureControlled({status:500,bytes:Buffer.alloc(0),visible:false,unchanged:false,informed:true}),false);
  assert.equal(failureControlled({status:500,bytes:Buffer.alloc(0),visible:false,unchanged:true,informed:false}),false);
});
test('20 por minuto es plan de referencia; PRE/rollback prevalecen',()=>{
  assert.deepEqual(ratePolicy({responses:{'429':{}},'x-rate-limit':{limite:10,ventana_seg:60}}),{max:10,window:60,otherUserMaxMs:null});
  assert.equal(ratePolicy({responses:{'429':{}}}),null);
  const offsets=ratePlan();
  assert.equal(offsets.length,20);
  assert.ok(offsets.at(-1)<60000);
  assert.equal(ratePlan(26,120000).length,26);
  assert.throws(()=>ratePlan(31,60000));
  assert.equal(verdict('CONCLUIDA',[{ok:false}],[{ok:false,observado:true}],true),'BLOQUEADO');
  assert.equal(verdict('CONCLUIDA',[{ok:true}],[{ok:false,observado:true}],true),'RECHAZADO');
});
