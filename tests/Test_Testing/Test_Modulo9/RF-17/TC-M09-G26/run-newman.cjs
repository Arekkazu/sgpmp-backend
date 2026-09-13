const fs=require('fs'),path=require('path'),newman=require('newman');
require.resolve('newman-reporter-htmlextra');
const {BASE,FRONT,VARIANTES,settings,dir,save,clean,get,login,discover}=require('./helpers.cjs');
const {caso,runId,variante}=settings();
const file=`newman-${caso}-${variante}`;
const evid=dir(runId),htmlDir=dir(runId,'newman');
if(fs.existsSync(path.join(evid,file+'.json'))||fs.existsSync(path.join(htmlDir,file+'.html')))throw Error('No sobrescribir evidencia ya registrada');
// Presupuesto duro: dos POST por original y ni uno mas.
const yaHechos=VARIANTES[caso].filter(v=>fs.existsSync(path.join(evid,`newman-${caso}-${v}.json`)));
if(yaHechos.length>=2)throw Error(`Maximo 2 POST por original: ${caso} ya consumio su presupuesto`);
if(caso!=='TC-M09-57'&&variante==='intento2'&&!yaHechos.includes('intento1'))throw Error('El intento 2 requiere el intento 1 registrado');
const events=[];
(async()=>{
 const preflight=[];
 for(const url of [FRONT+'/login',BASE+'/health',BASE+'/openapi.json']){
  const r=await fetch(url,{signal:AbortSignal.timeout(25000)});preflight.push({url,status:r.status});
  if(r.status!==200)throw Error('ENVIRONMENT_ERROR preflight HTTP '+r.status);
  if(url.endsWith('openapi.json')){const j=await r.json();
   const op=j.paths['/configuracion/umbrales']?.post;
   if(!op)throw Error('Contrato ausente: POST /configuracion/umbrales');
   preflight.push({contrato:'POST /configuracion/umbrales',respuestasDeclaradas:Object.keys(op.responses)});}
 }
 const token=await login(),plan=await discover(token,caso,variante);
 save(runId,`datos-${caso}-${variante}.json`,{preflight,loginStatus:200,plan});
 const collection=JSON.parse(fs.readFileSync(path.join(__dirname,'TC-M09-G26.postman_collection.json')));
 collection.item=collection.item.filter(item=>item.name===caso);
 if(collection.item.length!==1)throw Error('Una invocacion ejecuta un unico original');
 const {payload,...contexto}=plan;
 const summary=await new Promise((resolve,reject)=>{
  const run=newman.run({collection,reporters:['htmlextra'],timeoutRequest:25000,
   reporter:{htmlextra:{export:path.join(htmlDir,file+'.html'),omitHeaders:true,showEnvironmentData:false,showGlobalData:false,
    skipEnvironmentVars:['token'],logs:false,silentProgressBar:true,title:`${caso} (${variante}) G26 TEST`}},
   environment:{values:Object.entries({base_url:BASE,token,id_especie:payload.id_especie,id_variable:payload.id_variable_ambiental,
    payload:JSON.stringify(payload),contexto:JSON.stringify(contexto)}).map(([key,value])=>({key,value:String(value),enabled:true}))}},
   (err,s)=>err?reject(Error('Newman execution error')):resolve(s));
  run.on('request',(err,args)=>{
   let body;try{body=args.response?.json();}catch{}
   args.request.headers.remove('Authorization');args.response?.headers?.remove('set-cookie');
   events.push({caso,variante,metodo:args.request.method,url:args.request.url.getPath(),status:args.response?.code??null,
    payload:args.request.method==='POST'?payload:undefined,respuesta:args.request.method==='POST'?body:undefined,transportError:!!err});
  });
 });
 const after=await get(`/configuracion/umbrales?id_especie=${payload.id_especie}`,token).catch(()=>null);
 const catalogoDespues=(await get('/configuracion/variables-ambientales',token)).items.map(v=>v.id_variable_ambiental).sort((a,b)=>a-b);
 const post=events.find(e=>e.metodo==='POST');
 const deLaCombinacion=after?after.items.filter(u=>u.id_variable_ambiental===payload.id_variable_ambiental):[];
 const esperaUnaExistente=caso==='TC-M09-58';
 // Persistencia inesperada: cualquier registro nuevo o un 201 sobre un payload invalido.
 const idsPrevios=plan.umbralesPrevios.map(u=>u.id).sort((a,b)=>a-b);
 const idsAhora=after?after.items.map(u=>u.id_umbral_ambiental).sort((a,b)=>a-b):[];
 const registroNuevo=idsAhora.filter(id=>!idsPrevios.includes(id));
 const variableCreada=catalogoDespues.includes(payload.id_variable_ambiental)&&caso==='TC-M09-65';
 const contaminado=post?.status===201||registroNuevo.length>0||variableCreada;
 const failed=summary.run.failures.length>0||contaminado;
 const html=path.join(htmlDir,file+'.html');
 if(!fs.existsSync(html))throw Error('HTML reporter no generado');
 fs.writeFileSync(html,clean(fs.readFileSync(html,'utf8')));
 save(runId,file+'.json',{caso,variante,resultado:failed?'FAIL':'PASS',
  metodo:'POST',endpoint:'/configuracion/umbrales',
  especie:plan.especie,variable:plan.variable,
  evidenciaEspecie:plan.evidenciaEspecie,evidenciaVariable:plan.evidenciaVariable,
  configuracionExistente:plan.configuracionExistente,invalidezIntencional:plan.invalidezIntencional,
  payloadEnviado:payload,umbralesPrevios:plan.umbralesPrevios,
  status:post?.status??null,errorCode:post?.respuesta?.error_code??null,respuesta:post?.respuesta??null,
  eventos:events,
  getPosterior:after?{status:200,total:after.total,ids:idsAhora}:{status:'no consultado'},
  persistencia:{umbralesDeLaCombinacion:deLaCombinacion.length,esperado:esperaUnaExistente?1:0,
   registrosNuevos:registroNuevo,catalogoVariablesDespues:catalogoDespues,variableInvalidaCreada:variableCreada},
  STOP_ALL:contaminado,
  assertions:summary.run.stats.assertions,
  failures:summary.run.failures.map(f=>({test:f.error?.test||f.error?.name,message:clean(f.error?.message||'')})),
  newman:'6.2.2',reporter:'newman-reporter-htmlextra 1.23.1',html:path.relative(evid,html).split(path.sep).join('/')});
 console.log(caso,`(${variante})`,failed?'FAIL':'PASS','| POST',post?.status,post?.respuesta?.error_code??'-',
  '| combinacion',deLaCombinacion.length,'| nuevos',registroNuevo.length,'| assertions',summary.run.stats.assertions.total,
  'failures',summary.run.failures.length,'| STOP_ALL',contaminado);
 if(summary.run.failures.length)summary.run.failures.forEach(f=>console.log('   FAIL:',f.error?.test,'->',clean(f.error?.message||'').slice(0,120)));
 process.exitCode=failed?1:0;
})().catch(e=>{save(runId,file+'.json',{caso,variante,resultado:'ERROR',motivo:clean(e.message),eventos:events});console.log(clean(e.message));process.exitCode=1;});
