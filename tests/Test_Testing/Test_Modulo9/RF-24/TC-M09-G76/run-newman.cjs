const fs=require('fs'),path=require('path'),newman=require('newman');
require.resolve('newman-reporter-htmlextra');
const {BASE,FRONT,settings,dir,save,load,clean,get,login,discover,construirCuerpo}=require('./helpers.cjs');
const {caso,runId,intento}=settings();
const archivo=`newman-${caso}-intento${intento}`;
const evid=dir(runId),htmlDir=dir(runId,'newman');
if(fs.existsSync(path.join(evid,archivo+'.json'))||fs.existsSync(path.join(htmlDir,archivo+'.html')))
 throw Error('No sobrescribir la evidencia de este intento');
if(intento===2&&!fs.existsSync(path.join(evid,`newman-${caso}-intento1.json`)))
 throw Error('El intento 2 requiere el intento 1 registrado');
if(fs.existsSync(path.join(evid,`newman-${caso}-intento2.json`)))
 throw Error(`Maximo 2 POST por original: ${caso} ya consumio su presupuesto`);
const events=[];
(async()=>{
 const preflight=[];
 for(const url of [FRONT+'/login',BASE+'/health',BASE+'/openapi.json']){
  const r=await fetch(url,{signal:AbortSignal.timeout(25000)});preflight.push({url,status:r.status});
  if(r.status!==200)throw Error('ENVIRONMENT_ERROR preflight HTTP '+r.status);
  if(url.endsWith('openapi.json')){
   const j=await r.json();
   const op=j.paths['/configuracion/sensores/{id_sensor}/calibrar']?.post;
   if(!op)throw Error('Contrato ausente: POST /configuracion/sensores/{id_sensor}/calibrar');
   preflight.push({contrato:'POST /configuracion/sensores/{id_sensor}/calibrar',respuestasDeclaradas:Object.keys(op.responses)});
  }
 }
 const token=await login(process.env.QA_EMAIL,process.env.QA_PASSWORD);
 const permisos=(await get('/sesiones/me/permisos',token)).permisos.filter(p=>p.id_recurso===12).map(p=>p.id_accion);
 if(!permisos.includes(1))throw Error('BLOCKED: el actor no tiene permiso de creacion sobre el recurso 12');

 const previo=load(runId,`plan-${caso}.json`);
 const plan=previo?.plan||await discover(token,caso);
 // HISTORY_BEFORE siempre se relee: es la referencia de ausencia de persistencia.
 const antes=await get(`/configuracion/sensores/${plan.sensor.id}/calibraciones`,token);
 const historialPrevio={total:antes.total,items:antes.items.map(c=>({id_calibracion:c.id_calibracion,
  valor_referencia:c.valor_referencia,fecha_calibracion:c.fecha_calibracion}))};
 const contexto={...plan,historialPrevio};
 const cuerpo=construirCuerpo(caso,plan,runId);
 save(runId,`plan-${caso}.json`,{plan,permisosRecurso12:permisos});
 save(runId,`datos-${caso}-intento${intento}.json`,{preflight,loginStatus:200,permisosRecurso12:permisos,
  plan,historyBefore:historialPrevio,cuerpoEnviado:cuerpo.texto});

 const collection=JSON.parse(fs.readFileSync(path.join(__dirname,'TC-M09-G76.postman_collection.json')));
 collection.item=collection.item.filter(item=>item.name===caso);
 if(collection.item.length!==1)throw Error('Una invocacion ejecuta un unico original');
 const summary=await new Promise((resolve,reject)=>{
  const run=newman.run({collection,reporters:['htmlextra'],timeoutRequest:25000,
   reporter:{htmlextra:{export:path.join(htmlDir,archivo+'.html'),omitHeaders:true,showEnvironmentData:false,
    showGlobalData:false,skipEnvironmentVars:['token'],logs:false,silentProgressBar:true,
    title:`${caso} G76 RF-24 TEST intento ${intento}`}},
   environment:{values:Object.entries({base_url:BASE,token,id_sensor:plan.sensor.id,
    payload:cuerpo.texto,cuerpoEnviado:JSON.stringify(cuerpo.objeto),contexto:JSON.stringify(contexto)})
    .map(([key,value])=>({key,value:String(value),enabled:true}))}},
   (err,s)=>err?reject(Error('Newman execution error')):resolve(s));
  run.on('request',(err,args)=>{
   let body;try{body=args.response?.json();}catch{}
   args.request.headers.remove('Authorization');args.response?.headers?.remove('set-cookie');
   events.push({caso,metodo:args.request.method,status:args.response?.code??null,
    cuerpo:args.request.method==='POST'?cuerpo.texto:undefined,
    respuesta:args.request.method==='POST'?body:undefined,transportError:!!err});
  });
 });

 const despues=await get(`/configuracion/sensores/${plan.sensor.id}/calibraciones`,token);
 const historialPosterior={total:despues.total,items:despues.items.map(c=>({id_calibracion:c.id_calibracion,
  valor_referencia:c.valor_referencia,fecha_calibracion:c.fecha_calibracion}))};
 const post=events.find(e=>e.metodo==='POST');
 const idsPrevios=historialPrevio.items.map(c=>c.id_calibracion);
 const nuevos=historialPosterior.items.map(c=>c.id_calibracion).filter(id=>!idsPrevios.includes(id));
 const alterados=historialPrevio.items.filter(prev=>{
  const ahora=historialPosterior.items.find(c=>c.id_calibracion===prev.id_calibracion);
  return !ahora||String(ahora.valor_referencia)!==String(prev.valor_referencia)
   ||String(ahora.fecha_calibracion)!==String(prev.fecha_calibracion);
 }).map(c=>c.id_calibracion);
 // Ninguno de los dos originales admite persistencia: son escenarios de rechazo.
 const contaminado=nuevos.length>0||post?.status===201;
 const failed=summary.run.failures.length>0||contaminado||alterados.length>0;
 const html=path.join(htmlDir,archivo+'.html');
 if(!fs.existsSync(html))throw Error('HTML reporter no generado');
 fs.writeFileSync(html,clean(fs.readFileSync(html,'utf8')));

 save(runId,archivo+'.json',{caso,intento,resultado:failed?'FAIL':'PASS',
  metodo:'POST',endpoint:`/configuracion/sensores/${plan.sensor.id}/calibrar`,
  dispositivo:plan.dispositivo,estadoDispositivo:plan.dispositivo.es_activo?'activo':'inactivo',
  sensor:plan.sensor,areaCorrecta:plan.areaCorrecta,areaEnviada:plan.areaEnviada,
  areasHistoricasDelSensor:plan.areasHistoricasDelSensor,
  rangoTecnico:plan.rangoTecnico,valorEnviado:plan.valor,invalidezIntencional:plan.invalidezIntencional,
  cuerpoEnviado:cuerpo.texto,
  status:post?.status??null,errorCode:post?.respuesta?.error_code??null,respuesta:post?.respuesta??null,
  eventos:events,historyBefore:historialPrevio,historyAfter:historialPosterior,
  persistencia:{registrosNuevos:nuevos,historicosAlterados:alterados,
   idCreado:post?.status===201?post.respuesta?.id_calibracion??null:null},
  STOP_ALL:contaminado||alterados.length>0,
  assertions:summary.run.stats.assertions,
  failures:summary.run.failures.map(f=>({test:f.error?.test||f.error?.name,message:clean(f.error?.message||'')})),
  newman:'6.2.2',reporter:'newman-reporter-htmlextra 1.23.1',html:path.relative(evid,html).split(path.sep).join('/')});

 console.log(caso,'intento',intento,failed?'FAIL':'PASS','| POST',post?.status,post?.respuesta?.error_code??'-',
  '| historial',historialPrevio.total,'->',historialPosterior.total,'| nuevos',nuevos.length,'| alterados',alterados.length,
  '| assertions',summary.run.stats.assertions.total,'failures',summary.run.failures.length,
  '| STOP_ALL',contaminado||alterados.length>0);
 if(summary.run.failures.length)summary.run.failures.forEach(f=>console.log('   FAIL:',f.error?.test,'->',clean(f.error?.message||'').slice(0,140)));
 process.exitCode=failed?1:0;
})().catch(e=>{save(runId,archivo+'.json',{caso,intento,resultado:'ERROR',motivo:clean(e.message),eventos:events});console.log(clean(e.message));process.exitCode=1;});
