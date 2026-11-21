// TC-M09-G134: TEST decisorio. Dos POST de calibración sin reintentos.
// TC-267 consulta la BD TEST mediante Python/psycopg2 en modo SELECT read-only.
const fs=require('fs');
const path=require('path');
const crypto=require('crypto');
const {execFileSync,spawnSync}=require('child_process');

if(path.basename(__dirname)!=='TC-M09-G134')throw new Error('Carpeta de ejecución incorrecta.');
const runId=process.env.G134_RUN_ID;
if(!/^run-\d{8}-\d{6}$/.test(runId||''))throw new Error('G134_RUN_ID debe tener formato run-YYYYMMDD-HHMMSS.');
const base=(process.env.QA_BASE_URL||'').replace(/\/$/,'');
if(base!=='https://api.inmero.co/back-sigab-test')throw new Error('El ambiente decisorio debe ser TEST.');
const email=process.env.QA_ING_EMAIL,password=process.env.QA_ING_PASSWORD,adminPassword=process.env.QA_ADMIN_PASSWORD;
if(!email||!password||!adminPassword)throw new Error('Faltan credenciales en variables de proceso.');
const out=path.join(__dirname,'RESULTADOS',runId);
if(fs.existsSync(out))throw new Error('RUN_ID existente: no se sobrescribe.');
fs.mkdirSync(out,{recursive:true});
const collection=JSON.parse(fs.readFileSync(path.join(__dirname,'TC-M09-G134.postman_collection.json'),'utf8'));
const e={grupo:'TC-M09-G134',casos:['TC-M09-265','TC-M09-266','TC-M09-267'],run_id:runId,
  ambiente:'TEST',prueba_local:false,base_url:base,post_planificados:2,post_ejecutados:0,
  sql_escritura:false,git:{},openapi:{},actor:{},admin:{},fixture_266:{},fixture_267:{},
  'TC-M09-265':{},'TC-M09-266':{},'TC-M09-267':{},resultado_general:'',motivo_general:'',incidencias:[]};
const secrets=[password,adminPassword,process.env.QA_DB_PASSWORD].filter(Boolean);
function clean(value){let s=String(value??'');for(const v of new Set(secrets))s=s.split(v).join('[REDACTED]');
  return s.replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,'[JWT REDACTED]')
    .replace(/Bearer\s+[A-Za-z0-9_.-]{12,}/gi,'Bearer [REDACTED]');}
function esc(x){return String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function git(args){try{let d=__dirname;while(!fs.existsSync(path.join(d,'.git'))&&path.dirname(d)!==d)d=path.dirname(d);
  return execFileSync('git',args,{cwd:d,encoding:'utf8'}).trim();}catch(x){return `ERROR: ${clean(x.message)}`;}}
function digest(rows){return crypto.createHash('sha256').update(JSON.stringify(rows)).digest('hex');}
function decParts(x){if(typeof x!=='string'&&typeof x!=='number')return null;const m=/^([+-]?)(\d+)(?:\.(\d+))?$/.exec(String(x));
  if(!m)return null;const f=m[3]||'';return {n:(m[1]==='-'?-1n:1n)*BigInt(m[2]+f),d:10n**BigInt(f.length)};}
function decEq(a,b){const x=decParts(a),y=decParts(b);return Boolean(x&&y&&x.n*y.d===y.n*x.d);}
function historySummary(data){if(!Number.isInteger(data?.total)||!Array.isArray(data.items))throw new Error('Historial inválido.');
  const ids=data.items.map(x=>x.id_calibracion).sort((a,b)=>a-b);
  if(ids.some(x=>!Number.isInteger(x)))throw new Error('Historial sin IDs íntegros.');return {total:data.total,ids};}
function canonicalCal(x){return {id_calibracion:x.id_calibracion,valor_referencia:String(x.valor_referencia),
  fecha_calibracion:x.fecha_calibracion,id_usuario:x.id_usuario,observaciones:x.observaciones};}
function save(){fs.writeFileSync(path.join(out,'evidencia.json'),clean(JSON.stringify(e,null,2)),'utf8');}
async function request(method,route,token,body){const r=await fetch(base+route,{method,
  headers:{...(token?{Authorization:`Bearer ${token}`}:{ }),...(body?{'Content-Type':'application/json'}:{})},
  body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(30000)});
  return {status:r.status,body:await r.json().catch(()=>null)};}
async function login(user,pass){const r=await request('POST','/sesiones/',null,{correo_electronico:user,contrasena:pass});
  if(r.status!==200||!r.body?.token)throw new Error(`${user} no autentica (HTTP ${r.status}).`);return r.body.token;}
async function get(route,token){const r=await request('GET',route,token);if(r.status!==200)throw new Error(`GET ${route} HTTP ${r.status}.`);return r.body;}
async function history(sensor,token){const data=await get(`/configuracion/sensores/${sensor}/calibraciones`,token);
  return {items:data.items,summary:historySummary(data)};}
function python(args,extra={}){const env={...process.env,...extra};const r=spawnSync('python',[path.join(__dirname,'test_tc_m09_267.py'),...args],
  {cwd:__dirname,env,encoding:'utf8',maxBuffer:10*1024*1024,timeout:30000});
  if(r.status!==0)throw new Error(`SELECT read-only falló: ${clean((r.stderr||r.stdout||'').slice(0,500))}`);
  return JSON.parse(r.stdout);}
function dbEnv(sensor,period,postBefore){return {G134_SENSOR:String(sensor),G134_START:period.inicio_utc,
  G134_END_EXCLUSIVE:period.fin_exclusivo_utc,G134_POST_BEFORE:postBefore};}
function runPytest(extra){const r=spawnSync('python',['-m','pytest','-q','--noconftest','-p','no:cacheprovider','test_tc_m09_267.py',
  '--junitxml='+path.join(out,'pytest.xml')],{cwd:__dirname,env:{...process.env,...extra,PYTHONDONTWRITEBYTECODE:'1'},
  encoding:'utf8',maxBuffer:2*1024*1024,timeout:45000});
  return {exit_code:r.status,detalle:clean((r.stdout||r.stderr||'').slice(0,1200))};}
async function adminLogin(){const attempts=[];for(const user of ['admin.dev@gmail.com','administador.dev@gmail.com']){
  try{const token=await login(user,adminPassword);const me=await get('/usuarios/me',token);
    attempts.push({correo:user,id_usuario:me.id_usuario,rol:me.nombre_rol,estado:me.estado_cuenta});
    if(me.correo_electronico===user&&me.nombre_rol==='Administrador'&&me.estado_cuenta==='Activo'){
      e.admin={...attempts.at(-1),intentos:attempts};return token;}
  }catch(x){attempts.push({correo:user,resultado:clean(x.message)});}}
  e.admin={intentos:attempts};throw new Error('Ningún Administrador de lectura disponible.');}
async function fixture(deviceId,sensorId,areaId,token,ranges){
  const d=await get(`/configuracion/dispositivos-iot/${deviceId}`,token);
  const sensors=await get(`/configuracion/dispositivos-iot/${deviceId}/sensores`,token);
  const s=sensors.items?.find(x=>x.id_sensores===sensorId&&x.id_dispositivo_iot===deviceId);
  const assoc=await get(`/configuracion/sensores/${sensorId}/asociaciones`,token);
  const a=assoc.items?.find(x=>x.id_sensor===sensorId&&x.id_dispositivo_iot===deviceId&&
    x.id_infraestructura===areaId&&x.tiene_estado===true&&x.fecha_finalizacion===null);
  const area=await get(`/configuracion/infraestructuras/${areaId}`,token);
  const range=ranges.items?.find(x=>x.categoria===s?.categoria);
  if(d.es_activo!==true||s?.es_activo!==true||!a||area.es_activo!==true||!range||
    Number(range.valor_min)>30||30>Number(range.valor_max))return null;
  return {sensor:sensorId,dispositivo:deviceId,area:areaId,categoria:s.categoria,
    asociacion:a.id_sensores_area_asociada,rango:{min:range.valor_min,max:range.valor_max},
    activo:{sensor:s.es_activo,dispositivo:d.es_activo,area:area.es_activo},fuente:'GET con Administrador TEST'};}
async function findFixture(preferred,token,ranges){try{const f=await fixture(...preferred,token,ranges);if(f)return f;}catch{ /* descubrir */ }
  const devices=(await get('/configuracion/dispositivos-iot',token)).items||[];
  for(const d of devices.filter(x=>x.es_activo===true)){
    let sensors;try{sensors=(await get(`/configuracion/dispositivos-iot/${d.id_dispositivo_iot}/sensores`,token)).items||[];}catch{continue;}
    for(const s of sensors.filter(x=>x.es_activo===true)){
      let assoc;try{assoc=(await get(`/configuracion/sensores/${s.id_sensores}/asociaciones`,token)).items||[];}catch{continue;}
      for(const a of assoc.filter(x=>x.tiene_estado===true&&x.fecha_finalizacion===null)){
        try{const f=await fixture(d.id_dispositivo_iot,s.id_sensores,a.id_infraestructura,token,ranges);if(f)return f;}catch{ /* siguiente */ }
      }
    }
  }
  throw new Error('No existe fixture activo y asociado cuyo rango admita 30.0000.');}
function officialReferences(){const root=path.dirname(__dirname);
  const files=[
    ['TC-M09-141-v2.0','TC-M09-G74-v2.0/RESULTADOS/run-20261007-064935/evidencia/response_calibracion.json'],
    ['TC-M09-142-v2.0','TC-M09-G75-v2.0/RESULTADOS/run-20261007-072226/142_calibracion_creada.json'],
    ['TC-M09-143-v2.0','TC-M09-G75-v2.0/RESULTADOS/run-20261007-072226/143_calibracion_creada.json']];
  return files.map(([caso,f])=>{const p=path.join(root,f);if(!fs.existsSync(p))throw new Error(`Falta evidencia oficial ${caso}: ${f}`);
    const d=JSON.parse(fs.readFileSync(p,'utf8'));
    for(const k of ['id_calibracion','id_dispositivo_iot','id_sensor','id_usuario','fecha_calibracion','valor_referencia','observaciones'])
      if(d[k]===undefined||d[k]===null)throw new Error(`Evidencia oficial ${caso} sin ${k}.`);
    return {caso,fuente:path.join('tests','Test_Testing','Test_Modulo9','RF-24',f).replace(/\\/g,'/'),
      id_calibracion:d.id_calibracion,id_dispositivo_iot:d.id_dispositivo_iot,id_sensor:d.id_sensor,
      id_usuario:d.id_usuario,fecha_calibracion:d.fecha_calibracion,valor_referencia:d.valor_referencia,
      observaciones:d.observaciones};});}
async function case265(token){const r=e['TC-M09-265'];
  try{r.referencias_oficiales=officialReferences();}catch(x){r.resultado='BLOQUEADO / NO VERIFICABLE';r.motivo=clean(x.message);return;}
  const sensor=r.referencias_oficiales[0].id_sensor;
  const response=await request('GET',`/configuracion/sensores/${sensor}/calibraciones`,token);
  r.http=response.status;if(!(response.status>=200&&response.status<300)){r.resultado='RECHAZADO';r.motivo=`Historial respondió HTTP ${response.status} en vez de 2xx.`;return;}
  const items=response.body?.items;if(!Array.isArray(items)){r.resultado='RECHAZADO';r.motivo='Historial 2xx sin items verificables.';return;}
  r.total=response.body.total;r.ids=items.map(x=>x.id_calibracion).sort((a,b)=>a-b);
  r.items_de_otro_sensor=items.filter(x=>x.id_sensor!==sensor).map(x=>({id_calibracion:x.id_calibracion,id_sensor:x.id_sensor}));
  r.comparaciones=r.referencias_oficiales.map(ref=>{
    const found=items.find(x=>x.id_calibracion===ref.id_calibracion);
    const iguales=found?{
      id_dispositivo_iot:found.id_dispositivo_iot===ref.id_dispositivo_iot,
      id_sensor:found.id_sensor===ref.id_sensor,id_usuario:found.id_usuario===ref.id_usuario,
      fecha_calibracion:found.fecha_calibracion===ref.fecha_calibracion,
      valor_referencia:decEq(found.valor_referencia,ref.valor_referencia),
      observaciones:found.observaciones===ref.observaciones}:null;
    return {caso:ref.caso,id_calibracion:ref.id_calibracion,presente:Boolean(found),iguales,
      obtenido:found?{id_dispositivo_iot:found.id_dispositivo_iot,id_sensor:found.id_sensor,
        id_usuario:found.id_usuario,fecha_calibracion:found.fecha_calibracion,
        valor_referencia:found.valor_referencia,observaciones:found.observaciones}:null};});
  const failures=r.comparaciones.filter(x=>!x.presente||Object.values(x.iguales).some(v=>v===false));
  if(failures.length||r.items_de_otro_sensor.length){r.resultado='RECHAZADO';
    r.motivo=`${failures.length} referencia(s) oficial(es) ausente(s) o distinta(s); ${r.items_de_otro_sensor.length} registro(s) de otro sensor.`;}
  else{r.resultado='APROBADO';r.motivo=`HTTP ${r.http}; calibraciones ${r.comparaciones.map(x=>x.id_calibracion).join(', ')} presentes con todos los campos iguales y sin mezcla de sensores. Orden no evaluado.`;}}
function newmanPost(sensor,body,token){let newman;try{newman=require('newman');}catch{newman=require(path.join(path.dirname(process.execPath),'node_modules','newman'));}
  const raw=JSON.stringify(body).replace(/"valor_referencia":30(?=,)/,'"valor_referencia":30.0000');
  return new Promise((resolve,reject)=>newman.run({collection,reporters:['cli'],timeoutRequest:30000,
    envVar:[['base_url',base],['sensor_id',sensor],['body_json',raw],['token',token]].map(([key,value])=>({key,value:String(value)}))},
  (err,run)=>{const ex=run?.run?.executions?.[0];if(err||!ex?.response)return reject(new Error(`Newman sin respuesta: ${clean(err?.message||'desconocido')}`));
    let response=null;try{response=JSON.parse(ex.response.stream.toString('utf8'));}catch{ /* no JSON */ }
    resolve({status:ex.response.code,body:response,assertions:ex.assertions?.map(a=>({name:a.assertion,error:a.error?.message||null}))||[]});}));}
function bodyFor(f,caseId){return {modo_calibracion:'SENSOR',id_dispositivo_iot:f.dispositivo,id_infraestructura:f.area,
  valor_referencia:30,observaciones:`QA ${caseId}`,fecha_calibracion:new Date().toISOString()};}
async function sendCalibration(r,f,caseId,token){const body=bodyFor(f,caseId);
  r.request={ruta:`/configuracion/sensores/${f.sensor}/calibrar`,body,valor_referencia_literal:'30.0000'};
  e.post_ejecutados+=1;
  try{const response=await newmanPost(f.sensor,body,token);r.response={http:response.status,id_calibracion:response.body?.id_calibracion??null,
    id_usuario:response.body?.id_usuario??null,id_sensor:response.body?.id_sensor??null,
    valor_referencia:response.body?.valor_referencia??null,observaciones:response.body?.observaciones??null,
    error_code:response.body?.error_code??null,mensaje:clean(response.body?.message??response.body?.detail??'')};
    r.assertions_newman=response.assertions;}catch(x){r.error_ejecucion=clean(x.message);}}
async function case266(f,token){const r=e['TC-M09-266'];
  const before=await history(f.sensor,token);r.pre={...before.summary,filas:before.items.map(canonicalCal)};
  await sendCalibration(r,f,'TC-M09-266',token);
  const after=await history(f.sensor,token);r.post={...after.summary,filas:after.items.map(canonicalCal)};
  const old=new Map(r.pre.filas.map(x=>[x.id_calibracion,x]));
  const current=new Map(r.post.filas.map(x=>[x.id_calibracion,x]));
  r.previas_ausentes=r.pre.ids.filter(id=>!current.has(id));
  r.previas_modificadas=r.pre.ids.filter(id=>current.has(id)&&JSON.stringify(old.get(id))!==JSON.stringify(current.get(id)))
    .map(id=>({id_calibracion:id,pre:old.get(id),post:current.get(id)}));
  r.ids_nuevos=r.post.ids.filter(id=>!old.has(id));
  const id=r.response?.id_calibracion;
  r.nueva_por_id=Number.isInteger(id)?current.get(id)||null:null;
  r.nueva_atribuible=Boolean(r.nueva_por_id&&r.nueva_por_id.id_usuario===e.actor.id_usuario&&
    r.nueva_por_id.observaciones==='QA TC-M09-266'&&decEq(r.nueva_por_id.valor_referencia,'30.0000'));
  if(r.previas_ausentes.length||r.previas_modificadas.length){r.resultado='RECHAZADO';
    r.motivo=`Calibraciones previas alteradas: ausentes ${r.previas_ausentes.join(', ')||'ninguna'}; modificadas ${r.previas_modificadas.map(x=>x.id_calibracion).join(', ')||'ninguna'}.`;}
  else if(r.ids_nuevos.length>1&&r.nueva_atribuible){r.resultado='BLOQUEADO / NO VERIFICABLE';
    r.motivo=`Interferencia concurrente: aparecieron ${r.ids_nuevos.length} IDs nuevos (${r.ids_nuevos.join(', ')}) y solo uno es atribuible a G134.`;}
  else if(!(r.response?.http>=200&&r.response.http<300)||!Number.isInteger(id)||r.ids_nuevos.length!==1||!r.nueva_atribuible){
    r.resultado='RECHAZADO';r.motivo=`HTTP ${r.response?.http??'no verificable'}, id ${id??'ausente'}, IDs nuevos ${r.ids_nuevos.join(', ')||'ninguno'}, atribuible ${r.nueva_atribuible}; el oráculo exige 2xx y exactamente una calibración G134 nueva.`;}
  else{r.resultado='APROBADO';r.motivo=`HTTP ${r.response.http}; ID ${id} nuevo atribuible a G134 y ${r.pre.total} calibraciones PRE intactas campo por campo.`;}}
async function apiTelemetry(sensor,day,ingToken,adminToken){
  const query=(page)=>`/iot/monitoreo/historial?fecha_inicio=${day}&fecha_fin=${day}&sensor_id=${sensor}&por_pagina=500&orden=ASC&pagina=${page}`;
  let token=ingToken,actor='Ingeniero';let first=await request('GET',query(1),token);
  if(first.status!==200||first.body?.total===0){const admin=await request('GET',query(1),adminToken);
    if(admin.status===200&&admin.body?.total>0){first=admin;token=adminToken;actor='Administrador';}
    else throw new Error(`GET telemetría: Ingeniero HTTP ${first.status}/total ${first.body?.total}; Admin HTTP ${admin.status}/total ${admin.body?.total}.`);}
  const total=first.body?.total,pages=first.body?.paginas_totales;
  if(!Number.isInteger(total)||!Number.isInteger(pages)||pages<1)throw new Error('Paginación API de telemetría no verificable.');
  const items=[...(first.body.items||[])];
  for(let p=2;p<=pages;p++){const x=await request('GET',query(p),token);if(x.status!==200)throw new Error(`Página API ${p} HTTP ${x.status}.`);
    items.push(...(x.body.items||[]));}
  if(items.length!==total)throw new Error(`Paginación API incompleta: ${items.length}/${total}.`);
  const rows=items.map(x=>({id_telemetria:x.id_telemetria,valor:x.valor,
    valor_ajustado:x.valor_ajustado,timestamp_captura:x.timestamp_captura})).sort((a,b)=>a.id_telemetria-b.id_telemetria);
  return {http:first.status,actor,paginas:pages,cantidad:rows.length,sha256:digest(rows),filas:rows};}
async function discover267(f266,adminToken,ingToken,ranges){const candidates=[f266.sensor,...python(['--sensors']).map(x=>x.sensor)].filter((x,i,a)=>a.indexOf(x)===i);
  const reasons=[];
  for(const sensor of candidates){const days=python(['--days'],{G134_SENSOR:String(sensor)});
    if(!days.length){reasons.push(`sensor ${sensor}: sin telemetría de día cerrado`);continue;}
    let f=null;
    if(sensor===f266.sensor)f=f266;
    else{
      const devices=(await get('/configuracion/dispositivos-iot',adminToken)).items||[];
      for(const d of devices.filter(x=>x.es_activo===true)){
        const sl=(await get(`/configuracion/dispositivos-iot/${d.id_dispositivo_iot}/sensores`,adminToken)).items||[];
        if(!sl.some(x=>x.id_sensores===sensor&&x.es_activo===true))continue;
        const assocs=(await get(`/configuracion/sensores/${sensor}/asociaciones`,adminToken)).items||[];
        for(const a of assocs.filter(x=>x.tiene_estado===true&&x.fecha_finalizacion===null)){
          try{f=await fixture(d.id_dispositivo_iot,sensor,a.id_infraestructura,adminToken,ranges);if(f)break;}catch{ /* siguiente */ }}
        if(f)break;}}
    if(!f){reasons.push(`sensor ${sensor}: fixture no válido para 30.0000`);continue;}
    for(const day of days){try{const api=await apiTelemetry(sensor,day.dia,ingToken,adminToken);
      if(api.cantidad>0)return {fixture:f,dia:day.dia,cantidad_sql_descubierta:day.cantidad,api_actor:api.actor};}
      catch(x){reasons.push(`sensor ${sensor}/${day.dia}: ${clean(x.message)}`);}}
  }
  throw new Error(`No se halló telemetría histórica cerrada consultable por API para fixture 30.0000. ${reasons.slice(0,12).join('; ')}`);}
function rowDiff(pre,post,key){const a=new Map(pre.map(x=>[x[key],x])),b=new Map(post.map(x=>[x[key],x]));
  return {ausentes:pre.filter(x=>!b.has(x[key])),nuevas:post.filter(x=>!a.has(x[key])),
    modificadas:pre.filter(x=>b.has(x[key])&&JSON.stringify(x)!==JSON.stringify(b.get(x[key])))
      .map(x=>({id:x[key],pre:x,post:b.get(x[key])}))};}
async function case267(f266,ingToken,adminToken,ranges){const r=e['TC-M09-267'];
  for(const k of ['QA_DB_HOST','QA_DB_PORT','QA_DB_USER','QA_DB_PASSWORD','QA_DB_NAME'])
    if(!process.env[k]){r.resultado='BLOQUEADO / NO VERIFICABLE';r.motivo=`Falta variable de conexión read-only ${k}.`;return;}
  let found;
  try{found=await discover267(f266,adminToken,ingToken,ranges);}catch(x){r.resultado='BLOQUEADO / NO VERIFICABLE';r.motivo=clean(x.message);return;}
  const f=found.fixture;e.fixture_267={...f,dia_historico:found.dia,api_actor:found.api_actor};
  const next=new Date(Date.parse(found.dia+'T00:00:00Z')+86400000).toISOString().slice(0,10);
  r.periodo={dia:found.dia,inicio_utc:found.dia+'T00:00:00Z',fin_exclusivo_utc:next+'T00:00:00Z'};
  const postBefore=new Date().toISOString();r.t_post_before=postBefore;
  const vars=dbEnv(f.sensor,r.periodo,postBefore);
  try{
    r.sql_pre=python(['--snapshot'],vars);
    if(r.sql_pre.cantidad<1)throw new Error('SELECT PRE no devolvió lecturas históricas.');
    r.api_pre=await apiTelemetry(f.sensor,found.dia,ingToken,adminToken);
    const sqlIds=r.sql_pre.filas.map(x=>x.id_telemetria).sort((a,b)=>a-b);
    const apiIds=r.api_pre.filas.map(x=>x.id_telemetria).sort((a,b)=>a-b);
    if(JSON.stringify(sqlIds)!==JSON.stringify(apiIds))throw new Error(`SQL/API PRE no observan los mismos IDs: SQL ${sqlIds}, API ${apiIds}.`);
  }catch(x){r.resultado='BLOQUEADO / NO VERIFICABLE';r.motivo=`No se pudo formar snapshot PRE estable: ${clean(x.message)}`;return;}
  await sendCalibration(r,f,'TC-M09-267',ingToken);
  r.t_post_after=new Date().toISOString();
  try{r.sql_post=python(['--snapshot'],vars);r.api_post=await apiTelemetry(f.sensor,found.dia,ingToken,adminToken);
    r.pytest=runPytest({...vars,G134_EXPECTED_COUNT:String(r.sql_pre.cantidad),G134_EXPECTED_SHA256:r.sql_pre.sha256});
  }catch(x){r.resultado='BLOQUEADO / NO VERIFICABLE';r.motivo=`POST enviado, pero snapshot POST no verificable: ${clean(x.message)}. No se reenvió.`;return;}
  r.sql_diferencias=rowDiff(r.sql_pre.filas,r.sql_post.filas,'id_telemetria');
  r.api_diferencias=rowDiff(r.api_pre.filas,r.api_post.filas,'id_telemetria');
  r.digest_sql_igual=r.sql_pre.sha256===r.sql_post.sha256;
  r.digest_api_igual=r.api_pre.sha256===r.api_post.sha256;
  if(!(r.response?.http>=200&&r.response.http<300)){r.resultado='RECHAZADO';r.motivo=`Fixture válido, POST respondió HTTP ${r.response?.http??'no verificable'} en vez de 2xx.`;}
  else if(r.sql_diferencias.modificadas.length||r.sql_diferencias.ausentes.length||
    r.api_diferencias.modificadas.length||r.api_diferencias.ausentes.length){r.resultado='RECHAZADO';
    r.motivo=`Lecturas históricas alteradas: SQL modificadas ${r.sql_diferencias.modificadas.length}/ausentes ${r.sql_diferencias.ausentes.length}; API modificadas ${r.api_diferencias.modificadas.length}/ausentes ${r.api_diferencias.ausentes.length}.`;}
  else if(r.sql_diferencias.nuevas.length||r.api_diferencias.nuevas.length){r.resultado='BLOQUEADO / NO VERIFICABLE';
    r.motivo=`Aparecieron filas en período cerrado (SQL ${r.sql_diferencias.nuevas.length}, API ${r.api_diferencias.nuevas.length}); posible backfill concurrente, no atribuible automáticamente al POST.`;}
  else if(!r.digest_sql_igual||!r.digest_api_igual||r.pytest.exit_code!==0){r.resultado='RECHAZADO';
    r.motivo=`Digest SQL ${r.digest_sql_igual?'igual':'distinto'}, API ${r.digest_api_igual?'igual':'distinto'}, pytest exit ${r.pytest.exit_code}.`;}
  else{r.resultado='APROBADO';r.motivo=`POST HTTP ${r.response.http}; ${r.sql_pre.cantidad} lectura(s) SQL y ${r.api_pre.cantidad} lectura(s) API idénticas PRE/POST; pytest pasó.`;}}
function buildIncidents(){for(const id of ['TC-M09-265','TC-M09-266','TC-M09-267']){const r=e[id];if(r.resultado!=='RECHAZADO')continue;
  const owner=id==='TC-M09-267'?'Por determinar':'Desarrollo';
  e.incidencias.push({grupo_responsable:owner,grupo_prueba:'TC-M09-G134',casos:[id],resultado:'RECHAZADO',
    motivo:r.motivo,esperado:id==='TC-M09-265'?'Histórico oficial completo por ID y sin mezcla de sensores.':
      id==='TC-M09-266'?'Una calibración 30.0000 nueva y todas las anteriores intactas.':
      'POST 2xx y telemetría histórica SQL/API idéntica PRE/POST.',
    obtenido:id==='TC-M09-267'?`SQL diferencias ${JSON.stringify(r.sql_diferencias??null)}; API diferencias ${JSON.stringify(r.api_diferencias??null)}.`:
      id==='TC-M09-266'?`HTTP ${r.response?.http}; ausentes ${r.previas_ausentes}; modificadas ${JSON.stringify(r.previas_modificadas)}; nuevos ${r.ids_nuevos}.`:
      `HTTP ${r.http}; comparaciones ${JSON.stringify(r.comparaciones)}; otros sensores ${JSON.stringify(r.items_de_otro_sensor)}.`,
    causa_raiz:id==='TC-M09-267'?'Por determinar; distinguir backend, pipeline AIoT o mecanismo DB con evidencia adicional.':
      'Posible lógica del historial o persistencia de calibraciones; mecanismo del despliegue por confirmar.',
    type:'bug',severity:'Important',priority:'High',evidencia:'evidencia.json / newman.html / pytest.xml'});}}
function render(){const ids=['TC-M09-265','TC-M09-266','TC-M09-267'];
  const rows=ids.map(id=>`| ${id} | ${e[id].resultado} | ${e[id].motivo} |`).join('\n');
  const a=e['TC-M09-265'],b=e['TC-M09-266'],c=e['TC-M09-267'];
  const incidents=e.incidencias.length?e.incidencias.map(i=>
    `### ${i.casos.join(', ')}\n\nINCIDENCIA REQUERIDA: SÍ  \nGrupo responsable: ${i.grupo_responsable}  \nGrupo de prueba: ${i.grupo_prueba}  \nResultado: ${i.resultado}  \nMotivo: ${i.motivo}  \nEsperado: ${i.esperado}  \nObtenido: ${i.obtenido}  \nCausa raíz: ${i.causa_raiz}  \nType: ${i.type}  \nSeverity: ${i.severity}  \nPriority: ${i.priority}  \nEvidencia: ${i.evidencia}`).join('\n\n'):'INCIDENCIA REQUERIDA: NO.';
  const md=`# TC-M09-G134 — Resultado\n\n## Decisión general\n\n**${e.resultado_general}.** ${e.motivo_general}\n\n| Caso | Resultado | Motivo |\n|---|---|---|\n${rows}\n\n## Entorno y actores\n\nTEST: ${base}. Prueba local: NO. RUN_ID: ${runId}. Rama: ${e.git.rama}; HEAD y origin/test: ${e.git.head} / ${e.git.origin_test}; divergencia ${e.git.divergencia}.\n\nIngeniero funcional: ${JSON.stringify(e.actor)}. Administrador de GET: ${JSON.stringify(e.admin)}. OpenAPI: ${JSON.stringify(e.openapi)}. BD TEST usada exclusivamente con SELECT read-only; SQL de escritura: NO.\n\n## TC-M09-265 — historial oficial\n\n**Esperado:** tres calibraciones oficiales por ID, con dispositivo, sensor, usuario, fecha, valor y observaciones idénticos; ningún item de otro sensor. Orden no evaluado.\n\nReferencias oficiales y fuentes: ${JSON.stringify(a.referencias_oficiales??null)}.\n\nGET HTTP ${a.http??'no ejecutado'}; total ${a.total??'no verificable'}; IDs ${JSON.stringify(a.ids??null)}. Comparaciones: ${JSON.stringify(a.comparaciones??null)}. Items de otro sensor: ${JSON.stringify(a.items_de_otro_sensor??null)}.\n\n**Resultado:** ${a.resultado}. **Motivo:** ${a.motivo}\n\n## TC-M09-266 — calibraciones previas inmutables\n\nFixture: ${JSON.stringify(e.fixture_266)}. POST del Ingeniero: ${JSON.stringify(b.request??null)}; respuesta ${JSON.stringify(b.response??null)}.\n\nSnapshot PRE: ${JSON.stringify(b.pre??null)}. Snapshot POST: ${JSON.stringify(b.post??null)}.\n\nPrevias ausentes: ${JSON.stringify(b.previas_ausentes??null)}; modificadas: ${JSON.stringify(b.previas_modificadas??null)}; IDs nuevos: ${JSON.stringify(b.ids_nuevos??null)}; nueva atribuible: ${JSON.stringify(b.nueva_atribuible??null)}.\n\n**Resultado:** ${b.resultado}. **Motivo:** ${b.motivo}\n\n## TC-M09-267 — telemetría histórica\n\nFixture: ${JSON.stringify(e.fixture_267)}. Período cerrado: ${JSON.stringify(c.periodo??null)}. t_post_before: ${c.t_post_before??'no registrado'}; t_post_after: ${c.t_post_after??'no registrado'}.\n\nSQL PRE: ${JSON.stringify(c.sql_pre??null)}. SQL POST: ${JSON.stringify(c.sql_post??null)}. Digest SQL igual: ${JSON.stringify(c.digest_sql_igual??null)}.\n\nAPI PRE: ${JSON.stringify(c.api_pre??null)}. API POST: ${JSON.stringify(c.api_post??null)}. Digest API igual: ${JSON.stringify(c.digest_api_igual??null)}.\n\nPOST del Ingeniero: ${JSON.stringify(c.request??null)}; respuesta ${JSON.stringify(c.response??null)}. Diferencias SQL: ${JSON.stringify(c.sql_diferencias??null)}. Diferencias API: ${JSON.stringify(c.api_diferencias??null)}. Pytest read-only: ${JSON.stringify(c.pytest??null)}.\n\n**Resultado:** ${c.resultado}. **Motivo:** ${c.motivo}\n\n## Incidencias\n\n${incidents}\n\n## Conclusión\n\n${e.motivo_general} POST planificados: 2; ejecutados: ${e.post_ejecutados}; sin reintentos ni SQL de escritura.\n`;
  fs.writeFileSync(path.join(out,'TC-M09-G134_resultado.md'),clean(md),'utf8');
  const trs=ids.map(id=>`<tr><td>${esc(id)}</td><td>${esc(e[id].resultado)}</td><td>${esc(e[id].motivo)}</td></tr>`).join('');
  fs.writeFileSync(path.join(out,'newman.html'),`<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman ${esc(runId)}</title><style>body{font:16px Arial,sans-serif;max-width:1100px;margin:40px auto;color:#182331}table{border-collapse:collapse;width:100%}td,th{border:1px solid #bbc5ce;padding:9px;text-align:left}th{background:#e9eef2}</style><h1>Newman — TC-M09-G134</h1><p>RUN ${esc(runId)} · TEST · ${esc(e.resultado_general)} · ${e.post_ejecutados}/2 POST</p><table><thead><tr><th>Caso</th><th>Resultado</th><th>Motivo</th></tr></thead><tbody>${trs}</tbody></table><p>Detalle: evidencia.json y TC-M09-G134_resultado.md.</p></html>`,'utf8');}
function finalize(){for(const id of ['TC-M09-265','TC-M09-266','TC-M09-267'])if(!e[id].resultado)
  Object.assign(e[id],{resultado:'BLOQUEADO / NO VERIFICABLE',motivo:e.motivo_general||'Ejecución no verificable.'});
  buildIncidents();const states=['TC-M09-265','TC-M09-266','TC-M09-267'].map(id=>e[id].resultado);
  e.resultado_general=states.every(x=>x==='APROBADO')?'APROBADO':states.includes('RECHAZADO')?'RECHAZADO':'BLOQUEADO / NO VERIFICABLE';
  if(!e.motivo_general)e.motivo_general=e.resultado_general==='APROBADO'
    ?'Las tres verificaciones cumplieron: historial oficial, calibraciones previas intactas y telemetría histórica SQL/API inalterada.'
    :e.resultado_general==='RECHAZADO'?`Incumplimiento demostrado en ${['TC-M09-265','TC-M09-266','TC-M09-267'].filter(id=>e[id].resultado==='RECHAZADO').join(', ')}.`
    :`Cobertura incompleta: ${['TC-M09-265','TC-M09-266','TC-M09-267'].filter(id=>e[id].resultado!=='APROBADO').join(', ')}.`;
  if(!fs.existsSync(path.join(out,'pytest.xml')))fs.writeFileSync(path.join(out,'pytest.xml'),
    '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="TC-M09-267" tests="1" skipped="1"><testcase name="test_historico_inmutable"><skipped message="Precondición no alcanzada"/></testcase></testsuite></testsuites>','utf8');
  save();render();console.log(`TC-M09-G134 → ${e.resultado_general}; POST ${e.post_ejecutados}/2; SQL escritura: NO`);
  console.log(path.join(out,'TC-M09-G134_resultado.md'));}
async function main(){e.git={rama:git(['branch','--show-current']),status_short:git(['status','--short']),
  diff_stat:git(['diff','--stat']),diff_cached_stat:git(['diff','--cached','--stat']),
  head:git(['rev-parse','HEAD']),origin_test:git(['rev-parse','origin/test']),
  divergencia:git(['rev-list','--left-right','--count','HEAD...origin/test'])};
  if(e.git.rama!=='qa/juan-esteban-rf24-v2')throw new Error('La rama QA requerida no está activa.');
  const o=await request('GET','/openapi.json');if(o.status!==200)throw new Error(`OpenAPI TEST HTTP ${o.status}.`);
  const endpoints=[['GET historial calibraciones','/configuracion/sensores/{id_sensor}/calibraciones','get'],
    ['POST calibrar','/configuracion/sensores/{id_sensor}/calibrar','post'],
    ['GET telemetría histórica','/iot/monitoreo/historial','get']];
  e.openapi=Object.fromEntries(endpoints.map(([n,p,m])=>[n,{presente:Boolean(o.body.paths?.[p]?.[m]),
    codigos_declarados:Object.keys(o.body.paths?.[p]?.[m]?.responses||{})}]));
  if(Object.values(e.openapi).some(x=>!x.presente))throw new Error('Falta un endpoint requerido en OpenAPI TEST.');
  const ingToken=await login(email,password);
  const me=await get('/usuarios/me',ingToken),perms=await get('/sesiones/me/permisos',ingToken);
  e.actor={id_usuario:me.id_usuario,correo:me.correo_electronico,rol:me.nombre_rol,
    estado:me.estado_cuenta,permisos_calibracion:(perms.permisos||[]).filter(x=>x.id_recurso===12).map(x=>x.id_accion)};
  if(me.correo_electronico!==email||me.nombre_rol!=='Ingeniero de Campo'||me.estado_cuenta!=='Activo'||
    !e.actor.permisos_calibracion.includes(1)||!e.actor.permisos_calibracion.includes(2))
    throw new Error('Ingeniero sin identidad, estado o permisos de calibración requeridos.');
  const adminToken=await adminLogin();
  await case265(ingToken);
  const ranges=await get('/configuracion/sensores/rangos-calibracion',ingToken);
  let f266;try{f266=await findFixture([3,6,3],adminToken,ranges);e.fixture_266=f266;}
  catch(x){e['TC-M09-266'].resultado='BLOQUEADO / NO VERIFICABLE';e['TC-M09-266'].motivo=clean(x.message);
    e['TC-M09-267'].resultado='BLOQUEADO / NO VERIFICABLE';e['TC-M09-267'].motivo='No se pudo validar un fixture 30.0000 para el POST de telemetría.';return;}
  await case266(f266,ingToken);
  await case267(f266,ingToken,adminToken,ranges);
}
main().catch(x=>{e.motivo_general=`BLOQUEADO: ${clean(x.message)}`;}).finally(finalize);
