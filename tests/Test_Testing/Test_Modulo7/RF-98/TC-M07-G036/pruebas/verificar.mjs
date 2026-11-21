// Verificador local G036 V2. RED bloquea destinos externos; los pasos con spawn los ejecuta QA.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {CAPACIDADES,comprobar,principal} from '../g036.mjs';
import {simuladorG036} from './simulador_g036.mjs';
import {ejecutarEscenarios} from './escenarios_g036.mjs';
const {clasificarIntercepcion}=createRequire(import.meta.url)('../lib/intercepcion.cjs');
const {sanearError}=createRequire(import.meta.url)('../lib/privacidad.cjs');
const DIR=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const sha=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
export function comprobarPrivacidad(dir){
  const archivos=p=>fs.readdirSync(p,{withFileTypes:true}).flatMap(x=>{const ruta=path.join(p,x.name);return x.isDirectory()?archivos(ruta):[ruta];});
  const lista=archivos(dir);
  assert(!lista.some(x=>/\.mp4$|\(failed\)/i.test(x)),'Vídeo o captura automática de fallo');
  for(const archivo of lista){
    const contenido=fs.readFileSync(archivo).toString('latin1');
    assert(!/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}|authorization/i.test(contenido),'Artefacto privado: '+path.relative(dir,archivo));
  }
  return lista;
}
export function comprobarPaso6(dir,x,runId){
  const r=JSON.parse(fs.readFileSync(path.join(dir,'resultado.json')));
  assert.equal(r.grupo,'G036');assert.equal(r.run_id,runId);assert.equal(r.version,2);
  assert.equal(typeof r.autorizacion_referencia,'string');assert.equal(typeof r.consume_version,'boolean');
  assert.equal(r.oficial,x.oficial);assert.deepEqual(['01','02','03','04','05'].map(k=>r.veredictos[k]),['01','02','03','04','05'].map(k=>x.veredictos[k]));
  assert.equal(r.cierre.rollback.verificado,x.rollback);
  assert.deepEqual(Object.keys(r.casos).sort(),CAPACIDADES.casos.slice().sort());
  assert(Array.isArray(r.comprobaciones));for(const v of r.comprobaciones)for(const k of ['caso','fuente','id','tipo','estado','evidencia'])assert.equal(typeof v[k],'string');
  assert.equal(typeof r.cypress.total_pruebas,'number');
  assert(Array.isArray(r.solicitudes));for(const x of r.solicitudes)assert.equal(x.actor,'administrador');
  assert(Array.isArray(r.evidencias));for(const e of r.evidencias)assert(fs.statSync(path.join(dir,e),{throwIfNoEntry:false})?.isFile(),e);
  assert(Array.isArray(r.incidencias));for(const v of r.incidencias)for(const k of ['caso','regla','severidad','certeza','equipo_inicial','fundamento'])assert.equal(typeof v[k],'string');
  for(const v of r.incidencias)assert(['Desarrollo','AIoT','DBA','Implementación','POR DETERMINAR'].includes(v.equipo_inicial));
  if(x.id==='b_mappers_val_entrada')assert(r.incidencias.some(v=>v.caso==='TC-M07-04'&&v.severidad==='BAJA'));
  if(x.id==='c_activar_habilitado_cupo_lleno')assert(r.incidencias.some(v=>v.caso==='TC-M07-05'&&v.severidad==='MEDIA'));
  if(x.id==='e_sin_anexo_revision')assert.equal(r.preflight_datos.find(v=>v.requisito==='ANEXO_EN_REVISION')?.cumple,false);
  if(x.id==='g_login_invalido'){assert.equal(r.consume_version,false);assert.equal(r.newman,undefined);}
  if(r.auditoria)for(const e of r.auditoria){for(const k of ['id','tipo','version','estado','fecha','actor'])assert(Object.hasOwn(e,k));assert(!Object.keys(e).some(k=>/nombre|correo/i.test(k)));}
  assert.equal(fs.readdirSync(dir).filter(f=>f.endsWith('.md')).length,1);
  assert(fs.existsSync(path.join(dir,'TC-M07-G036_reevaluacion_V2.md')));
  comprobarPrivacidad(dir);
  return r;
}
export function comprobarPaso10(dir,esperada){
  const r=JSON.parse(fs.readFileSync(path.join(dir,'resultado.json'))),runId=path.basename(dir);
  assert.equal(r.run_id,runId);assert.equal(r.version,2);
  const http=r.cierre?.run?.cierre_http,confirmado=http===200,rollback=r.cierre?.rollback?.verificado===true;
  const estadoRun=confirmado||(http===404&&rollback)?'CERRADO':http==null&&r.consume_version?'ABIERTO_PENDIENTE':http==null?'PREPARADO':'DESCONOCIDO';
  const hechas=new Set(r.comprobaciones.filter(v=>v.tipo==='ASSERT'&&['APROBADO','RECHAZADO'].includes(v.estado)).map(v=>[v.caso,v.fuente,v.id].join('|')));
  const completas=Object.entries(CAPACIDADES.comprobaciones_obligatorias).every(([caso,fuentes])=>Object.entries(fuentes).every(([fuente,ids])=>ids.every(id=>hechas.has([caso,fuente,id].join('|')))));
  const completo=completas&&r.cypress?.total_pruebas>0&&Object.values(r.casos).every(x=>['APROBADO','RECHAZADO'].includes(x.estado));
  const informe=path.join(dir,'TC-M07-G036_reevaluacion_V2.md');
  const evidenciaValida=fs.existsSync(informe)&&r.evidencias.every(x=>typeof x==='string'&&!x.split(/[\\/]/).includes('..')&&fs.statSync(path.join(dir,x),{throwIfNoEntry:false})?.isFile());
  const clasificacion=r.oficial===true&&completo&&rollback&&confirmado&&evidenciaValida?'OFICIAL':r.oficial===false&&['CERRADO','PREPARADO'].includes(estadoRun)?'TECNICO':'INCIERTO';
  assert.equal(clasificacion,esperada);return clasificacion;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const temporal=fs.mkdtempSync(path.join(os.tmpdir(),'g036-v2-verificar-'));
  const log=path.join(temporal,'red-bloqueada.log'),guard=path.join(temporal,'guard.cjs');
  fs.writeFileSync(guard,'const fs=require("node:fs"),net=require("node:net");const old=net.Socket.prototype.connect;net.Socket.prototype.connect=function(...args){const x=args[0],h=typeof x==="object"?(x.host||x.hostname):typeof args[1]==="string"?args[1]:null;if(h&&!["127.0.0.1","localhost","::1"].includes(h)){fs.appendFileSync('+JSON.stringify(log)+',String(h)+"\\n");throw Error("RED_REMOTA_BLOQUEADA");}return old.apply(this,args);};');
  const env={...process.env,NODE_OPTIONS:'--require="'+guard.replace(/\\/g,'/')+'"',CYPRESS_CRASH_REPORTS:'0'};
  const runId='RUN-G036-V2-20261120-000000',tabla=[];
  async function proceso(programa,args,variables=env,entrada='',timeout=300000){return new Promise(resolve=>{let p;try{p=spawn(programa,args,{cwd:DIR,env:variables,windowsHide:true,stdio:['pipe','pipe','pipe'],timeout});}catch(e){resolve({code:null,error:e.code??e.message,out:'',err:''});return;}let out='',err='',done=false;const finish=x=>{if(!done){done=true;resolve(x);}};p.stdout.on('data',x=>out+=x);p.stderr.on('data',x=>err+=x);p.on('error',e=>finish({code:null,error:e.code??e.message,out,err}));p.on('close',code=>finish({code,error:null,out,err}));p.stdin.on('error',()=>{});p.stdin.end(entrada);});}
  async function paso(numero,nombre,categoria,fn){try{await fn();tabla.push({numero,nombre,estado:'OK',clasificacion_fallo:'NINGUNO'});}catch(e){const detalle=String(e?.message??e);tabla.push({numero,nombre,estado:'FALLO',clasificacion_fallo:/EPERM/.test(detalle)?'SANDBOX':categoria,detalle});}}
  const archivos=d=>fs.readdirSync(d,{withFileTypes:true}).flatMap(x=>{if(['Resultados','EvaluacionV2','node_modules'].includes(x.name))return[];const p=path.join(d,x.name);return x.isDirectory()?archivos(p):/\.(?:mjs|js|cjs)$/.test(x.name)?[p]:[];});
  try{
    await paso(1,'Modo estricto y sintaxis','CONTRATO',async()=>{for(const f of archivos(DIR)){if(!f.endsWith('.mjs'))new vm.Script('"use strict";\n'+fs.readFileSync(f,'utf8'));const z=await proceso(process.execPath,['--check',f]);assert.equal(z.code,0,z.error||z.err);}});
    await paso(2,'Cypress real contra doble actual','HERRAMIENTA_CYPRESS_EJECUCION',async()=>{const bin=path.resolve(DIR,'../../../../../node_modules/cypress/bin/cypress');assert(fs.existsSync(bin),'Cypress no instalado');const invalido=path.join(temporal,'cypress-invalido');fs.mkdirSync(invalido);const bloqueo=await proceso(process.execPath,[bin,'run','--config-file',path.join(DIR,'g036.cypress.config.cjs'),'--spec',path.join(DIR,'g036.cy.js'),'--headless','--browser','electron'],{...env,CYPRESS_ARTIFACTS_DIR:invalido,CYPRESS_API_BASE:'https://invalid.example.invalid',CYPRESS_FRONT_BASE:'https://invalid.example.invalid',CYPRESS_RUN_ID:runId,CYPRESS_ADMIN_TOKEN:'LOCAL',CYPRESS_SANDBOX_SECRET:'LOCAL',CYPRESS_VERSION_LIBRE:'6.2',CYPRESS_LOCAL_SMOKE:'SI'});assert.notEqual(bloqueo.code,null,bloqueo.error||bloqueo.err);assert.notEqual(bloqueo.code,0,'Cypress aceptó host inválido');assert.equal(JSON.parse(fs.readFileSync(path.join(invalido,'G036-cypress.json'))).totalTests,1);const sim=await simuladorG036();try{const inicio=sim.peticiones.length;const dir=path.join(temporal,runId,'cypress');const input={api:sim.api,front:sim.front,dir,runId,token:'LOCAL',secret:'LOCAL',fecha:'2027-12-31',anexoId:2,anexoCodigo:'ANEXO-AAEF-V2.0',versionLibre:'6.2',cupoLleno:true,versiones:{ACTIVO:'2.1',DEPRECADO:'2.0',INACTIVO:'1.0'},localSmoke:true};const z=await proceso(process.execPath,[path.join(DIR,'pruebas/cypress_hijo.mjs')],env,JSON.stringify(input),180000);assert.equal(z.code,0,z.error||z.err.slice(-800));const out=JSON.parse(z.out);assert.equal(out.totalTests,1);assert.equal(out.acta?.pendiente_activar,true);assert.equal(out.acta?.captura,true);const pantalla=sim.peticiones.slice(inicio).filter(x=>x.api&&!['/sesiones/','/sesiones/refresh'].includes(x.ruta));assert(pantalla.length>0,'sin lecturas API de pantalla');assert(pantalla.every(x=>x.runCorrecto&&x.sandbox),'peticion de pantalla sin cabeceras del sandbox');assert(pantalla.every(x=>!x.concurrente),'peticiones concurrentes del mismo run');assert(pantalla.some(x=>x.metodo==='GET'&&x.ruta==='/integracion/contratos'),'sin lectura de contratos');comprobarPrivacidad(dir);const del=await fetch(sim.api+'/test-control/runs/'+runId,{method:'DELETE',headers:{'X-Sandbox-Secret':'LOCAL'}});assert.equal(del.status,200);}finally{await sim.cerrar();}});
    await paso(3,'CLI y preflight antes de red','PREFLIGHT_ENTORNO',async()=>{const dir=path.join(temporal,'cli',runId);fs.mkdirSync(dir,{recursive:true});const contexto=path.join(dir,'contexto_operacion.json');fs.writeFileSync(contexto,JSON.stringify({grupo:'G036',version:2,intento:1,run_id:runId,operacion:'REEVALUAR',referencia:'LOCAL',casos:CAPACIDADES.casos}));const args=['--autorizacion','LOCAL','--operacion','reevaluar','--version','2','--intento','1','--run-id',runId,'--contexto',contexto];const z=await principal(args,{proceso:{QA_AUTORIZADO:'NO'},archivo:path.join(temporal,'inexistente.env'),prueba:true});assert.equal(z.codigo,2);assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'preflight.json'))).ok,false);await assert.rejects(()=>principal(args.map(x=>x==='LOCAL'?'OTRA':x),{proceso:{QA_AUTORIZADO:'SI'},archivo:path.join(temporal,'inexistente.env'),prueba:true}),/CONTEXTO_INCOHERENTE/);});
    await paso(4,'Lanzador Newman con spawn real','HERRAMIENTA_NEWMAN',async()=>{const sim=await simuladorG036();try{const input={coleccion:JSON.parse(fs.readFileSync(path.join(DIR,'G036.postman_collection.json'))),environment:{values:[['base_url',sim.api],['run_id',runId],['sandbox_secret','LOCAL'],['admin_token','LOCAL']].map(([key,value])=>({key,value,enabled:true}))},salida:path.join(temporal,runId,'newman')};const z=await proceso(process.execPath,[path.join(DIR,'pruebas/newman_hijo.mjs')],env,JSON.stringify(input));assert.equal(z.code,0,z.error||z.err);const x=JSON.parse(z.out);assert.equal(x.fallos,0);assert.equal(x.reportes,true);comprobarPrivacidad(input.salida);}finally{await sim.cerrar();}});
    await paso(5,'Dieciseis escenarios V2 integrales','CONTRATO',async()=>{const r=await ejecutarEscenarios(path.join(temporal,'escenarios'));assert.equal(r.length,16);});
    await paso(6,'Forma de resultado y privacidad','CONTRATO',async()=>{for(const x of JSON.parse(fs.readFileSync(path.join(temporal,'escenarios','resumen_escenarios.json'))))comprobarPaso6(x.dir,x,runId);const p=path.join(temporal,'privacidad');fs.mkdirSync(p);fs.writeFileSync(path.join(p,'muestra.txt'),'Authorization: Bearer eyJhbGci.eyJzdWI.abc persona@local.invalid');assert.throws(()=>comprobarPrivacidad(p),/Artefacto privado/);assert(!/Authorization|eyJ/.test(sanearError('Authorization: Bearer eyJhbGci.eyJzdWI.abc')));});
    await paso(7,'Pydantic real actual','CONTRATO',async()=>{const py=path.resolve(DIR,'../../../../../.venv/Scripts/python.exe');assert(fs.existsSync(py));const z=await proceso(py,[path.join(DIR,'pruebas/g036_dto.test.py')]);assert.equal(z.code,0,z.error||z.err);});
    await paso(8,'Capacidades, contrato T2-T4 y SHA-256','CONTRATO',async()=>{assert.equal(comprobar(),0);for(const flag of ['--comprobar','--capacidades']){const q=await proceso(process.execPath,[path.join(DIR,'g036.mjs'),flag]);assert.equal(q.code,0,q.error||q.err);if(flag==='--capacidades')assert.deepEqual(JSON.parse(q.out),CAPACIDADES);}const z=await proceso(process.execPath,[path.join(DIR,'pruebas/contrato_cruzado.test.mjs')]);assert.equal(z.code,0,z.error||z.err);for(const key of ['T2','T3','T4'])assert(z.out.includes('OK '+key));const readme=fs.readFileSync(path.join(DIR,'README.md'),'utf8');for(const f of ['g036.mjs','verificar.mjs']){const label=f==='verificar.mjs'?'pruebas/verificar.mjs':f;const h=readme.match(new RegExp('SHA-256 esperado de '+f.replace('.','\\.')+': ([0-9a-f]{64})'))?.[1];assert(h,label);assert.equal(sha(path.join(DIR,label)),h);}});
    await paso(9,'Intercepción y origen permitido','HERRAMIENTA_CYPRESS_EJECUCION',async()=>{for(const host of ['api.inmero.co','www.api.inmero.co']){const z=clasificarIntercepcion('https://'+host+'/api-sgpmp-test/integracion/contratos','GET','https://www.api.inmero.co/api-sgpmp-test','https://api.inmero.co/sigab-test');assert.equal(z.destino,'API');}assert.equal(clasificarIntercepcion('https://fonts.googleapis.com/css','GET','https://www.api.inmero.co/api-sgpmp-test','https://api.inmero.co/sigab-test').destino,'BLOQUEADO');const archivo=path.join(temporal,runId,'cypress','G036-cypress-salida.log');if(!fs.existsSync(archivo)&&tabla.find(x=>x.numero===2)?.clasificacion_fallo==='SANDBOX')throw Error('EPERM_CYPRESS_SIN_LOG_PASO2');assert(fs.existsSync(archivo),'CYPRESS_SIN_LOG_PASO2');assert(!fs.readFileSync(archivo,'utf8').includes('RED_REMOTA_BLOQUEADA'));});
    await paso(10,'Clasificación oficial y ejemplo de registro_qa','CONTRATO',async()=>{const xs=JSON.parse(fs.readFileSync(path.join(temporal,'escenarios','resumen_escenarios.json')));for(const x of xs)comprobarPaso10(x.dir,x.oficial?'OFICIAL':'TECNICO');const ejemplo=path.join(os.tmpdir(),'g036-v2-verificar-ejemplo');fs.mkdirSync(ejemplo,{recursive:true});fs.cpSync(xs[0].dir,path.join(ejemplo,runId),{recursive:true,force:true});fs.writeFileSync(path.join(ejemplo,'capacidades.json'),JSON.stringify(CAPACIDADES));const registro=path.resolve(DIR,'../../../../../../SIGAB_QA_ORQUESTACION/scripts/registro_qa.py'),py=path.resolve(DIR,'../../../../../.venv/Scripts/python.exe');assert(fs.existsSync(registro));const z=await proceso(py,[registro,'validar','--grupo','G036','--resultado',path.join(ejemplo,runId,'resultado.json'),'--capacidades',path.join(ejemplo,'capacidades.json')]);assert.equal(z.code,0,z.error||z.err);assert.equal(JSON.parse(z.out).clasificacion,'OFICIAL');});
    await paso(11,'Pruebas locales y dirRun','CONTRATO',async()=>{const z=await proceso(process.execPath,[path.join(DIR,'pruebas/g036_local.test.mjs')]);assert.equal(z.code,0,z.error||z.err);assert(z.out.includes('dirRun V2'));});
    const intentos=fs.existsSync(log)?fs.readFileSync(log,'utf8').trim().split(/\r?\n/).filter(Boolean).length:0;
    tabla.push({numero:'RED',nombre:'Intentos a red externa',estado:intentos===0?'OK':'FALLO',clasificacion_fallo:intentos===0?'NINGUNO':'PREFLIGHT_ENTORNO',intentos});
    process.stdout.write(JSON.stringify({tabla},null,2)+'\n');
    if(tabla.some(x=>x.estado==='FALLO'))process.exitCode=2;
  }finally{if(tabla.some(x=>x.estado==='FALLO'))process.stdout.write('Temporal conservado: '+temporal+'\n');else fs.rmSync(temporal,{recursive:true,force:true});}
}



