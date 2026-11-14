const fs=require('fs'),path=require('path'),newman=require('newman');
require.resolve('newman-reporter-htmlextra');
const {BASE,FRONT,settings,dir,save,clean,get,login,discover}=require('./helpers.cjs');
const {caso,runId,intento}=settings();
const file=`newman-${caso}-intento${intento}`;
const evid=dir(runId),htmlDir=dir(runId,'newman');
if(fs.existsSync(path.join(evid,file+'.json'))||fs.existsSync(path.join(htmlDir,file+'.html')))throw Error('No sobrescribir la evidencia de este intento');
if(intento===2&&!fs.existsSync(path.join(evid,`newman-${caso}-intento1.json`)))throw Error('El intento 2 requiere el intento 1 registrado');
if(fs.existsSync(path.join(evid,`newman-${caso}-intento2.json`)))throw Error('Maximo 2 POST por original: no hay tercer intento');
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
 const token=await login(),plan=await discover(token,caso);
 save(runId,`datos-${caso}-intento${intento}.json`,{preflight,loginStatus:200,plan});
 const collection=JSON.parse(fs.readFileSync(path.join(__dirname,'TC-M09-G25.postman_collection.json')));
 collection.item=collection.item.filter(item=>item.name===caso);
 if(collection.item.length!==1)throw Error('Una invocacion ejecuta un unico original');
 const contexto={especie:plan.especie,variable:plan.variable,combinacionLibre:plan.combinacionLibre,umbralesPrevios:plan.umbralesPrevios};
 const summary=await new Promise((resolve,reject)=>{
  const run=newman.run({collection,reporters:['htmlextra'],timeoutRequest:25000,
   reporter:{htmlextra:{export:path.join(htmlDir,file+'.html'),omitHeaders:true,showEnvironmentData:false,showGlobalData:false,
    skipEnvironmentVars:['token'],logs:false,silentProgressBar:true,title:`${caso} G25 TEST intento ${intento}`}},
   environment:{values:Object.entries({base_url:BASE,token,id_especie:plan.payload.id_especie,id_variable:plan.payload.id_variable_ambiental,
    payload:JSON.stringify(plan.payload),contexto:JSON.stringify(contexto)}).map(([key,value])=>({key,value:String(value),enabled:true}))}},
   (err,s)=>err?reject(Error('Newman execution error')):resolve(s));
  run.on('request',(err,args)=>{
   let body;try{body=args.response?.json();}catch{}
   args.request.headers.remove('Authorization');args.response?.headers?.remove('set-cookie');
   events.push({caso,metodo:args.request.method,endpoint:'/configuracion/umbrales',status:args.response?.code??null,
    payload:args.request.method==='POST'?plan.payload:undefined,respuesta:body,transportError:!!err});
  });
 });
 const after=await get(`/configuracion/umbrales?id_especie=${plan.payload.id_especie}`,token);
 const persisted=after.items.filter(u=>u.id_variable_ambiental===plan.payload.id_variable_ambiental);
 const post=events.find(e=>e.metodo==='POST');
 // Un dato invalido no puede quedar almacenado bajo ninguna circunstancia.
 const contaminado=persisted.length>0||post?.status===201;
 const failed=summary.run.failures.length>0||contaminado;
 const html=path.join(htmlDir,file+'.html');
 if(!fs.existsSync(html))throw Error('HTML reporter no generado');
 fs.writeFileSync(html,clean(fs.readFileSync(html,'utf8')));
 save(runId,file+'.json',{caso,intento,resultado:failed?'FAIL':'PASS',
  metodo:'POST',endpoint:'/configuracion/umbrales',
  especie:plan.especie,variable:plan.variable,reglaFisica:plan.regla,invalidezIntencional:plan.invalidezIntencional,
  rangoEnviado:{valor_min:plan.payload.valor_min,valor_max:plan.payload.valor_max,niveles:plan.payload.niveles},
  combinacionLibrePrevia:plan.combinacionLibre,umbralesPrevios:plan.umbralesPrevios,
  status:post?.status??null,errorCode:post?.respuesta?.error_code??null,respuesta:post?.respuesta??null,
  eventos:events,getPosterior:{status:200,total:after.total,ids:after.items.map(u=>u.id_umbral_ambiental)},
  persistencia:{registrosDeLaVariable:persisted.length,detalle:persisted},
  STOP_ALL:contaminado,
  assertions:summary.run.stats.assertions,
  failures:summary.run.failures.map(f=>({test:f.error?.test||f.error?.name,message:clean(f.error?.message||'')})),
  newman:'6.2.2',reporter:'newman-reporter-htmlextra 1.23.1',html:path.relative(evid,html).split(path.sep).join('/')});
 console.log(caso,'intento',intento,failed?'FAIL':'PASS','| POST',post?.status,post?.respuesta?.error_code??'-',
  '| persisted',persisted.length,'| assertions',summary.run.stats.assertions.total,'failures',summary.run.failures.length,'| STOP_ALL',contaminado);
 process.exitCode=failed?1:0;
})().catch(e=>{save(runId,file+'.json',{caso,intento,resultado:'ERROR',motivo:clean(e.message),eventos:events});console.log(clean(e.message));process.exitCode=1;});
