import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {CASOS} from '../lib/g43_core.mjs';
import {leerEnv} from '../g43.mjs';

const dir=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g43-cli-'));
const envFile=path.join(tmp,'.env.qa');
const base={SIGAB_API_TEST_BASE:'https://www.api.inmero.co/api-sgpmp-test',QA_SANDBOX_SECRET:'SINTETICO',QA_CONTADOR_EMAIL:'local@example.invalid',QA_CONTADOR_PASSWORD:'SINTETICO'};
let conexiones=0;
const server=http.createServer((_req,res)=>{conexiones++;res.writeHead(500);res.end();});
const writeEnv=values=>fs.writeFileSync(envFile,Object.entries(values).filter(([,v])=>v!==undefined).map(([k,v])=>`${k}=${v}`).join('\n'));

async function run(n,autorizado,values,expectFetch=false){
  writeEnv(values);
  const runId=`RUN-G43-V1-20261110-${String(n).padStart(6,'0')}`;
  const runDir=path.join(tmp,runId);fs.mkdirSync(runDir);
  const ctx=path.join(runDir,'contexto_operacion.json');
  fs.writeFileSync(ctx,JSON.stringify({grupo:'G43',run_id:runId,version:1,intento:1,operacion:'EVALUAR',referencia:'AUT-LOCAL',casos:CASOS}));
  const args=[process.execPath,path.join(dir,'g43.mjs'),'--prueba-cli-local','--operacion','evaluar','--version','1','--intento','1','--run-id',runId,'--autorizacion','AUT-LOCAL','--contexto',ctx];
  const old={argv:process.argv,exitCode:process.exitCode,env:{...process.env},fetch:globalThis.fetch,log:console.log,error:console.error};
  const output=[];let peticiones=0;
  try{
    process.argv=args;process.exitCode=0;
    process.env.NODE_ENV='test';process.env.G43_PRUEBA_ENV_FILE=envFile;
    for(const k of Object.keys(base))delete process.env[k];
    if(autorizado)process.env.QA_AUTORIZADO='SI';else delete process.env.QA_AUTORIZADO;
    globalThis.fetch=async()=>{peticiones++;const pf=JSON.parse(fs.readFileSync(path.join(runDir,'preflight.json'),'utf8'));assert.equal(pf.ok,true);throw Error('PETICION_INTERCEPTADA_LOCAL');};
    console.log=(...x)=>output.push(x.join(' '));console.error=(...x)=>output.push(x.join(' '));
    // Importación nueva ejecuta el guard del CLI; ejecutar() no recibe ensayo ni API local.
    await import(`../g43.mjs?cli=${n}`);
    const pf=JSON.parse(fs.readFileSync(path.join(runDir,'preflight.json'),'utf8'));
    assert.equal(pf.grupo,'G43');assert.equal(pf.run_id,runId);assert.equal(pf.version,1);assert.equal(pf.referencia,'AUT-LOCAL');
    assert.equal(peticiones,expectFetch?1:0);
    assert(!JSON.stringify(pf).includes('SINTETICO'));
    assert(!output.join(' ').includes('SINTETICO'));
    return{pf,code:process.exitCode};
  }finally{
    process.argv=old.argv;process.exitCode=old.exitCode;globalThis.fetch=old.fetch;console.log=old.log;console.error=old.error;
    for(const k of Object.keys(process.env))if(!(k in old.env))delete process.env[k];
    Object.assign(process.env,old.env);
  }
}

try{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  writeEnv(base);
  assert.equal(leerEnv({QA_AUTORIZADO:'SI'},envFile).QA_CONTADOR_EMAIL,base.QA_CONTADOR_EMAIL);
  assert.equal(leerEnv({QA_AUTORIZADO:'SI',QA_CONTADOR_EMAIL:'precedencia'},envFile).QA_CONTADOR_EMAIL,'precedencia');
  assert.equal(leerEnv({},envFile).QA_CONTADOR_EMAIL,undefined);
  const valido=await run(1,true,base,true);assert.equal(valido.pf.ok,true);assert.equal(valido.code,0);
  const sinAuth=await run(2,false,base);assert.equal(sinAuth.pf.ok,false);assert(sinAuth.pf.barreras.includes('QA_AUTORIZADO'));assert(sinAuth.pf.barreras.includes('QA_CONTADOR_EMAIL'));assert.equal(sinAuth.code,2);
  const sinClave=await run(3,true,{...base,QA_CONTADOR_PASSWORD:undefined});assert.equal(sinClave.pf.ok,false);assert.deepEqual(sinClave.pf.barreras,['QA_CONTADOR_PASSWORD']);assert.equal(sinClave.code,2);
  const host=await run(4,true,{...base,SIGAB_API_TEST_BASE:`http://127.0.0.1:${server.address().port}`});assert.equal(host.pf.ok,false);assert.deepEqual(host.pf.barreras,['SIGAB_API_TEST_BASE']);assert.equal(host.code,2);
  const front=await run(5,true,{...base,SIGAB_FRONT_TEST_BASE:`http://127.0.0.1:${server.address().port}`});assert.equal(front.pf.ok,false);assert.deepEqual(front.pf.barreras,['SIGAB_FRONT_TEST_BASE']);assert.equal(front.code,2);
  assert.equal(conexiones,0);
  console.log('OK g43_cli: entorno, preflight antes de petición, host, salida 2 y cero conexiones');
}finally{await new Promise(resolve=>server.close(resolve));fs.rmSync(tmp,{recursive:true,force:true});}
