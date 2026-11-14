import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const DIR=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
if(path.basename(input.dir)!=='cypress'||!input.dir.includes(`${path.sep}RUN-G40-V`))throw Error('Cypress fuera del RUN');
const loopback=u=>{try{const x=new URL(u);return x.protocol==='http:'&&['127.0.0.1','localhost'].includes(x.hostname)&&Boolean(x.port)&&x.pathname==='/';}catch{return false;}};
const canonicalApi=/^https:\/\/(?:www\.)?api\.inmero\.co\/api-sgpmp-test$/;
const canonicalFront=/^https:\/\/(?:www\.)?api\.inmero\.co\/sigab-test$/;
if(input.localSmoke?!(loopback(input.api)&&loopback(input.front)):
  !(canonicalApi.test(input.api)&&canonicalFront.test(input.front)))throw Error('Cypress: hosts no permitidos');
const args=[path.join(DIR,'..','..','..','..','..','node_modules','cypress','bin','cypress'),
  'run','--config-file',path.join(DIR,'g40.cypress.config.cjs'),'--spec',path.join(DIR,'g40.cy.js'),
  '--headless','--browser','electron'];
const vars={API_BASE:input.api,FRONT_BASE:input.front,RUN_ID:input.runId,ARTIFACTS_DIR:input.dir,
  PROD_LOGIN_TOKEN:input.token,SANDBOX_SECRET:input.secret,EXPECTED_COUNT:input.expected.conteo,
   SPECIES_ID:input.expected.especie,SPECIES_NAME:input.expected.especieNombre,SENTIDO:input.expected.sentido,
  BASE_NOTICE_IDS:JSON.stringify(input.expected.avisosBase),LOCAL_SMOKE:input.localSmoke?'SI':'NO'};
const env={...process.env,CYPRESS_ARTIFACTS_DIR:input.dir,
  ...Object.fromEntries(Object.entries(vars).map(([k,v])=>['CYPRESS_'+k,String(v)]))};
const tail=(old,chunk)=>{const lines=(old+chunk).split(/\r?\n/);return lines.slice(-4000).join('\n').slice(-2000000);};
const sanear=x=>{
  let safe=String(x);
  for(const value of [input.token,input.secret].filter(Boolean))safe=safe.replaceAll(String(value),'[RESERVADO]');
  return safe.replace(/Bearer\s+\S+|eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+/gi,'[RESERVADO]');
};
const result=await new Promise(resolve=>{const p=spawn(process.execPath,args,{env,stdio:['ignore','pipe','pipe'],windowsHide:true,timeout:180000});
  let stdout='',stderr='',error=null;
  p.stdout.on('data',x=>stdout=tail(stdout,x.toString()));
  p.stderr.on('data',x=>stderr=tail(stderr,x.toString()));
  p.on('error',e=>error=e);p.on('close',code=>resolve({code,error:error?.code??null,stdout,stderr}));});
const salida=sanear(`[stdout]\n${result.stdout}\n[stderr]\n${result.stderr}`.split(/\r?\n/).slice(-4000).join('\n'));
fs.mkdirSync(input.dir,{recursive:true});
fs.writeFileSync(path.join(input.dir,'G40-cypress-salida.log'),salida);
const actaPath=path.join(input.dir,'G40-UI-018-01.json');let acta=null;
if(fs.existsSync(actaPath))try{acta=JSON.parse(fs.readFileSync(actaPath));}catch{}
process.stdout.write(JSON.stringify({codigo:result.code,error:result.error,acta}));
if(result.code!==0){process.stderr.write(salida+'\n');process.exitCode=2;}
