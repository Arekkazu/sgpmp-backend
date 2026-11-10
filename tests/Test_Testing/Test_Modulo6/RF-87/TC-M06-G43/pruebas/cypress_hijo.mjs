import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const DIR=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),input=JSON.parse(fs.readFileSync(0,'utf8'));
if(!input.dir.startsWith(path.join(DIR,'Resultados')+path.sep)&&!input.dir.startsWith(path.join(DIR,'EvaluacionV')))throw Error('CYPRESS_FUERA_RUN');
if(!/^RUN-G43-V\d+-\d{8}-\d{6}$/.test(input.runId)||!['025','026','027'].includes(input.panel))throw Error('CYPRESS_CONTEXTO');
const bin=path.resolve(DIR,'../../../../../node_modules/cypress/bin/cypress');
const args=[bin,'run','--config-file',path.join(DIR,'g43.cypress.config.cjs'),'--spec',path.join(DIR,'g43.cy.js'),'--headless','--browser','electron'];
const vars={API_BASE:input.api,FRONT_BASE:input.front,RUN_ID:input.runId,ARTIFACTS_DIR:input.dir,PANEL:input.panel,EXPECTED:JSON.stringify(input.esperado),PROD_LOGIN_TOKEN:input.token,SANDBOX_SECRET:input.secret};
const env={...process.env,CYPRESS_ARTIFACTS_DIR:input.dir,...Object.fromEntries(Object.entries(vars).map(([k,v])=>['CYPRESS_'+k,String(v)]))};
const result=await new Promise(resolve=>{const p=spawn(process.execPath,args,{env,stdio:['ignore','pipe','pipe'],windowsHide:true,timeout:180000});let out='',err='';p.stdout.on('data',x=>out=(out+x).slice(-100000));p.stderr.on('data',x=>err=(err+x).slice(-100000));p.on('error',e=>resolve({code:2,out,err:e.code??e.message}));p.on('close',code=>resolve({code,out,err}));});
const sanear=s=>String(s).replaceAll(String(input.token),'[RESERVADO]').replaceAll(String(input.secret),'[RESERVADO]').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+/g,'[RESERVADO]');
fs.mkdirSync(input.dir,{recursive:true});fs.writeFileSync(path.join(input.dir,'G43-cypress-salida.log'),sanear(result.out+'\n'+result.err));
let acta=null,meta=null;try{acta=JSON.parse(fs.readFileSync(path.join(input.dir,`G43-UI-${input.panel}.json`)));}catch{}try{meta=JSON.parse(fs.readFileSync(path.join(input.dir,'G43-cypress.json')));}catch{}
process.stdout.write(JSON.stringify({codigo:result.code,totalTests:meta?.totalTests??0,acta}));if(result.code!==0)process.exitCode=2;
