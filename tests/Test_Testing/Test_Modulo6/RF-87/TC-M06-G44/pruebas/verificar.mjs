// Procedimiento local único para la infraestructura del grupo. No crea RUN ni usa TEST.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {grupoDesdeCarpeta,sha256,validarFormaResultado} from '../lib/infra.mjs';
import {simuladorBase} from './simulador_base.mjs';

const base=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const grupo=grupoDesdeCarpeta(base);
assert(grupo,'La carpeta debe tener forma TC-M06-Gnn');
const stem=grupo.toLowerCase();
const escenarios=JSON.parse(fs.readFileSync(path.join(base,'pruebas',`escenarios_${stem}.json`),'utf8'));
const paneles=Object.values(escenarios.paneles);
const {CAPACIDADES}=await import(`../${stem}.mjs`);
const requiereUI=Object.values(CAPACIDADES.comprobaciones_obligatorias??{}).some(f=>Array.isArray(f.UI)&&f.UI.length>0);
const temporal=fs.mkdtempSync(path.join(os.tmpdir(),`${grupo.toLowerCase()}-verificar-`));
const guardLog=path.join(temporal,'red-bloqueada.log');
const guardFile=path.join(temporal,'guard.cjs');
fs.writeFileSync(guardFile,`const fs=require('node:fs');const net=require('node:net');
const original=net.Socket.prototype.connect;
net.Socket.prototype.connect=function(...args){
  const first=args[0];
  const host=typeof first==='object'?(first.host||first.hostname):typeof args[1]==='string'?args[1]:null;
  if(host&&!['127.0.0.1','localhost','::1'].includes(host)){
    fs.appendFileSync(${JSON.stringify(guardLog)},String(host)+'\\n');
    const e=Error('RED_REMOTA_BLOQUEADA');e.code='RED_REMOTA_BLOQUEADA';throw e;
  }
  return original.apply(this,args);
};\n`);
const envGuard={...process.env,NODE_OPTIONS:`--require="${guardFile.replace(/\\/g,'/')}"`,CYPRESS_CRASH_REPORTS:'0'};
const tabla=[];
async function proceso(programa,args,env=envGuard,entrada=null,timeout=240000){
  return await new Promise(resolve=>{
    let p;
    try{p=spawn(programa,args,{cwd:base,env,windowsHide:true,stdio:['pipe','pipe','pipe'],timeout});}
    catch(e){resolve({code:null,error:e.code??'EPERM',out:'',err:String(e.message)});return;}
    let out='',err='',error=null;
    p.stdout.on('data',x=>out=(out+x).slice(-100000));
    p.stderr.on('data',x=>err=(err+x).slice(-100000));
    p.on('error',e=>error=e);
    p.on('close',code=>resolve({code,error:error?.code??null,out,err}));
    p.stdin.on('error',()=>{});
    p.stdin.end(entrada??'');
  });
}
async function paso(numero,nombre,categoria,fn){
  try{await fn();tabla.push({numero,nombre,estado:'OK',clasificacion_fallo:'NINGUNO'});}
  catch(e){const detalle=String(e?.message??e);tabla.push({numero,nombre,estado:'FALLO',clasificacion_fallo:detalle.includes('EPERM')?'SANDBOX':categoria,detalle:detalle.slice(0,180)});}
}
function fuentes(dir){
  return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>{
    if(['Resultados','EvaluacionV2','node_modules'].includes(e.name))return [];
    const archivo=path.join(dir,e.name);
    return e.isDirectory()?fuentes(archivo):/\.(?:mjs|js|cjs)$/.test(e.name)?[archivo]:[];
  });
}
const runId=`RUN-${grupo}-V1-20261110-000000`;
const bin=path.resolve(base,'../../../../../node_modules/cypress/bin/cypress');
try{
  await paso(1,'Modo estricto y sintaxis','CONTRATO',async()=>{
    for(const archivo of fuentes(base)){
      const data=fs.readFileSync(archivo,'utf8');
      if(!archivo.endsWith('.mjs'))new vm.Script('"use strict";\n'+data,{filename:archivo});
      const z=await proceso(process.execPath,['--check',archivo]);
      assert.equal(z.code,0,`${path.relative(base,archivo)}: ${z.err.slice(-300)}`);
    }
  });
  if(!requiereUI)tabla.push({numero:2,nombre:'Cypress real: bloqueo y paneles LOCAL_SMOKE',estado:'NO_APLICA',clasificacion_fallo:'NINGUNO'});
  else await paso(2,'Cypress real: bloqueo y paneles LOCAL_SMOKE','HERRAMIENTA_CYPRESS_COMPILACION',async()=>{
    assert(fs.existsSync(bin),'Cypress no instalado');
    const invalido=path.join(temporal,'invalido');fs.mkdirSync(invalido);
    const env={...envGuard,CYPRESS_ARTIFACTS_DIR:invalido,CYPRESS_API_BASE:'https://invalid.example.invalid',CYPRESS_FRONT_BASE:'https://invalid.example.invalid',CYPRESS_RUN_ID:runId,CYPRESS_PANEL:paneles[0].panel,CYPRESS_EXPECTED:JSON.stringify(paneles[0].esperado),CYPRESS_PROD_LOGIN_TOKEN:'LOCAL',CYPRESS_SANDBOX_SECRET:'LOCAL'};
    const z=await proceso(process.execPath,[bin,'run','--config-file',path.join(base,`${stem}.cypress.config.cjs`),'--spec',path.join(base,`${stem}.cy.js`),'--headless','--browser','electron'],env,null,180000);
    if(z.error==='EPERM')throw Error('spawn EPERM');
    const meta=JSON.parse(fs.readFileSync(path.join(invalido,`${grupo}-cypress.json`),'utf8'));
    assert.equal(meta.totalTests,1);
    assert.notEqual(z.code,0);
    assert((z.out+z.err).includes('BLOQUEO_ENTORNO_CYPRESS'));
    assert(!/Webpack Compilation Error|Legacy octal literals/.test(z.out+z.err));
    const sim=await simuladorBase(escenarios);
    try{
      for(const {panel,esperado} of paneles){
        const dir=path.join(temporal,runId,'cypress',panel);
        const input={dir,api:sim.url,front:sim.url,runId,panel,esperado,token:'LOCAL',secret:'LOCAL',localSmoke:true};
        const salida=await proceso(process.execPath,[path.join(base,'pruebas','cypress_hijo.mjs')],envGuard,JSON.stringify(input),180000);
        assert.equal(salida.code,0,`panel ${panel}: ${(salida.out+salida.err).slice(-600)}`);
        const meta=JSON.parse(fs.readFileSync(path.join(dir,`${grupo}-cypress.json`),'utf8'));
        assert.equal(meta.totalTests,1);
        const acta=JSON.parse(fs.readFileSync(path.join(dir,`${grupo}-UI-${panel}.json`),'utf8'));
        assert(['APROBADO','RECHAZADO'].includes(acta.estado));
        assert(acta.captura);
      }
    }finally{await sim.cerrar();}
  });
  await paso(3,'CLI y preflight antes de red','PREFLIGHT_ENTORNO',async()=>{
    const z=await proceso(process.execPath,[path.join(base,'pruebas',`${stem}_cli.test.mjs`)]);
    if(z.error==='EPERM'){await import(`./${stem}_cli.test.mjs`);return;}
    assert.equal(z.code,0,(z.out+z.err).slice(-500));
  });
  await paso(4,'Lanzadores con spawn real','HERRAMIENTA_NEWMAN',async()=>{
    const sim=await simuladorBase(escenarios);
    try{
      const dir=path.join(temporal,runId,'newman');
      const coleccion=path.join(temporal,'coleccion.json');
      fs.writeFileSync(coleccion,JSON.stringify({info:{name:'Local',_postman_id:'local',schema:'https://schema.getpostman.com/json/collection/v2.1.0/collection.json'},item:[{name:'GET',request:{method:'GET',url:sim.url+'finanzas/periodos/'+Object.keys(escenarios.paneles)[0]+'/prevalidacion'}}]}));
      const z=await proceso(process.execPath,[path.join(base,'pruebas','newman_hijo.mjs')],envGuard,JSON.stringify({salida:dir,coleccion,environment:{values:[]}}));
      if(z.error==='EPERM')throw Error('spawn EPERM');
      assert.equal(z.code,0,(z.out+z.err).slice(-500));
      const d=JSON.parse(z.out);assert.equal(d.codigo,0);assert(d.reportes);
      assert(fs.existsSync(path.join(dir,`newman-${grupo}.json`)));
      if(requiereUI)assert(fs.existsSync(path.join(temporal,runId,'cypress',paneles[0].panel,`${grupo}-cypress-salida.log`)));
    }finally{await sim.cerrar();}
  });
  await paso(5,'Escenarios integrales con y sin campos inyectados','CONTRATO',async()=>{
    const salidas=path.join(temporal,'escenarios');fs.mkdirSync(salidas);
    const z=await proceso(process.execPath,[path.join(base,'pruebas',`${stem}_escenarios.test.mjs`)],{...envGuard,QA_VERIFICAR_SALIDAS:salidas},null,300000);
    if(z.error==='EPERM'){
      process.env.QA_VERIFICAR_SALIDAS=salidas;
      try{await import(`./${stem}_escenarios.test.mjs`);}finally{delete process.env.QA_VERIFICAR_SALIDAS;}
      assert.equal(fs.readdirSync(salidas).length,escenarios.integrales);
      return;
    }
    assert.equal(z.code,0,(z.out+z.err).slice(-800));
    assert.equal(fs.readdirSync(salidas).length,escenarios.integrales);
  });
  await paso(6,'Forma de resultado.json y reglas de registro','CONTRATO',async()=>{
    const {CAPACIDADES}=await import(`../${stem}.mjs`);
    const salidas=path.join(temporal,'escenarios');
    assert(fs.existsSync(salidas)&&fs.readdirSync(salidas).length===escenarios.integrales,'Faltan resultados de escenarios');
    for(const nombre of fs.readdirSync(salidas)){
      const dir=path.join(salidas,nombre),r=JSON.parse(fs.readFileSync(path.join(dir,'resultado.json')));
      const errores=validarFormaResultado(r,CAPACIDADES,dir);
      assert.deepEqual(errores,[],`${nombre}: ${errores.join(',')}`);
      for(const clave of ['grupo','run_id','version','oficial','consume_version','casos','comprobaciones','evidencias','cierre','cypress'])assert(Object.hasOwn(r,clave),`${nombre}: ${clave}`);
    }
    const ejemplo=path.join(salidas,'conforme','resultado.json');
    process.stdout.write(`python scripts/registro_qa.py validar --grupo ${grupo} --resultado <ruta> --capacidades <ruta>\nEjemplo local: ${ejemplo}\n`);
  });
  await paso(7,'Pydantic local','CONTRATO',async()=>{
    const python=path.resolve(base,'../../../../../.venv/Scripts/python.exe');
    assert(fs.existsSync(python),'Python de .venv ausente');
    const z=await proceso(python,[path.join(base,'pruebas',`${stem}_dto.test.py`)]);
    if(z.error==='EPERM')throw Error('spawn EPERM');
    assert.equal(z.code,0,(z.out+z.err).slice(-500));
  });
  await paso(8,'--comprobar, --capacidades y SHA-256','CONTRATO',async()=>{
    const modulo=await import(`../${stem}.mjs`);
    for(const flag of ['--comprobar','--capacidades']){
      const z=await proceso(process.execPath,[path.join(base,`${stem}.mjs`),flag]);
      if(z.error==='EPERM'){
        if(flag==='--comprobar')assert.equal(modulo.comprobar(),0);
        else assert.equal(modulo.CAPACIDADES.grupo,grupo);
        continue;
      }
      assert.equal(z.code,0,(z.out+z.err).slice(-500));
    }
  });
  if(!requiereUI)tabla.push({numero:9,nombre:'Intercepción con orígenes reales de TEST (sin red)',estado:'NO_APLICA',clasificacion_fallo:'NINGUNO'});
  else await paso(9,'Intercepción con orígenes reales de TEST (sin red)','HERRAMIENTA_CYPRESS_EJECUCION',async()=>{
    const {createRequire}=await import('node:module');
    const {clasificarIntercepcion}=createRequire(import.meta.url)('../lib/intercepcion.cjs');
    const API='https://www.api.inmero.co/api-sgpmp-test',FRONT='https://api.inmero.co/sigab-test';
    const casos=[
      ['https://api.inmero.co/api-sgpmp-test/sesiones/','POST','API','/sesiones/'],
      ['https://www.api.inmero.co/api-sgpmp-test/sesiones/','POST','API','/sesiones/'],
      ['https://api.inmero.co/api-sgpmp-test/finanzas/periodos/219/prevalidacion','GET','API','/finanzas/periodos/219/prevalidacion'],
      ['https://www.api.inmero.co/api-sgpmp-test/__sonda__','GET','API','/__sonda__'],
      ['https://api.inmero.co/sigab-test/finanzas/cierre','GET','FRONTAL',null],
      ['https://api.inmero.co/sigab-test/assets/index.js','GET','FRONTAL',null],
      ['https://api.inmero.co/otra-app/x','GET','BLOQUEADO',null],
      ['https://fonts.googleapis.com/css','GET','BLOQUEADO',null]];
    for(const [u,m,d,r] of casos){
      const z=clasificarIntercepcion(u,m,API,FRONT,false);
      assert.equal(z.destino,d,u);assert.equal(z.ruta,r,u);
    }
  });
  const bloqueos=fs.existsSync(guardLog)?fs.readFileSync(guardLog,'utf8').trim().split(/\r?\n/).filter(Boolean):[];
  tabla.push({numero:'RED',nombre:'Intentos externos',estado:bloqueos.length===0?'OK':'FALLO',clasificacion_fallo:bloqueos.length===0?'NINGUNO':'PREFLIGHT_ENTORNO',intentos:bloqueos.length});
  const infraestructura=['lib/infra.mjs','lib/contrato.mjs','lib/informe.mjs','pruebas/newman_hijo.mjs','pruebas/simulador_base.mjs','pruebas/verificar.mjs'];
  process.stdout.write(JSON.stringify({tabla,sha256:{ejecutor:sha256(path.join(base,`${stem}.mjs`)),infraestructura:Object.fromEntries(infraestructura.map(x=>[x,sha256(path.join(base,x))]))}},null,2)+'\n');
  if(tabla.some(x=>x.estado==='FALLO'))process.exitCode=2;
}finally{fs.rmSync(temporal,{recursive:true,force:true});}
