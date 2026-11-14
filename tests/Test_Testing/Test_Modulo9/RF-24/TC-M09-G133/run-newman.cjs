// TC-M09-G133 — TEST decisorio, 3 POST funcionales y 1 DELETE /sesiones/.
// Newman envía cada POST. No se repite ninguna calibración automáticamente.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

if (path.basename(__dirname) !== 'TC-M09-G133') throw new Error('Carpeta de ejecución incorrecta.');
const runId = process.env.G133_RUN_ID;
if (!/^run-\d{8}-\d{6}$/.test(runId || '')) throw new Error('G133_RUN_ID debe tener formato run-YYYYMMDD-HHMMSS.');
const base = (process.env.QA_BASE_URL || '').replace(/\/$/, '');
if (base !== 'https://api.inmero.co/back-sigab-test') throw new Error('El ambiente decisorio debe ser TEST.');
const ingEmail = process.env.QA_ING_EMAIL;
const ingPassword = process.env.QA_ING_PASSWORD;
const adminPassword = process.env.QA_ADMIN_PASSWORD;
if (!ingEmail || !ingPassword || !adminPassword) throw new Error('Faltan credenciales en variables de proceso.');
const out = path.join(__dirname, 'RESULTADOS', runId);
if (fs.existsSync(out)) throw new Error('RUN_ID existente: no se sobrescribe evidencia.');
fs.mkdirSync(out, {recursive:true});
const collection = JSON.parse(fs.readFileSync(path.join(__dirname,'TC-M09-G133.postman_collection.json'),'utf8'));
const cases = [
  ['TC-M09-264','Administrador', 'TC-M09-264'],
  ['TC-M09-263','Sin Authorization', 'sin_token'],
  ['TC-M09-263','Token de sesión cerrada', 'sesion_cerrada']
];
const evidence = {
  grupo:'TC-M09-G133',casos:['TC-M09-263','TC-M09-264'],run_id:runId,ambiente:'TEST',
  base_url:base,prueba_local:false,post_calibracion_planificados:3,
  post_calibracion_ejecutados:0,delete_sesiones_ejecutados:0,
  git:{},openapi:{},fixture:{},admin:{},ingeniero:{},
  'TC-M09-264':{},'TC-M09-263':{sin_token:{},sesion_cerrada:{}},
  stop_all:false,resultado_general:'',motivo_general:'',incidencias:[]
};
const secrets = [ingPassword,adminPassword].filter(Boolean);
function clean(value) {
  let s=String(value??'');
  for (const x of new Set(secrets)) s=s.split(x).join('[REDACTED]');
  return s.replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,'[JWT REDACTED]')
    .replace(/Bearer\s+[A-Za-z0-9_.-]+/gi,'Bearer [REDACTED]');
}
function esc(x) { return String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function git(args) {
  try {let d=__dirname;while(!fs.existsSync(path.join(d,'.git'))&&path.dirname(d)!==d)d=path.dirname(d);
    return execFileSync('git',args,{cwd:d,encoding:'utf8'}).trim();}
  catch(e){return `ERROR: ${clean(e.message)}`;}
}
function decimalParts(x) {
  if (typeof x!=='string'&&typeof x!=='number') return null;
  if (typeof x==='number'&&!Number.isFinite(x)) return null;
  const m=/^([+-]?)(\d+)(?:\.(\d+))?$/.exec(String(x));if(!m)return null;
  const f=m[3]||'';return {n:(m[1]==='-'?-1n:1n)*BigInt(m[2]+f),d:10n**BigInt(f.length)};
}
function decimalEqual(a,b){const x=decimalParts(a),y=decimalParts(b);return Boolean(x&&y&&x.n*y.d===y.n*x.d);}
function snapshot(data) {
  if (!Number.isInteger(data?.total)||!Array.isArray(data.items))throw new Error('Historial sin total/items verificables.');
  const ids=data.items.map(x=>x.id_calibracion).sort((a,b)=>a-b);
  if(ids.some(x=>!Number.isInteger(x)))throw new Error('Historial sin IDs íntegros.');
  return {total:data.total,ids};
}
function same(a,b){return a&&b&&a.total===b.total&&JSON.stringify(a.ids)===JSON.stringify(b.ids);}
function save(){fs.writeFileSync(path.join(out,'evidencia.json'),clean(JSON.stringify(evidence,null,2)),'utf8');}
function resultOf(id,k){return id==='TC-M09-264'?evidence[id]:evidence[id][k];}
function markPending(status,reason){for(const [id,,k] of cases){const r=resultOf(id,k);if(!r.resultado)Object.assign(r,{resultado:status,motivo:reason});}}
async function request(method,route,token,body){
  const r=await fetch(base+route,{method,headers:{...(token?{Authorization:`Bearer ${token}`}:{ }),
    ...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined,
    signal:AbortSignal.timeout(30000)});
  return {status:r.status,body:await r.json().catch(()=>null)};
}
async function login(user,pass){
  const r=await request('POST','/sesiones/',null,{correo_electronico:user,contrasena:pass});
  if(r.status!==200||!r.body?.token)throw new Error(`${user} no autentica (HTTP ${r.status}).`);
  return {token:r.body.token,status:r.status};
}
async function get(route,token){const r=await request('GET',route,token);if(r.status!==200)throw new Error(`GET ${route} HTTP ${r.status}.`);return r.body;}
async function history(sensor,token){const all=await get(`/configuracion/sensores/${sensor}/calibraciones`,token);return {all,brief:snapshot(all)};}
function hasPermission(data,recurso,accion){return (data.permisos||[]).some(x=>x.id_recurso===recurso&&x.id_accion===accion);}
async function effectiveAdmin(){
  const attempts=[];
  for(const user of ['admin.dev@gmail.com','administador.dev@gmail.com']){
    try{
      const auth=await login(user,adminPassword);
      const me=await get('/usuarios/me',auth.token);
      const perms=await get('/sesiones/me/permisos',auth.token);
      const valid=me.correo_electronico===user&&me.nombre_rol==='Administrador'&&me.estado_cuenta==='Activo'&&
        hasPermission(perms,12,1)&&hasPermission(perms,12,2);
      attempts.push({correo:user,login_status:auth.status,id_usuario:me.id_usuario,rol:me.nombre_rol,
        estado:me.estado_cuenta,permiso_registrar:hasPermission(perms,12,1),permiso_historial:hasPermission(perms,12,2)});
      if(valid){evidence.admin={...attempts.at(-1),intentos:attempts};return auth.token;}
    }catch(e){attempts.push({correo:user,resultado:clean(e.message)});}
  }
  evidence.admin={intentos:attempts};
  throw new Error('Ningún Administrador autenticó con identidad, estado y permisos de calibración/historial requeridos.');
}
async function inspectFixture(deviceId,sensorId,areaId,token,ranges){
  const d=await get(`/configuracion/dispositivos-iot/${deviceId}`,token);
  const sl=await get(`/configuracion/dispositivos-iot/${deviceId}/sensores`,token);
  const s=sl.items?.find(x=>x.id_sensores===sensorId&&x.id_dispositivo_iot===deviceId);
  const al=await get(`/configuracion/sensores/${sensorId}/asociaciones`,token);
  const a=al.items?.find(x=>x.id_sensor===sensorId&&x.id_dispositivo_iot===deviceId&&
    x.id_infraestructura===areaId&&x.tiene_estado===true&&x.fecha_finalizacion===null);
  const area=await get(`/configuracion/infraestructuras/${areaId}`,token);
  const range=ranges.items?.find(x=>x.categoria===s?.categoria);
  if(d.es_activo!==true||s?.es_activo!==true||!a||area.es_activo!==true||!range||
    Number(range.valor_min)>22.5||22.5>Number(range.valor_max))return null;
  return {sensor:sensorId,dispositivo:deviceId,area:areaId,categoria:s.categoria,
    asociacion:a.id_sensores_area_asociada,rango:{min:range.valor_min,max:range.valor_max},
    activo:{sensor:s.es_activo,dispositivo:d.es_activo,area:area.es_activo},fuente:'GET con Administrador en TEST'};
}
async function findFixture(token){
  const ranges=await get('/configuracion/sensores/rangos-calibracion',token);
  try{const f=await inspectFixture(3,6,3,token,ranges);if(f)return f;}
  catch(e){evidence.fixture.preferido_error=clean(e.message);}
  const devices=(await get('/configuracion/dispositivos-iot',token)).items||[];
  for(const d of devices.filter(x=>x.es_activo===true)){
    let sensors;try{sensors=(await get(`/configuracion/dispositivos-iot/${d.id_dispositivo_iot}/sensores`,token)).items||[];}catch{continue;}
    for(const s of sensors.filter(x=>x.es_activo===true)){
      let assocs;try{assocs=(await get(`/configuracion/sensores/${s.id_sensores}/asociaciones`,token)).items||[];}catch{continue;}
      for(const a of assocs.filter(x=>x.tiene_estado===true&&x.fecha_finalizacion===null)){
        try{const f=await inspectFixture(d.id_dispositivo_iot,s.id_sensores,a.id_infraestructura,token,ranges);if(f)return f;}
        catch{ /* siguiente */ }
      }
    }
  }
  throw new Error('No existe fixture activo verificable por GET cuyo rango incluya 22.5000.');
}
function newmanOnce(itemName,vars){
  let newman;try{newman=require('newman');}catch{newman=require(path.join(path.dirname(process.execPath),'node_modules','newman'));}
  const item=collection.item.find(x=>x.name===itemName);if(!item)throw new Error(`Item ${itemName} ausente.`);
  if(itemName==='TC-M09-263/A Sin Authorization'&&
    (item.request.header||[]).some(h=>h.key.toLowerCase()==='authorization'))throw new Error('El item sin token contiene Authorization.');
  const selected={...collection,item:[item]};
  return new Promise((resolve,reject)=>newman.run({collection:selected,reporters:['cli'],
    envVar:Object.entries(vars).map(([key,value])=>({key,value:String(value)})),timeoutRequest:30000},(err,run)=>{
    const ex=run?.run?.executions?.[0];if(err||!ex?.response)return reject(new Error(`Newman sin respuesta: ${clean(err?.message||'desconocido')}`));
    let body=null;try{body=JSON.parse(ex.response.stream.toString('utf8'));}catch{ /* no JSON */ }
    resolve({status:ex.response.code,body,assertions:ex.assertions?.map(a=>({name:a.assertion,error:a.error?.message||null}))||[]});
  }));
}
function bodyFor(f,caseId){return {modo_calibracion:'SENSOR',id_dispositivo_iot:f.dispositivo,
  id_infraestructura:f.area,valor_referencia:22.5000,observaciones:`QA ${caseId}`,
  fecha_calibracion:new Date().toISOString()};}
async function postCase(itemName,body,token,caseResult,adminToken,fixture){
  const before=await history(fixture.sensor,adminToken);caseResult.pre=before.brief;
  const bodyJson=JSON.stringify(body).replace(/"valor_referencia":22\.5(?=,)/,'"valor_referencia":22.5000');
  caseResult.request={ruta:`/configuracion/sensores/${fixture.sensor}/calibrar`,body,valor_referencia_literal:'22.5000',
    authorization:itemName==='TC-M09-263/A Sin Authorization'?'ausente':
      itemName==='TC-M09-264 Administrador'?'Administrador':'mismo token del Ingeniero cerrado'};
  evidence.post_calibracion_ejecutados+=1;
  try{
    const vars={base_url:base,sensor_id:fixture.sensor,body_json:bodyJson};
    if(token)vars.token=token;
    const r=await newmanOnce(itemName,vars);
    caseResult.response={http:r.status,id_calibracion:r.body?.id_calibracion??null,
      id_usuario:r.body?.id_usuario??null,id_sensor:r.body?.id_sensor??null,
      id_dispositivo_iot:r.body?.id_dispositivo_iot??null,valor_referencia:r.body?.valor_referencia??null,
      observaciones:r.body?.observaciones??null,error_code:r.body?.error_code??null,
      mensaje:clean(r.body?.message??r.body?.detail??'')};
    caseResult.assertions_newman=r.assertions;
  }catch(e){caseResult.error_ejecucion=clean(e.message);}
  try{
    const after=await history(fixture.sensor,adminToken);caseResult.post=after.brief;
    const id=caseResult.response?.id_calibracion;
    if(Number.isInteger(id)){
      const row=after.all.items.find(x=>x.id_calibracion===id);
      caseResult.registro_por_id=row?{
        id_calibracion:row.id_calibracion,id_sensor:row.id_sensor,
        id_dispositivo_iot:row.id_dispositivo_iot,id_usuario:row.id_usuario,
        valor_referencia:row.valor_referencia,observaciones:row.observaciones}:null;
    }
  }catch(e){caseResult.error_historial_post=clean(e.message);}
  caseResult.ids_creados=caseResult.post?caseResult.post.ids.filter(x=>!caseResult.pre.ids.includes(x)):[];
}
function decide264(r,fixture){
  const s=r.response?.http, id=r.response?.id_calibracion, row=r.registro_por_id;
  const failures=[];
  if(!(s>=200&&s<300))failures.push(`TEST respondió HTTP ${s??'no verificable'} en vez de 2xx`);
  if(!Number.isInteger(id))failures.push('la respuesta no devolvió id_calibracion íntegro');
  if(!r.post)failures.push('historial POST no verificable');
  else if(!row)failures.push(`el historial no contiene el ID ${id??'devuelto'}`);
  if(row){
    if(row.id_sensor!==fixture.sensor)failures.push(`sensor persistido ${row.id_sensor}, esperado ${fixture.sensor}`);
    if(row.id_dispositivo_iot!==fixture.dispositivo)failures.push(`dispositivo persistido ${row.id_dispositivo_iot}, esperado ${fixture.dispositivo}`);
    if(!decimalEqual(row.valor_referencia,'22.5000'))failures.push(`valor persistido ${JSON.stringify(row.valor_referencia)}, esperado 22.5000`);
    if(row.id_usuario!==evidence.admin.id_usuario)failures.push(`id_usuario persistido ${row.id_usuario}, Admin esperado ${evidence.admin.id_usuario}`);
    if(row.observaciones!=='QA TC-M09-264')failures.push(`observaciones persistidas ${JSON.stringify(row.observaciones)}`);
  }
  r.resultado=failures.length?'RECHAZADO':'APROBADO';
  r.motivo=failures.length?failures.join('; ')+'.':`HTTP ${s}, calibración ${id} recuperada por GET con id_usuario ${row.id_usuario} del Administrador y datos coincidentes.`;
}
function decide263(r){
  const s=r.response?.http,changes=r.post&&!same(r.pre,r.post);
  const failures=[];
  if(!(s>=400&&s<500))failures.push(`HTTP ${s??'no verificable'} en vez de 4xx`);
  if(changes)failures.push(`historial alterado; IDs nuevos ${r.ids_creados.join(', ')||'ninguno'}`);
  if(!r.post)failures.push('historial POST no verificable');
  r.resultado=failures.length?'RECHAZADO':'APROBADO';
  r.motivo=failures.length?failures.join('; ')+'.':`HTTP ${s}; total e IDs del historial sin cambios.`;
  if(changes||!r.post||!s){evidence.stop_all=true;
    evidence.motivo_stop_all=`Variante de seguridad ${r.request?.authorization}: ${changes?'persistencia/historial alterado':'verificación ambigua'}; IDs nuevos ${r.ids_creados.join(', ')||'no verificables'}.`;}
}
function render(){
  const rows=cases.map(([id,label,k])=>{const r=resultOf(id,k);return `| ${id} | ${label} | ${r.resultado} | ${r.motivo} |`;}).join('\n');
  const a=evidence['TC-M09-264'], b=evidence['TC-M09-263'].sin_token, c=evidence['TC-M09-263'].sesion_cerrada;
  const incidents=evidence.incidencias.length?evidence.incidencias.map(i=>
    `### ${i.titulo}\n\n**INCIDENCIA REQUERIDA:** SÍ  \n**Grupo responsable:** ${i.grupo_responsable}  \n**Grupo de prueba:** TC-M09-G133  \n**Casos afectados:** ${i.casos.join(', ')}  \n**Resultado:** ${i.resultado}  \n**Motivo:** ${i.motivo}  \n**Esperado:** ${i.esperado}  \n**Obtenido:** ${i.obtenido}  \n**Causa raíz:** ${i.causa_raiz}  \n**Type:** ${i.type}  \n**Severity:** ${i.severity}  \n**Priority:** ${i.priority}  \n**Evidencia:** evidencia.json / newman.html`).join('\n\n'):'INCIDENCIA REQUERIDA: NO.';
  const md=`# TC-M09-G133 — Resultado\n\n## Decisión general\n\n**${evidence.resultado_general}.** ${evidence.motivo_general}\n\n| Caso | Variante | Resultado | Motivo |\n|---|---|---|---|\n${rows}\n\n## Entorno / fixture\n\nTEST: ${base}. Prueba local: NO. RUN_ID: ${runId}. Rama: ${evidence.git.rama}. HEAD: ${evidence.git.head}; origin/test: ${evidence.git.origin_test}; divergencia: ${evidence.git.divergencia}.\n\nOpenAPI: ${JSON.stringify(evidence.openapi)}.\n\nFixture validado por GET: ${JSON.stringify(evidence.fixture)}. El oráculo no exige códigos HTTP exactos para rechazo 4xx ni éxito 2xx.\n\n## TC-M09-264 — Administrador autorizado\n\nAdmin efectivo: ${JSON.stringify(evidence.admin)}.\n\n**Esperado:** 2xx, id_calibracion, registro recuperado por ese ID con sensor, dispositivo, valor 22.5000, observaciones e id_usuario del Administrador.\n\n**Obtenido:** ${JSON.stringify(a.response??null)}. Registro por ID: ${JSON.stringify(a.registro_por_id??null)}.\n\nHistorial PRE: ${JSON.stringify(a.pre??null)}. POST: ${JSON.stringify(a.post??null)}.\n\n**Resultado:** ${a.resultado}. **Motivo:** ${a.motivo}\n\n## TC-M09-263/A — sin Authorization\n\nEl item Postman carece de cabecera Authorization; no se envió valor vacío ni token ficticio. El historial fue consultado con el Administrador.\n\n**Esperado:** cualquier 4xx y mismo total/IDs. **Obtenido:** ${JSON.stringify(b.response??null)}.\n\nHistorial PRE: ${JSON.stringify(b.pre??null)}. POST: ${JSON.stringify(b.post??null)}.\n\n**Resultado:** ${b.resultado}. **Motivo:** ${b.motivo}\n\n## TC-M09-263/B — token de sesión cerrada\n\nCadena: login nuevo del Ingeniero → mismo token T en DELETE /sesiones/ → cierre 2xx → mismo T en POST de calibración. No se hizo un login intermedio ni se guardó T.\n\nIngeniero: ${JSON.stringify(evidence.ingeniero)}. Setup de cierre: login_status ${JSON.stringify(c.login_status??null)}, logout_status ${JSON.stringify(c.logout_status??null)}, mensaje ${JSON.stringify(c.logout_mensaje??null)}, timestamp ${JSON.stringify(c.logout_timestamp??null)}, mismo_token_reutilizado ${JSON.stringify(c.mismo_token_reutilizado??null)}.\n\n**Esperado:** cualquier 4xx y mismo total/IDs. **Obtenido:** ${JSON.stringify(c.response??null)}.\n\nHistorial PRE: ${JSON.stringify(c.pre??null)}. POST: ${JSON.stringify(c.post??null)}.\n\n**Resultado:** ${c.resultado}. **Motivo:** ${c.motivo}\n\n## STOP_ALL\n\n${evidence.stop_all?'SÍ: '+evidence.motivo_stop_all:'NO'}. POST de calibración planificados: 3; ejecutados: ${evidence.post_calibracion_ejecutados}. DELETE /sesiones/ ejecutados: ${evidence.delete_sesiones_ejecutados}. Sin reintentos ni borrado de calibraciones.\n\n## Incidencias\n\n${incidents}\n\n## Conclusión\n\n${evidence.motivo_general}\n`;
  fs.writeFileSync(path.join(out,'TC-M09-G133_resultado.md'),clean(md),'utf8');
  const trs=cases.map(([id,label,k])=>{const r=resultOf(id,k);return `<tr><td>${esc(id)}</td><td>${esc(label)}</td><td>${esc(r.resultado)}</td><td>${esc(r.response?.http??'—')}</td><td>${esc(r.motivo)}</td></tr>`;}).join('');
  fs.writeFileSync(path.join(out,'newman.html'),`<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman ${esc(runId)}</title><style>body{font:16px Arial,sans-serif;max-width:1100px;margin:40px auto;color:#182331}table{border-collapse:collapse;width:100%}td,th{border:1px solid #bbc5ce;padding:9px;text-align:left}th{background:#e9eef2}</style><h1>Newman — TC-M09-G133</h1><p>RUN ${esc(runId)} · TEST · ${esc(evidence.resultado_general)} · ${evidence.post_calibracion_ejecutados}/3 POST</p><table><thead><tr><th>Caso</th><th>Variante</th><th>Resultado</th><th>HTTP</th><th>Motivo</th></tr></thead><tbody>${trs}</tbody></table><p>${esc(evidence.motivo_general)}</p><p>Detalle: evidencia.json y TC-M09-G133_resultado.md.</p></html>`,'utf8');
}
function finalize(){
  const a=evidence['TC-M09-264'],b=evidence['TC-M09-263'].sin_token,c=evidence['TC-M09-263'].sesion_cerrada;
  const failedSecurity=[b,c].filter(x=>x.resultado==='RECHAZADO');
  if(failedSecurity.length)evidence.incidencias.push({titulo:'Calibración aceptada sin sesión válida',
    grupo_responsable:'Desarrollo',casos:['TC-M09-263'],resultado:'RECHAZADO',
    motivo:failedSecurity.map(x=>x.motivo).join(' '),esperado:'Ambas variantes 4xx y sin persistencia.',
    obtenido:failedSecurity.map(x=>`HTTP ${x.response?.http}; PRE ${JSON.stringify(x.pre)}; POST ${JSON.stringify(x.post)}.`).join(' '),
    causa_raiz:'Validación de autenticación/sesión en el backend; mecanismo exacto del despliegue por confirmar.',
    type:'bug',severity:'Critical',priority:'High'});
  if(a.resultado==='RECHAZADO')evidence.incidencias.push({titulo:'Administrador autorizado no registra calibración correctamente',
    grupo_responsable:'Por determinar',casos:['TC-M09-264'],resultado:'RECHAZADO',motivo:a.motivo,
    esperado:'2xx y fila con id_usuario del Administrador, sensor, dispositivo, valor y observaciones correctos.',
    obtenido:`HTTP ${a.response?.http}; fila ${JSON.stringify(a.registro_por_id??null)}.`,
    causa_raiz:'Por determinar; contrastar autorización, atribución y código/despliegue.',
    type:'bug',severity:'Important',priority:'High'});
  evidence['TC-M09-263'].resultado=b.resultado==='APROBADO'&&c.resultado==='APROBADO'?'APROBADO':
    [b.resultado,c.resultado].includes('RECHAZADO')?'RECHAZADO':'BLOQUEADO / NO VERIFICABLE';
  evidence.resultado_general=a.resultado==='APROBADO'&&evidence['TC-M09-263'].resultado==='APROBADO'?'APROBADO':
    a.resultado==='RECHAZADO'||evidence['TC-M09-263'].resultado==='RECHAZADO'?'RECHAZADO':'BLOQUEADO / NO VERIFICABLE';
  if(!evidence.motivo_general)evidence.motivo_general=evidence.resultado_general==='APROBADO'
    ?'El Administrador registró una calibración atribuida a su id_usuario y ambas peticiones sin sesión válida recibieron 4xx sin persistencia.'
    :evidence.resultado_general==='RECHAZADO'
      ?`Incumplimiento observado en ${cases.filter(([id,,k])=>resultOf(id,k).resultado==='RECHAZADO').map(([id,label])=>`${id}/${label}`).join(', ')}.`
      :'No se pudieron verificar todos los oráculos por una precondición externa.';
  save();render();
  console.log(`TC-M09-G133 → ${evidence.resultado_general}; POST calibración: ${evidence.post_calibracion_ejecutados}; DELETE /sesiones/: ${evidence.delete_sesiones_ejecutados}; STOP_ALL: ${evidence.stop_all?'SÍ':'NO'}`);
  console.log(path.join(out,'TC-M09-G133_resultado.md'));
}
async function main(){
  evidence.git={rama:git(['branch','--show-current']),status_short:git(['status','--short']),
    diff_stat:git(['diff','--stat']),diff_cached_stat:git(['diff','--cached','--stat']),
    head:git(['rev-parse','HEAD']),origin_test:git(['rev-parse','origin/test']),
    divergencia:git(['rev-list','--left-right','--count','HEAD...origin/test'])};
  if(evidence.git.rama!=='qa/juan-esteban-rf24-v2')throw new Error('La rama QA requerida no está activa.');
  const o=await request('GET','/openapi.json');if(o.status!==200)throw new Error(`OpenAPI TEST HTTP ${o.status}.`);
  const endpoints=[['POST /sesiones/','/sesiones/','post'],['DELETE /sesiones/','/sesiones/','delete'],
    ['POST /configuracion/sensores/{id_sensor}/calibrar','/configuracion/sensores/{id_sensor}/calibrar','post'],
    ['GET /configuracion/sensores/{id_sensor}/calibraciones','/configuracion/sensores/{id_sensor}/calibraciones','get']];
  evidence.openapi=Object.fromEntries(endpoints.map(([name,p,m])=>[name,{
    presente:Boolean(o.body.paths?.[p]?.[m]),codigos_declarados:Object.keys(o.body.paths?.[p]?.[m]?.responses||{})}]));
  if(Object.values(evidence.openapi).some(x=>!x.presente))throw new Error('Falta un endpoint requerido en OpenAPI TEST.');
  const adminToken=await effectiveAdmin();
  const fixture=await findFixture(adminToken);evidence.fixture={...evidence.fixture,...fixture};
  await history(fixture.sensor,adminToken); // confirmar observabilidad antes de escribir

  const positive=evidence['TC-M09-264'];
  await postCase('TC-M09-264 Administrador',bodyFor(fixture,'TC-M09-264'),adminToken,positive,adminToken,fixture);
  decide264(positive,fixture);
  if(!positive.post||!positive.response?.http){evidence.stop_all=true;evidence.motivo_stop_all='Resultado de TC-M09-264 ambiguo; no se arriesgan otros POST.';
    markPending('NO EJECUTADO',`STOP_ALL: ${evidence.motivo_stop_all}`);return;}

  const without=evidence['TC-M09-263'].sin_token;
  await postCase('TC-M09-263/A Sin Authorization',bodyFor(fixture,'TC-M09-263'),null,without,adminToken,fixture);
  decide263(without);
  if(evidence.stop_all){markPending('NO EJECUTADO',`STOP_ALL: ${evidence.motivo_stop_all}`);return;}

  const closed=evidence['TC-M09-263'].sesion_cerrada;
  let engineerToken;
  try{
    const auth=await login(ingEmail,ingPassword);engineerToken=auth.token;closed.login_status=auth.status;
    const me=await get('/usuarios/me',engineerToken);
    const permissions=await get('/sesiones/me/permisos',engineerToken);
    evidence.ingeniero={id_usuario:me.id_usuario,correo:me.correo_electronico,rol:me.nombre_rol,
      estado:me.estado_cuenta,permisos_calibracion:(permissions.permisos||[]).filter(x=>x.id_recurso===12).map(x=>x.id_accion)};
    if(me.correo_electronico!==ingEmail||me.nombre_rol!=='Ingeniero de Campo'||me.estado_cuenta!=='Activo')
      throw new Error('La identidad Ingeniero no coincide o su cuenta no está activa.');
    evidence.delete_sesiones_ejecutados+=1;
    const logout=await request('DELETE','/sesiones/',engineerToken);
    closed.logout_status=logout.status;
    closed.logout_mensaje=clean(logout.body?.message??logout.body?.detail??'');
    closed.logout_timestamp=logout.body?.timestamp??new Date().toISOString();
    if(!(logout.status>=200&&logout.status<300))throw new Error(`DELETE /sesiones/ respondió HTTP ${logout.status}; no se verificó revocación.`);
  }catch(err){closed.resultado='BLOQUEADO / NO VERIFICABLE';closed.motivo=`No se pudo preparar la cadena login → logout exitoso → reutilización: ${clean(err.message)}`;return;}
  closed.mismo_token_reutilizado=true;
  await postCase('TC-M09-263/B Token de sesión cerrada',bodyFor(fixture,'TC-M09-263'),engineerToken,closed,adminToken,fixture);
  decide263(closed);

}
main().catch(err=>{evidence.motivo_general=`BLOQUEADO: ${clean(err.message)}`;
  markPending('BLOQUEADO / NO VERIFICABLE',evidence.motivo_general);
}).finally(finalize);
