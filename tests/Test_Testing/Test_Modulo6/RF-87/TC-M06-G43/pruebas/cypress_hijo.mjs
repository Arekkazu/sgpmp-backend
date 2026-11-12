// Copiado de TC-M06-G40/pruebas/cypress_hijo.mjs; salida por panel y grupo deducido.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const DIR=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),input=JSON.parse(fs.readFileSync(0,'utf8'));
const grupo=path.basename(DIR).match(/^TC-M06-(G\d+)$/)?.[1];
const local=Boolean(input.localSmoke)&&path.resolve(input.dir).startsWith(path.resolve(os.tmpdir())+path.sep);
if(!local&&!input.dir.startsWith(path.join(DIR,'Resultados')+path.sep)&&!input.dir.startsWith(path.join(DIR,'EvaluacionV')))throw Error('CYPRESS_FUERA_RUN');
if(!grupo||!new RegExp(`^RUN-${grupo}-V\\d+-\\d{8}-\\d{6}$`).test(input.runId)||!/^[0-9]{3}$/.test(input.panel))throw Error('CYPRESS_CONTEXTO');
const loopback=u=>{try{const x=new URL(u);return x.protocol==='http:'&&['127.0.0.1','localhost'].includes(x.hostname)&&Boolean(x.port)&&x.pathname==='/';}catch{return false;}};
if(local?!(loopback(input.api)&&loopback(input.front)):!(/^https:\/\/(?:www\.)?api\.inmero\.co\/api-sgpmp-test$/.test(input.api)&&/^https:\/\/(?:www\.)?api\.inmero\.co\/sigab-test$/.test(input.front)))throw Error('CYPRESS_HOST');
const bin=path.resolve(DIR,'../../../../../node_modules/cypress/bin/cypress');
const stem=grupo.toLowerCase();
const args=[bin,'run','--config-file',path.join(DIR,`${stem}.cypress.config.cjs`),'--spec',path.join(DIR,`${stem}.cy.js`),'--headless','--browser','electron'];
const vars={API_BASE:input.api,FRONT_BASE:input.front,RUN_ID:input.runId,ARTIFACTS_DIR:input.dir,PANEL:input.panel,EXPECTED:JSON.stringify(input.esperado),PROD_LOGIN_TOKEN:input.token,SANDBOX_SECRET:input.secret,LOCAL_SMOKE:local?'SI':'NO'};
const env={...process.env,CYPRESS_ARTIFACTS_DIR:input.dir,...Object.fromEntries(Object.entries(vars).map(([k,v])=>['CYPRESS_'+k,String(v)]))};
const result=await new Promise(resolve=>{const p=spawn(process.execPath,args,{env,stdio:['ignore','pipe','pipe'],windowsHide:true,timeout:180000});let out='',err='';p.stdout.on('data',x=>out=(out+x).slice(-100000));p.stderr.on('data',x=>err=(err+x).slice(-100000));p.on('error',e=>resolve({code:2,out,err:e.code??e.message}));p.on('close',code=>resolve({code,out,err}));});
const sanear=s=>String(s).replaceAll(String(input.token),'[RESERVADO]').replaceAll(String(input.secret),'[RESERVADO]').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+/g,'[RESERVADO]');
fs.mkdirSync(input.dir,{recursive:true});fs.writeFileSync(path.join(input.dir,`${grupo}-cypress-salida.log`),sanear(result.out+'\n'+result.err));
let acta=null,meta=null;try{acta=JSON.parse(fs.readFileSync(path.join(input.dir,`${grupo}-UI-${input.panel}.json`)));}catch{}try{meta=JSON.parse(fs.readFileSync(path.join(input.dir,`${grupo}-cypress.json`)));}catch{}
process.stdout.write(JSON.stringify({codigo:result.code,totalTests:meta?.totalTests??0,acta}));if(result.code!==0)process.exitCode=2;
