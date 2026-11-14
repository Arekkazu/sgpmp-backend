import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const child=path.join(ROOT,'pruebas','cypress_hijo.mjs');
const results=path.join(os.tmpdir(),'g40-cypress-smoke-local');
const resultsExisted=fs.existsSync(results);
const secret='g40-smoke-secret-local';
const species='Bovino';
const scenarios=[
  {name:'aviso_nuevo',notice:true,conteo:1,panelDelay:0,expected:'APROBADO'},
  {name:'sin_aviso',notice:false,conteo:1,panelDelay:0,expected:'RECHAZADO'},
  {name:'render_diferido',notice:true,conteo:1,panelDelay:1800,expected:'APROBADO'},
  {name:'aviso_plural',notice:true,conteo:2,panelDelay:0,expected:'APROBADO'},
];
const listen=server=>new Promise((resolve,reject)=>server.once('error',reject).listen(0,'127.0.0.1',resolve));
const close=server=>new Promise(resolve=>server.close(resolve));
function runChild(input){return new Promise(resolve=>{
  let p;try{p=spawn(process.execPath,[child],{cwd:ROOT,stdio:['pipe','pipe','pipe'],windowsHide:true,timeout:180000});}
  catch(error){resolve({code:null,stdout:'',stderr:'',error});return;}
  let stdout='',stderr='',error=null;
  p.stdout?.on('data',x=>stdout+=x);p.stderr?.on('data',x=>stderr+=x);
  p.on('error',e=>error=e);p.on('close',code=>resolve({code,stdout,stderr,error}));
  p.stdin?.on('error',()=>{});p.stdin?.end(JSON.stringify(input));
});}
const page=api=>`<!doctype html><html lang="es"><meta charset="utf-8"><title>G40 humo local</title>
<body><main id="app"></main><script>
const API=${JSON.stringify(api)};
const app=document.getElementById('app');
function render(){
  if(location.pathname==='/login'){
    app.innerHTML='<form><input type="email"><input type="password"><button type="submit">Entrar</button></form>';
    app.querySelector('form').onsubmit=async e=>{e.preventDefault();await fetch(API+'/sesiones/',{method:'POST'});};
    return;
  }
  if(location.pathname==='/finanzas/configuracion'){
    app.innerHTML='<div id="alert-slot"></div><section aria-labelledby="cfg-general"><h2 id="cfg-general">General</h2></section><button aria-controls="notification-tray">Avisos</button><section id="notification-tray" role="dialog" hidden></section>';
    fetch(API+'/finanzas/configuracion').then(r=>r.json()).then(data=>setTimeout(()=>{
      const count=data.lineas_pendientes_cuenta;
      const title=count+' '+(count===1?'línea':'líneas')+' de asiento sin cuenta contable';
      document.getElementById('alert-slot').innerHTML=count>0?'<div role="alert" class="ds-alert ds-alert--warning"><span class="ds-alert__title">'+title+'</span></div>':'';
    },data.panelDelay));
    app.querySelector('button').onclick=async()=>{
      const data=await fetch(API+'/notificaciones').then(r=>r.json());
      const tray=document.getElementById('notification-tray');tray.hidden=false;
      tray.innerHTML='<p class="notification-tray__empty">Cargando notificaciones...</p>';
      setTimeout(()=>{tray.innerHTML=data.items.length
        ?data.items.map(n=>'<article class="notification-tray__item"><p>'+n.mensaje+'</p></article>').join('')
        :'<div class="notification-tray__empty"><p>No tienes notificaciones</p></div>';},1800);
    };
  }
}
addEventListener('popstate',render);render();
</script></body></html>`;

async function scenario(s,index){
  const runId=`RUN-G40-V1-20990101-00000${index+1}`;
  const run=path.join(results,runId),dir=path.join(run,'cypress');
  if(fs.existsSync(run))throw Error(`RUN sintético ya existe: ${runId}`);
  const seen=[];
  const apiServer=http.createServer((req,res)=>{
    seen.push({path:req.url,run:req.headers['x-test-run-id'],secret:req.headers['x-sandbox-secret']});
    const headers={'content-type':'application/json','x-test-run-id':runId,
      'access-control-allow-origin':'*','access-control-allow-methods':'GET, OPTIONS',
      'access-control-allow-headers':'X-Test-Run-Id, X-Sandbox-Secret'};
    if(req.method==='OPTIONS'){res.writeHead(204,headers).end();return;}
    if(req.url==='/finanzas/configuracion')res.writeHead(200,headers).end(JSON.stringify({lineas_pendientes_cuenta:s.conteo,panelDelay:s.panelDelay}));
    else if(req.url==='/notificaciones')res.writeHead(200,headers).end(JSON.stringify({items:s.notice?[{id_notificacion:2,mensaje:`Falta la cuenta contable de Variación por transformación biológica (ganancia) para ${species}. El registro quedó pendiente de cuenta.`}]:[]}));
    else res.writeHead(404,headers).end('{}');
  });
  let frontServer;
  try{
    await listen(apiServer);
    const api=`http://127.0.0.1:${apiServer.address().port}`;
    frontServer=http.createServer((req,res)=>res.writeHead(200,{'content-type':'text/html; charset=utf-8'}).end(page(api)));
    await listen(frontServer);
    const front=`http://127.0.0.1:${frontServer.address().port}`;
    fs.mkdirSync(dir,{recursive:true});
    const input={dir,runId,api,front,token:'g40-local-token',secret,
      expected:{conteo:s.conteo,especie:39,especieNombre:species,sentido:'GANANCIA',avisosBase:[1]},localSmoke:true};
    if(index===0){
      const blocked=await runChild({...input,localSmoke:false});
      if(blocked.error?.code==='EPERM')throw blocked.error;
      if(blocked.code===0||!blocked.stderr.includes('hosts no permitidos'))throw Error('El RUN real aceptó loopback');
    }
    const result=await runChild(input);
    if(result.error?.code==='EPERM')throw result.error;
    if(result.code!==0){
      const log=path.join(dir,'G40-cypress-salida.log');
      const salida=fs.existsSync(log)?fs.readFileSync(log,'utf8'):result.stderr;
      throw Error(`Cypress ${s.name}: código ${result.code}\n${salida.split(/\r?\n/).slice(-4000).join('\n')}`);
    }
    const actaPath=path.join(dir,'G40-UI-018-01.json');
    const png=path.join(dir,'screenshots','g40.cy.js','G40-UI-018-01.png');
    if(!fs.existsSync(actaPath)||!fs.existsSync(png)||fs.statSync(png).size===0)throw Error(`Faltan artefactos ${s.name}`);
    const acta=JSON.parse(fs.readFileSync(actaPath,'utf8'));
    if(acta.estado!==s.expected||acta.captura!==true||acta.panel_visible!==true||acta.conteo!==s.conteo||acta.bandeja_abierta!==true||
      acta.avisos_en_ui!==(s.notice?1:0)||acta.avisos_nuevos_api!==(s.notice?1:0))
      throw Error(`Acta ${s.name}: ${acta.estado}, captura ${acta.captura}, bandeja ${acta.bandeja_abierta}, avisos UI ${acta.avisos_en_ui}, avisos API ${acta.avisos_nuevos_api}`);
    const apiCalls=seen.filter(x=>['/finanzas/configuracion','/notificaciones'].includes(x.path));
    const headersOk=apiCalls.length===2&&apiCalls.every(x=>x.run===runId&&x.secret===secret);
    if(!headersOk)throw Error(`Cabeceras API inválidas en ${s.name}: ${JSON.stringify(apiCalls.map(x=>({path:x.path,run:x.run===runId,secret:x.secret===secret})))}`);
    process.stdout.write(`OK cypress_smoke_${s.name}: acta=${acta.estado} cabeceras=OK captura=OK\n`);
  }finally{
    if(frontServer?.listening)await close(frontServer);
    if(apiServer.listening)await close(apiServer);
    fs.rmSync(run,{recursive:true,force:true});
    if(!resultsExisted&&fs.existsSync(results)&&fs.readdirSync(results).length===0)fs.rmdirSync(results);
  }
}
try{for(let i=0;i<scenarios.length;i++)await scenario(scenarios[i],i);}
catch(error){if(error?.code==='EPERM'){
  process.stderr.write('PENDIENTE cypress_smoke: spawn EPERM; ejecutar en Windows antes del RUN.\n');
  process.exitCode=2;
}else throw error;}
