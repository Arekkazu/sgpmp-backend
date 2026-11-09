import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { leerEnv, sanear, periodoDestino, preciosVigentes } from '../g34.mjs';
import { CASOS, evaluarA, evaluarB, costosDe, mismosCostos, oficialidadLocal } from '../lib/g34_core.mjs';
import { ejecutarNewman } from './newman_hijo.mjs';

test('leerEnv prioriza autorización del proceso y sanea secretos',()=>{
  const f=path.join(os.tmpdir(),'g34-env-'+process.pid+'.txt');
  try {
    fs.writeFileSync(f,'QA_AUTORIZADO=SI\nQA_CONTADOR_PASSWORD=clave-local\n');
    const e=leerEnv({QA_AUTORIZADO:undefined},f);
    assert.equal(e.QA_AUTORIZADO,undefined);assert.equal(e.QA_CONTADOR_PASSWORD,'clave-local');
    assert.ok(!sanear('clave-local',['clave-local']).includes('clave-local'));
  } finally {fs.rmSync(f,{force:true});}
});
test('período destino y precio vigente',()=>{
  const p=[{id_periodo_contable:1,numero_id_tributaria:'x',estado:'CERRADO',fecha_inicio:'2026-11-01',fecha_fin:'2026-11-30'},
    {id_periodo_contable:2,numero_id_tributaria:'x',estado:'ABIERTO',fecha_inicio:'2026-12-01',fecha_fin:'2026-12-31'}];
  assert.equal(periodoDestino(p,'x','2026-11-08').periodo.id_periodo_contable,2);
  const pr={id_especie:3,categoria:'PESO_KG',fuente:'MERCADO_ACTIVO',fecha_vigencia:'2026-11-08'};
  assert.equal(preciosVigentes([{...pr,id_precio_mercado:5},{...pr,id_precio_mercado:6}],3,'2026-11-08').id_precio_mercado,6);
});
test('costos activos de GENERAL y restauración exacta',()=>{
  const c={costos_venta:[{id_especie:3,region:'GENERAL',es_activo:true,pct_transporte:'0.02',
    pct_comisiones:'0.01',pct_impuestos:'0.00'}]};
  const original=costosDe(c,3);
  assert.ok(mismosCostos(original,{pct_transporte:'0.02',pct_comisiones:'0.01',pct_impuestos:'0.00'}));
  assert.ok(!mismosCostos(original,{pct_transporte:1,pct_comisiones:0,pct_impuestos:0}));
});
test('A exige ausencias, auditoría y aviso del evento',()=>{
  const base={completa:true,variaciones:[],lineas:[],mediciones:[],calculos:[],auditoria:[],bandeja:[],bandejaLineaBase:null};
  const post={...base,auditoria:[{id_evento:7,tipo_evento:'MEDICION_PENDIENTE',severidad_evento:'WARNING',
    id_activo_biologico:2,id_periodo_contable:3,id_referencia:9,payload_evento:{motivo:'VALOR_NETO_NO_POSITIVO',id_evento:9}}],
    bandeja:[{id_notificacion:1,mensaje:'RF_83_NO_COMPLETADO activo 2 evento 9'}]};
  const p={activo:2,periodo:3,evento:9,identificador:'A'};
  assert.equal(evaluarA(base,post,p).estado,'APROBADO');
  assert.equal(evaluarA(base,{...post,bandeja:[]},p).estado,'RECHAZADO');
  assert.equal(evaluarA(base,{...post,variaciones:[{id_variacion_valor_razonable:10,id_activo_biologico:2}]},p).estado,'RECHAZADO');
  assert.equal(evaluarA(base,{...post,completa:false},p).estado,'NO_CONCLUYENTE');
});
test('B valida TB, PM cero y línea',()=>{
  const base={completa:true,variaciones:[],lineas:[],mediciones:[]};
  const post={...base,variaciones:[{id_variacion_valor_razonable:4,id_activo_biologico:2,tipo:'GANANCIA_TRANSFORMACION_BIOLOGICA',monto_variacion:'20'}],
    lineas:[{id_linea_asiento_nic41:5,id_activo_biologico:2,id_origen:4}],
    mediciones:[{id_medicion_posterior:6,id_activo_biologico:2,id_evento:9,estado:'COMPLETADO',
      ganancia_perdida_transformacion:'20',ganancia_perdida_precio_mercado:'0'}]};
  const p={activo:2,evento:9,periodo:3,calculoPrevio:{valor_neto:1000,magnitud:400},pesoNuevo:408};
  assert.equal(evaluarB(base,post,p).estado,'APROBADO');
  assert.equal(evaluarB(base,{...post,variaciones:[]},p).estado,'RECHAZADO');
});
test('oficialidad requiere UI ejecutada y costos restaurados',()=>{
  const r={cierre:{rollback:{verificado:true},costos:{restaurados:true}},cypress:{total_pruebas:1,total_failed:0,captura:true},
    casos:{[CASOS[0]]:{estado:'APROBADO'}},herramientas:{newman:{iteraciones:1,codigo:0,fallos:0}}};
  assert.equal(oficialidadLocal(r),true);
  r.cypress.total_pruebas=0;assert.equal(oficialidadLocal(r),false);
});
test('hijo Newman exporta en temporal y deja limpio',async()=>{
  const antes=fs.readdirSync(os.tmpdir()).filter(x=>x.startsWith('g34-newman-')).sort();
  const server=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'application/json'});res.end('{"ok":true}');});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  try {
    const url='http://127.0.0.1:'+server.address().port+'/sonda';
    const col={info:{name:'sonda',schema:'https://schema.getpostman.com/json/collection/v2.1.0/collection.json'},
      item:[{name:'sonda',request:{method:'GET',url}}]};
    const x=await ejecutarNewman({coleccion:col,environment:{values:[]},timeout:30000});
    assert.equal(x.fallido,false);assert.equal(x.solicitudes[0].http,200);
    assert.deepEqual(fs.readdirSync(os.tmpdir()).filter(x=>x.startsWith('g34-newman-')).sort(),antes);
  } finally {await new Promise(resolve=>server.close(resolve));}
});
