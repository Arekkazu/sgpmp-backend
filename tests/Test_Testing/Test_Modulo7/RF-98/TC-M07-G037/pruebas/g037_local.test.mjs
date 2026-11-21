import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {CAPACIDADES,contexto,dirRun,preflight,principal,sanitize,versionesLibres,verificarRollback,leerGracia,mismoInstante} from '../g037.mjs';
import {contrato,validarSolicitud} from '../lib/contrato.mjs';
import {simuladorG037} from './simulador_g037.mjs';

test('capacidades V3 y solo API',()=>{
  assert.deepEqual(CAPACIDADES.operaciones,['reevaluar','reintentar']);
  assert.deepEqual(CAPACIDADES.versiones,{min:3,max:3});
  assert.equal(contrato.version,'ORD-G037-009');
  assert.equal(contrato.version_ejecucion,3);
  assert.deepEqual(CAPACIDADES.casos,['TC-M07-06','TC-M07-07','TC-M07-08']);
  assert(Object.values(CAPACIDADES.comprobaciones_obligatorias).every(x=>x.API.length&&!('UI' in x)));
});
test('dirRun de produccion usa exclusivamente EvaluacionV3',()=>{
  const runId='RUN-G037-V3-20261120-000000';
  const dir=dirRun({ensayo:false,runId,version:3});
  assert.equal(path.basename(dir),runId);
  assert.equal(path.basename(path.dirname(dir)),'Resultados');
  assert.equal(path.basename(path.dirname(path.dirname(dir))),'EvaluacionV3');
  assert(!dir.includes('EvaluacionV2'));
});
test('contexto V3 exige decisión y preflight local',()=>{
  const raiz=fs.mkdtempSync(path.join(os.tmpdir(),'g037-contexto-'));
  try{
    const runId='RUN-G037-V3-20261118-000000',dir=path.join(raiz,runId);fs.mkdirSync(dir);
    const archivo=path.join(dir,'contexto_operacion.json');
    const dato={grupo:'G037',run_id:runId,version:3,intento:1,operacion:'REEVALUAR',referencia:'AUT-LOCAL',casos:CAPACIDADES.casos,version_anterior:2,alcance_reevaluacion:{casos:CAPACIDADES.casos,motivo:'INC-M07-G037-01 corregida'}};
    fs.writeFileSync(archivo,JSON.stringify(dato));
    const args=['--operacion','reevaluar','--version','3','--intento','1','--run-id',runId,'--autorizacion','AUT-LOCAL','--contexto',archivo];
    const c=contexto(args,true);assert.equal(c.dir,dir);
    assert(preflight(c,{QA_AUTORIZADO:'SI',QA_ADMIN_EMAIL:'a@local.invalid',QA_ADMIN_PASSWORD:'LOCAL',QA_SANDBOX_SECRET:'LOCAL',SIGAB_API_TEST_BASE:'http://127.0.0.1:12345/api-sgpmp-test'}).ok);
    delete dato.alcance_reevaluacion;fs.writeFileSync(archivo,JSON.stringify(dato));assert.throws(()=>contexto(args,true),/REEVALUACION_SIN_DECISION/);
    const otroRun='RUN-G037-V3-20261118-000001',otroDir=path.join(raiz,otroRun);fs.mkdirSync(otroDir);
    const otroArchivo=path.join(otroDir,'contexto_operacion.json');
    fs.writeFileSync(otroArchivo,JSON.stringify({...dato,run_id:otroRun,intento:2,operacion:'REINTENTAR'}));
    const reintento=['--operacion','reintentar','--version','3','--intento','2','--run-id',otroRun,'--autorizacion','AUT-LOCAL','--contexto',otroArchivo];
    assert.equal(contexto(reintento,true).dir,otroDir);
    assert.equal(fs.existsSync(path.join(dir,'resultado.json')),false);
  }finally{fs.rmSync(raiz,{recursive:true,force:true});}
});
test('versiones libres desde 6.0 y gracia leída sin constantes de prueba',()=>{
  assert.deepEqual(versionesLibres([{contrato_version:'6.0'},{contrato_version:'6.2'}],3),['6.1','6.3','6.4']);
  assert.deepEqual(leerGracia([{nombre:'aaef_gracia_minima_dias',valor:37,fuente:'CONFIGURADO'},{nombre:'aaef_gracia_defecto_dias',valor:118,fuente:'CONFIGURADO'}]),{min:37,def:118,fuentes:{min:'CONFIGURADO',def:'CONFIGURADO'}});
  assert.deepEqual(leerGracia([{nombre:'aaef_gracia_minima_dias',valor:'37',fuente:'CONFIGURADO'},{nombre:'aaef_gracia_defecto_dias',valor:'118',fuente:'CONFIGURADO'}]),{min:37,def:118,fuentes:{min:'CONFIGURADO',def:'CONFIGURADO'}});
});
test('solicitudes estrictas y rechazo semántico en servidor',()=>{
  assert(validarSolicitud('PATCH','/configuracion/parametros-integracion-contable',{parametros:{aaef_gracia_defecto_dias:44}}));
  assert.throws(()=>validarSolicitud('PATCH','/configuracion/parametros-integracion-contable',{parametros:{aaef_gracia_defecto_dias:'44'}}));
  assert.throws(()=>validarSolicitud('POST','/sesiones/',{correo_electronico:'x',contrasena:'y',otro:'z'}));
});
test('privacidad, rollback y comparación de instantes',()=>{
  const marcador='SENTINELA_NOMBRE_G037';
  const s=JSON.stringify(sanitize({nombre_usuario:marcador,nombre_cliente:marcador,correo_usuario:'test@local.invalid',password:'LOCAL'}));
  assert(!s.includes(marcador));assert(!s.includes('test@local.invalid'));assert(!s.includes('LOCAL'));
  const a=[{id_version_contrato_aaef:1,estado:'ACTIVO'}],b=[{id_version_contrato_aaef:1,estado:'ACTIVO'}];
  assert(verificarRollback(a,b));assert(!verificarRollback(a,[{id_version_contrato_aaef:1,estado:'DEPRECADO'}]));
  assert(mismoInstante('2026-12-18T12:00:00.000Z','2026-12-18T07:00:00-05:00'));
});

test('reintento V3 escribe solo en un RUN nuevo',async()=>{
  const raiz=fs.mkdtempSync(path.join(os.tmpdir(),'g037-reintento-'));
  const previo='RUN-G037-V3-20261118-000000',nuevo='RUN-G037-V3-20261118-000001';
  const previoDir=path.join(raiz,previo),nuevoDir=path.join(raiz,nuevo);fs.mkdirSync(previoDir);fs.mkdirSync(nuevoDir);
  const sello=path.join(previoDir,'resultado.json');fs.writeFileSync(sello,'HISTORICO_LOCAL');
  const contextoArchivo=path.join(nuevoDir,'contexto_operacion.json');
  fs.writeFileSync(contextoArchivo,JSON.stringify({grupo:'G037',run_id:nuevo,version:3,intento:2,operacion:'REINTENTAR',referencia:'AUT-LOCAL',casos:CAPACIDADES.casos}));
  const sim=await simuladorG037({runId:nuevo});
  try{
    const archivo=path.join(raiz,'local.env');fs.writeFileSync(archivo,`QA_ADMIN_EMAIL=local@example.invalid\nQA_ADMIN_PASSWORD=LOCAL\nQA_SANDBOX_SECRET=LOCAL\nSIGAB_API_TEST_BASE=${sim.api}\n`);
    const args=['--operacion','reintentar','--version','3','--intento','2','--run-id',nuevo,'--autorizacion','AUT-LOCAL','--contexto',contextoArchivo];
    const z=await principal(args,{proceso:{QA_AUTORIZADO:'SI'},archivo,prueba:true,dobles:{newman:async()=>({codigo:0,fallos:0,solicitudes:2,reportes:true})}});
    assert.equal(z.codigo,0);assert.equal(z.resultado.run_id,nuevo);assert.deepEqual(Object.values(z.resultado.veredictos),['APROBADO','APROBADO','APROBADO']);
    assert.equal(fs.readFileSync(sello,'utf8'),'HISTORICO_LOCAL');
    assert(fs.existsSync(path.join(nuevoDir,'resultado.json')));
    assert.equal(fs.readdirSync(nuevoDir).filter(f=>f.endsWith('.md')).length,1);
  }finally{await sim.cerrar();fs.rmSync(raiz,{recursive:true,force:true});}
});
