// TC-M09-G135: seis POST de calibración, uno por caso; GET de historial y RF-10.
const fs = require('fs');
const path = require('path');
const {execFileSync} = require('child_process');
const newman = require(path.join(path.dirname(process.execPath), 'node_modules', 'newman'));

const base = (process.env.QA_BASE_URL || '').replace(/\/$/, '');
if (path.basename(__dirname) !== 'TC-M09-G135' || base !== 'https://api.inmero.co/back-sigab-test')
  throw new Error('Carpeta o ambiente TEST incorrectos.');
const runId = process.env.G135_RUN_ID;
const preflightOnly = process.argv.includes('--preflight');
if (!preflightOnly && !/^run-\d{8}-\d{6}$/.test(runId || '')) throw new Error('G135_RUN_ID inválido.');
const out = preflightOnly ? null : path.join(__dirname, 'RESULTADOS', runId);
if (out && fs.existsSync(out)) throw new Error('RUN_ID existente: no se sobrescribe.');
for (const k of ['QA_ING_EMAIL', 'QA_ING_PASSWORD', 'QA_ADMIN_PASSWORD'])
  if (!process.env[k]) throw new Error(`Falta ${k} en variable de proceso.`);
const secrets = [process.env.QA_ING_PASSWORD, process.env.QA_ADMIN_PASSWORD, process.env.QA_PRODUCTOR_PASSWORD].filter(Boolean);
function clean(s) { let v = String(s ?? ''); for (const secret of new Set(secrets)) v = v.split(secret).join('[REDACTED]');
  return v.replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[JWT REDACTED]')
    .replace(/Bearer\s+[A-Za-z0-9_.-]{12,}/gi, 'Bearer [REDACTED]'); }
function save() { if (out) fs.writeFileSync(path.join(out, 'evidencia.json'), clean(JSON.stringify(e, null, 2)), 'utf8'); }
function git(args) { try { let d = __dirname; while (!fs.existsSync(path.join(d, '.git')) && path.dirname(d) !== d) d = path.dirname(d);
  return execFileSync('git', args, {cwd:d, encoding:'utf8'}).trim(); } catch (x) { return `ERROR ${clean(x.message)}`; } }
function gitSnapshot() { return {rama:git(['branch','--show-current']),status_short:git(['status','--short']),
  diff_stat:git(['diff','--stat']),diff_cached_stat:git(['diff','--cached','--stat']),
  head:git(['rev-parse','HEAD']),origin_test:git(['rev-parse','origin/test']),
  divergencia:git(['rev-list','--left-right','--count','HEAD...origin/test'])}; }
const ids = [268,269,270,271,272,273].map(x => `TC-M09-${x}`);
const expected = {'TC-M09-268':403,'TC-M09-269':422,'TC-M09-270':400,'TC-M09-271':400,'TC-M09-272':400,'TC-M09-273':404};
const motive = {'TC-M09-268':/acceso|permiso|rol|autoriza/i,'TC-M09-269':/inactiv|activ/i,
  'TC-M09-270':/rango|l[ií]mite|fuera/i,'TC-M09-271':/n[uú]mer|decimal|valor/i,
  'TC-M09-272':/[aá]rea|ubicaci[oó]n|infraestructura/i,'TC-M09-273':/existe|encontr|dispositivo/i};
const e = {grupo:'TC-M09-G135',casos:ids,run_id:runId || 'preflight',ambiente:'TEST',base_url:base,
  git:{},openapi:{},actores:{},fixtures:{},discovery:[],post_planificados:6,post_ejecutados:0,
  sql_ejecutado:'ninguno',resultado_general:'',motivo_general:'',incidencias:[]};
for (const id of ids) e[id] = {esperado_http:expected[id],resultado:'PENDIENTE'};

async function request(method, route, token, body) {
  const r = await fetch(base + route, {method,headers:{...(token ? {Authorization:`Bearer ${token}`} : {}),
    ...(body !== undefined ? {'Content-Type':'application/json'} : {})},
    body:body === undefined ? undefined : JSON.stringify(body),signal:AbortSignal.timeout(30000)});
  const raw = await r.text(); let data; try { data = JSON.parse(raw); } catch { data = raw.slice(0,500); }
  return {status:r.status,body:data};
}
async function login(email, password) { const r = await request('POST','/sesiones/',null,{correo_electronico:email,contrasena:password});
  if (r.status !== 200 || !r.body?.token) throw new Error(`login ${email}: HTTP ${r.status}`); return r.body.token; }
async function get(route, token) { const r = await request('GET',route,token); if (r.status !== 200) throw new Error(`GET ${route}: HTTP ${r.status}`); return r.body; }
async function discover(route, ing, admin) { const r = await request('GET',route,ing); const d = {ruta:route,ingeniero_http:r.status};
  if (r.status === 200) {e.discovery.push(d);return r.body;}
  if (r.status === 404 && admin) { const a = await request('GET',route,admin); d.admin_http=a.status;e.discovery.push(d);
    if (a.status === 200) return a.body; throw new Error(`Discovery ${route}: Ingeniero 404, Administrador ${a.status}`); }
  e.discovery.push(d); throw new Error(`Discovery ${route}: Ingeniero HTTP ${r.status}`); }
function info(me) { return {correo:me.correo_electronico,id_usuario:me.id_usuario,rol:me.nombre_rol,estado:me.estado_cuenta}; }
async function adminLogin() {const attempts=[]; for (const correo of ['admin.dev@gmail.com','administador.dev@gmail.com']) {
    try {const token=await login(correo,process.env.QA_ADMIN_PASSWORD);const me=await get('/usuarios/me',token);
      const a=await request('GET','/auditoria/?tamano=1',token);attempts.push({...info(me),auditoria_http:a.status});
      if(me.correo_electronico===correo && me.nombre_rol==='Administrador' && me.estado_cuenta==='Activo' &&
        [200,206].includes(a.status) && Array.isArray(a.body?.items))
        return {token,info:{...info(me),auditoria_http:a.status,intentos:attempts}};
    } catch (x) {attempts.push({correo,problema:clean(x.message)});} }
  e.actores.administrador={intentos:attempts}; throw new Error('Ningún Administrador puede consultar GET /auditoria/.'); }
async function history(sensor,token) {const r=await request('GET',`/configuracion/sensores/${sensor}/calibraciones`,token);
  if(r.status!==200 || !Array.isArray(r.body?.items) || !Number.isInteger(r.body.total))
    throw new Error(`Historial sensor ${sensor}: HTTP ${r.status} o cuerpo no verificable`);
  return {total:r.body.total,ids:r.body.items.map(x=>x.id_calibracion).sort((a,b)=>a-b)}; }
function sameHistory(a,b) {return a.total===b.total && JSON.stringify(a.ids)===JSON.stringify(b.ids);}
function findAssoc(data,sensor,device,area) {return data.items?.find(x=>x.id_sensor===sensor && x.id_dispositivo_iot===device &&
  x.id_infraestructura===area && x.tiene_estado===true && x.fecha_finalizacion===null);}
async function fixtureValid(ing,admin,ranges) {
  const device=await discover('/configuracion/dispositivos-iot/3',ing,admin);
  const sensors=await discover('/configuracion/dispositivos-iot/3/sensores',ing,admin);
  const sensor=sensors.items?.find(x=>x.id_sensores===6 && x.id_dispositivo_iot===3);
  const associations=await discover('/configuracion/sensores/6/asociaciones',ing,admin);
  const assoc=findAssoc(associations,6,3,3);
  const area=await discover('/configuracion/infraestructuras/3',ing,admin);
  const range=ranges.items?.find(x=>x.categoria===sensor?.categoria);
  if(device.es_activo!==true || sensor?.es_activo!==true || !assoc || area.es_activo!==true || !range ||
    Number(range.valor_min)>22.5 || Number(range.valor_max)<22.5)
    throw new Error('Fixture 6/3/3 no cumple estado activo, asociación vigente o rango que incluya 22.5000.');
  return {sensor:6,dispositivo:3,area:3,categoria:sensor.categoria,asociacion:assoc.id_sensores_area_asociada,
    rango:{min:range.valor_min,max:range.valor_max},estado:{sensor:sensor.es_activo,dispositivo:device.es_activo,area:area.es_activo},
    asociaciones_vigentes:associations.items.filter(x=>x.id_sensor===6 && x.tiene_estado===true && x.fecha_finalizacion===null)
      .map(x=>({id_dispositivo_iot:x.id_dispositivo_iot,id_infraestructura:x.id_infraestructura}))};
}
async function fixtureInactive(ing,admin) {
  const device=await discover('/configuracion/dispositivos-iot/47',ing,admin);
  const sensors=await discover('/configuracion/dispositivos-iot/47/sensores',ing,admin);
  const sensor=sensors.items?.find(x=>x.id_sensores===29 && x.id_dispositivo_iot===47);
  const associations=await discover('/configuracion/sensores/29/asociaciones',ing,admin);
  const assoc=findAssoc(associations,29,47,3);
  const area=await discover('/configuracion/infraestructuras/3',ing,admin);
  if(device.es_activo!==false || sensor?.es_activo!==true || !assoc || area.es_activo!==true)
    throw new Error('Fixture 29/47/3 no demuestra únicamente dispositivo inactivo con asociación vigente.');
  return {sensor:29,dispositivo:47,area:3,dispositivo_activo:device.es_activo,sensor_activo:sensor.es_activo,
    area_activa:area.es_activo,asociacion:assoc.id_sensores_area_asociada};
}
async function preflight() {
  e.git=gitSnapshot();if(e.git.rama!=='qa/juan-esteban-rf24-v2')throw new Error(`Rama inesperada: ${e.git.rama}`);
  const o=await request('GET','/openapi.json');if(o.status!==200)throw new Error(`OpenAPI TEST HTTP ${o.status}`);
  for(const [label,route,method] of [['calibrar','/configuracion/sensores/{id_sensor}/calibrar','post'],
    ['historial','/configuracion/sensores/{id_sensor}/calibraciones','get'],['auditoria','/auditoria/','get'],
    ['catalogo_tipos','/auditoria/catalogo/tipos-evento','get']])
    e.openapi[label]={presente:Boolean(o.body.paths?.[route]?.[method]),codigos:Object.keys(o.body.paths?.[route]?.[method]?.responses||{})};
  if(['calibrar','historial','auditoria'].some(k=>!e.openapi[k].presente))throw new Error('Falta endpoint requerido en OpenAPI TEST.');
  const ing=await login(process.env.QA_ING_EMAIL,process.env.QA_ING_PASSWORD);
  const me=await get('/usuarios/me',ing),p=await get('/sesiones/me/permisos',ing);
  e.actores.ingeniero={...info(me),permisos_calibracion:(p.permisos||[]).filter(x=>x.id_recurso===12).map(x=>x.id_accion)};
  if(me.correo_electronico!==process.env.QA_ING_EMAIL || me.nombre_rol!=='Ingeniero de Campo' || me.estado_cuenta!=='Activo' ||
    !e.actores.ingeniero.permisos_calibracion.includes(1))throw new Error('Ingeniero sin identidad, estado o permiso de calibración requerido.');
  const admin=await adminLogin();e.actores.administrador=admin.info;
  let producer=null;const email=process.env.QA_PRODUCTOR_EMAIL||'m2m.nuevo@ejemplo.com';
  if(process.env.QA_PRODUCTOR_PASSWORD)try {const token=await login(email,process.env.QA_PRODUCTOR_PASSWORD);
    const m=await get('/usuarios/me',token),per=await get('/sesiones/me/permisos',token);
    e.actores.productor={...info(m),permisos_calibracion:(per.permisos||[]).filter(x=>x.id_recurso===12).map(x=>x.id_accion)};
    if(m.correo_electronico===email && m.nombre_rol==='Productor' && m.estado_cuenta==='Activo')producer=token;
    else e.actores.productor.precondicion='La identidad no confirma Productor activo.';
  } catch(x) {e.actores.productor={correo:email,precondicion:clean(x.message)};}
  else e.actores.productor={correo:email,precondicion:'QA_PRODUCTOR_PASSWORD no está disponible en variable de proceso.'};
  const ranges=await get('/configuracion/sensores/rangos-calibracion',ing);
  try {e.fixtures.valido=await fixtureValid(ing,admin.token,ranges);}catch(x){e.fixtures.valido={problema:clean(x.message)};}
  try {e.fixtures.inactivo=await fixtureInactive(ing,admin.token);}catch(x){e.fixtures.inactivo={problema:clean(x.message)};}
  try {const wrong=await discover('/configuracion/infraestructuras/1',ing,admin.token);
    e.fixtures.area_incorrecta={id:1,existe:true,es_activo:wrong.es_activo,
      no_asociada:!e.fixtures.valido?.asociaciones_vigentes?.some(x=>x.id_infraestructura===1)};
  }catch(x){e.fixtures.area_incorrecta={problema:clean(x.message)};}
  const absent=await request('GET','/configuracion/dispositivos-iot/999999',ing);
  e.fixtures.dispositivo_inexistente={id:999999,ingeniero_http:absent.status};
  if(absent.status===404){const a=await request('GET','/configuracion/dispositivos-iot/999999',admin.token);
    e.fixtures.dispositivo_inexistente.admin_http=a.status;}
  e.fixtures.rangos=ranges.items?.filter(x=>x.categoria===e.fixtures.valido?.categoria).map(x=>({categoria:x.categoria,min:x.valor_min,max:x.valor_max}));
  return {ing,admin:admin.token,producer};
}

function calibrationBody(id, f) {const body={modo_calibracion:'SENSOR',id_dispositivo_iot:f.dispositivo,
  id_infraestructura:f.area,valor_referencia:id==='TC-M09-270'?45.0001:id==='TC-M09-271'?'abc':
    id==='TC-M09-269'?7.0000:22.5000,observaciones:`QA ${id}`,fecha_calibracion:new Date().toISOString()};
  return body;}
function newmanPost(id,sensor,token,body) {const collection=JSON.parse(fs.readFileSync(path.join(__dirname,'TC-M09-G135.postman_collection.json'),'utf8'));
  const raw=JSON.stringify(body).replace(/"valor_referencia":22\.5(?=,)/,'"valor_referencia":22.5000')
    .replace(/"valor_referencia":7(?=,)/,'"valor_referencia":7.0000');
  return new Promise(resolve=>{let response=null,transport=null;const started=new Date().toISOString();
    const emitter=newman.run({collection,envVar:[
      {key:'base_url',value:base},{key:'token',value:token},{key:'case_id',value:id},
      {key:'sensor_id',value:String(sensor)},{key:'body_json',value:raw},
      {key:'expected_status',value:String(expected[id])}],reporters:['cli'],silent:true,
      timeoutRequest:30000,followRedirects:false},(err,summary)=>{
      const ex=summary?.run?.executions?.[0];if(!response && ex?.response){let data;try{data=JSON.parse(ex.response.stream.toString('utf8'));}
        catch{data=ex.response.stream.toString('utf8').slice(0,500);}response={status:ex.response.code,body:data};}
      resolve({t_before:started,t_after:new Date().toISOString(),response,transport:clean(transport||err?.message||''),
        assertions:(summary?.run?.failures||[]).map(x=>clean(x.error?.message||'assertion fallida'))});});
    emitter.on('request',(err,args)=>{if(err){transport=err.message;return;}const raw=args.response?.stream?.toString('utf8')||'';
      let data;try{data=JSON.parse(raw);}catch{data=raw.slice(0,500);}response={status:args.response?.code,body:data};});
  });}
function auditUrl(actor,start,end,page) {const p=new URLSearchParams({id_usuario:String(actor),fecha_desde:start,
  fecha_hasta:end,tamano:'50',pagina:String(page)});return `/auditoria/?${p}`;}
async function auditPages(actor,tBefore,tAfter,token) {const start=new Date(Date.parse(tBefore)-60000).toISOString();
  const end=new Date(Date.parse(tAfter)+60000).toISOString();const pages=[],items=[];
  for(let page=1;page<=20;page++){const r=await request('GET',auditUrl(actor,start,end,page),token);
    pages.push({pagina:page,http:r.status,total:r.body?.total,items:r.body?.items?.length});
    if(![200,206].includes(r.status)||!Array.isArray(r.body?.items))return {ventana:{fecha_desde:start,fecha_hasta:end},paginas:pages,error:`GET /auditoria/ HTTP ${r.status} o cuerpo inválido`,items};
    items.push(...r.body.items);if(items.length>=r.body.total||r.body.items.length===0)return {ventana:{fecha_desde:start,fecha_hasta:end},paginas:pages,items};}
  return {ventana:{fecha_desde:start,fecha_hasta:end},paginas:pages,error:'Se excedieron 20 páginas',items};}
function auditCheck(id, data,actor,tBefore,tAfter,sensor) {const candidates=(data.items||[]).filter(x=>x.id_usuario===actor &&
  Date.parse(x.fecha_evento)>=Date.parse(tBefore)-60000 && Date.parse(x.fecha_evento)<=Date.parse(tAfter)+60000 &&
  (/calibraci[oó]n/i.test(x.descripcion||'') || /CALIBRACION/i.test(x.detalle?.operacion||'')));
  const evaluated=candidates.map(x=>{const d=x.detalle||{},m=String(d.motivo||x.descripcion||'');const checks={
    resultado:String(x.resultado||'').toUpperCase()==='FALLIDO',modulo:/M[OÓ]DULO\s*9|MODULO9/i.test(x.modulo||''),
    usuario:x.id_usuario===actor,fecha:Number.isFinite(Date.parse(x.fecha_evento)),motivo:motive[id].test(m),
    ip:typeof x.direccion_ip==='string'&&x.direccion_ip.trim().length>0,
    operacion:d.operacion==null || /CALIBRACION/i.test(String(d.operacion)),
    codigo_http:d.codigo_http==null || Number(d.codigo_http)===expected[id],
    id_sensor:d.id_sensor==null || Number(d.id_sensor)===sensor,
    detalle_ip:d.ip==null || String(d.ip)===String(x.direccion_ip)};
    return {id_evento:x.id_evento,tipo_evento:x.tipo_evento,fecha_evento:x.fecha_evento,resultado:x.resultado,
      modulo:x.modulo,id_usuario:x.id_usuario,direccion_ip:x.direccion_ip,descripcion:x.descripcion,detalle:d,
      checks,completo:Object.values(checks).every(Boolean)};});
  return {candidatos:evaluated,match:evaluated.find(x=>x.completo)||null};}
async function oneCase(id,f,token,admin,actor) {const c=e[id];c.fixture=f;c.actor_id=actor;c.actor=id==='TC-M09-268'?'Productor':'Ingeniero de Campo';
  try {c.historial_pre=await history(f.sensor,id==='TC-M09-268'?e._ing:token);}catch(x){c.resultado='BLOQUEADO / NO VERIFICABLE';c.motivo=`No se puede verificar persistencia PRE: ${clean(x.message)}`;return;}
  const body=calibrationBody(id,f);c.solicitud={ruta:`/configuracion/sensores/${f.sensor}/calibrar`,body,
    valor_referencia_literal:id==='TC-M09-269'?'7.0000':id==='TC-M09-270'?'45.0001':id==='TC-M09-271'?'"abc"':'22.5000'};
  const result=await newmanPost(id,f.sensor,token,body);e.post_ejecutados++;c.request_window={t_before:result.t_before,t_after:result.t_after};
  c.post_status=result.response?.status??null;c.post_body=result.response?.body??null;c.newman_assertions=result.assertions;
  if(result.transport)c.transporte=result.transport;
  try {c.historial_post=await history(f.sensor,id==='TC-M09-268'?e._ing:token);
    c.historial_sin_cambios=sameHistory(c.historial_pre,c.historial_post);
  }catch(x){c.historial_error=clean(x.message);c.historial_sin_cambios=null;}
  if(c.post_status>=200 && c.post_status<300 || c.historial_sin_cambios===false){
    c.resultado='RECHAZADO';c.motivo='STOP_ALL: el intento debía rechazarse pero respondió 2xx o cambió el historial; se conserva cualquier calibración creada.';
    e.stop_all=true;save();return;}
  try {const a=await auditPages(actor,result.t_before,result.t_after,admin);c.auditoria={ventana:a.ventana,paginas:a.paginas,error:a.error||null,
      ...auditCheck(id,a,actor,result.t_before,result.t_after,f.sensor)};c.audit_match=c.auditoria.match;}
  catch(x){c.auditoria={error:clean(x.message),candidatos:[],match:null};c.audit_match=null;}
  const failures=[];if(c.post_status!==expected[id])failures.push(`HTTP ${c.post_status??'sin respuesta'} en vez de ${expected[id]}`);
  if(c.post_body?.id_calibracion!=null)failures.push(`respuesta contiene id_calibracion=${c.post_body.id_calibracion}`);
  if(c.historial_sin_cambios!==true)failures.push(c.historial_sin_cambios===null?'historial POST no verificable':'historial PRE/POST diferente');
  if(c.auditoria?.error){c.resultado=failures.length?'RECHAZADO':'BLOQUEADO / NO VERIFICABLE';
    c.motivo=`${failures.join('; ')}${failures.length?'; ':''}Consulta RF-10 no verificable: ${c.auditoria.error}`;}
  else if(!c.audit_match){const candidates=c.auditoria?.candidatos||[];
    failures.push(candidates.length?`hay ${candidates.length} evento(s) de calibración, pero ninguno tiene completos resultado, módulo, usuario, motivo, IP y correlación`:
      'GET /auditoria/ 200 sin evento de calibración correlacionable en la ventana');
    c.resultado='RECHAZADO';c.motivo=failures.join('; ');}
  else {c.resultado=failures.length?'RECHAZADO':'APROBADO';c.motivo=failures.length?failures.join('; '):
    `HTTP ${expected[id]}, historial intacto y evento RF-10 ${c.audit_match.id_evento} completo/correlacionado.`;}
  save();
}
function esc(s){return clean(String(s??'')).replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));}
function classify(id,c){if(c.resultado==='BLOQUEADO / NO VERIFICABLE')return 'precondicion';
  if(c.post_status!==expected[id])return `http-${id}`;
  if(c.historial_sin_cambios!==true)return `persistencia-${id}`;
  const a=c.auditoria;if(!a?.candidatos?.length)return id==='TC-M09-268'?'auditoria-rbac':id==='TC-M09-271'?'auditoria-validacion-body':'auditoria-dominio';
  if(a.candidatos.every(x=>!x.checks.ip))return 'auditoria-ip';return `auditoria-campos-${id}`;}
function incidents(){const groups=new Map();for(const id of ids){const c=e[id];if(c.resultado==='APROBADO')continue;
    const key=classify(id,c);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(id);}
  e.incidencias=[...groups].map(([key,cases],i)=>{const blocked=key==='precondicion';const first=e[cases[0]];
    const cause=key==='auditoria-ip'?'Los eventos se generan, pero direccion_ip llega vacío; la causa técnica exacta requiere revisar la propagación de IP al repositorio RF-10.':
      key==='auditoria-rbac'?'El rechazo RBAC no produjo un evento RF-10 visible; revisar la dependencia de autorización y su llamada de auditoría.':
      key==='auditoria-validacion-body'?'La validación del body ocurre antes del caso de uso y el manejador global no registra este rechazo de Módulo 9 en RF-10.':
      key==='auditoria-dominio'?'Los rechazos de dominio no produjeron eventos RF-10 visibles; revisar emisión, persistencia y despliegue del helper de auditoría.':
      key==='precondicion'?'Precondición o acceso ausente; no se atribuye defecto funcional sin alcanzar el escenario.':'Causa técnica por determinar con la evidencia API disponible.';
    return {id:`INC-G135-${String(i+1).padStart(2,'0')}`,incidencia_requerida:blocked?'Por determinar':'SÍ',
      grupo_responsable:blocked?'Por determinar':'Desarrollo',grupo_prueba:'TC-M09-G135',casos_afectados:cases,
      resultado:blocked?'BLOQUEADO':'RECHAZADO',motivo_resultado:cases.map(id=>`${id}: ${e[id].motivo}`).join(' | '),
      esperado:cases.map(id=>`${id}: HTTP ${expected[id]} sin persistencia y RF-10 FALLIDO completo`).join(' | '),
      obtenido:cases.map(id=>`${id}: HTTP ${e[id].post_status??'no ejecutado'}, eventos candidatos ${e[id].auditoria?.candidatos?.length??'N/A'}, match ${e[id].audit_match?.id_evento??'ninguno'}`).join(' | '),
      causa_raiz:cause,type:blocked?'question':'bug',severity:blocked?'Normal':'Important',priority:blocked?'Normal':'High',
      evidencia:'evidencia.json / newman.html'};});}
function render(){const rows=ids.map(id=>{const c=e[id];return `| ${id} | ${expected[id]} | ${c.post_status??'—'} | ${c.audit_match?'Sí':'No'} | ${c.resultado} | ${c.motivo||'—'} |`;});
  const lines=[`# TC-M09-G135 — Resultado`, '',`RUN_ID: ${runId} · TEST · ${e.resultado_general} · ${e.post_ejecutados}/6 POST de calibración.`,
    '', '## Decisión general','', '| Caso | Rechazo esperado | HTTP obtenido | Evento FALLIDO | Resultado | Motivo |',
    '|---|---:|---:|---|---|---|',...rows,'','## Entorno y actores','',
    `- Backend: ${base}` ,`- Rama: ${e.git.rama}; HEAD: ${e.git.head}; origin/test: ${e.git.origin_test}; divergencia HEAD...origin/test: ${e.git.divergencia}.`,
    `- Estado Git previo: ${e.git.status_short||'(limpio)'}. Diff: ${e.git.diff_stat||'(vacío)'}; staged: ${e.git.diff_cached_stat||'(vacío)'}.`,
    `- Ingeniero: ${JSON.stringify(e.actores.ingeniero||{})}.`,
    `- Productor: ${JSON.stringify(e.actores.productor||{})}.`,
    `- Administrador de lectura RF-10: ${JSON.stringify(e.actores.administrador||{})}.`,
    `- OpenAPI TEST: ${JSON.stringify(e.openapi)}.`,
    `- SQL ejecutado: ninguno. POST funcionales: ${e.post_ejecutados}; sin reintentos.`,
    '', '## Resultado por caso',''];
  for(const id of ids){const c=e[id],a=c.auditoria||{},m=c.audit_match;
    lines.push(`### ${id} — ${c.resultado}`,'',
      `- Fixture: ${JSON.stringify(c.fixture||{})}.`,
      `- Ventana del intento: ${c.request_window?.t_before||'no hubo POST'} → ${c.request_window?.t_after||'—'}; consulta RF-10: ${a.ventana?.fecha_desde||'—'} → ${a.ventana?.fecha_hasta||'—'}.`,
      `- HTTP esperado/obtenido: ${expected[id]} / ${c.post_status??'no ejecutado'}; respuesta: ${JSON.stringify(c.post_body??null)}.`,
      `- Historial PRE/POST: ${JSON.stringify(c.historial_pre??null)} / ${JSON.stringify(c.historial_post??null)}; sin cambios: ${c.historial_sin_cambios??'no verificable'}.`,
      `- GET RF-10: ${JSON.stringify(a.paginas||[])}; candidatos de calibración: ${(a.candidatos||[]).length}; evento correlacionado: ${m?.id_evento??'ninguno'}.`,
      `- Evento — resultado: ${m?.resultado??'—'}; módulo: ${m?.modulo??'—'}; usuario: ${m?.id_usuario??'—'}; motivo: ${m?.detalle?.motivo??'—'}; IP: ${m?.direccion_ip??'—'}.`,
      `- Candidatos y campos: ${JSON.stringify((a.candidatos||[]).map(x=>({id_evento:x.id_evento,resultado:x.resultado,modulo:x.modulo,id_usuario:x.id_usuario,fecha_evento:x.fecha_evento,motivo:x.detalle?.motivo,ip:x.direccion_ip,checks:x.checks})))||'[]'}.`,
      `- Decisión y causa observada: **${c.resultado}**. ${c.motivo||'Sin ejecución.'}`,'');}
  lines.push('## Incidencias','');
  if(e.incidencias.length===0)lines.push('**INCIDENCIA REQUERIDA: NO.**','',
    'Grupo de prueba: TC-M09-G135. Casos afectados: ninguno. Resultado: APROBADO. Grupo responsable, Type, Severity y Priority: no aplican.','',
    'Motivo: los seis POST devolvieron exactamente 403, 422, 400, 400, 400 y 404; ningún historial PRE/POST cambió; cada intento tuvo un evento RF-10 distinto, con resultado FALLIDO, módulo MODULO9, usuario, fecha, motivo e IP correlacionados. No se observó incumplimiento que justifique abrir una incidencia.','',
    'Evidencia: evidencia.json y newman.html.','');
  for(const x of e.incidencias)lines.push(`### ${x.id}`,'',
    `- INCIDENCIA REQUERIDA: ${x.incidencia_requerida}; grupo responsable: ${x.grupo_responsable}; grupo de prueba: ${x.grupo_prueba}.`,
    `- Casos afectados: ${x.casos_afectados.join(', ')}; resultado: ${x.resultado}.`,
    `- Motivo del resultado: ${x.motivo_resultado}.`, `- Esperado: ${x.esperado}.`,`- Obtenido: ${x.obtenido}.`,
    `- Causa raíz o hipótesis: ${x.causa_raiz}.`,`- Type: ${x.type}; Severity: ${x.severity}; Priority: ${x.priority}.`,
    `- Evidencia: ${x.evidencia}.`,'');
  lines.push('## Conclusión','',e.motivo_general,'');
  fs.writeFileSync(path.join(out,'TC-M09-G135_resultado.md'),clean(lines.join('\n')),'utf8');
  fs.writeFileSync(path.join(out,'newman.html'),`<!doctype html><html lang="es"><meta charset="utf-8"><title>TC-M09-G135 Newman</title><style>body{font:15px system-ui;margin:2rem;max-width:90rem}table{border-collapse:collapse}td,th{border:1px solid #aaa;padding:.5rem}pre{white-space:pre-wrap}</style><h1>TC-M09-G135 — Newman y RF-10</h1><p>${esc(runId)} · ${esc(e.resultado_general)} · ${e.post_ejecutados}/6 POST</p><table><tr><th>Caso</th><th>HTTP esperado</th><th>HTTP Newman</th><th>Assertions Newman</th><th>Evento RF-10</th><th>Resultado</th></tr>${ids.map(id=>{const c=e[id];return `<tr><td>${esc(id)}</td><td>${expected[id]}</td><td>${esc(c.post_status??'—')}</td><td>${esc(JSON.stringify(c.newman_assertions||[]))}</td><td>${esc(c.audit_match?.id_evento??'—')}</td><td>${esc(c.resultado)}</td></tr>`;}).join('')}</table><h2>Respuestas y auditoría</h2>${ids.map(id=>`<h3>${esc(id)}</h3><pre>${esc(JSON.stringify({respuesta:e[id].post_body,request_window:e[id].request_window,auditoria:e[id].auditoria},null,2))}</pre>`).join('')}</html>`,'utf8');}
async function main(){if(out)fs.mkdirSync(out,{recursive:true});let ctx;
  try{ctx=await preflight();}catch(x){e.motivo_general=`Preflight no completado: ${clean(x.message)}`;
    if(preflightOnly){console.log(clean(JSON.stringify({error:e.motivo_general,preflight:e},null,2)));return;}
    for(const id of ids){e[id].resultado='BLOQUEADO / NO VERIFICABLE';e[id].motivo=e.motivo_general;}
    e.resultado_general='BLOQUEADO / NO VERIFICABLE';incidents();save();render();console.log(e.motivo_general);return;}
  if(preflightOnly){console.log(clean(JSON.stringify({git:e.git,openapi:e.openapi,actores:e.actores,fixtures:e.fixtures,discovery:e.discovery},null,2)));return;}
  Object.defineProperty(e,'_ing',{value:ctx.ing,enumerable:false});
  for(const id of ids){const c=e[id];let f,token,actor;
    if(id==='TC-M09-268') {f=e.fixtures.valido;token=ctx.producer;actor=e.actores.productor?.id_usuario;
      if(!token||!actor){c.resultado='BLOQUEADO / NO VERIFICABLE';c.motivo=`Productor activo/autenticable no confirmado: ${e.actores.productor?.precondicion||'sin credencial'}`;save();continue;}}
    else if(id==='TC-M09-269'){f=e.fixtures.inactivo;token=ctx.ing;actor=e.actores.ingeniero.id_usuario;}
    else {f=e.fixtures.valido;token=ctx.ing;actor=e.actores.ingeniero.id_usuario;}
    if(f?.problema||!f?.sensor){c.resultado='BLOQUEADO / NO VERIFICABLE';c.motivo=`Fixture no verificable por API: ${f?.problema||'ausente'}`;save();continue;}
    if(id==='TC-M09-270' && !(45.0001>Number(f.rango?.max))){c.resultado='BLOQUEADO / NO VERIFICABLE';c.motivo='45.0001 no se confirmó fuera del rango vigente.';save();continue;}
    if(id==='TC-M09-272'){const a=e.fixtures.area_incorrecta;
      if(!a?.existe||!a?.no_asociada||a.es_activo!==true){c.resultado='BLOQUEADO / NO VERIFICABLE';c.motivo=`Área incorrecta no verificada: ${JSON.stringify(a)}`;save();continue;}
      f={...f,area:1,area_original:3};}
    if(id==='TC-M09-273'){const d=e.fixtures.dispositivo_inexistente;
      if(d?.admin_http!==404){c.resultado='BLOQUEADO / NO VERIFICABLE';c.motivo=`No se confirmó dispositivo inexistente por API: ${JSON.stringify(d)}`;save();continue;}
      f={...f,dispositivo:999999,dispositivo_original:3};}
    try{await oneCase(id,f,token,ctx.admin,actor);}catch(x){c.resultado='BLOQUEADO / NO VERIFICABLE';c.motivo=`Error de automatización/infraestructura: ${clean(x.stack||x.message)}`;save();}
    console.log(`${id}: ${c.resultado}; HTTP ${c.post_status??'—'}; RF-10 ${c.audit_match?.id_evento??'—'}`);
    if(e.stop_all)break;
  }
  if(e.stop_all)for(const id of ids)if(e[id].resultado==='PENDIENTE'){e[id].resultado='BLOQUEADO / NO VERIFICABLE';e[id].motivo='No ejecutado por STOP_ALL tras persistencia inesperada.';}
  const states=ids.map(id=>e[id].resultado);e.resultado_general=states.every(x=>x==='APROBADO')?'APROBADO':
    states.includes('RECHAZADO')?'RECHAZADO':'BLOQUEADO / NO VERIFICABLE';
  e.motivo_general=e.resultado_general==='APROBADO'?'Los seis rechazos exactos conservaron el historial y tuvieron un evento RF-10 completo.':
    `Casos rechazados: ${ids.filter(id=>e[id].resultado==='RECHAZADO').join(', ')||'ninguno'}. Casos bloqueados: ${ids.filter(id=>e[id].resultado==='BLOQUEADO / NO VERIFICABLE').join(', ')||'ninguno'}.`;
  incidents();save();render();console.log(`G135 ${e.resultado_general}; ${e.post_ejecutados}/6 POST; ${out}`);
}
main().catch(x=>{console.error(clean(x.stack||x.message));process.exitCode=1;});
