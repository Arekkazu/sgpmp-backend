import assert from 'node:assert/strict';
import {test} from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {leerEnv,preflight,contexto,principal,conPeticiones,fetchEnContexto,comprobar,CAPACIDADES,
  verificarPermisos,contrastarRespuesta} from '../g40.mjs';
import {clasificarRegistro} from './registro_qa.mjs';
import {CONTRATO,validarActor,mock} from '../lib/g40_core.mjs';
import {sanearReporte} from './newman_hijo.mjs';
import avisoG40 from '../lib/aviso_g40.cjs';
const {coincideCombinacion,clasificarIntercepcion}=avisoG40;
const DIR=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const RUN='RUN-G40-V1-20261109-120000';
test('aviso acepta código y traducción, rechaza genérico y especie distinta',()=>{
  assert.equal(coincideCombinacion('VARIACION_VR_TB GANANCIA especie 39',39,'Bovino'),true);
  assert.equal(coincideCombinacion('Variación por transformación biológica. Ganancia. Especie Bovino',39,'Bovino'),true);
  assert.equal(coincideCombinacion('Línea sin cuenta contable',39,'Bovino'),false);
  assert.equal(coincideCombinacion('VARIACION_VR_TB GANANCIA especie 40',39,'Bovino'),false);
});
test('interceptor clasifica frontal, API y terceros en modo real',()=>{
  const api='https://www.api.inmero.co/api-sgpmp-test';
  const front='https://api.inmero.co/sigab-test';
  const casos=[
    ['https://api.inmero.co/sigab-test/login','GET','FRONTAL'],
    ['https://api.inmero.co/sigab-test/assets/x.js','GET','FRONTAL'],
    ['https://www.api.inmero.co/api-sgpmp-test/finanzas/configuracion','GET','API'],
    ['https://api.inmero.co/api-sgpmp-test/finanzas/configuracion','GET','API'],
    ['https://cdn.otro.com/x.js','GET','BLOQUEADO'],
    ['https://api.inmero.co/otra','GET','BLOQUEADO'],
    ['https://api.inmero.co/sigab-test/otra','POST','BLOQUEADO'],
  ];
  for(const [url,metodo,esperado] of casos)
    assert.equal(clasificarIntercepcion(url,metodo,api,front).destino,esperado,url);
});
test('interceptor clasifica frontal raíz y API en modo ensayo',()=>{
  const api='http://127.0.0.1:42002';
  const front='http://127.0.0.1:42001';
  const casos=[
    ['http://127.0.0.1:42001/login','GET','FRONTAL'],
    ['http://127.0.0.1:42001/assets/x.js','GET','FRONTAL'],
    ['http://127.0.0.1:42002/finanzas/configuracion','GET','API'],
    ['http://evil.test/','GET','BLOQUEADO'],
  ];
  for(const [url,metodo,esperado] of casos)
    assert.equal(clasificarIntercepcion(url,metodo,api,front,true).destino,esperado,url);
  assert.deepEqual(clasificarIntercepcion('http://127.0.0.1:42001/api/finanzas/configuracion','GET',
    'http://127.0.0.1:42001/api',front,true),{destino:'API',ruta:'/finanzas/configuracion'});
});
test('interceptor normaliza rutas API en modos real y ensayo',()=>{
  const rutas=[['/__g40_sonda__','/__g40_sonda__'],['/sesiones/','/sesiones/'],
    ['/finanzas/configuracion','/finanzas/configuracion'],['/notificaciones?pagina=1','/notificaciones']];
  for(const [api,front,ensayo] of [
    ['https://www.api.inmero.co/api-sgpmp-test','https://api.inmero.co/sigab-test',false],
    ['http://127.0.0.1:42002','http://127.0.0.1:42001',true]]){
    for(const [sufijo,ruta] of rutas){
      const url=api+sufijo;
      assert.deepEqual(clasificarIntercepcion(url,'GET',api,front,ensayo),{destino:'API',ruta},url);
    }
  }
  assert.deepEqual(clasificarIntercepcion('https://www.api.inmero.co/api-sgpmp-test','GET',
    'https://www.api.inmero.co/api-sgpmp-test/','https://api.inmero.co/sigab-test'),
    {destino:'API',ruta:'/'});
});
const setup=()=>{const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g40-env-')),dir=path.join(tmp,RUN);
  fs.mkdirSync(dir);const file=path.join(dir,'contexto_operacion.json');
  fs.writeFileSync(file,JSON.stringify({grupo:'G40',run_id:RUN,version:1,intento:1,operacion:'EVALUAR',
    referencia:'AUT-LOCAL',casos:['TC-M06-018']}));
  return{tmp,dir,file,args:['--operacion','evaluar','--version','1','--intento','1','--run-id',RUN,
    '--autorizacion','AUT-LOCAL','--contexto',file]};};
test('lector de entorno no abre .env sin autorización',()=>{const s=setup(),p=path.join(s.tmp,'.env.qa');
  try{fs.writeFileSync(p,'QA_SANDBOX_SECRET=archivo\n');assert.equal(leerEnv({QA_AUTORIZADO:'NO'},p).QA_SANDBOX_SECRET,undefined);
    assert.equal(leerEnv({QA_AUTORIZADO:'SI'},p).QA_SANDBOX_SECRET,'archivo');}
  finally{fs.rmSync(s.tmp,{recursive:true,force:true});}});
test('CLI real --comprobar y capacidades',()=>{assert.equal(comprobar(),0);
  const x=spawnSync(process.execPath,[path.join(DIR,'g40.mjs'),'--capacidades'],{encoding:'utf8'});
  if(x.error?.code==='EPERM')return; // Windows sandbox; CLI se ejecuta aparte por PowerShell.
  assert.equal(x.status,0);assert.equal(JSON.parse(x.stdout).grupo,'G40');});
test('contexto RUN coherente y sin salida fuera del temporal',()=>{const s=setup();try{
  assert.equal(contexto(s.args,true).runId,RUN);const invalido=[...s.args];invalido[invalido.indexOf('--run-id')+1]='RUN-G39-V1-20261109-120000';
  assert.throws(()=>contexto(invalido,true));
  }finally{fs.rmSync(s.tmp,{recursive:true,force:true});}});
test('preflight se escribe antes de cualquier petición',async()=>{const s=setup();try{let calls=0;
  const r=await principal(s.args,{proceso:{QA_AUTORIZADO:'NO'},ensayo:true,fetcher:async()=>{calls++;throw Error('No debe llamar');}});
  assert.equal(r.preflight.ok,false);assert.equal(calls,0);assert.equal(fs.existsSync(path.join(s.dir,'preflight.json')),true);
  assert.equal(fs.existsSync(path.join(s.dir,'resultado.json')),false);
  }finally{fs.rmSync(s.tmp,{recursive:true,force:true});}});
test('peticiones estrictamente en serie',async()=>{let release;const gate=new Promise(r=>release=r);
  await conPeticiones(async()=>{await gate;return{status:200,headers:new Headers(),json:async()=>({})};},async()=>{
    const first=fetchEnContexto('http://127.0.0.1/');
    await assert.rejects(fetchEnContexto('http://127.0.0.1/'),/PETICION_CONCURRENTE/);release();await first;});});
test('registro QA exige UI y evidencia real',()=>{const c={...CAPACIDADES};
  assert.equal(clasificarRegistro(c,{run_id:RUN,version:1,autorizacion_referencia:'AUT-LOCAL',
    oficial:true,consume_version:true,cierre:{run:{cierre_http:200},rollback:{verificado:true}},
    casos:{'TC-M06-018':{estado:'APROBADO'}},herramientas:{newman:{codigo:0},cypress:{codigo:0,acta:{captura:true}}},
    comprobaciones:[],evidencias:[]},new Set(),{runId:RUN,version:1,referencia:'AUT-LOCAL'}),false);});
test('preflight rechaza host no canónico sin red',()=>{const s=setup();try{const p=preflight(contexto(s.args,true),{
  QA_AUTORIZADO:'SI',SIGAB_API_TEST_BASE:'https://www.api.inmero.co/api-sgpmp-test',
  QA_SANDBOX_SECRET:'local',QA_CONTADOR_EMAIL:'c',QA_CONTADOR_PASSWORD:'p',QA_ADMIN_EMAIL:'a',QA_ADMIN_PASSWORD:'p'});
  assert.equal(p.ok,false);assert.ok(p.barreras.includes('API_NO_CANONICA'));
  }finally{fs.rmSync(s.tmp,{recursive:true,force:true});}});
test('contexto rechaza grupo y RUN incoherentes',()=>{const s=setup();try{const bad=JSON.parse(fs.readFileSync(s.file));bad.grupo='G39';
  fs.writeFileSync(s.file,JSON.stringify(bad));assert.throws(()=>contexto(s.args,true),/incoherente/);
  }finally{fs.rmSync(s.tmp,{recursive:true,force:true});}});
test('contrato exige permiso de matriz C/U y de lectura',()=>{for(const id of ['configuracion','matriz_post','matriz_delete'])
  assert.equal(validarActor(id,'contador'),true);assert.throws(()=>validarActor('matriz_post','admin'));
  assert.equal(validarActor('bandeja','contador'),true);});
test('permisos ausentes se detectan antes de escribir',()=>{
  const p=CONTRATO.peticiones.filter(x=>x.actor==='contador'&&x.permiso!=='autenticado:0');
  const permisos=p.filter(x=>x.permiso!=='configuracion_contable:1').map(x=>{
    const [nombre_recurso,id_accion]=x.permiso.split(':');return{nombre_recurso,id_accion:Number(id_accion)};});
  assert.throws(()=>verificarPermisos({permisos},'contador'),/configuracion_contable:1/);});
test('contraste rechaza GET de forma incorrecta',()=>{const r={contraste_contrato:[],discrepancias_contrato:[]};
  assert.equal(contrastarRespuesta(r,'configuracion','contador',200,{matriz:[]},'/finanzas/configuracion'),false);
  assert.equal(r.discrepancias_contrato.length,1);
  const ok={contraste_contrato:[],discrepancias_contrato:[]};
  assert.equal(contrastarRespuesta(ok,'configuracion','contador',200,mock('configuracion'),'/finanzas/configuracion'),true);});
test('reporte Newman sanea secretos y correos',()=>{const x=sanearReporte('token-local contador@local.invalid eyJabc.def.ghi',['token-local']);
  assert.equal(x.includes('token-local'),false);assert.equal(x.includes('contador@'),false);});
test('capacidad declara API y UI obligatorias',()=>{assert.deepEqual(CAPACIDADES.comprobaciones_obligatorias['TC-M06-018'],
  {API:['G40-API-018-01'],UI:['G40-UI-018-01']});});
