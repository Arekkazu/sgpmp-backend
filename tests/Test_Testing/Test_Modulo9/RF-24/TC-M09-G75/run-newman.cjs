const fs=require('fs'),path=require('path'),newman=require('newman');
require.resolve('newman-reporter-htmlextra');
const {BASE,FRONT,ORIGINAL,ESTADO,settings,dir,save,load,clean,get,login,discover,construirCuerpo}=require('./helpers.cjs');
const {caso,runId,original,archivo}=settings();
const evid=dir(runId),htmlDir=dir(runId,'newman');
if(fs.existsSync(path.join(evid,archivo+'.json'))||fs.existsSync(path.join(htmlDir,archivo+'.html')))
 throw Error('No sobrescribir evidencia ya registrada para '+caso);
// Presupuesto duro por original: 2 POST y ni uno mas.
const previo=load(runId,ESTADO)||{ejecuciones:[],historialInicial:null,ultimaValida:null};
const delOriginal=previo.ejecuciones.filter(e=>e.original===original);
if(delOriginal.length>=2)throw Error(`Presupuesto agotado: ${original} ya consumio 2 POST. No hay tercero.`);
if(delOriginal.some(e=>e.caso===caso))throw Error(`El subescenario ${caso} ya se ejecuto.`);
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
 // Actor funcional del caso; el descubrimiento puede usar otro actor con permiso de lectura.
 const tokenActor=await login(process.env.QA_EMAIL,process.env.QA_PASSWORD);
 const tokenDescubrimiento=process.env.QA_DISCOVERY_EMAIL
  ? await login(process.env.QA_DISCOVERY_EMAIL,process.env.QA_DISCOVERY_PASSWORD)
  : tokenActor;
 const actorEsElDescubridor=tokenActor===tokenDescubrimiento;

 const plan=previo.plan||await discover(tokenDescubrimiento);
 // El historial previo se relee siempre: es la referencia de ausencia/persistencia.
 const historialPrevio=await get(`/configuracion/sensores/${plan.sensor.id}/calibraciones`,tokenDescubrimiento);
 const contexto={...plan,historialPrevio:{total:historialPrevio.total,ids:historialPrevio.items.map(c=>c.id_calibracion)},
  ultimaValida:previo.ultimaValida};
 const cuerpo=construirCuerpo(caso,plan,runId);
 save(runId,`datos-${caso}.json`,{preflight,loginStatus:200,actor:{descubrimientoConOtroActor:!actorEsElDescubridor},
  plan,historialPrevio:contexto.historialPrevio,ultimaValida:previo.ultimaValida,cuerpoEnviado:cuerpo.texto});

 const collection=JSON.parse(fs.readFileSync(path.join(__dirname,'TC-M09-G75.postman_collection.json')));
 collection.item=collection.item.filter(item=>item.name===caso);
 if(collection.item.length!==1)throw Error('Una invocacion ejecuta un unico subescenario');
 const summary=await new Promise((resolve,reject)=>{
  const run=newman.run({collection,reporters:['htmlextra'],timeoutRequest:25000,
   reporter:{htmlextra:{export:path.join(htmlDir,archivo+'.html'),omitHeaders:true,showEnvironmentData:false,
    showGlobalData:false,skipEnvironmentVars:['token'],logs:false,silentProgressBar:true,title:`${caso} G75 RF-24 TEST`}},
   environment:{values:Object.entries({base_url:BASE,token:tokenActor,id_sensor:plan.sensor.id,
    payload:cuerpo.texto,cuerpoEnviado:JSON.stringify(cuerpo.objeto),
    contexto:JSON.stringify(contexto)}).map(([key,value])=>({key,value:String(value),enabled:true}))}},
   (err,s)=>err?reject(Error('Newman execution error')):resolve(s));
  run.on('request',(err,args)=>{
   let body;try{body=args.response?.json();}catch{}
   args.request.headers.remove('Authorization');args.response?.headers?.remove('set-cookie');
   events.push({caso,metodo:args.request.method,status:args.response?.code??null,
    cuerpo:args.request.method==='POST'?cuerpo.texto:undefined,
    respuesta:args.request.method==='POST'?body:undefined,transportError:!!err});
  });
 });

 const despues=await get(`/configuracion/sensores/${plan.sensor.id}/calibraciones`,tokenDescubrimiento);
 const post=events.find(e=>e.metodo==='POST');
 const idCreado=post?.status===201?post.respuesta?.id_calibracion??null:null;
 const positivo=['TC-M09-142','TC-M09-143'].includes(caso);
 const nuevos=despues.items.map(c=>c.id_calibracion).filter(id=>!contexto.historialPrevio.ids.includes(id));
 // Un dato invalido no puede persistir bajo ninguna circunstancia.
 const contaminado=!positivo&&(nuevos.length>0||post?.status===201);
 const historicosAlterados=contexto.historialPrevio.ids.some(id=>!despues.items.some(c=>c.id_calibracion===id));
 const failed=summary.run.failures.length>0||contaminado||historicosAlterados;
 const html=path.join(htmlDir,archivo+'.html');
 if(!fs.existsSync(html))throw Error('HTML reporter no generado');
 fs.writeFileSync(html,clean(fs.readFileSync(html,'utf8')));

 save(runId,archivo+'.json',{caso,original,resultado:failed?'FAIL':'PASS',
  metodo:'POST',endpoint:`/configuracion/sensores/${plan.sensor.id}/calibrar`,
  dispositivo:plan.dispositivo,sensor:plan.sensor,area:plan.area,rangoTecnico:plan.rangoTecnico,
  valorEnviado:cuerpo.valorEnviado,cuerpoEnviado:cuerpo.texto,
  status:post?.status??null,errorCode:post?.respuesta?.error_code??null,respuesta:post?.respuesta??null,
  eventos:events,
  historialPrevio:contexto.historialPrevio,
  historialPosterior:{total:despues.total,ids:despues.items.map(c=>c.id_calibracion)},
  persistencia:{idCreado,registrosNuevos:nuevos,historicosAlterados},
  calibracionValidaAnterior:previo.ultimaValida,
  STOP_ALL:contaminado||historicosAlterados,
  assertions:summary.run.stats.assertions,
  failures:summary.run.failures.map(f=>({test:f.error?.test||f.error?.name,message:clean(f.error?.message||'')})),
  newman:'6.2.2',reporter:'newman-reporter-htmlextra 1.23.1',html:path.relative(evid,html).split(path.sep).join('/')});

 const creada=idCreado?despues.items.find(c=>c.id_calibracion===idCreado):null;
 save(runId,ESTADO,{plan,historialInicial:previo.historialInicial||contexto.historialPrevio,
  ultimaValida:creada?{id_calibracion:creada.id_calibracion,valor_referencia:creada.valor_referencia,
   id_sensor:creada.id_sensor,fecha_calibracion:creada.fecha_calibracion,caso}:previo.ultimaValida,
  ejecuciones:[...previo.ejecuciones,{caso,original,status:post?.status??null,idCreado,fecha:new Date().toISOString()}]});

 console.log(caso,failed?'FAIL':'PASS','| POST',post?.status,post?.respuesta?.error_code??'-',
  '| idCreado',idCreado,'| historial',contexto.historialPrevio.total,'->',despues.total,
  '| assertions',summary.run.stats.assertions.total,'failures',summary.run.failures.length,'| STOP_ALL',contaminado||historicosAlterados);
 if(summary.run.failures.length)summary.run.failures.forEach(f=>console.log('   FAIL:',f.error?.test,'->',clean(f.error?.message||'').slice(0,130)));
 process.exitCode=failed?1:0;
})().catch(e=>{save(runId,archivo+'.json',{caso,original,resultado:'ERROR',motivo:clean(e.message),eventos:events});console.log(clean(e.message));process.exitCode=1;});
