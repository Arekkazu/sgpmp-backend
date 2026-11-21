import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { CASOS, CONTRATO, entrada, validarActor, mock, validarMock } from '../lib/g38_core.mjs';
import { CAPACIDADES, leerEnv, preflight, comprobar, contexto, principal, conPeticiones, fetchEnContexto, contrastarRespuesta } from '../g38.mjs';
import { sanearReporte, directorioNewman } from './newman_hijo.mjs';

test('capacidades y contrato canónico',()=>{
  assert.deepEqual(CASOS,['TC-M06-014','TC-M06-015']);
  assert.equal(CAPACIDADES.grupo,'G38');
  for(const id of ['configuracion','lineas','mediciones','precios_post','evento_crecimiento'])
    assert.equal(validarActor(id,entrada(id).actor),true);
  assert.equal(entrada('configuracion').ruta,'/finanzas/configuracion');
  assert.equal(entrada('lineas').campos.valor,'decimal|number');
  assert.ok(CONTRATO.peticiones.every(x=>x.ruta&&!x.ruta.includes('/test-control/query')));
  assert.equal(comprobar(),0);
});
test('sin autorización no se lee archivo de entorno',()=>{
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g38-env-'));
  try{const archivo=path.join(tmp,'.env.qa');fs.writeFileSync(archivo,'QA_SANDBOX_SECRET=NO_LEER\n');
    const e=leerEnv({QA_AUTORIZADO:'NO'},archivo);assert.equal(e.QA_SANDBOX_SECRET,undefined);
    const p=preflight({runId:'RUN-G38-V1-20261108-000000',ensayo:false},e,'6.2.2');
    assert.equal(p.ok,false);assert.ok(p.barreras.includes('QA_AUTORIZADO'));
  }finally{fs.rmSync(tmp,{recursive:true,force:true});}
});
test('PETICION_CONCURRENTE al solapar requests',async()=>{
  let resolver;
  const fetcher=()=>new Promise(r=>resolver=r);
  await conPeticiones(fetcher,async()=>{
    const primera=fetchEnContexto('http://localhost:1');
    await assert.rejects(fetchEnContexto('http://localhost:1'),/PETICION_CONCURRENTE/);
    resolver({status:200,headers:new Headers(),json:async()=>({})});await primera;
  });
});
test('CLI real rechaza preflight sin autorización y limpia Resultados',()=>{
  const grupo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
  const raiz=path.join(grupo,'Resultados'),runId='RUN-G38-V1-20261108-000000',dir=path.join(raiz,runId);
  assert.ok(path.resolve(dir).startsWith(path.resolve(grupo)+path.sep));
  fs.mkdirSync(dir,{recursive:true});
  const archivo=path.join(dir,'contexto_operacion.json');
  fs.writeFileSync(archivo,JSON.stringify({grupo:'G38',run_id:runId,version:1,intento:1,
    operacion:'EVALUAR',referencia:'AUT-LOCAL',casos:CASOS}));
  try{
    const args=[path.join(grupo,'g38.mjs'),'--operacion','evaluar','--version','1','--intento','1',
      '--run-id',runId,'--autorizacion','AUT-LOCAL','--contexto',archivo];
    const x=spawnSync(process.execPath,args,{cwd:grupo,env:{...process.env,QA_AUTORIZADO:'NO'},windowsHide:true,encoding:'utf8'});
    if(x.error?.code==='EPERM')return console.log('PENDIENTE CLI real: spawn EPERM en Windows');
    assert.equal(x.status,2);assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'preflight.json'),'utf8')).ok,false);
  }finally{
    fs.rmSync(dir,{recursive:true,force:true});
    if(fs.existsSync(raiz)&&fs.readdirSync(raiz).length===0)fs.rmdirSync(raiz);
  }
});
test('archivo temporal de entorno solo tras autorizacion',()=>{
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g38-env-'));
  try{const archivo=path.join(tmp,'local.env');fs.writeFileSync(archivo,'QA_SANDBOX_SECRET=local-ficticio\n');
    assert.equal(leerEnv({QA_AUTORIZADO:'SI'},archivo).QA_SANDBOX_SECRET,'local-ficticio');
    assert.equal(leerEnv({QA_AUTORIZADO:'NO'},archivo).QA_SANDBOX_SECRET,undefined);
  }finally{fs.rmSync(tmp,{recursive:true,force:true});}
});
test('todos los actores, mocks y negativos del contrato',()=>{
  for(const p of CONTRATO.peticiones){
    assert.equal(validarActor(p.id,p.actor),true,p.id);
    assert.throws(()=>validarActor(p.id,p.actor==='contador'?'admin':'contador'),/Actor sin permiso/);
    const cuerpo=mock(p.id);assert.equal(validarMock(p.id,cuerpo),true);
    const r={contraste_contrato:[],discrepancias_contrato:[],problemas_tecnicos:[]};
    assert.equal(contrastarRespuesta(r,p.id,p.actor,p.http??200,cuerpo),true,p.id);
    assert.equal(contrastarRespuesta(r,p.id,p.actor,p.http??200,null),false,p.id);
    assert.equal(r.discrepancias_contrato.length,1,p.id);
  }
});
test('ruta Newman, permisos de coleccion y saneamiento',()=>{
  assert.ok(path.isAbsolute(directorioNewman));
  const grupo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
  const col=JSON.parse(fs.readFileSync(path.join(grupo,'G38.postman_collection.json'),'utf8'));
  for(const item of col.item){
    const p=entrada(item.name);assert.equal(p.actor,'contador');
    assert.ok(item.request.header.some(h=>h.key==='X-Test-Run-Id'&&h.value==='{{run_id}}'));
    assert.ok(item.request.header.some(h=>h.key==='Authorization'&&h.value==='Bearer {{contador_token}}'));
  }
  const saneado=sanearReporte(JSON.stringify({headers:{authorization:'token-ficticio'},body:'privado',
    email:'usuario@ejemplo.invalid',valor:'token-ficticio'}),['token-ficticio'],true);
  assert.ok(!saneado.includes('token-ficticio')&&!saneado.includes('usuario@ejemplo.invalid'));
  assert.match(saneado,/REDACTADO/);
});
test('contexto fuera de Resultados se rechaza',()=>{
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g38-contexto-'));
  try{const runId='RUN-G38-V1-20261108-000001',archivo=path.join(tmp,'contexto_operacion.json');
    fs.writeFileSync(archivo,JSON.stringify({grupo:'G38',run_id:runId,version:1,intento:1,
      operacion:'EVALUAR',referencia:'AUT-LOCAL',casos:CASOS}));
    const args=['--operacion','evaluar','--version','1','--intento','1','--run-id',runId,
      '--autorizacion','AUT-LOCAL','--contexto',archivo];
    assert.throws(()=>contexto(args),/Contexto fuera del RUN/);
  }finally{fs.rmSync(tmp,{recursive:true,force:true});}
});
test('principal sin secreto escribe preflight y hace cero peticiones',async()=>{
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g38-sin-secreto-'));
  const runId='RUN-G38-V1-20261108-000002',dir=path.join(tmp,runId);
  try{fs.mkdirSync(dir);const archivo=path.join(dir,'contexto_operacion.json');
    fs.writeFileSync(archivo,JSON.stringify({grupo:'G38',run_id:runId,version:1,intento:1,
      operacion:'EVALUAR',referencia:'AUT-LOCAL',casos:CASOS}));
    const args=['--operacion','evaluar','--version','1','--intento','1','--run-id',runId,
      '--autorizacion','AUT-LOCAL','--contexto',archivo];
    let peticiones=0;const salida=await principal(args,{ensayo:true,archivoEnv:path.join(tmp,'inexistente'),
      proceso:{QA_AUTORIZADO:'SI',SIGAB_API_TEST_BASE:'http://127.0.0.1:1'},
      fetcher:async()=>{peticiones++;throw Error('No debe llamarse');}});
    assert.equal(salida.preflight.ok,false);assert.equal(peticiones,0);
    assert.ok(salida.preflight.barreras.includes('QA_SANDBOX_SECRET'));
    assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'preflight.json'),'utf8')).ok,false);
  }finally{fs.rmSync(tmp,{recursive:true,force:true});}
});
