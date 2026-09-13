const fs=require('fs'),path=require('path'),newman=require('newman');
require.resolve('newman-reporter-htmlextra');
const {BASE,FRONT,CASO,settings,dir,save,clean,api,require200,actorNoAutorizado,discoverAdmin,functional}=require('./helpers.cjs');
const {runId,attempt}=settings(),file=`newman-${CASO}-intento${attempt}`,evid=dir(runId),htmlDir=dir(runId,'newman');
if(fs.existsSync(path.join(evid,file+'.json'))||fs.existsSync(path.join(htmlDir,file+'.html')))throw Error('No sobrescribir evidencia existente');
if(attempt===2&&!fs.existsSync(path.join(evid,`newman-${CASO}-intento1.json`)))throw Error('El intento 2 requiere evidencia del intento 1');
if(fs.existsSync(path.join(evid,`newman-${CASO}-intento2.json`)))throw Error('Maximo de dos PATCH alcanzado');
const events=[];
(async()=>{
 const preflight=[];
 for(const url of [FRONT+'/login',BASE+'/health',BASE+'/openapi.json']){
  const r=await fetch(url,{signal:AbortSignal.timeout(25000)});preflight.push({url,status:r.status});if(r.status!==200)throw Error(`ENVIRONMENT_ERROR preflight HTTP ${r.status}`);
  if(url.endsWith('openapi.json')){const j=await r.json(),op=j.paths['/configuracion/umbrales/{id_umbral_ambiental}']?.patch;if(!op)throw Error('Contrato PATCH /configuracion/umbrales/{id} ausente');preflight.push({contrato:'PATCH /configuracion/umbrales/{id_umbral_ambiental}',respuestasDeclaradas:Object.keys(op.responses)});}
 }
 const target=await discoverAdmin(),actorSel=await actorNoAutorizado();
 const actor=actorSel.actor;
 const contexto={preflight,admin:target.admin,actor,seleccionActor:actorSel.intentos,contract:target.contract,especie:target.especie,variable:target.variable,before:target.before,payloadSolicitado:target.payload};
 save(runId,`datos-${CASO}-intento${attempt}.json`,contexto);
 const collection=JSON.parse(fs.readFileSync(path.join(__dirname,'TC-M09-G27.postman_collection.json')));
 const summary=await new Promise((resolve,reject)=>{
  const run=newman.run({collection,reporters:['htmlextra'],timeoutRequest:25000,
   reporter:{htmlextra:{export:path.join(htmlDir,file+'.html'),omitHeaders:true,showEnvironmentData:false,showGlobalData:false,skipEnvironmentVars:['token'],logs:false,silentProgressBar:true,title:`${CASO} G27 TEST intento ${attempt}`}},
   environment:{values:Object.entries({base_url:BASE,token:actorSel.token,id_umbral:target.before.id_umbral_ambiental,payload:JSON.stringify(target.payload)}).map(([key,value])=>({key,value:String(value),enabled:true}))}},(err,s)=>err?reject(Error('Newman execution error')):resolve(s));
  run.on('request',(err,args)=>{let body;try{body=args.response?.json();}catch{}args.request.headers.remove('Authorization');args.response?.headers?.remove('set-cookie');events.push({metodo:args.request.method,endpoint:`/configuracion/umbrales/${target.before.id_umbral_ambiental}`,status:args.response?.code??null,respuesta:body,transportError:!!err});});
 });
 const lista=await require200(`/configuracion/umbrales?id_especie=${target.especie.id}`,target.adminToken);
 const afterRaw=lista.items.find(u=>u.id_umbral_ambiental===target.before.id_umbral_ambiental),after=afterRaw?functional(afterRaw):null;
 const post=events.find(e=>e.metodo==='PATCH'),persistio=!after||JSON.stringify(after)!==JSON.stringify(target.before);
 const pass=post?.status===403&&post?.respuesta?.error_code==='ACCESO_DENEGADO'&&!persistio&&summary.run.failures.length===0;
 const html=path.join(htmlDir,file+'.html');if(!fs.existsSync(html))throw Error('HTML reporter no generado');fs.writeFileSync(html,clean(fs.readFileSync(html,'utf8')));
 save(runId,`${file}.json`,{resultado:pass?'APROBADO':'DESAPROBADO',caso:CASO,intento:attempt,actor,seleccionActor:actorSel.intentos,autenticacion:{actorLogin:200,actorIdentity:200,actorPermisos:200,rolNoAutorizado:!['Administrador','Veterinario'].includes(actor.rol),permisoActualizarRF17:false},contract:target.contract,especie:target.especie,variable:target.variable,before:target.before,payloadSolicitado:target.payload,metodo:'PATCH',endpoint:target.contract.endpoint,status:post?.status??null,errorCode:post?.respuesta?.error_code??null,respuesta:post?.respuesta??null,eventos:events,after,persistencia:persistio,assertions:summary.run.stats.assertions,failures:summary.run.failures.map(f=>({test:f.error?.test||f.error?.name,message:clean(f.error?.message||'')})),STOP_ALL:persistio,html:path.relative(evid,html).split(path.sep).join('/')});
 console.log(CASO,pass?'APROBADO':'DESAPROBADO','PATCH',post?.status,post?.respuesta?.error_code??'-','persistencia',persistio,'assertions',summary.run.stats.assertions.total,'failures',summary.run.failures.length);
 process.exitCode=pass?0:1;
})().catch(e=>{save(runId,`${file}.json`,{caso:CASO,intento:attempt,resultado:'ERROR',motivo:clean(e.message),seleccionActor:e.intentos??null,eventos:events});console.log(clean(e.message));process.exitCode=1;});
