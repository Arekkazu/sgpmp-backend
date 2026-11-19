// Procedimiento local único de G036. Conserva los diez pasos de G43; no usa TEST.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {simuladorG036} from './simulador_g036.mjs';
import {CAPACIDADES,comprobar,principal} from '../g036.mjs';
import {ejecutar as ejecutarNewman} from './newman_hijo.mjs';
import {cuerpo} from '../lib/g036_core.mjs';
// Contrato del resultado y clasificación replicada de registro_qa.py:226-263.
export function comprobarPaso6(dir,x,runId){
  const r=JSON.parse(fs.readFileSync(path.join(dir,'resultado.json')));
  const tipo=(v,t,n)=>assert.equal(typeof v,t,`${x.id}: ${n}`);
  assert.equal(r.grupo,'G036');assert.equal(r.run_id,runId);assert.equal(r.version,1);
  tipo(r.autorizacion_referencia,'string','autorizacion_referencia');tipo(r.consume_version,'boolean','consume_version');
  assert.equal(r.oficial,x.oficial);assert.deepEqual(['01','02','03','04','05'].map(k=>r.veredictos[k]),x.esperado);
  assert.equal(r.cierre.rollback.verificado,!x.rollbackFallido);if(x.problemaTecnico)assert(r.problemas_tecnicos.some(v=>v.includes('cy.visit()')));else assert.deepEqual(r.problemas_tecnicos,[]);
  assert.deepEqual(Object.keys(r.casos).sort(),CAPACIDADES.casos.slice().sort());
  for(const [caso,v] of Object.entries(r.casos)){tipo(v.estado,'string',caso+'.estado');assert(Array.isArray(v.comprobaciones));assert(v.comprobaciones.every(id=>typeof id==='string'));}
  assert(Array.isArray(r.comprobaciones));for(const v of r.comprobaciones){for(const k of ['caso','fuente','id','tipo','estado','evidencia'])tipo(v[k],'string','comprobaciones.'+k);assert.equal(v.tipo,'ASSERT');}
  tipo(r.cypress.codigo,'number','cypress.codigo');tipo(r.cypress.total_pruebas,'number','cypress.total_pruebas');
  if(r.consume_version){assert(r.newman);tipo(r.newman.codigo,'number','newman.codigo');}
  tipo(r.cierre.http,'number','cierre.http');tipo(r.cierre.run.cierre_http,'number','cierre.run.cierre_http');tipo(r.cierre.rollback.verificado,'boolean','rollback.verificado');
  assert(Array.isArray(r.evidencias));assert(r.evidencias.every(e=>typeof e==='string'&&fs.existsSync(path.join(dir,e))));
  assert(Array.isArray(r.incidencias));for(const v of r.incidencias)for(const k of ['caso','regla','severidad','certeza','equipo_inicial','fundamento'])tipo(v[k],'string','incidencias.'+k);
  tipo(r.oficial,'boolean','oficial');assert(Array.isArray(r.preflight_datos));assert.equal(fs.readdirSync(dir).filter(f=>f.endsWith('.md')).length,1);
  return r;
}
export function comprobarPaso10(dir,esperada){
  const r=JSON.parse(fs.readFileSync(path.join(dir,'resultado.json')));
  // registro_qa.py:231-244: coherencia, cierre, rollback y efectos remotos.
  assert.equal(r.run_id,path.basename(dir));assert.equal(r.version,1);
  const http=r.cierre?.run?.cierre_http,confirmado=http===200,rollback=r.cierre?.rollback?.verificado===true;
  const efectos=Boolean(r.consume_version||r.datos?.ids_telemetria);
  const estadoRun=confirmado||(http===404&&rollback)?'CERRADO':http==null&&efectos?'ABIERTO_PENDIENTE':http==null?'PREPARADO':'DESCONOCIDO';
  // registro_qa.py:245-254: solo ASSERT conclusivos cubren las comprobaciones obligatorias.
  const hechas=new Set(r.comprobaciones.filter(v=>v.tipo==='ASSERT'&&['APROBADO','RECHAZADO'].includes(v.estado)).map(v=>[v.caso,v.fuente,v.id].join('|')));
  const requeridas=CAPACIDADES.comprobaciones_obligatorias;
  const completas=Object.entries(requeridas).every(([caso,fuentes])=>Object.entries(fuentes).every(([fuente,ids])=>ids.every(id=>hechas.has([caso,fuente,id].join('|')))));
  const requiereUI=Object.values(requeridas).some(x=>'UI' in x);
  const completo=Object.keys(r.casos).length===Object.keys(requeridas).length&&Object.keys(r.casos).every(k=>k in requeridas)&&completas&&(!requiereUI||r.cypress?.total_pruebas>0)&&Object.values(r.casos).every(x=>['APROBADO','RECHAZADO'].includes(x.estado));
  // registro_qa.py:255-263: informe y evidencias existentes, luego clasificación.
  const informe=path.join(dir,'TC-M07-G036_resultado.md');
  const evidenciaValida=fs.existsSync(informe)&&r.evidencias.every(x=>typeof x==='string'&&!x.split(/[\\/]/).includes('..')&&fs.statSync(path.join(dir,x),{throwIfNoEntry:false})?.isFile());
  const clasificacion=r.oficial===true&&completo&&rollback&&confirmado&&evidenciaValida?'OFICIAL':r.oficial===false&&['CERRADO','PREPARADO'].includes(estadoRun)?'TECNICO':'INCIERTO';
  assert.equal(clasificacion,esperada,path.basename(path.dirname(dir)));return clasificacion;
}
const base=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const grupo=path.basename(base).match(/^TC-M07-(G\d{3})$/)?.[1];
assert.equal(grupo,'G036');
const esc=JSON.parse(fs.readFileSync(path.join(base,'pruebas','escenarios_g036.json')));
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
const temporal=fs.mkdtempSync(path.join(os.tmpdir(),'g036-verificar-'));
const guardLog=path.join(temporal,'red-bloqueada.log'),guardFile=path.join(temporal,'guard.cjs');
fs.writeFileSync(guardFile,`const fs=require('node:fs'),net=require('node:net');const original=net.Socket.prototype.connect;net.Socket.prototype.connect=function(...args){const f=args[0],h=typeof f==='object'?(f.host||f.hostname):typeof args[1]==='string'?args[1]:null;if(h&&!['127.0.0.1','localhost','::1'].includes(h)){fs.appendFileSync(${JSON.stringify(guardLog)},String(h)+'\\n');const e=Error('RED_REMOTA_BLOQUEADA');e.code='RED_REMOTA_BLOQUEADA';throw e;}return original.apply(this,args);};`);
const envGuard={...process.env,NODE_OPTIONS:`--require="${guardFile.replace(/\\/g,'/')}"`,CYPRESS_CRASH_REPORTS:'0'};
const tabla=[];const sha=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
async function proceso(programa,args,env=envGuard,entrada='',timeout=300000){return new Promise(resolve=>{let p;try{p=spawn(programa,args,{cwd:base,env,windowsHide:true,stdio:['pipe','pipe','pipe'],timeout});}catch(e){resolve({code:null,error:e.code??'EPERM',out:'',err:e.message});return;}let out='',err='',error=null,done=false;const finish=x=>{if(!done){done=true;resolve(x);}};p.stdout.on('data',x=>out=(out+x).slice(-100000));p.stderr.on('data',x=>err=(err+x).slice(-100000));p.on('error',e=>{error=e;finish({code:null,error:e.code??'EPERM',out,err:e.message});});p.on('close',code=>finish({code,error:error?.code??null,out,err}));p.stdin.on('error',()=>{});p.stdin.end(entrada);});}
async function paso(numero,nombre,categoria,fn){try{await fn();tabla.push({numero,nombre,estado:'OK',clasificacion_fallo:'NINGUNO'});}catch(e){const detalle=String(e?.message??e);tabla.push({numero,nombre,estado:'FALLO',clasificacion_fallo:detalle.includes('EPERM')?'SANDBOX':categoria,detalle});}}
const runId='RUN-G036-V1-20261117-000000';
const bin=path.resolve(base,'../../../../../node_modules/cypress/bin/cypress');
function archivos(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>{if(['Resultados','EvaluacionV2','node_modules'].includes(e.name))return [];const f=path.join(dir,e.name);return e.isDirectory()?archivos(f):/\.(?:mjs|js|cjs)$/.test(e.name)?[f]:[];});}
try{
  await paso(1,'Modo estricto y sintaxis','CONTRATO',async()=>{for(const f of archivos(base)){if(!f.endsWith('.mjs'))new vm.Script('"use strict";\n'+fs.readFileSync(f,'utf8'),{filename:f});const z=await proceso(process.execPath,['--check',f]);assert.equal(z.code,0,`${path.relative(base,f)}: ${z.error||z.err}`);}});
  await paso(2,'Cypress real contra doble de ContratosView.tsx','HERRAMIENTA_CYPRESS_EJECUCION',async()=>{assert(fs.existsSync(bin),'Cypress no instalado');const invalido=path.join(temporal,'cypress-invalido');fs.mkdirSync(invalido);const envInvalido={...envGuard,CYPRESS_ARTIFACTS_DIR:invalido,CYPRESS_API_BASE:'https://invalid.example.invalid',CYPRESS_FRONT_BASE:'https://invalid.example.invalid',CYPRESS_RUN_ID:runId,CYPRESS_ADMIN_TOKEN:'LOCAL',CYPRESS_SANDBOX_SECRET:'LOCAL',CYPRESS_LOCAL_SMOKE:'SI'};const bloqueo=await proceso(process.execPath,[bin,'run','--config-file',path.join(base,'g036.cypress.config.cjs'),'--spec',path.join(base,'g036.cy.js'),'--headless','--browser','electron'],envInvalido,'',180000);assert.notEqual(bloqueo.code,0,'Cypress aceptó host inválido');assert.equal(JSON.parse(fs.readFileSync(path.join(invalido,'G036-cypress.json'))).totalTests,1);const sim=await simuladorG036();try{const dir=path.join(temporal,runId,'cypress');const input={api:sim.api,front:sim.front,dir,runId,token:'LOCAL',secret:'LOCAL',fecha:'2027-12-31',anexoId:2,anexoCodigo:'ANEXO-AAEF-V2.0',versiones:{ACTIVO:'2.1',DEPRECADO:'2.0',INACTIVO:'1.0'},localSmoke:true};const r=await proceso(process.execPath,[path.join(base,'pruebas','cypress_hijo.mjs')],envGuard,JSON.stringify(input),180000);assert.equal(r.code,0,r.error||r.err.slice(-800));const out=JSON.parse(r.out);assert.equal(out.totalTests,1);assert.equal(out.acta?.version_4_2_visible,true);assert(fs.readdirSync(path.join(dir,'screenshots'),{recursive:true}).some(x=>x.endsWith('.png')),'Captura Cypress ausente');const del=await fetch(sim.api+'/test-control/runs/'+runId,{method:'DELETE',headers:{'X-Sandbox-Secret':'LOCAL'}});assert.equal(del.status,200);}finally{await sim.cerrar();}});
  await paso(3,'CLI y preflight antes de red','PREFLIGHT_ENTORNO',async()=>{
    assert.equal(CAPACIDADES.contrato,'sigab-qa-ejecutor/1');
    assert(CAPACIDADES.operaciones.includes('evaluar'));
    assert.deepEqual(Object.keys(CAPACIDADES.comprobaciones_obligatorias).sort(),CAPACIDADES.casos.slice().sort());
    const sim=await simuladorG036();
    try{
      const dir=path.join(temporal,'cli',runId);fs.mkdirSync(dir,{recursive:true});
      const contexto={grupo:'G036',version:1,intento:1,run_id:runId,operacion:'EVALUAR',referencia:'REF-LOCAL',casos:CAPACIDADES.casos,alcance_reevaluacion:null,version_anterior:null};
      const archivo=path.join(dir,'contexto_operacion.json');fs.writeFileSync(archivo,JSON.stringify(contexto));
      const args=['--autorizacion','REF-LOCAL','--operacion','evaluar','--version','1','--intento','1','--run-id',runId,'--contexto',archivo];
      const envFile=path.join(temporal,'cli.env');fs.writeFileSync(envFile,`QA_ADMIN_EMAIL=local@example.invalid\nQA_ADMIN_PASSWORD=LOCAL\nQA_SANDBOX_SECRET=LOCAL\nSIGAB_API_TEST_BASE=${sim.api}/\nSIGAB_FRONT_TEST_BASE=${sim.front}/\n`);
      const env={...envGuard,NODE_ENV:'test',G036_PRUEBA_ENV_FILE:envFile,QA_AUTORIZADO:'NO'};
      const cli=[path.join(base,'g036.mjs'),...args,'--prueba-cli-local'];
      const faltante=await proceso(process.execPath,cli,env);assert.equal(faltante.code,2,faltante.err);assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'preflight.json'))).ok,false);assert.equal(sim.peticiones.length,0);
      const incoherente=await proceso(process.execPath,[path.join(base,'g036.mjs'),...args.map(x=>x==='REF-LOCAL'?'OTRA-REF':x),'--prueba-cli-local'],{...env,QA_AUTORIZADO:'SI'});assert.equal(incoherente.code,2,incoherente.err);assert.equal(sim.peticiones.length,0);
      const acta={caso:'TC-M07-05',http_registro:201,version_4_2_visible:true,pendiente_activar:true,activo_deprecar:true,deprecado_sin_accion:true,inactivo_sin_accion:true,subcomprobaciones_sin_dato:[],captura:true,video:true,peticiones:[],hitos:{frontal_cargado:true,login_interceptado:true,pantalla_contrato:true,modal_abierto:true,registro_enviado:true}};
      const cypress=async input=>{const headers={'X-Test-Run-Id':input.runId,'X-Sandbox-Secret':input.secret,'Content-Type':'application/json'};const alta=await fetch(input.api+'/integracion/contratos',{method:'POST',headers,body:JSON.stringify(cuerpo('4.2',input.anexoId,input.fecha))});assert.equal(alta.status,201);fs.mkdirSync(path.join(input.dir,'screenshots'),{recursive:true});fs.mkdirSync(path.join(input.dir,'videos'),{recursive:true});fs.writeFileSync(path.join(input.dir,'G036-UI-05.json'),JSON.stringify(acta));fs.writeFileSync(path.join(input.dir,'G036-cypress.json'),JSON.stringify({totalTests:1,simulacion:true}));fs.writeFileSync(path.join(input.dir,'screenshots','simulada.png'),'SIMULACION_LOCAL');fs.writeFileSync(path.join(input.dir,'videos','g036.cy.js.mp4'),'SIMULACION_LOCAL');return{codigo:0,totalTests:1,acta};};
      const z=await principal(args,{proceso:{QA_AUTORIZADO:'SI'},archivo:envFile,prueba:true,dobles:{newman:ejecutarNewman,cypress}});
      assert.equal(z.codigo,0);assert.equal(z.preflight.ok,true);assert(fs.existsSync(path.join(dir,'preflight.json')));assert(fs.existsSync(path.join(dir,'resultado.json')));assert(fs.existsSync(path.join(dir,'TC-M07-G036_resultado.md')));
    }finally{await sim.cerrar();}
  });
  await paso(4,'Lanzadores Newman y Cypress con spawn real','HERRAMIENTA_NEWMAN',async()=>{const sim=await simuladorG036();try{const dir=path.join(temporal,runId,'newman');const col=JSON.parse(fs.readFileSync(path.join(base,'G036.postman_collection.json')));col.item=col.item.slice(0,1);const env={values:[['base_url',sim.api],['run_id',runId],['sandbox_secret','LOCAL'],['admin_token','LOCAL']].map(([key,value])=>({key,value,enabled:true}))};const z=await proceso(process.execPath,[path.join(base,'pruebas','newman_hijo.mjs')],envGuard,JSON.stringify({salida:dir,coleccion:col,environment:env}));assert.equal(z.code,0,z.error||z.err.slice(-500));const resumenNewman=JSON.parse(z.out);assert.equal(resumenNewman.reportes,true);assert.equal(resumenNewman.codigo,0);assert.equal(resumenNewman.fallos,0);assert.equal(resumenNewman.solicitudes,1);assert(fs.existsSync(path.join(dir,'newman-G036.json')));assert(fs.existsSync(path.join(dir,'newman-G036.html')));assert(fs.existsSync(path.join(temporal,runId,'cypress','G036-cypress-salida.log')));}finally{await sim.cerrar();}});
  await paso(5,'Escenarios integrales con inyección y listas barajadas','CONTRATO',async()=>{const salidas=path.join(temporal,'escenarios');const z=await proceso(process.execPath,[path.join(base,'pruebas','escenarios_g036.mjs')],{...envGuard,QA_VERIFICAR_SALIDAS:salidas},'',600000);assert.equal(z.code,0,z.error||z.err.slice(-1000));const salidasEsc=JSON.parse(z.out);assert.equal(salidasEsc.length,esc.integrales);for(const x of esc.escenarios){const salidaEsc=salidasEsc.find(y=>y.id===x.id);assert(salidaEsc, 'Escenario ausente: '+x.id);assert.deepEqual(['01','02','03','04','05'].map(k=>salidaEsc.veredictos[k]),x.esperado,x.id+': veredictos');assert.equal(salidaEsc.oficial,x.oficial,x.id+': oficial');assert.equal(salidaEsc.rollback,!x.rollbackFallido,x.id+': rollback');if(x.problemaTecnico)assert(salidaEsc.problemas_tecnicos.some(v=>v.includes('cy.visit()')));else assert.deepEqual(salidaEsc.problemas_tecnicos,[],x.id+': problemas técnicos');process.stdout.write('OK escenario_'+x.id+': '+['01','02','03','04','05'].map(k=>k+'='+salidaEsc.veredictos[k]).join(' ')+' oficial='+salidaEsc.oficial+' solicitudes='+salidaEsc.peticiones+'/80\n');}});
  await paso(6,'Forma de resultado.json y reglas de registro_qa','CONTRATO',async()=>{for(const x of esc.escenarios)comprobarPaso6(path.join(temporal,'escenarios',x.id,runId),x,runId);});
  await paso(7,'Pydantic real de .venv','CONTRATO',async()=>{const python=path.resolve(base,'../../../../../.venv/Scripts/python.exe');assert(fs.existsSync(python),'Python .venv ausente');const z=await proceso(python,[path.join(base,'pruebas','g036_dto.test.py')]);assert.equal(z.code,0,z.error||z.err.slice(-500));});
  await paso(8,'--comprobar, --capacidades y SHA-256','CONTRATO',async()=>{assert.equal(comprobar(),0);for(const flag of ['--comprobar','--capacidades']){const z=await proceso(process.execPath,[path.join(base,'g036.mjs'),flag]);assert.equal(z.code,0,z.error||z.err);if(flag==='--capacidades')assert.equal(JSON.parse(z.out).grupo,grupo);}const readme=fs.readFileSync(path.join(base,'README.md'),'utf8');for(const [archivo,etiqueta] of [['g036.mjs','g036.mjs'],['pruebas/verificar.mjs','verificar.mjs']]){const esperado=readme.match(new RegExp('SHA-256 esperado de `'+etiqueta.replace('.','\\.')+'`: `([0-9a-f]{64})`'))?.[1];assert(esperado,'SHA ausente: '+etiqueta);assert.equal(sha(path.join(base,archivo)),esperado,'SHA distinto: '+etiqueta);}});
  await paso(9,'Intercepción X-Test-Run-Id y ambos orígenes','HERRAMIENTA_CYPRESS_EJECUCION',async()=>{const {clasificarIntercepcion}=createRequire(import.meta.url)('../lib/intercepcion.cjs');for(const host of ['api.inmero.co','www.api.inmero.co']){const z=clasificarIntercepcion(`https://${host}/api-sgpmp-test/integracion/contratos`,'POST','https://www.api.inmero.co/api-sgpmp-test','https://api.inmero.co/sigab-test');assert.equal(z.destino,'API');assert.equal(z.ruta,'/integracion/contratos');}assert.equal(clasificarIntercepcion('https://fonts.googleapis.com/css','GET','https://www.api.inmero.co/api-sgpmp-test','https://api.inmero.co/sigab-test').destino,'BLOQUEADO');const log=fs.readFileSync(path.join(temporal,runId,'cypress','G036-cypress-salida.log'),'utf8');assert(!log.includes('RED_REMOTA_BLOQUEADA'));});
  await paso(10,'Ejemplo conforme y validación externa','CONTRATO',async()=>{const salidas=path.join(temporal,'escenarios');for(const [id,esperada] of [['a_conforme','OFICIAL'],['i_rollback_fallido','TECNICO'],['f_sin_permisos','TECNICO'],['h_sin_aprobado','TECNICO']])comprobarPaso10(path.join(salidas,id,runId),esperada);const origen=path.join(salidas,'a_conforme',runId),dest=path.join(os.tmpdir(),'g036-verificar-ejemplo');fs.mkdirSync(dest,{recursive:true});fs.cpSync(origen,path.join(dest,runId),{recursive:true,force:true});fs.writeFileSync(path.join(dest,'capacidades.json'),JSON.stringify(CAPACIDADES,null,2));const registro=path.resolve(base,'../../../../../../SIGAB_QA_ORQUESTACION/scripts/registro_qa.py');assert(fs.existsSync(registro),'registro_qa.py no localizado');const python=path.resolve(base,'../../../../../.venv/Scripts/python.exe');const z=await proceso(python,[registro,'validar','--grupo','G036','--resultado',path.join(dest,runId,'resultado.json'),'--capacidades',path.join(dest,'capacidades.json')]);assert.equal(z.code,0,z.error||z.err.slice(-500));assert.equal(JSON.parse(z.out).clasificacion,'OFICIAL');});
  const bloqueos=fs.existsSync(guardLog)?fs.readFileSync(guardLog,'utf8').trim().split(/\r?\n/).filter(Boolean):[];
  tabla.push({numero:'RED',nombre:'Intentos a red externa',estado:bloqueos.length===0?'OK':'FALLO',clasificacion_fallo:bloqueos.length===0?'NINGUNO':'PREFLIGHT_ENTORNO',intentos:bloqueos.length});
  process.stdout.write(JSON.stringify({tabla,sha256:{ejecutor:sha(path.join(base,'g036.mjs')),infraestructura:Object.fromEntries(['lib/intercepcion.cjs','pruebas/cypress_hijo.mjs','pruebas/simulador_g036.mjs','pruebas/verificar.mjs'].map(x=>[x,sha(path.join(base,x))]))}},null,2)+'\n');
  if(tabla.some(x=>x.estado==='FALLO'))process.exitCode=2;
}finally{if(tabla.some(x=>x.estado==='FALLO'))process.stdout.write(`Temporal conservado: ${temporal}\n`);else fs.rmSync(temporal,{recursive:true,force:true});}
}





