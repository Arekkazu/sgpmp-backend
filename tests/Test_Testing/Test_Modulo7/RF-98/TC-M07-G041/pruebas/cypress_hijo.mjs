// Estructura del lanzador TC-M06-G43; contexto y variables adaptados a M07.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
const {sanearError}=createRequire(import.meta.url)('../lib/privacidad.cjs');
const DIR=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const grupo=path.basename(DIR).match(/^TC-M07-(G\d{3})$/)?.[1];
const local=Boolean(input.localSmoke)&&path.resolve(input.dir).startsWith(path.resolve(os.tmpdir())+path.sep);
if(!local&&path.resolve(input.dir)!==path.join(DIR,'Resultados',input.runId,'cypress'))throw Error('CYPRESS_FUERA_RUN');
if(grupo!=='G041'||!/^RUN-G041-V1-\d{8}-\d{6}$/.test(input.runId))throw Error('CYPRESS_CONTEXTO');
const loop=u=>{try{const x=new URL(u);return x.protocol==='http:'&&['127.0.0.1','localhost'].includes(x.hostname)&&!!x.port;}catch{return false;}};
if(!input.token||typeof input.token!=='string')throw Error('CYPRESS_TOKEN_AUSENTE');
if(local?!(loop(input.api)&&loop(input.front)):input.api!=='https://www.api.inmero.co/api-sgpmp-test'||input.front!=='https://api.inmero.co/sigab-test')throw Error('CYPRESS_HOST');
const bin=path.resolve(DIR,'../../../../../node_modules/cypress/bin/cypress');
const args=[bin,'run','--config-file',path.join(DIR,'g041.cypress.config.cjs'),'--spec',path.join(DIR,'g041.cy.js'),'--headless','--browser','electron'];
const vars={API_BASE:input.api,FRONT_BASE:input.front,RUN_ID:input.runId,ARTIFACTS_DIR:input.dir,CONTADOR_TOKEN:input.token,LOCAL_SMOKE:local?'SI':'NO'};
const env={...process.env,CYPRESS_ARTIFACTS_DIR:input.dir,...Object.fromEntries(Object.entries(vars).map(([k,v])=>['CYPRESS_'+k,String(v)]))};
const result=await new Promise(resolve=>{const p=spawn(process.execPath,args,{env,stdio:['ignore','pipe','pipe'],windowsHide:true,timeout:180000});let out='',err='',done=false;const finish=x=>{if(!done){done=true;resolve(x);}};p.stdout.on('data',x=>out=(out+x).slice(-100000));p.stderr.on('data',x=>err=(err+x).slice(-100000));p.on('error',e=>finish({code:2,out,err:e.code??e.message}));p.on('close',code=>finish({code,out,err}));});
const sanear=s=>sanearError(s,[input.token]);
fs.mkdirSync(input.dir,{recursive:true});fs.writeFileSync(path.join(input.dir,'G041-cypress-salida.log'),sanear(result.out+'\n'+result.err));
let acta=null,meta=null;try{acta=JSON.parse(fs.readFileSync(path.join(input.dir,'G041-UI-22.json')));}catch{}try{meta=JSON.parse(fs.readFileSync(path.join(input.dir,'G041-cypress.json')));}catch{}
process.stdout.write(JSON.stringify({codigo:result.code,totalTests:meta?.totalTests??0,acta,error:result.code===0?null:sanear(result.err).slice(-500)}));if(result.code!==0)process.exitCode=2;
