// Base: verificador V2 de G040. G037 solo requiere API (pasos 2 y 9 NO_APLICA).
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {CAPACIDADES,comprobar,dirRun,principal} from '../g037.mjs';
import {simuladorG037} from './simulador_g037.mjs';
import {ejecutarEscenarios} from './escenarios_g037.mjs';

export function comprobarPaso6(dir,x,runId){
  const r=JSON.parse(fs.readFileSync(path.join(dir,'resultado.json')));
  assert.equal(r.grupo,'G037');assert.equal(r.run_id,runId);assert.equal(r.version,3);
  assert.equal(typeof r.autorizacion_referencia,'string');assert.equal(typeof r.consume_version,'boolean');
  assert.equal(r.oficial,x.oficial);assert.deepEqual(['06','07','08'].map(k=>r.veredictos[k]),x.esperado);
  assert.equal(r.cierre.rollback.verificado,!x.rollbackFallido&&!x.loginInvalido&&!x.sinPermisos&&!x.deleteHttp);
  assert.equal(r.cierre.run.cierre_http,x.loginInvalido?null:x.deleteHttp??200);
  if(x.loginInvalido||x.sinPermisos)assert.equal(r.newman,null);else assert(r.newman&&typeof r.newman.codigo==='number');
  assert.deepEqual(Object.keys(r.casos).sort(),CAPACIDADES.casos.slice().sort());
  assert.equal(r.cypress.no_aplica,true);assert.equal(r.cypress.total_pruebas,0);
  for(const [caso,v] of Object.entries(r.casos)){assert.equal(typeof v.estado,'string');assert(Array.isArray(v.comprobaciones));assert.deepEqual(v.comprobaciones,CAPACIDADES.comprobaciones_obligatorias[caso].API);}
  assert(Array.isArray(r.comprobaciones));for(const v of r.comprobaciones){for(const k of ['caso','fuente','id','tipo','estado','evidencia'])assert.equal(typeof v[k],'string');assert.equal(v.tipo,'ASSERT');assert.match(v.id,/^[A-Za-z0-9_-]+$/);}
  assert(Array.isArray(r.evidencias));assert(r.evidencias.every(e=>typeof e==='string'&&fs.existsSync(path.join(dir,e))));
  assert(Array.isArray(r.incidencias));for(const v of r.incidencias){for(const k of ['caso','regla','severidad','certeza','equipo_inicial','fundamento'])assert.equal(typeof v[k],'string');assert(['CRÍTICA','ALTA','MEDIA','BAJA'].includes(v.severidad));assert(['Desarrollo','AIoT','DBA','Implementación'].includes(v.equipo_inicial));}
  assert(Array.isArray(r.preflight_datos));assert.equal(fs.readdirSync(dir).filter(f=>f.endsWith('.md')).length,1);
  const texto=fs.readFileSync(path.join(dir,'TC-M07-G037_reevaluacion_V3.md'),'utf8');assert(texto.includes(runId));for(const id of CAPACIDADES.casos)assert(texto.includes(id));
  return r;
}
export function comprobarPaso10(dir,esperada){
  const r=JSON.parse(fs.readFileSync(path.join(dir,'resultado.json'))),runId=path.basename(dir);
  assert.equal(r.run_id,runId);assert.equal(r.version,3);
  const http=r.cierre?.run?.cierre_http,confirmado=http===200,rollback=r.cierre?.rollback?.verificado===true;
  const efectos=Boolean(r.consume_version);
  const estadoRun=confirmado||(http===404&&rollback)?'CERRADO':http==null&&efectos?'ABIERTO_PENDIENTE':http==null?'PREPARADO':'DESCONOCIDO';
  const hechas=new Set(r.comprobaciones.filter(v=>v.tipo==='ASSERT'&&['APROBADO','RECHAZADO'].includes(v.estado)).map(v=>[v.caso,v.fuente,v.id].join('|')));
  const completas=Object.entries(CAPACIDADES.comprobaciones_obligatorias).every(([caso,fuentes])=>Object.entries(fuentes).every(([fuente,ids])=>ids.every(id=>hechas.has([caso,fuente,id].join('|')))));
  const completo=Object.keys(r.casos).length===CAPACIDADES.casos.length&&completas&&Object.values(r.casos).every(x=>['APROBADO','RECHAZADO'].includes(x.estado));
  const informe=path.join(dir,'TC-M07-G037_reevaluacion_V3.md');
  const evidenciaValida=fs.existsSync(informe)&&r.evidencias.every(x=>typeof x==='string'&&!x.split(/[\\/]/).includes('..')&&fs.statSync(path.join(dir,x),{throwIfNoEntry:false})?.isFile());
  const clasificacion=r.oficial===true&&completo&&rollback&&confirmado&&evidenciaValida?'OFICIAL':r.oficial===false&&['CERRADO','PREPARADO'].includes(estadoRun)?'TECNICO':'INCIERTO';
  assert.equal(clasificacion,esperada);return clasificacion;
}

const DIR=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const temporal=fs.mkdtempSync(path.join(os.tmpdir(),'g037-verificar-'));
  const log=path.join(temporal,'red-bloqueada.log'),guard=path.join(temporal,'guard.cjs');
  fs.writeFileSync(guard,`const fs=require('node:fs'),net=require('node:net');const old=net.Socket.prototype.connect;net.Socket.prototype.connect=function(...args){const x=args[0],h=typeof x==='object'?(x.host||x.hostname):typeof args[1]==='string'?args[1]:null;if(h&&!['127.0.0.1','localhost','::1'].includes(h)){fs.appendFileSync(${JSON.stringify(log)},String(h)+'\\n');throw Error('RED_REMOTA_BLOQUEADA');}return old.apply(this,args);};`);
  const env={...process.env,PYTHONDONTWRITEBYTECODE:'1',NODE_OPTIONS:`--require="${guard.replace(/\\/g,'/')}"`};
  const runId='RUN-G037-V3-20261118-000000';
  const esc=JSON.parse(fs.readFileSync(path.join(DIR,'pruebas/escenarios_g037.json'))).escenarios;
  const tabla=[],sha=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
  async function proceso(programa,args,variables=env,entrada=''){
    return new Promise(resolve=>{let p;try{p=spawn(programa,args,{cwd:DIR,env:variables,windowsHide:true,stdio:['pipe','pipe','pipe'],timeout:300000});}catch(e){resolve({code:null,error:e.code??e.message,out:'',err:''});return;}
      let out='',err='';p.stdout.on('data',x=>out+=x);p.stderr.on('data',x=>err+=x);p.on('error',e=>resolve({code:null,error:e.code??e.message,out,err}));p.on('close',code=>resolve({code,out,err}));p.stdin.on('error',()=>{});p.stdin.end(entrada);});
  }
  async function paso(numero,nombre,categoria,fn){try{await fn();tabla.push({numero,nombre,estado:'OK',clasificacion_fallo:'NINGUNO'});}catch(e){const detalle=String(e?.message??e);tabla.push({numero,nombre,estado:'FALLO',clasificacion_fallo:/EPERM/.test(detalle)?'SANDBOX':categoria,detalle});}}
  const archivos=d=>fs.readdirSync(d,{withFileTypes:true}).flatMap(x=>{if(['Resultados','EvaluacionV2','EvaluacionV3'].includes(x.name))return[];const p=path.join(d,x.name);return x.isDirectory()?archivos(p):/\.(?:mjs|js|cjs)$/.test(x.name)?[p]:[];});
  try{
    await paso(1,'Modo estricto y sintaxis','CONTRATO',async()=>{for(const f of archivos(DIR)){if(!f.endsWith('.mjs'))new vm.Script('"use strict";\n'+fs.readFileSync(f,'utf8'));const z=await proceso(process.execPath,['--check',f]);assert.equal(z.code,0,z.error||z.err);}});
    tabla.push({numero:2,nombre:'Cypress',estado:'NO_APLICA',clasificacion_fallo:'NINGUNO',motivo:'G037 solo exige API'});
    await paso(3,'CLI y preflight antes de red','PREFLIGHT_ENTORNO',async()=>{
      assert.equal(CAPACIDADES.contrato,'sigab-qa-ejecutor/1');assert.deepEqual(Object.keys(CAPACIDADES.comprobaciones_obligatorias).sort(),CAPACIDADES.casos.slice().sort());assert(CAPACIDADES.operaciones.includes('reintentar'));assert.deepEqual(CAPACIDADES.versiones,{min:3,max:3});assert.equal(dirRun({ensayo:false,version:3,runId}),path.join(DIR,'EvaluacionV3','Resultados',runId));
      const sim=await simuladorG037();try{
        const dir=path.join(temporal,'cli',runId);fs.mkdirSync(dir,{recursive:true});
        const archivo=path.join(dir,'contexto_operacion.json');
        fs.writeFileSync(archivo,JSON.stringify({grupo:'G037',version:3,intento:1,run_id:runId,operacion:'REEVALUAR',referencia:'REF-LOCAL',casos:CAPACIDADES.casos,alcance_reevaluacion:{casos:CAPACIDADES.casos,version_anterior:2,motivo:'Reevaluación V3 completa decidida por QA tras INC-M07-G037-01',incumplimientos_previos:'V2 07 RECHAZADO: oraculo patch_invalido demasiado estricto',correcciones_informadas:'ORD-G037-009: oraculo patch_invalido corregido',resultado_esperado:'Tres casos según RF-98 v1.2'},version_anterior:2}));
        const args=['--autorizacion','REF-LOCAL','--operacion','reevaluar','--version','3','--intento','1','--run-id',runId,'--contexto',archivo];
        const reintentoId='RUN-G037-V3-20261118-000001',reintentoDir=path.join(temporal,'cli',reintentoId);fs.mkdirSync(reintentoDir);
        const reintentoArchivo=path.join(reintentoDir,'contexto_operacion.json');fs.writeFileSync(reintentoArchivo,JSON.stringify({grupo:'G037',version:3,intento:2,run_id:reintentoId,operacion:'REINTENTAR',referencia:'REF-LOCAL',casos:CAPACIDADES.casos}));
        const reintentoArgs=['--autorizacion','REF-LOCAL','--operacion','reintentar','--version','3','--intento','2','--run-id',reintentoId,'--contexto',reintentoArchivo];
        const envFile=path.join(temporal,'cli.env');fs.writeFileSync(envFile,`QA_ADMIN_EMAIL=local@example.invalid\nQA_ADMIN_PASSWORD=LOCAL\nQA_SANDBOX_SECRET=LOCAL\nSIGAB_API_TEST_BASE=${sim.api}/\n`);
        const local={...env,NODE_ENV:'test',G037_PRUEBA_ENV_FILE:envFile,QA_AUTORIZADO:'NO'};
        const faltante=await proceso(process.execPath,[path.join(DIR,'g037.mjs'),...args,'--prueba-cli-local'],local);assert.equal(faltante.code,2,faltante.error||faltante.err);assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'preflight.json'))).ok,false);assert.equal(sim.peticiones.length,0);
        const incoherente=await proceso(process.execPath,[path.join(DIR,'g037.mjs'),...args.map(x=>x==='REF-LOCAL'?'OTRA-REF':x),'--prueba-cli-local'],{...local,QA_AUTORIZADO:'SI'});assert.equal(incoherente.code,2);assert.equal(sim.peticiones.length,0);
        const z=await principal(args,{proceso:{QA_AUTORIZADO:'SI'},archivo:envFile,prueba:true,dobles:{newman:async()=>({codigo:0,fallos:0,solicitudes:2,reportes:true})}});assert.equal(z.codigo,0);assert.equal(z.resultado.oficial,true);assert(fs.existsSync(path.join(dir,'resultado.json')));
        const simReintento=await simuladorG037({runId:reintentoId});try{
          fs.writeFileSync(envFile,`QA_ADMIN_EMAIL=local@example.invalid\nQA_ADMIN_PASSWORD=LOCAL\nQA_SANDBOX_SECRET=LOCAL\nSIGAB_API_TEST_BASE=${simReintento.api}/\n`);
          const reintento=await principal(reintentoArgs,{proceso:{QA_AUTORIZADO:'SI'},archivo:envFile,prueba:true,dobles:{newman:async()=>({codigo:0,fallos:0,solicitudes:2,reportes:true})}});assert.equal(reintento.codigo,0);assert.equal(reintento.resultado.run_id,reintentoId);assert.equal(reintento.resultado.oficial,true);assert(fs.existsSync(path.join(reintentoDir,'resultado.json')));assert(fs.existsSync(path.join(dir,'resultado.json')));
        }finally{await simReintento.cerrar();}
      }finally{await sim.cerrar();}
    });
    await paso(4,'Lanzador Newman con spawn real','HERRAMIENTA_NEWMAN',async()=>{
      const sim=await simuladorG037();try{
        const dir=path.join(temporal,runId,'newman'),col=JSON.parse(fs.readFileSync(path.join(DIR,'G037.postman_collection.json')));
        const environment={values:[['base_url',sim.api],['run_id',runId],['sandbox_secret','LOCAL'],['admin_token','LOCAL_ADMIN_TOKEN']].map(([key,value])=>({key,value,enabled:true}))};
        const z=await proceso(process.execPath,[path.join(DIR,'pruebas/newman_hijo.mjs')],env,JSON.stringify({salida:dir,coleccion:col,environment}));assert.equal(z.code,0,z.error||z.err);
        const r=JSON.parse(z.out);assert.equal(r.codigo,0);assert.equal(r.fallos,0);assert.equal(r.solicitudes,2);assert.equal(r.reportes,true);
        for(const f of ['newman-G037.json','newman-G037.html'])assert(fs.existsSync(path.join(dir,f)));
      }finally{await sim.cerrar();}
    });
    await paso(5,'Veinte escenarios integrales','CONTRATO',async()=>{
      const salidas=path.join(temporal,'escenarios');await ejecutarEscenarios(salidas);
      const resultados=JSON.parse(fs.readFileSync(path.join(salidas,'resumen_escenarios.json')));assert.equal(resultados.length,20);
      for(const x of esc){const r=resultados.find(y=>y.id===x.id);assert(r,x.id);assert.deepEqual(['06','07','08'].map(k=>r.veredictos[k]),x.esperado);assert.equal(r.oficial,x.oficial);assert.match(r.linea??'',new RegExp(`OK escenario_${x.id}:`));const detalle=JSON.parse(fs.readFileSync(path.join(r.dir,'resultado.json')));assert.equal(detalle.cierre.rollback.verificado,!x.rollbackFallido&&!x.loginInvalido&&!x.sinPermisos&&!x.deleteHttp);if(detalle.newman){assert.equal(detalle.newman.codigo,0);assert.equal(detalle.newman.fallos,0);assert.equal(detalle.newman.reportes,true);}if(x.loginInvalido)assert.deepEqual(detalle.problemas_tecnicos,['LOGIN_FALLIDO']);}
    });
    await paso(6,'Forma de resultado.json','CONTRATO',async()=>{for(const x of esc)comprobarPaso6(path.join(temporal,'escenarios',x.id,runId),x,runId);});
    await paso(7,'Pydantic real de .venv','CONTRATO',async()=>{const python=path.resolve(DIR,'../../../../../.venv/Scripts/python.exe');assert(fs.existsSync(python));const z=await proceso(python,['-B','-m','pytest','-p','no:cacheprovider',path.join(DIR,'pruebas/g037_dto_test.py'),'-q']);assert.equal(z.code,0,z.error||z.err);});
    await paso(8,'--comprobar, --capacidades y SHA-256','CONTRATO',async()=>{
      assert.equal(comprobar(),0);
      for(const flag of ['--comprobar','--capacidades']){const z=await proceso(process.execPath,[path.join(DIR,'g037.mjs'),flag]);assert.equal(z.code,0,z.error||z.err);if(flag==='--capacidades')assert.deepEqual(JSON.parse(z.out),CAPACIDADES);}
      const cruzado=await proceso(process.execPath,[path.join(DIR,'pruebas/contrato_cruzado.test.mjs')]);assert.equal(cruzado.code,0,cruzado.error||cruzado.err);for(const t of ['T2','T3','T4'])assert.match(cruzado.out,new RegExp(`OK ${t}`));
      const readme=fs.readFileSync(path.join(DIR,'README.md'),'utf8');for(const [f,label] of [['g037.mjs','g037.mjs'],['pruebas/verificar.mjs','verificar.mjs']]){const esperado=readme.match(new RegExp('SHA-256 esperado de `'+label.replace('.','\\.')+'`: `([0-9a-f]{64})`'))?.[1];assert(esperado,label);assert.equal(sha(path.join(DIR,f)),esperado,label);}
    });
    tabla.push({numero:9,nombre:'Intercepción UI',estado:'NO_APLICA',clasificacion_fallo:'NINGUNO',motivo:'No hay UI ni interceptor Cypress en G037'});
    await paso(10,'Ejemplo conforme y registro_qa validar','CONTRATO',async()=>{
      const salidas=path.join(temporal,'escenarios');for(const x of esc)comprobarPaso10(path.join(salidas,x.id,runId),x.clasificacion??(x.oficial?'OFICIAL':'TECNICO'));
      const destino=path.join(temporal,'registro_qa');fs.mkdirSync(destino,{recursive:true});fs.cpSync(path.join(salidas,'a_conforme_v3',runId),path.join(destino,runId),{recursive:true,force:true});fs.writeFileSync(path.join(destino,'capacidades.json'),JSON.stringify(CAPACIDADES,null,2));
      const registro=path.resolve(DIR,'../../../../../../SIGAB_QA_ORQUESTACION/scripts/registro_qa.py'),python=path.resolve(DIR,'../../../../../.venv/Scripts/python.exe');
      assert(fs.existsSync(registro));const z=await proceso(python,[registro,'validar','--grupo','G037','--resultado',path.join(destino,runId,'resultado.json'),'--capacidades',path.join(destino,'capacidades.json')]);assert.equal(z.code,0,z.error||z.err);assert.equal(JSON.parse(z.out).clasificacion,'OFICIAL');
    });
    const intentos=fs.existsSync(log)?fs.readFileSync(log,'utf8').trim().split(/\r?\n/).filter(Boolean).length:0;
    tabla.push({numero:'RED',nombre:'Intentos a red externa',estado:intentos===0?'OK':'FALLO',clasificacion_fallo:intentos===0?'NINGUNO':'PREFLIGHT_ENTORNO',intentos});
    process.stdout.write(JSON.stringify({tabla},null,2)+'\n');if(tabla.some(x=>x.estado==='FALLO'))process.exitCode=2;
  }finally{if(tabla.some(x=>x.estado==='FALLO'))process.stdout.write(`Temporal conservado: ${temporal}\n`);else fs.rmSync(temporal,{recursive:true,force:true});}
}
