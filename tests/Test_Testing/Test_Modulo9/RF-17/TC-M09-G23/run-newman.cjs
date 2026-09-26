const fs=require('fs'),path=require('path'),newman=require('newman');
require.resolve('newman-reporter-htmlextra');
const {BASE,FRONT,settings,save,clean,get,login,discover}=require('./helpers.cjs');
const {caso,id}=settings(),file=`newman-${caso}-${id}`,dir=path.join(__dirname,'RESULTADOS');
if(fs.existsSync(path.join(dir,file+'.json'))||fs.existsSync(path.join(dir,file+'.html')))throw Error('No sobrescribir evidencia');
const events=[];
(async()=>{
 const preflight=[];
 for(const url of [FRONT+'/login',BASE+'/health',BASE+'/openapi.json']){const r=await fetch(url,{signal:AbortSignal.timeout(25000)});preflight.push({url,status:r.status});if(r.status!==200)throw Error('ENVIRONMENT_ERROR preflight');if(url.endsWith('openapi.json')){const j=await r.json();if(!j.paths['/configuracion/umbrales']?.post)throw Error('Contrato ausente');}}
 const token=await login(),plan=await discover(token,caso);save(`datos-${caso}-${id}.json`,{preflight,loginStatus:200,plan});
 const collection=JSON.parse(fs.readFileSync(path.join(__dirname,'TC-M09-G23.postman_collection.json')));
 collection.item=collection.item.filter(item=>item.name===caso);
 const summary=await new Promise((resolve,reject)=>{
  const run=newman.run({collection,reporters:['htmlextra'],timeoutRequest:25000,
   reporter:{htmlextra:{export:path.join(dir,file+'.html'),omitHeaders:true,showEnvironmentData:false,showGlobalData:false,skipEnvironmentVars:['token'],logs:false,silentProgressBar:true,title:`${caso} G23 TEST`}},
   environment:{values:Object.entries({base_url:BASE,token,id_especie:plan.payload.id_especie,id_variable:plan.payload.id_variable_ambiental,payload:JSON.stringify(plan.payload)}).map(([key,value])=>({key,value:String(value),enabled:true}))}},
   (err,s)=>err?reject(Error('Newman execution error')):resolve(s));
  run.on('request',(err,args)=>{
   let body;try{body=args.response?.json();}catch{}
   args.request.headers.remove('Authorization');args.response?.headers?.remove('set-cookie');
   events.push({caso,method:args.request.method,endpoint:'/configuracion/umbrales',status:args.response?.code??null,payload:args.request.method==='POST'?plan.payload:undefined,response:body,transportError:!!err});
   save(file+'.json',{estado:'EN_EJECUCION',events});
  });
 });
 const after=await get(`/configuracion/umbrales?id_especie=${plan.payload.id_especie}`,token);
 const persisted=after.items.filter(u=>u.id_variable_ambiental===plan.payload.id_variable_ambiental);
 const contaminated=persisted.length>0||events.some(e=>e.method==='POST'&&e.status===201);
 const failed=summary.run.failures.length>0||contaminated;
 const html=path.join(dir,file+'.html');if(!fs.existsSync(html))throw Error('HTML reporter no generado');
 fs.writeFileSync(html,clean(fs.readFileSync(html,'utf8')));
 save(file+'.json',{estado:failed?'FAIL':'PASS',caso,plan,events,postGetStatus:200,persisted,STOP_ALL:contaminated,stats:summary.run.stats,failures:summary.run.failures.map(f=>({test:f.error?.test||f.error?.name,message:clean(f.error?.message||'')})),reporter:'htmlextra 1.23.1',html:path.basename(html)});
 console.log(caso,failed?'FAIL':'PASS','POST',events.find(e=>e.method==='POST')?.status,'persisted',persisted.length,'assertions',summary.run.stats.assertions.total,'failures',summary.run.failures.length);
 process.exitCode=failed?1:0;
})().catch(e=>{save(file+'.json',{estado:'ENVIRONMENT_ERROR',caso,error:clean(e.message),events});console.log(clean(e.message));process.exitCode=1;});
